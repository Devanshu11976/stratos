import os
import re
import uuid
import traceback
from pathlib import Path
from typing import Annotated, Any
from litestar import Controller, post, get
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.datastructures import UploadFile
from litestar.exceptions import HTTPException
from litestar.response import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from redis import Redis
from rq import Queue

# TCP keepalive constants
TCP_KEEPIDLE = 0x4  # Seconds before sending first keepalive
TCP_KEEPINTVL = 0x5  # Seconds between keepalive probes
TCP_KEEPCNT = 0x6    # Number of failed probes before dropping

from app.schemas.jobs import (
    UploadResponse,
    JobStatusResponse,
    JobDetailsResponse,
    JobListItem,
    DownloadLinksResponse,
    AIReportResponse,
    CountryStatEntry,
    ChunkInfo,
)
from app.models.jobs import UploadedFiles, ProcessingJobs
from app.repositories.jobs import JobsRepository
from app.config.settings import settings

JOB_ID_RE = re.compile(r"^TXN-[A-F0-9]{8}$")


def _validate_job_id(job_id: str) -> str:
    if not JOB_ID_RE.match(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id")
    return job_id


def _validate_chunk_number(chunk_number: str) -> str:
    if not chunk_number.isdigit():
        raise HTTPException(status_code=400, detail="Invalid chunk number")
    return chunk_number


def _safe_output_path(job_id: str, *parts: str) -> Path:
    """Resolve a path under OUTPUT_DIR/job_id, rejecting traversal."""
    base = (Path(settings.OUTPUT_DIR) / job_id).resolve()
    target = (base / Path(*parts)).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path")
    return target


def _safe_file_size(path: Path) -> int:
    """Return file size in bytes, 0 if missing."""
    try:
        return path.stat().st_size if path.exists() else 0
    except OSError:
        return 0


def _safe_record_count(path: Path) -> int:
    """Return CSV row count (excluding header), 0 if missing."""
    try:
        if not path.exists():
            return 0
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return max(0, sum(1 for _ in fh) - 1)
    except OSError:
        return 0


class UploadController(Controller):
    path = "/api"

    # ── POST /api/upload ──────────────────────────────────────────────────
    @post(path="/upload", media_type="application/json")
    async def upload_file(
        self,
        data: Annotated[dict[str, Any], Body(media_type=RequestEncodingType.MULTI_PART)],
        session: AsyncSession,
    ) -> UploadResponse:
        file_item   = data.get("file")
        country_code = data.get("country_code")

        if not file_item or not isinstance(file_item, UploadFile):
            raise HTTPException(status_code=400, detail="No file uploaded")
        if not country_code:
            raise HTTPException(status_code=400, detail="No country_code specified")
        if isinstance(country_code, bytes):
            country_code = country_code.decode("utf-8")

        # Normalise: AUTO means infer from dataset — pass through as-is,
        # validation service will resolve per-row from the country column
        country_code = country_code.strip().upper() or "AUTO"

        filename = os.path.basename(file_item.filename or "upload")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("csv", "xlsx"):
            raise HTTPException(status_code=400, detail="Only CSV and XLSX files are accepted")

        content   = await file_item.read()
        file_size = len(content)

        # Enforce upload size limit
        if file_size > settings.MAX_UPLOAD_BYTES:
            limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"File exceeds {limit_mb} MB upload limit")

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        job_id    = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        safe_name = f"{job_id}_{filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, safe_name)

        # Save file temporarily to local filesystem
        try:
            with open(file_path, "wb") as fh:
                fh.write(content)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

        # Upload to Supabase Storage
        storage_path = None
        try:
            from app.services.storage import storage_service
            storage_path = storage_service.upload_file(file_path, safe_name)
        except Exception as exc:
            import logging
            logger = logging.getLogger("xeno.api")
            logger.error(
                f"Failed to upload file to Supabase for job {job_id}:\n"
                f"Error type: {type(exc).__name__}\n"
                f"Error message: {str(exc)}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
            # Cleanup local file on Supabase upload failure
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as cleanup_exc:
                    logger.error(f"Failed to cleanup file {file_path}: {cleanup_exc}")
            raise HTTPException(status_code=500, detail=f"Failed to upload file to storage: {str(exc)}")

        try:
            repo = JobsRepository(session)
            uploaded_file = UploadedFiles(
                filename=filename, storage_path=storage_path,
                file_size=file_size,
                mime_type=file_item.content_type or "application/octet-stream",
            )
            await repo.create_file_metadata(uploaded_file)
            job = ProcessingJobs(
                id=job_id, uploaded_file_id=uploaded_file.id, status="queued",
            )
            await repo.create(job)
            await session.commit()
        except Exception as exc:
            import logging
            logger = logging.getLogger("xeno.api")
            logger.error(
                f"Database registration failed for job {job_id}:\n"
                f"Error type: {type(exc).__name__}\n"
                f"Error message: {str(exc)}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
            # Cleanup local file and Supabase file on DB error
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as cleanup_exc:
                    logger.error(f"Failed to cleanup file {file_path}: {cleanup_exc}")
            try:
                from app.services.storage import storage_service
                storage_service.delete_file(storage_path)
            except Exception as storage_cleanup_exc:
                logger.error(f"Failed to cleanup Supabase file {storage_path}: {storage_cleanup_exc}")
            raise HTTPException(status_code=500, detail=f"DB registration failed: {str(exc)}")

        # Cleanup local temp file after successful upload and DB registration
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError as exc:
            import logging
            logger = logging.getLogger("xeno.api")
            logger.warning(f"Failed to cleanup temp file {file_path}: {exc}")

        try:
            # Create Redis connection with reconnection logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    redis_conn = Redis.from_url(
                        settings.REDIS_URL,
                        socket_keepalive=True,
                        socket_keepalive_options={
                            TCP_KEEPIDLE: 10,
                            TCP_KEEPINTVL: 5,
                            TCP_KEEPCNT: 3
                        },
                        socket_timeout=30,
                        socket_connect_timeout=30,
                        health_check_interval=15,
                        retry_on_timeout=True,
                        decode_responses=False
                    )
                    # Test connection
                    redis_conn.ping()
                    q = Queue("default", connection=redis_conn)
                    from rq import Retry
                    q.enqueue(
                        "app.workers.tasks.process_dataset_task",
                        job_id, storage_path, country_code,
                        retry=Retry(max=3, interval=[60, 120, 240]),
                    )
                    break
                except Exception as redis_exc:
                    if attempt == max_retries - 1:
                        raise
                    import logging
                    logger = logging.getLogger("xeno.api")
                    logger.warning(f"Redis connection attempt {attempt + 1} failed, retrying: {redis_exc}")
                    import time
                    time.sleep(1)
        except Exception as exc:
            import logging
            logger = logging.getLogger("xeno.api")
            logger.error(
                f"Failed to enqueue task for job {job_id}:\n"
                f"Error type: {type(exc).__name__}\n"
                f"Error message: {str(exc)}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail=f"Failed to enqueue task: {str(exc)}")

        return UploadResponse(job_id=job_id, status="queued")

    # ── GET /api/jobs ─────────────────────────────────────────────────────
    @get(path="/jobs")
    async def list_jobs(self, session: AsyncSession) -> list[JobListItem]:
        stmt   = select(ProcessingJobs).order_by(desc(ProcessingJobs.id))
        result = await session.execute(stmt)
        jobs   = result.scalars().all()
        return [
            JobListItem(
                job_id=j.id, status=j.status,
                total_records=j.total_records,
                valid_records=j.valid_records,
                invalid_records=j.invalid_records,
            )
            for j in jobs
        ]

    # ── GET /api/jobs/{job_id} ────────────────────────────────────────────
    @get(path="/jobs/{job_id:str}")
    async def get_job_details(self, job_id: str, session: AsyncSession) -> JobDetailsResponse:
        job_id = _validate_job_id(job_id)
        repo = JobsRepository(session)
        job  = await repo.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        # Extract country_stats and error-type breakdown from the JSON blob
        raw_bd: dict = job.validation_breakdown or {}
        raw_country_stats: dict = raw_bd.get("country_stats", {})
        country_stat_entries: dict[str, CountryStatEntry] = {
            code: CountryStatEntry(
                total=v.get("total", 0),
                valid=v.get("valid", 0),
                invalid=v.get("invalid", 0),
            )
            for code, v in raw_country_stats.items()
            if isinstance(v, dict)
        }

        # Error-type distribution (strip country_stats key)
        error_type_bd: dict[str, int] = {
            k: v for k, v in raw_bd.items()
            if k != "country_stats" and isinstance(v, int)
        }

        return JobDetailsResponse(
            job_id=job.id,
            uploaded_file_id=job.uploaded_file_id,
            status=job.status,
            total_records=job.total_records,
            valid_records=job.valid_records,
            invalid_records=job.invalid_records,
            clean_file_path=job.clean_file_path,
            error_report_path=job.error_report_path,
            processing_time_ms=job.processing_time_ms,
            country_stats=country_stat_entries,
            validation_breakdown=error_type_bd,
            error_message=raw_bd.get("error_message"),
        )

    # ── GET /api/jobs/{job_id}/status ─────────────────────────────────────
    @get(path="/jobs/{job_id:str}/status")
    async def get_job_status(self, job_id: str, session: AsyncSession) -> JobStatusResponse:
        job_id = _validate_job_id(job_id)
        repo = JobsRepository(session)
        job  = await repo.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return JobStatusResponse(job_id=job.id, status=job.status)

    # ── GET /api/jobs/{job_id}/report ─────────────────────────────────────
    @get(path="/jobs/{job_id:str}/report")
    async def get_job_ai_report(self, job_id: str, session: AsyncSession) -> AIReportResponse:
        job_id = _validate_job_id(job_id)
        repo   = JobsRepository(session)
        report = await repo.get_ai_report(job_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"No AI report for job {job_id}")
        return AIReportResponse(
            quality_score=report.quality_score,
            common_errors=report.common_errors or [],
            country_analysis=report.country_analysis or {},
            recommendations=report.recommendations or [],
            executive_summary=report.executive_summary or "",
        )

    # ── GET /api/jobs/{job_id}/validation-breakdown ───────────────────────
    @get(path="/jobs/{job_id:str}/validation-breakdown")
    async def get_validation_breakdown(self, job_id: str, session: AsyncSession) -> dict:
        job_id = _validate_job_id(job_id)
        repo = JobsRepository(session)
        job  = await repo.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        if job.validation_breakdown:
            return job.validation_breakdown
        # fallback: read from file
        try:
            import json
            from app.services.storage import storage_service
            p = storage_service.get_validation_breakdown_path(job_id)
            if p.exists():
                with open(p) as fh:
                    return json.load(fh)
        except Exception:
            pass
        return {}

    # ── GET /api/jobs/{job_id}/downloads ──────────────────────────────────
    @get(path="/jobs/{job_id:str}/downloads")
    async def get_job_downloads(self, job_id: str, session: AsyncSession) -> DownloadLinksResponse:
        job_id = _validate_job_id(job_id)
        repo = JobsRepository(session)
        job  = await repo.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        import logging
        logger = logging.getLogger("xeno.api")
        logger.info(f"Job {job_id}: Fetching downloads - job.status={job.status}, clean_file_path={job.clean_file_path}, error_report_path={job.error_report_path}")

        # Check if files are in Supabase (storage path) or local filesystem
        clean_url = None
        error_url = None
        clean_rc = None
        clean_sz = None
        error_rc = None
        error_sz = None
        chunk_infos: list[ChunkInfo] = []

        # Try to get signed URLs from Supabase if paths are storage paths
        try:
            from app.services.storage import storage_service
            
            # Clean file
            if job.clean_file_path:
                logger.info(f"Job {job_id}: Processing clean_file_path={job.clean_file_path}")
                if job.clean_file_path.startswith("/") or job.clean_file_path.startswith("./"):
                    # Local filesystem path
                    clean_path = Path(job.clean_file_path)
                    if clean_path.exists():
                        clean_url = f"/api/downloads/{job_id}/clean"
                        clean_rc = _safe_record_count(clean_path)
                        clean_sz = _safe_file_size(clean_path)
                        logger.info(f"Job {job_id}: Clean file from local filesystem: {clean_path}, url={clean_url}")
                    else:
                        logger.warning(f"Job {job_id}: Clean file path exists but file not found: {clean_path}")
                else:
                    # Supabase storage path
                    try:
                        clean_url = storage_service.generate_signed_url(job.clean_file_path, expires_in=3600, download_filename="clean.csv")
                        # Try to get file size from Supabase metadata
                        try:
                            clean_sz = storage_service.get_file_size(job.clean_file_path)
                        except Exception:
                            clean_sz = None
                        # Record count not available from Supabase without downloading, use job.valid_records
                        clean_rc = job.valid_records
                        logger.info(f"Job {job_id}: Clean file from Supabase: {job.clean_file_path}, url={clean_url}, size={clean_sz}")
                    except Exception as e:
                        logger.error(f"Job {job_id}: Failed to generate signed URL for clean file: {e}")
            else:
                logger.warning(f"Job {job_id}: clean_file_path is None or empty")
            
            # Error file
            if job.error_report_path:
                logger.info(f"Job {job_id}: Processing error_report_path={job.error_report_path}")
                if job.error_report_path.startswith("/") or job.error_report_path.startswith("./"):
                    # Local filesystem path
                    error_path = Path(job.error_report_path)
                    if error_path.exists():
                        error_url = f"/api/downloads/{job_id}/errors"
                        error_rc = _safe_record_count(error_path)
                        error_sz = _safe_file_size(error_path)
                        logger.info(f"Job {job_id}: Error file from local filesystem: {error_path}, url={error_url}")
                    else:
                        logger.warning(f"Job {job_id}: Error file path exists but file not found: {error_path}")
                else:
                    # Supabase storage path
                    try:
                        error_url = storage_service.generate_signed_url(job.error_report_path, expires_in=3600, download_filename="errors.csv")
                        # Try to get file size from Supabase metadata
                        try:
                            error_sz = storage_service.get_file_size(job.error_report_path)
                        except Exception:
                            error_sz = None
                        # Record count not available from Supabase without downloading, use job.invalid_records
                        error_rc = job.invalid_records
                        logger.info(f"Job {job_id}: Error file from Supabase: {job.error_report_path}, url={error_url}, size={error_sz}")
                    except Exception as e:
                        logger.error(f"Job {job_id}: Failed to generate signed URL for error file: {e}")
            else:
                logger.warning(f"Job {job_id}: error_report_path is None or empty")
            
            # Chunks - for now, we'll need to store chunk paths in DB or generate them
            # For simplicity, we'll skip chunks for Supabase for now
            logger.info(f"Job {job_id}: Chunks not yet implemented for Supabase storage")
            
        except Exception as e:
            logger.error(f"Job {job_id}: Error getting download URLs: {e}")

        logger.info(f"Job {job_id}: Final download URLs - clean_url={clean_url}, error_url={error_url}")

        return DownloadLinksResponse(
            job_id=job_id,
            clean_transactions_url=clean_url,
            clean_record_count=clean_rc,
            clean_file_size_bytes=clean_sz,
            error_report_url=error_url,
            error_record_count=error_rc,
            error_file_size_bytes=error_sz,
            chunks=chunk_infos,
        )

    # ── GET /api/downloads/{job_id}/clean ─────────────────────────────────
    @get(path="/downloads/{job_id:str}/clean")
    async def download_clean(self, job_id: str) -> Response:
        """Serve the clean validated CSV for download."""
        job_id = _validate_job_id(job_id)
        path = _safe_output_path(job_id, "clean_transactions.csv")
        if not path.exists():
            raise HTTPException(status_code=404, detail="Clean file not found")
        return Response(
            content=path.read_bytes(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="clean.csv"'},
        )

    # ── GET /api/downloads/{job_id}/errors ────────────────────────────────
    @get(path="/downloads/{job_id:str}/errors")
    async def download_errors(self, job_id: str) -> Response:
        """Serve the error report CSV for download."""
        job_id = _validate_job_id(job_id)
        path = _safe_output_path(job_id, "error_report.csv")
        if not path.exists():
            raise HTTPException(status_code=404, detail="Error report not found")
        return Response(
            content=path.read_bytes(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="errors.csv"'},
        )

    # ── GET /api/downloads/{job_id}/chunk/{chunk_number} ─────────────────
    @get(path="/downloads/{job_id:str}/chunk/{chunk_number:str}")
    async def download_chunk(self, job_id: str, chunk_number: str) -> Response:
        """Serve a specific output chunk CSV for download."""
        job_id = _validate_job_id(job_id)
        chunk_number = _validate_chunk_number(chunk_number)
        path = _safe_output_path(job_id, f"chunk_{chunk_number}.csv")
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Chunk {chunk_number} not found")
        return Response(
            content=path.read_bytes(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="chunk_{chunk_number}.csv"'},
        )
