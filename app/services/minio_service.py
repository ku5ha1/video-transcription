from minio import Minio
from minio.error import S3Error
from app.core.config import settings
from app.core.logging import get_logger
from typing import BinaryIO

logger = get_logger("services.minio")

class MinIOService:
    """Service for MinIO object storage operations"""
    
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure
        )
        self.bucket_name = "video-uploads"
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created MinIO bucket: {self.bucket_name}")
            else:
                logger.info(f"MinIO bucket already exists: {self.bucket_name}")
        except S3Error as e:
            logger.error(f"Failed to create/check bucket: {e}", exc_info=True)
            raise
    
    def upload_file(self, file_data: bytes, object_name: str, content_type: str = "video/mp4") -> str:
        """
        Upload file to MinIO
        Returns the object name/key
        """
        try:
            from io import BytesIO
            
            file_stream = BytesIO(file_data)
            file_size = len(file_data)
            
            self.client.put_object(
                self.bucket_name,
                object_name,
                file_stream,
                file_size,
                content_type=content_type
            )
            
            logger.info(f"Uploaded file to MinIO: {object_name}")
            return object_name
            
        except S3Error as e:
            logger.error(f"Failed to upload file to MinIO: {e}", exc_info=True)
            raise
    
    def download_file(self, object_name: str, file_path: str) -> str:
        """
        Download file from MinIO to local path
        Returns the local file path
        """
        try:
            self.client.fget_object(
                self.bucket_name,
                object_name,
                file_path
            )
            
            logger.info(f"Downloaded file from MinIO: {object_name} to {file_path}")
            return file_path
            
        except S3Error as e:
            logger.error(f"Failed to download file from MinIO: {e}", exc_info=True)
            raise
    
    def delete_file(self, object_name: str):
        """Delete file from MinIO"""
        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"Deleted file from MinIO: {object_name}")
        except S3Error as e:
            logger.error(f"Failed to delete file from MinIO: {e}", exc_info=True)
            raise
    
    def get_file_url(self, object_name: str, expires_in_seconds: int = 3600) -> str:
        """Get presigned URL for file access"""
        try:
            from datetime import timedelta
            
            url = self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=timedelta(seconds=expires_in_seconds)
            )
            
            logger.info(f"Generated presigned URL for: {object_name}")
            return url
            
        except S3Error as e:
            logger.error(f"Failed to generate presigned URL: {e}", exc_info=True)
            raise