import os
import logging
import tempfile
from pathlib import Path
from typing import Optional
from supabase import create_client, Client
from app.config.settings import settings

logger = logging.getLogger("xeno.storage")


class StorageService:
    """Manages file storage using Supabase Storage for shared access between Render and Railway."""
    
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.output_dir = Path(settings.OUTPUT_DIR)
        self._ensure_directories()
        
        # Initialize Supabase client
        self.supabase: Optional[Client] = None
        if settings.supabase_url and settings.supabase_service_key:
            try:
                self.supabase = create_client(
                    settings.supabase_url,
                    settings.supabase_service_key
                )
                logger.info("Supabase client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
        else:
            logger.warning("Supabase credentials not configured, storage operations will fail")

    def _ensure_directories(self) -> None:
        """Helper checking and building folders structures."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_upload_path(self, filename: str) -> Path:
        """Resolve save path for raw file uploads (local temp)."""
        return self.upload_dir / filename

    def get_job_output_dir(self, job_id: str) -> Path:
        """Resolve specific output directory matching the tracking job_id."""
        job_dir = self.output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def get_clean_output_path(self, job_id: str) -> Path:
        """Clean CSV save path."""
        return self.get_job_output_dir(job_id) / "clean_transactions.csv"

    def get_error_report_path(self, job_id: str) -> Path:
        """Error failure CSV report path."""
        return self.get_job_output_dir(job_id) / "error_report.csv"

    def get_chunk_output_path(self, job_id: str, chunk_index: int) -> Path:
        """Batch sub-split chunk CSV file path."""
        return self.get_job_output_dir(job_id) / f"chunk_{chunk_index}.csv"

    def get_validation_breakdown_path(self, job_id: str) -> Path:
        """Validation breakdown JSON file path."""
        return self.get_job_output_dir(job_id) / "validation_breakdown.json"
    
    def get_validation_report_path(self, job_id: str) -> Path:
        """Comprehensive validation report JSON file path."""
        return self.get_job_output_dir(job_id) / "validation_report.json"
    
    def get_error_summary_path(self, job_id: str) -> Path:
        """Error summary report JSON file path."""
        return self.get_job_output_dir(job_id) / "error_summary.json"
    
    def get_ai_insights_path(self, job_id: str) -> Path:
        """AI insights report JSON file path."""
        return self.get_job_output_dir(job_id) / "ai_insights.json"
    
    def get_processing_stats_path(self, job_id: str) -> Path:
        """Processing statistics JSON file path."""
        return self.get_job_output_dir(job_id) / "processing_stats.json"

    def upload_file(self, local_path: str, storage_path: Optional[str] = None) -> str:
        """
        Upload a file to Supabase Storage.
        
        Args:
            local_path: Path to the local file to upload
            storage_path: Optional storage path. If not provided, uses filename from local_path
            
        Returns:
            The storage path of the uploaded file
            
        Raises:
            Exception: If upload fails
        """
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")
        
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")
        
        if storage_path is None:
            storage_path = os.path.basename(local_path)
        
        try:
            logger.info(f"Uploading {local_path} to Supabase bucket {settings.supabase_bucket_name} as {storage_path}")
            with open(local_path, "rb") as f:
                self.supabase.storage.from_(settings.supabase_bucket_name).upload(
                    storage_path, f
                )
            logger.info(f"Successfully uploaded {local_path} to {storage_path}")
            return storage_path
        except Exception as e:
            logger.error(
                f"Failed to upload {local_path} to Supabase:\n"
                f"Error type: {type(e).__name__}\n"
                f"Error message: {str(e)}\n"
                f"Bucket: {settings.supabase_bucket_name}\n"
                f"Storage path: {storage_path}"
            )
            raise

    def download_file(self, storage_path: str, local_path: Optional[str] = None) -> str:
        """
        Download a file from Supabase Storage.
        
        Args:
            storage_path: Path in Supabase Storage
            local_path: Optional local path to save to. If not provided, uses temp directory
            
        Returns:
            The local path of the downloaded file
            
        Raises:
            Exception: If download fails
        """
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")
        
        if local_path is None:
            # Create temp file with same extension in temp directory
            ext = os.path.splitext(storage_path)[1]
            local_path = tempfile.mktemp(suffix=ext, dir=self.upload_dir)
        
        try:
            logger.info(f"Downloading {storage_path} from bucket {settings.supabase_bucket_name}")
            response = self.supabase.storage.from_(settings.supabase_bucket_name).download(
                storage_path
            )
            
            # Ensure parent directory exists
            parent_dir = os.path.dirname(local_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            
            with open(local_path, "wb") as f:
                f.write(response)
            
            file_size = os.path.getsize(local_path)
            logger.info(f"Successfully downloaded {storage_path} to {local_path} ({file_size} bytes)")
            return local_path
        except Exception as e:
            logger.error(
                f"Failed to download {storage_path} from Supabase:\n"
                f"Error type: {type(e).__name__}\n"
                f"Error message: {str(e)}\n"
                f"Bucket: {settings.supabase_bucket_name}"
            )
            raise

    def delete_file(self, storage_path: str) -> None:
        """
        Delete a file from Supabase Storage.
        
        Args:
            storage_path: Path in Supabase Storage to delete
            
        Raises:
            Exception: If deletion fails
        """
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")
        
        try:
            self.supabase.storage.from_(settings.supabase_bucket_name).remove(
                [storage_path]
            )
            logger.info(f"Successfully deleted {storage_path} from Supabase")
        except Exception as e:
            logger.error(f"Failed to delete {storage_path} from Supabase: {e}")
            raise

    def generate_signed_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """
        Generate a signed URL for temporary access to a file.
        
        Args:
            storage_path: Path in Supabase Storage
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Signed URL string
            
        Raises:
            Exception: If URL generation fails
        """
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")
        
        try:
            response = self.supabase.storage.from_(settings.supabase_bucket_name).create_signed_url(
                storage_path, expires_in
            )
            signed_url = response.get("signedURL")
            logger.info(f"Generated signed URL for {storage_path}")
            return signed_url
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {storage_path}: {e}")
            raise

    def cleanup_temp_file(self, local_path: str) -> None:
        """
        Clean up a temporary local file.
        
        Args:
            local_path: Path to the temporary file to delete
        """
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
                logger.info(f"Cleaned up temporary file: {local_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup temporary file {local_path}: {e}")

    def get_file_size(self, storage_path: str) -> Optional[int]:
        """
        Get file size from Supabase Storage metadata.
        
        Args:
            storage_path: Path in Supabase Storage
            
        Returns:
            File size in bytes, or None if unavailable
        """
        if not self.supabase:
            return None
        
        try:
            # Get file metadata from Supabase
            response = self.supabase.storage.from_(settings.supabase_bucket_name).get_metadata(
                [storage_path]
            )
            if response and len(response) > 0:
                # Supabase returns metadata with size in bytes
                return response[0].get("metadata", {}).get("size") or response[0].get("size")
        except Exception as e:
            logger.warning(f"Failed to get file size for {storage_path}: {e}")
        
        return None


storage_service = StorageService()
