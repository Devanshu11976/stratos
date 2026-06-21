import time
import logging
import asyncio
import traceback
from redis import Redis
from rq import Queue, Worker, Retry
from app.config.settings import settings

# TCP keepalive constants
TCP_KEEPIDLE = 0x4  # Seconds before sending first keepalive
TCP_KEEPINTVL = 0x5  # Seconds between keepalive probes
TCP_KEEPCNT = 0x6    # Number of failed probes before dropping

logger = logging.getLogger("xeno.worker")

# Retry up to 3 times with exponential back-off: 60s, 120s, 240s
RETRY_POLICY = Retry(max=3, interval=[60, 120, 240])


def _run_async(coro):
    """Helper to run async coroutines in sync RQ context with proper event loop handling."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def process_dataset_task(job_id: str, storage_path: str, country_code: str) -> None:
    """RQ entry point — orchestrates validation, DB updates, and AI report."""
    logger.info(f"Starting processing for job {job_id}")
    local_file_path = None
    try:
        local_file_path = _run_async(_process_async(job_id, storage_path, country_code))
        logger.info(f"Finished processing job {job_id}")
    except Exception as exc:
        logger.error(
            f"Job {job_id} failed with full traceback:\n"
            f"Error type: {type(exc).__name__}\n"
            f"Error message: {str(exc)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        try:
            _run_async(_mark_failed(job_id, str(exc)))
        except Exception as mark_exc:
            logger.error(
                f"Could not mark job {job_id} as failed in DB:\n"
                f"Error type: {type(mark_exc).__name__}\n"
                f"Error message: {str(mark_exc)}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
        # Re-raise so RQ can apply the retry policy
        raise
    finally:
        # Cleanup temporary downloaded file
        if local_file_path:
            try:
                from app.services.storage import storage_service
                storage_service.cleanup_temp_file(local_file_path)
            except Exception as cleanup_exc:
                logger.error(f"Failed to cleanup temp file {local_file_path}: {cleanup_exc}")
        
        # Cleanup entire local outputs directory
        try:
            from app.services.storage import storage_service
            job_out_dir = storage_service.get_job_output_dir(job_id)
            if job_out_dir.exists():
                import shutil
                shutil.rmtree(job_out_dir)
                logger.info(f"Cleaned up local output directory: {job_out_dir}")
        except Exception as cleanup_exc:
            logger.error(f"Failed to cleanup output directory for job {job_id}: {cleanup_exc}")


async def _process_async(job_id: str, storage_path: str, country_code: str) -> str:
    from app.config.db import session_scope
    from app.repositories.jobs import JobsRepository
    from app.services.validation import validation_service
    from app.services.ai import ai_service
    from app.services.storage import storage_service
    from app.models.ai import AIReports

    # ── Step 1: Mark processing ───────────────────────────────────────────
    async with session_scope() as session:
        repo = JobsRepository(session)
        job = await repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in database")
        job.status = "processing"
        await session.flush()

    # ── Step 2: Download file from Supabase Storage ─────────────────────
    local_file_path = None
    try:
        logger.info(f"Attempting to download file from Supabase: {storage_path}")
        local_file_path = storage_service.download_file(storage_path)
        logger.info(f"Downloaded file from Supabase to {local_file_path}")
        
        # Verify file exists and log details
        import os
        if os.path.exists(local_file_path):
            file_size = os.path.getsize(local_file_path)
            logger.info(f"Downloaded file exists, size: {file_size} bytes")
        else:
            logger.error(f"Downloaded file does not exist at {local_file_path}")
            raise FileNotFoundError(f"Downloaded file not found: {local_file_path}")
    except Exception as exc:
        logger.error(
            f"Failed to download file from Supabase:\n"
            f"Error type: {type(exc).__name__}\n"
            f"Error message: {str(exc)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        raise RuntimeError(f"Failed to download file from storage: {str(exc)}")

    # ── Step 3: Run validation (timed) ───────────────────────────────────
    t_start = time.monotonic()
    result = await validation_service.process_dataset(job_id, local_file_path, country_code)
    t_end = time.monotonic()
    processing_time_ms = int((t_end - t_start) * 1000)

    # ── Step 4: Upload output files to Supabase Storage ───────────────────
    clean_storage_path = None
    error_storage_path = None
    chunk_storage_paths = []
    
    try:
        # Upload clean file if it exists
        clean_local_path = result.get("clean_file_path")
        if clean_local_path and os.path.exists(clean_local_path):
            clean_storage_name = f"{job_id}/clean_transactions.csv"
            clean_storage_path = storage_service.upload_file(clean_local_path, clean_storage_name)
            logger.info(f"Job {job_id}: Uploaded clean file to Supabase: {clean_storage_path}")
            # Cleanup local file after upload
            storage_service.cleanup_temp_file(clean_local_path)
        
        # Upload error file if it exists
        error_local_path = result.get("error_report_path")
        if error_local_path and os.path.exists(error_local_path):
            error_storage_name = f"{job_id}/error_report.csv"
            error_storage_path = storage_service.upload_file(error_local_path, error_storage_name)
            logger.info(f"Job {job_id}: Uploaded error file to Supabase: {error_storage_path}")
            # Cleanup local file after upload
            storage_service.cleanup_temp_file(error_local_path)
        
        # Upload chunks if they exist
        chunk_local_paths = result.get("chunk_paths", [])
        for idx, chunk_path in enumerate(chunk_local_paths):
            if os.path.exists(chunk_path):
                chunk_storage_name = f"{job_id}/chunk_{idx + 1}.csv"
                chunk_storage_path = storage_service.upload_file(chunk_path, chunk_storage_name)
                chunk_storage_paths.append(chunk_storage_path)
                logger.info(f"Job {job_id}: Uploaded chunk {idx + 1} to Supabase: {chunk_storage_path}")
                # Cleanup local file after upload
                storage_service.cleanup_temp_file(chunk_path)
        
        logger.info(f"Job {job_id}: Uploaded {len(chunk_storage_paths)} chunks to Supabase")
    except Exception as exc:
        logger.error(f"Job {job_id}: Failed to upload output files to Supabase: {exc}")
        # Continue with local paths if upload fails
        clean_storage_path = clean_local_path
        error_storage_path = error_local_path

    # ── Step 5: Persist metrics ───────────────────────────────────────────
    async with session_scope() as session:
        repo = JobsRepository(session)
        job = await repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found after validation")
        job.total_records        = result.get("total_records", 0)
        job.valid_records        = result.get("valid_records", 0)
        job.invalid_records      = result.get("invalid_records", 0)
        job.clean_file_path      = clean_storage_path or result.get("clean_file_path")
        job.error_report_path    = error_storage_path or result.get("error_report_path")
        job.validation_breakdown = result.get("validation_breakdown")
        job.processing_time_ms   = processing_time_ms
        logger.info(
            f"Job {job_id}: Persisting metrics - "
            f"total={job.total_records}, valid={job.valid_records}, invalid={job.invalid_records}, "
            f"clean_path={job.clean_file_path}, error_path={job.error_report_path}"
        )
        await session.flush()

    # ── Step 5: AI report ────────────────────────────────────────────────
    ai_report_data = await ai_service.generate_quality_report(
        {
            "job_id": job_id,
            "country_code": country_code,
            "total_records": result.get("total_records", 0),
            "valid_records": result.get("valid_records", 0),
            "invalid_records": result.get("invalid_records", 0),
            "country_stats": result.get("country_stats", {}),
            "validation_breakdown": result.get("validation_breakdown", {}),
        },
        result.get("error_logs", []),
    )

    # ── Step 6: Save AI report ────────────────────────────────────────────
    async with session_scope() as session:
        repo = JobsRepository(session)
        report = AIReports(
            job_id=job_id,
            quality_score=ai_report_data.get("quality_score", 0.0),
            common_errors=ai_report_data.get("common_errors", []),
            country_analysis=ai_report_data.get("country_analysis", {}),
            recommendations=ai_report_data.get("recommendations", []),
            executive_summary=ai_report_data.get("executive_summary", ""),
        )
        await repo.save_ai_report(report)

    # ── Step 7: Mark completed ────────────────────────────────────────────
    async with session_scope() as session:
        repo = JobsRepository(session)
        job = await repo.get_by_id(job_id)
        if job:
            job.status = "completed"
            logger.info(f"Job {job_id}: Marked as completed")
            await session.flush()
        else:
            logger.error(f"Job {job_id}: Job not found when trying to mark as completed")

    logger.info(f"Job {job_id}: Processing complete, returning local_file_path={local_file_path}")
    return local_file_path


async def _mark_failed(job_id: str, error_msg: str) -> None:
    from app.config.db import session_scope
    from app.repositories.jobs import JobsRepository
    async with session_scope() as session:
        repo = JobsRepository(session)
        job = await repo.get_by_id(job_id)
        if job:
            job.status = "failed"
            job.validation_breakdown = {"error_message": error_msg}
            await session.flush()


if __name__ == "__main__":
    # Create Redis connection with reconnection logic
    max_retries = 5
    redis_conn = None
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
                socket_timeout=60,
                socket_connect_timeout=30,
                health_check_interval=15,
                retry_on_timeout=True,
                decode_responses=False
            )
            # Test connection
            redis_conn.ping()
            print(f"Redis connection established on attempt {attempt + 1}")
            break
        except Exception as exc:
            print(f"Redis connection attempt {attempt + 1} failed: {exc}")
            if attempt == max_retries - 1:
                print("Failed to establish Redis connection after maximum retries")
                raise
            print(f"Retrying in 2 seconds...")
            import time
            time.sleep(2)
    
    worker = Worker([Queue("default", connection=redis_conn)], connection=redis_conn)
    worker.work(with_scheduler=True)
