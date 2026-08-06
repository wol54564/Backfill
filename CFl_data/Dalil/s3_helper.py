import boto3
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import mimetypes
import requests
import asyncio
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Cloudflare R2 Configuration - Use environment variables for GitHub Actions
CF_R2_ACCESS_KEY = os.getenv('CF_R2_ACCESS_KEY_ID')
CF_R2_SECRET_KEY = os.getenv('CF_R2_SECRET_ACCESS_KEY')
CF_R2_ENDPOINT_URL = os.getenv('CF_R2_ENDPOINT_URL')


class R2Helper:
    """
    Helper class for Cloudflare R2 operations with partition structure
    Partitions data by date: 4sale-data/Dalil/year=YYYY/month=MM/day=DD/
    """
    
    def __init__(self, bucket_name: str, profile_name: Optional[str] = None, region_name: str = None):
        """
        Initialize R2 client using AWS access key and secret key
        
        Args:
            bucket_name: R2 bucket name
            profile_name: Deprecated (kept for backward compatibility)
            region_name: Cloudflare R2 region (auto)
        """
        region_name = 'auto'
            
        self.bucket_name = bucket_name
        self.region_name = region_name
        
        try:
            # Create session using access key and secret key from environment variables
            if not CF_R2_ACCESS_KEY or not CF_R2_SECRET_KEY:
                raise ValueError("CF_R2_ACCESS_KEY_ID and CF_R2_SECRET_ACCESS_KEY environment variables must be set")
            if not CF_R2_ENDPOINT_URL:
                raise ValueError("CF_R2_ENDPOINT_URL environment variable must be set (e.g. https://<account_id>.r2.cloudflarestorage.com)")
            
            logger.info(f"Connecting to Cloudflare R2 endpoint: {CF_R2_ENDPOINT_URL}, bucket: {bucket_name}")
            self.R2_client = boto3.client(
                's3',
                endpoint_url=CF_R2_ENDPOINT_URL.rstrip("/").removesuffix("/" + bucket_name),
                aws_access_key_id=CF_R2_ACCESS_KEY,
                aws_secret_access_key=CF_R2_SECRET_KEY,
                region_name='auto'
            )
            
            # Test connection with HeadBucket (optional - some IAM roles may not have this permission)
            try:
                self.R2_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"Successfully verified access to R2 bucket: {self.bucket_name}")
            except self.R2_client.exceptions.NoSuchBucket:
                logger.error(f"Bucket does not exist: {self.bucket_name}")
                raise
            except Exception as e:
                # HeadBucket might fail due to IAM permissions, but we can still proceed
                logger.warning(f"Could not verify bucket access (this may be due to IAM permissions): {e}")
                logger.info(f"Proceeding with R2 client - bucket: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize R2 client: {e}")
            raise
    
    def get_partition_prefix(self, target_date: datetime = None) -> str:
        """
        Get R2 partition prefix based on date
        Format: 4sale-data/Dalil/year=YYYY/month=MM/day=DD/
        
        Args:
            target_date: Date to partition by (defaults to today)
        
        Returns:
            Partition prefix string
        """
        if target_date is None:
            target_date = datetime.now()
        
        year = target_date.strftime('%Y')
        month = target_date.strftime('%m')
        day = target_date.strftime('%d')
        
        return f"4sale-data/Dalil/year={year}/month={month}/day={day}"
    
    def upload_file(self, local_file_path: str, R2_filename: str, 
                    target_date: datetime = None, retries: int = 3) -> Optional[str]:
        """
        Upload a file to R2 with automatic partitioning
        
        Args:
            local_file_path: Path to local file
            R2_filename: Filename in R2 (relative path without partition)
            target_date: Date for partitioning (defaults to today)
            retries: Number of retry attempts
        
        Returns:
            Full R2 path or None if failed
        """
        partition = self.get_partition_prefix(target_date)
        R2_key = f"{partition}/{R2_filename}"
        
        for attempt in range(retries):
            try:
                local_path = Path(local_file_path)
                if not local_path.exists():
                    logger.error(f"Local file not found: {local_file_path}")
                    return None
                
                # Determine content type
                content_type, _ = mimetypes.guess_type(local_file_path)
                if content_type is None:
                    content_type = "application/octet-stream"
                
                logger.info(f"UPLOADING TO R2 (attempt {attempt + 1}/{retries}): R2://{self.bucket_name}/{R2_key}")
                
                self.R2_client.upload_file(
                    local_file_path,
                    self.bucket_name,
                    R2_key,
                    ExtraArgs={'ContentType': content_type}
                )
                
                logger.info(f"Successfully uploaded: {R2_key}")
                return R2_key
                
            except Exception as e:
                logger.warning(f"Upload attempt {attempt + 1} failed: {e}")
                if attempt == retries - 1:
                    logger.error(f"Failed to upload after {retries} attempts: {local_file_path}")
                    return None
        
        return None
    
    def upload_file_obj(self, file_obj, R2_filename: str, 
                       target_date: datetime = None, retries: int = 3) -> Optional[str]:
        """
        Upload a file object to R2 with automatic partitioning
        
        Args:
            file_obj: File-like object
            R2_filename: Filename in R2 (relative path without partition)
            target_date: Date for partitioning (defaults to today)
            retries: Number of retry attempts
        
        Returns:
            Full R2 path or None if failed
        """
        partition = self.get_partition_prefix(target_date)
        R2_key = f"{partition}/{R2_filename}"
        
        for attempt in range(retries):
            try:
                # Determine content type
                content_type = "application/octet-stream"
                if hasattr(file_obj, 'name'):
                    content_type, _ = mimetypes.guess_type(file_obj.name)
                    if content_type is None:
                        content_type = "application/octet-stream"
                
                logger.info(f"Uploading file object to R2 (attempt {attempt + 1}/{retries}): {R2_key}")
                
                self.R2_client.upload_fileobj(
                    file_obj,
                    self.bucket_name,
                    R2_key,
                    ExtraArgs={'ContentType': content_type}
                )
                
                logger.info(f"Successfully uploaded: {R2_key}")
                return R2_key
                
            except Exception as e:
                logger.warning(f"Upload attempt {attempt + 1} failed: {e}")
                if attempt == retries - 1:
                    logger.error(f"Failed to upload after {retries} attempts")
                    return None
        
        return None
    
    async def download_and_upload_image(self, image_url: str, R2_path: str, 
                                       target_date: datetime = None, 
                                       retries: int = 3) -> Optional[str]:
        """
        Download an image from URL and Upload to R2
        
        Args:
            image_url: URL of the image to download
            R2_path: R2 path (relative, without partition)
            target_date: Date for partitioning
            retries: Number of retry attempts
        
        Returns:
            Full R2 path or None if failed
        """
        partition = self.get_partition_prefix(target_date)
        R2_key = f"{partition}/{R2_path}"
        
        for attempt in range(retries):
            try:
                # Download image
                response = requests.get(image_url, timeout=30, stream=True)
                response.raise_for_status()
                
                # Determine content type from response or URL
                content_type = response.headers.get('Content-Type', 'image/jpeg')
                
                # Upload to R2
                self.R2_client.upload_fileobj(
                    response.raw,
                    self.bucket_name,
                    R2_key,
                    ExtraArgs={'ContentType': content_type}
                )
                
                logger.debug(f"Uploaded image to R2: {R2_key}")
                return R2_key
                
            except Exception as e:
                logger.warning(f"Image upload attempt {attempt + 1} failed for {image_url}: {e}")
                if attempt == retries - 1:
                    logger.error(f"Failed to upload image after {retries} attempts: {image_url}")
                    return None
                
                await asyncio.sleep(1)  # Wait before retry
        
        return None
    
    def list_files(self, prefix: str = "", max_keys: int = 1000) -> List[str]:
        """
        List files in R2 bucket with optional prefix
        
        Args:
            prefix: R2 prefix to filter by
            max_keys: Maximum number of keys to return
        
        Returns:
            List of R2 keys
        """
        try:
            response = self.R2_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            if 'Contents' not in response:
                return []
            
            return [obj['Key'] for obj in response['Contents']]
            
        except Exception as e:
            logger.error(f"Error listing files with prefix {prefix}: {e}")
            return []
    
    def file_exists(self, R2_key: str) -> bool:
        """
        Check if a file exists in R2
        
        Args:
            R2_key: Full R2 key
        
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.R2_client.head_object(Bucket=self.bucket_name, Key=R2_key)
            return True
        except:
            return False
    
    def delete_file(self, R2_key: str) -> bool:
        """
        Delete a file from R2
        
        Args:
            R2_key: Full R2 key
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.R2_client.delete_object(Bucket=self.bucket_name, Key=R2_key)
            logger.info(f"Deleted: {R2_key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting {R2_key}: {e}")
            return False
    
    def generate_presigned_url(self, R2_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for an R2 object
        
        Args:
            R2_key: Full R2 key
            expiration: URL expiration time in seconds (default: 1 hour)
        
        Returns:
            Presigned URL or None if failed
        """
        try:
            url = self.R2_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': R2_key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL for {R2_key}: {e}")
            return None
    
    def generate_R2_url(self, R2_key: str) -> str:
        """
        Generate a standard R2 URL (not presigned)
        
        Args:
            R2_key: Full R2 key
        
        Returns:
            R2 URL
        """
        return f"r2://{self.bucket_name}/{R2_key}"
    
    def get_file_size(self, R2_key: str) -> Optional[int]:
        """
        Get file size in bytes
        
        Args:
            R2_key: Full R2 key
        
        Returns:
            File size in bytes or None if failed
        """
        try:
            response = self.R2_client.head_object(Bucket=self.bucket_name, Key=R2_key)
            return response['ContentLength']
        except Exception as e:
            logger.error(f"Error getting file size for {R2_key}: {e}")
            return None
