"""
Storage abstraction for file uploads in remote Stats Compass server.

Provides pluggable backends for local development and S3 production.
Supports presigned URLs for direct client uploads.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from datetime import timedelta
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.
    
    Implementations must provide:
    - get_upload_url: Generate URL for client upload
    - get_file_path: Get path/URL to uploaded file
    - delete_session_files: Clean up files for a session
    """
    
    @abstractmethod
    def get_upload_url(
        self, 
        session_id: str, 
        filename: str,
        content_type: str = "text/csv",
        expires_in: int = 3600
    ) -> dict:
        """
        Generate upload URL/path for client.
        
        Args:
            session_id: Session ID for isolation
            filename: Desired filename
            content_type: MIME type of file
            expires_in: URL expiry in seconds (for presigned URLs)
        
        Returns:
            Dict with:
            - url: Upload URL/path
            - method: HTTP method (PUT/POST)
            - headers: Required headers
            - file_key: Storage key for later retrieval
        """
        pass
    
    @abstractmethod
    def get_file_path(self, session_id: str, file_key: str) -> str:
        """
        Get path/URL to access uploaded file.
        
        Args:
            session_id: Session ID
            file_key: Storage key from get_upload_url
        
        Returns:
            Path or URL to file
        """
        pass
    
    @abstractmethod
    def delete_session_files(self, session_id: str) -> int:
        """
        Delete all files for a session.
        
        Args:
            session_id: Session ID
        
        Returns:
            Number of files deleted
        """
        pass
    
    @abstractmethod
    def file_exists(self, session_id: str, file_key: str) -> bool:
        """Check if file exists in storage."""
        pass
    
    @abstractmethod
    def save_image(
        self,
        session_id: str,
        image_data: bytes,
        filename: str
    ) -> str:
        """
        Save an image to storage.
        
        Args:
            session_id: Session ID for isolation
            image_data: Raw image bytes
            filename: Filename (e.g., "plot_1.png")
        
        Returns:
            URL/path to access the image
        """
        pass


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage for development.
    
    Files stored in: {base_path}/{session_id}/{filename}
    
    NOTE: get_upload_url returns a local file path that the
    server must handle - not a true presigned URL.
    For local dev, use register_file tool to copy/move files.
    """
    
    def __init__(self, base_path: str = "/tmp/stats-compass-uploads"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorageBackend initialized: {self.base_path}")
    
    def _session_path(self, session_id: str) -> Path:
        """Get path for session's files."""
        return self.base_path / session_id
    
    def get_upload_url(
        self, 
        session_id: str, 
        filename: str,
        content_type: str = "text/csv",
        expires_in: int = 3600
    ) -> dict:
        """
        For local storage, return file path as 'url'.
        
        Client should use register_file tool to register
        existing local files instead of uploading.
        """
        session_path = self._session_path(session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        
        file_path = session_path / filename
        file_key = filename
        
        return {
            "url": str(file_path),
            "method": "LOCAL",  # Indicates local storage
            "headers": {},
            "file_key": file_key,
            "storage_type": "local",
            "note": "Use register_file tool to register local files"
        }
    
    def get_file_path(self, session_id: str, file_key: str) -> str:
        """Get local file path."""
        return str(self._session_path(session_id) / file_key)
    
    def delete_session_files(self, session_id: str) -> int:
        """Delete session directory and all files."""
        session_path = self._session_path(session_id)
        
        if not session_path.exists():
            return 0
        
        count = 0
        for f in session_path.iterdir():
            if f.is_file():
                f.unlink()
                count += 1
        
        session_path.rmdir()
        logger.info(f"Deleted {count} files for session {session_id}")
        return count
    
    def file_exists(self, session_id: str, file_key: str) -> bool:
        """Check if file exists locally."""
        return (self._session_path(session_id) / file_key).exists()
    
    def save_image(
        self,
        session_id: str,
        image_data: bytes,
        filename: str
    ) -> str:
        """
        Save an image to storage.
        
        Args:
            session_id: Session ID for isolation
            image_data: Raw image bytes
            filename: Filename (e.g., "plot_1.png")
        
        Returns:
            URL/path to access the image
        """
        session_path = self._session_path(session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        
        file_path = session_path / filename
        file_path.write_bytes(image_data)
        
        logger.debug(f"Saved image: {file_path}")
        return str(file_path)


class S3StorageBackend(StorageBackend):
    """
    AWS S3 storage for production.
    
    Files stored in: s3://{bucket}/{prefix}/{session_id}/{filename}
    
    Supports presigned URLs for direct client uploads.
    Configure S3 lifecycle policy for automatic cleanup.
    """
    
    def __init__(
        self,
        bucket: str,
        prefix: str = "uploads",
        region: str = "us-east-1",
        endpoint_url: Optional[str] = None  # For S3-compatible services
    ):
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise ImportError("boto3 required for S3 storage: pip install boto3")
        
        self.bucket = bucket
        self.prefix = prefix
        self.region = region
        
        # Create S3 client
        config = Config(signature_version='s3v4')
        
        client_kwargs = {
            "region_name": region,
            "config": config,
        }
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        
        self.s3 = boto3.client("s3", **client_kwargs)
        logger.info(f"S3StorageBackend initialized: s3://{bucket}/{prefix}")
    
    def _object_key(self, session_id: str, file_key: str) -> str:
        """Get S3 object key."""
        return f"{self.prefix}/{session_id}/{file_key}"
    
    def get_upload_url(
        self, 
        session_id: str, 
        filename: str,
        content_type: str = "text/csv",
        expires_in: int = 3600
    ) -> dict:
        """
        Generate presigned URL for S3 upload.
        
        Client uses PUT request to this URL with file body.
        """
        file_key = filename
        object_key = self._object_key(session_id, file_key)
        
        presigned_url = self.s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        
        return {
            "url": presigned_url,
            "method": "PUT",
            "headers": {
                "Content-Type": content_type,
            },
            "file_key": file_key,
            "storage_type": "s3",
            "bucket": self.bucket,
            "object_key": object_key,
        }
    
    def get_file_path(self, session_id: str, file_key: str) -> str:
        """
        Get S3 URL for file access.
        
        Returns s3:// URL. For HTTP access, use presigned download URL.
        """
        object_key = self._object_key(session_id, file_key)
        return f"s3://{self.bucket}/{object_key}"
    
    def get_download_url(
        self, 
        session_id: str, 
        file_key: str,
        expires_in: int = 3600
    ) -> str:
        """Generate presigned download URL."""
        object_key = self._object_key(session_id, file_key)
        
        return self.s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
            },
            ExpiresIn=expires_in,
        )
    
    def delete_session_files(self, session_id: str) -> int:
        """Delete all S3 objects for session."""
        prefix = f"{self.prefix}/{session_id}/"
        
        # List all objects with prefix
        paginator = self.s3.get_paginator("list_objects_v2")
        
        objects_to_delete = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                objects_to_delete.append({"Key": obj["Key"]})
        
        if not objects_to_delete:
            return 0
        
        # Delete in batches of 1000 (S3 limit)
        for i in range(0, len(objects_to_delete), 1000):
            batch = objects_to_delete[i:i+1000]
            self.s3.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": batch}
            )
        
        logger.info(f"Deleted {len(objects_to_delete)} S3 objects for session {session_id}")
        return len(objects_to_delete)
    
    def file_exists(self, session_id: str, file_key: str) -> bool:
        """Check if file exists in S3."""
        try:
            self.s3.head_object(
                Bucket=self.bucket,
                Key=self._object_key(session_id, file_key)
            )
            return True
        except self.s3.exceptions.ClientError:
            return False
    
    def save_image(
        self,
        session_id: str,
        image_data: bytes,
        filename: str
    ) -> str:
        """
        Save an image directly to S3.
        
        Args:
            session_id: Session ID for isolation
            image_data: Raw image bytes
            filename: Filename (e.g., "plot_1.png")
        
        Returns:
            Presigned download URL (expires in 1 hour)
        """
        object_key = self._object_key(session_id, filename)
        
        self.s3.put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=image_data,
            ContentType="image/png"
        )
        
        logger.debug(f"Saved image to S3: {object_key}")
        
        # Return presigned download URL
        return self.get_download_url(session_id, filename, expires_in=3600)


def create_storage_backend() -> StorageBackend:
    """
    Factory function to create appropriate storage backend.
    
    Uses environment variables:
    - STORAGE_BACKEND: "local" or "s3" (default: "local")
    - S3_BUCKET: S3 bucket name (required for S3)
    - S3_PREFIX: S3 key prefix (default: "uploads")
    - S3_REGION: AWS region (default: "us-east-1")
    - S3_ENDPOINT_URL: Custom endpoint (for S3-compatible services)
    - LOCAL_STORAGE_PATH: Local storage path (default: /tmp/stats-compass-uploads)
    """
    backend_type = os.getenv("STORAGE_BACKEND", "local").lower()
    
    if backend_type == "s3":
        bucket = os.getenv("S3_BUCKET")
        if not bucket:
            raise ValueError("S3_BUCKET environment variable required for S3 storage")
        
        return S3StorageBackend(
            bucket=bucket,
            prefix=os.getenv("S3_PREFIX", "uploads"),
            region=os.getenv("S3_REGION", "us-east-1"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        )
    else:
        return LocalStorageBackend(
            base_path=os.getenv("LOCAL_STORAGE_PATH", "/tmp/stats-compass-uploads")
        )
