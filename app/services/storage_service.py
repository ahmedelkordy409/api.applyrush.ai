"""
S3/R2 Storage Service for file uploads
Handles resume uploads to cloud storage
"""

import boto3
import logging
from typing import BinaryIO, Optional
from datetime import datetime
import os
from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    Unified storage service for S3 and Cloudflare R2
    """

    def __init__(self):
        # Prefer Cloudflare R2 if configured, fallback to AWS S3
        if settings.CLOUDFLARE_R2_ACCOUNT_ID and settings.CLOUDFLARE_R2_ACCESS_KEY:
            self.client = boto3.client(
                's3',
                endpoint_url=f'https://{settings.CLOUDFLARE_R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
                aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY,
                aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_KEY,
                region_name='auto'
            )
            self.bucket_name = 'applyrush-resumes'  # R2 bucket
            self.storage_type = 'r2'
            logger.info("Using Cloudflare R2 for storage")
        elif settings.AWS_S3_BUCKET:
            self.client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_SES_ACCESS_KEY,
                aws_secret_access_key=settings.AWS_SES_SECRET_KEY,
                region_name=settings.AWS_S3_REGION
            )
            self.bucket_name = settings.AWS_S3_BUCKET
            self.storage_type = 's3'
            logger.info(f"Using AWS S3 for storage: {self.bucket_name}")
        else:
            # Fallback to local storage
            self.client = None
            self.bucket_name = None
            self.storage_type = 'local'
            logger.warning("No cloud storage configured, using local storage")

    def upload_resume(
        self,
        file_content: bytes,
        user_id: str,
        filename: str,
        content_type: str = 'application/pdf'
    ) -> str:
        """
        Upload resume to storage and return the URL/path

        Args:
            file_content: File content as bytes
            user_id: User ID for organizing files
            filename: Original filename
            content_type: MIME type

        Returns:
            URL or path to the uploaded file
        """
        # Generate unique file key
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        safe_filename = filename.replace(' ', '_')
        file_key = f"resumes/{user_id}/{timestamp}_{safe_filename}"

        if self.storage_type in ['s3', 'r2']:
            try:
                # Upload to S3/R2
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=file_key,
                    Body=file_content,
                    ContentType=content_type,
                    Metadata={
                        'user_id': user_id,
                        'original_filename': filename,
                        'uploaded_at': timestamp
                    }
                )

                # Generate URL
                if self.storage_type == 'r2':
                    file_url = f"https://{settings.CLOUDFLARE_R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{self.bucket_name}/{file_key}"
                else:
                    file_url = f"https://{self.bucket_name}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{file_key}"

                logger.info(f"Uploaded resume to {self.storage_type}: {file_key}")
                return file_url

            except Exception as e:
                logger.error(f"Error uploading to {self.storage_type}: {str(e)}")
                # Fallback to local storage on error
                return self._save_local(file_content, file_key)

        else:
            # Local storage
            return self._save_local(file_content, file_key)

    def _save_local(self, file_content: bytes, file_key: str) -> str:
        """Save file locally as fallback"""
        local_path = f"/tmp/{file_key}"
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        with open(local_path, 'wb') as f:
            f.write(file_content)

        logger.info(f"Saved resume locally: {local_path}")
        return local_path

    def download_resume(self, file_url_or_path: str) -> bytes:
        """
        Download resume from storage

        Args:
            file_url_or_path: URL (for S3/R2) or local path

        Returns:
            File content as bytes
        """
        if file_url_or_path.startswith('/tmp/') or file_url_or_path.startswith('/'):
            # Local file
            with open(file_url_or_path, 'rb') as f:
                return f.read()

        elif file_url_or_path.startswith('http'):
            # Extract key from URL
            if self.storage_type == 'r2':
                file_key = file_url_or_path.split(f'{self.bucket_name}/')[-1]
            else:
                file_key = file_url_or_path.split(f'{self.bucket_name}.s3.')[-1].split('/', 1)[-1]

            try:
                response = self.client.get_object(
                    Bucket=self.bucket_name,
                    Key=file_key
                )
                return response['Body'].read()

            except Exception as e:
                logger.error(f"Error downloading from {self.storage_type}: {str(e)}")
                raise

        else:
            raise ValueError(f"Invalid file URL or path: {file_url_or_path}")

    def delete_resume(self, file_url_or_path: str) -> bool:
        """
        Delete resume from storage

        Args:
            file_url_or_path: URL (for S3/R2) or local path

        Returns:
            True if successful
        """
        if file_url_or_path.startswith('/tmp/') or file_url_or_path.startswith('/'):
            # Local file
            try:
                if os.path.exists(file_url_or_path):
                    os.remove(file_url_or_path)
                return True
            except Exception as e:
                logger.error(f"Error deleting local file: {str(e)}")
                return False

        elif file_url_or_path.startswith('http') and self.storage_type in ['s3', 'r2']:
            # Extract key from URL
            if self.storage_type == 'r2':
                file_key = file_url_or_path.split(f'{self.bucket_name}/')[-1]
            else:
                file_key = file_url_or_path.split(f'{self.bucket_name}.s3.')[-1].split('/', 1)[-1]

            try:
                self.client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_key
                )
                logger.info(f"Deleted resume from {self.storage_type}: {file_key}")
                return True

            except Exception as e:
                logger.error(f"Error deleting from {self.storage_type}: {str(e)}")
                return False

        return False


# Singleton instance
storage_service = StorageService()
