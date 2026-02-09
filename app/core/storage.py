"""
Ultra-optimized, Type-Safe Cloud Storage Service for Google Cloud Storage
Minimizes API calls, bandwidth, and storage costs.
"""

import hashlib
import io
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from google.cloud import storage
from google.cloud.exceptions import NotFound
from google.api_core import exceptions
from app.core.config import config


class StorageService:
    """
    Generic, type-safe cloud storage service optimized for Google Cloud Storage.

    Design Principles:
    1. Write once, read many (immutable files)
    2. Minimize PUT requests (no overwrites)
    3. Use signed URLs for direct downloads
    4. Keep metadata minimal
    5. Fail fast, return structured errors
    """

    _client: Optional[storage.Client] = None
    _bucket_name: str = config.gcp_bucket_name

    @classmethod
    def _get_client(cls) -> storage.Client:
        """
        Lazy-load GCS client with connection pooling.
        Ensures connection reuse and minimal latency.
        """
        if cls._client is None:
            cls._client = storage.Client(project=config.gcp_project_id)
        return cls._client

    @classmethod
    def _get_bucket(cls) -> storage.Bucket:
        """
        Get the GCS bucket instance.
        """
        client = cls._get_client()
        return client.bucket(cls._bucket_name)

    @classmethod
    def upload_file(
        cls,
        file_content: bytes,
        file_key: str,
        content_type: str = "application/pdf",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str]:
        """
        Upload a small file to GCS in a single PUT request.

        Returns:
            Tuple[str, str]: (file_url, checksum)
        Raises:
            Exception: On failure
        """
        bucket = cls._get_bucket()
        blob = bucket.blob(file_key)
        checksum: str = hashlib.md5(file_content).hexdigest()

        # Set content type
        blob.content_type = content_type

        # Set metadata if provided (GCS metadata keys must be lowercase)
        if metadata:
            blob.metadata = {
                k.lower(): str(v)[:100] for k, v in list(metadata.items())[:3]
            }

        try:
            blob.upload_from_string(
                file_content,
                content_type=content_type,
            )
            file_url: str = (
                f"https://storage.googleapis.com/{cls._bucket_name}/{file_key}"
            )
            return file_url, checksum
        except exceptions.GoogleAPIError as e:
            raise Exception(f"GCS upload failed: {str(e)}") from e


    @classmethod
    def generate_presigned_url(
        cls,
        file_key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate a temporary signed URL for secure file download.
        Works with both service account keys and Compute Engine credentials.

        Returns:
            str: Signed URL
        Raises:
            Exception: On failure
        """
        bucket = cls._get_bucket()
        blob = bucket.blob(file_key)

        try:
            import google.auth
            from google.auth import compute_engine, impersonated_credentials
            from google.auth.transport import requests
            
            credentials, project = google.auth.default()
            
            # For Compute Engine credentials, use impersonation for signing
            if isinstance(credentials, compute_engine.Credentials):
                # Get a fresh token
                auth_request = requests.Request()
                credentials.refresh(auth_request)
                
                # Create signing credentials via impersonation
                signing_credentials = impersonated_credentials.Credentials(
                    source_credentials=credentials,
                    target_principal=credentials.service_account_email,
                    target_scopes=['https://www.googleapis.com/auth/cloud-platform'],
                    lifetime=3600
                )
                
                url: str = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=expiration),
                    method="GET",
                    credentials=signing_credentials,
                )
            else:
                # Local development with service account key file
                url: str = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=expiration),
                    method="GET",
                )

            return url
        except exceptions.GoogleAPIError as e:
            raise Exception(f"Failed to generate signed URL: {str(e)}") from e

    @classmethod
    def file_exists(cls, file_key: str) -> bool:
        """
        Check if file exists in GCS.

        Returns:
            bool: True if file exists, False otherwise
        """
        bucket = cls._get_bucket()
        blob = bucket.blob(file_key)

        try:
            return blob.exists()
        except exceptions.GoogleAPIError as e:
            raise Exception(f"GCS existence check failed: {str(e)}") from e

    @classmethod
    def get_file_metadata(cls, file_key: str) -> Dict[str, Any]:
        """
        Retrieve metadata without downloading file content.

        Returns:
            Dict[str, Any]: Metadata with size, MD5 hash, and timestamps
        """
        bucket = cls._get_bucket()
        blob = bucket.blob(file_key)

        try:
            blob.reload()  # Fetch metadata from GCS
            metadata: Dict[str, Any] = {
                "size": int(blob.size or 0),
                "etag": blob.md5_hash or "",
                "last_modified": blob.updated or datetime.now(),
                "content_type": blob.content_type or "",
            }
            return metadata
        except NotFound:
            raise Exception(f"File not found: {file_key}")
        except exceptions.GoogleAPIError as e:
            raise Exception(f"Failed to get metadata: {str(e)}") from e

    @classmethod
    def delete_file(cls, file_key: str) -> None:
        """
        Delete a file from GCS (should be rarely used).

        Returns:
            None
        """
        bucket = cls._get_bucket()
        blob = bucket.blob(file_key)

        try:
            blob.delete()
        except exceptions.GoogleAPIError as e:
            raise Exception(f"Failed to delete file: {str(e)}") from e

    @classmethod
    def get_file_url(cls, file_key: str) -> str:
        """
        Get the URL of a file in GCS.
        Usage: StorageService.get_file_url("path/to/file.pdf")

        Returns:
            str: URL of the file
        """
        return f"https://storage.googleapis.com/{cls._bucket_name}/{file_key}"
