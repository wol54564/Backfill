import boto3
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import mimetypes

logger = logging.getLogger(__name__)

# Cloudflare R2 Configuration - Use environment variables for GitHub Actions
CF_R2_ACCESS_KEY = os.getenv('CF_R2_ACCESS_KEY_ID')
CF_R2_SECRET_KEY = os.getenv('CF_R2_SECRET_ACCESS_KEY')
CF_R2_ENDPOINT_URL = os.getenv('CF_R2_ENDPOINT_URL')


class R2Helper:
    """
    Helper class for Cloudflare R2 operations with partition structure for used-cars
    Partitions data by date: used-cars/year=YYYY/month=MM/day=DD/
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
                logger.info(f"Proceeding with R2 client - bucket: {self.bucket_name}, profile: {profile_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize R2 client: {e}")
            raise
    
    def get_partition_prefix(self, target_date: datetime = None) -> str:
        """
        Get R2 partition prefix based on date
        Format: 4sale-data/used-cars/year=YYYY/month=MM/day=DD/
        
        Args:
            target_date: Date to partition by (defaults to yesterday)
        
        Returns:
            Partition prefix string
        """
        if target_date is None:
            from datetime import timedelta
            target_date = datetime.now() - timedelta(days=1)
        
        year = target_date.strftime('%Y')
        month = target_date.strftime('%m')
        day = target_date.strftime('%d')
        
        return f"4sale-data/used-cars/year={year}/month={month}/day={day}"
    
    def upload_file(self, local_file_path: str, R2_filename: str, 
                    target_date: datetime = None, retries: int = 3) -> Optional[str]:
        """
        Upload a file to R2 with automatic partitioning
        
        Args:
            local_file_path: Path to local file
            R2_filename: Filename in R2 (relative path without partition)
            target_date: Date for partitioning (defaults to yesterday)
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
            target_date: Date for partitioning (defaults to yesterday)
            retries: Number of retry attempts
        
        Returns:
            Full R2 path or None if failed
        """
        partition = self.get_partition_prefix(target_date)
        R2_key = f"{partition}/{R2_filename}"
        
        for attempt in range(retries):
            try:
                # Determine content type based on filename
                content_type, _ = mimetypes.guess_type(R2_filename)
                if content_type is None:
                    content_type = "application/octet-stream"
                
                logger.info(f"Uploading file object (attempt {attempt + 1}/{retries}): {R2_key}")
                
                self.R2_client.upload_fileobj(
                    file_obj,
                    self.bucket_name,
                    R2_key,
                    ExtraArgs={'ContentType': content_type}
                )
                
                logger.info(f"Successfully uploaded file object: {R2_key}")
                return R2_key
                
            except Exception as e:
                logger.warning(f"Upload attempt {attempt + 1} failed: {e}")
                if attempt == retries - 1:
                    logger.error(f"Failed to upload file object after {retries} attempts")
                    return None
        
        return None
    
    def download_file(self, R2_filename: str, local_file_path: str, 
                     target_date: datetime = None) -> bool:
        """
        Download a file from R2
        
        Args:
            R2_filename: Filename in R2 (relative path without partition)
            local_file_path: Path to save the local file
            target_date: Date for partitioning (defaults to yesterday)
        
        Returns:
            True if successful, False otherwise
        """
        partition = self.get_partition_prefix(target_date)
        R2_key = f"{partition}/{R2_filename}"
        
        try:
            # Create parent directories if they don't exist
            Path(local_file_path).parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Downloading from R2: {R2_key}")
            self.R2_client.download_file(
                self.bucket_name,
                R2_key,
                local_file_path
            )
            
            logger.info(f"Successfully downloaded: {local_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading {R2_key}: {e}")
            return False
    
    def download_file_obj(self, R2_filename: str, file_obj,
                         target_date: datetime = None) -> bool:
        """
        Download a file from R2 to a file object
        
        Args:
            R2_filename: Filename in R2 (relative path without partition)
            file_obj: File-like object to write to
            target_date: Date for partitioning (defaults to yesterday)
        
        Returns:
            True if successful, False otherwise
        """
        partition = self.get_partition_prefix(target_date)
        R2_key = f"{partition}/{R2_filename}"
        
        try:
            logger.info(f"Downloading from R2 to file object: {R2_key}")
            self.R2_client.download_fileobj(
                self.bucket_name,
                R2_key,
                file_obj
            )
            
            logger.info(f"Successfully downloaded file object from: {R2_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading {R2_key} to file object: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> list:
        """
        List all files in R2 with optional prefix filter
        
        Args:
            prefix: R2 key prefix to filter by
        
        Returns:
            List of file keys
        """
        try:
            files = []
            paginator = self.R2_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        files.append(obj['Key'])
            
            logger.info(f"Found {len(files)} files with prefix: {prefix}")
            return files
            
        except Exception as e:
            logger.error(f"Error listing files with prefix {prefix}: {e}")
            return []
    
    def file_exists(self, R2_filename: str, target_date: datetime = None) -> bool:
        """
        Check if a file exists in R2
        
        Args:
            R2_filename: Filename in R2 (relative path without partition)
            target_date: Date for partitioning (defaults to yesterday)
        
        Returns:
            True if file exists, False otherwise
        """
        partition = self.get_partition_prefix(target_date)
        R2_key = f"{partition}/{R2_filename}"
        
        try:
            self.R2_client.head_object(Bucket=self.bucket_name, Key=R2_key)
            return True
        except self.R2_client.exceptions.NoSuchKey:
            return False
        except Exception as e:
            logger.warning(f"Error checking if file exists: {e}")
            return False
    
    def get_file_size(self, R2_filename: str, target_date: datetime = None) -> Optional[int]:
        """
        Get the size of a file in R2
        
        Args:
            R2_filename: Filename in R2 (relative path without partition)
            target_date: Date for partitioning (defaults to yesterday)
        
        Returns:
            File size in bytes or None if error
        """
        partition = self.get_partition_prefix(target_date)
        R2_key = f"{partition}/{R2_filename}"
        
        try:
            response = self.R2_client.head_object(Bucket=self.bucket_name, Key=R2_key)
            return response['ContentLength']
        except Exception as e:
            logger.warning(f"Error getting file size: {e}")
            return None
    
    def upload_image(self, image_url: str, image_data: bytes, subcategory_slug: str,
                     target_date: datetime = None, listing_id: Optional[str] = None, 
                     image_index: int = 0) -> Optional[str]:
        """
        Upload image bytes to R2 with ID-based naming
        
        Args:
            image_url: Original image URL
            image_data: Image bytes to upload
            subcategory_slug: Category slug for organization
            target_date: Date for partitioning
            listing_id: Listing ID for image naming (if provided, image will be named as listing_id_index.jpg)
            image_index: Index of image in the list (0, 1, 2, etc.)
        
        Returns:
            Full R2 path or None if failed
        """
        try:
            # Generate filename based on listing_id if provided
            if listing_id:
                filename = f"{listing_id}_{image_index}.jpg"
            else:
                # Fallback: extract filename from URL
                filename = image_url.split('/')[-1]
                if not filename:
                    filename = f"image_{int(__import__('time').time())}.jpg"
            
            partition = self.get_partition_prefix(target_date)
            R2_key = f"{partition}/images/{subcategory_slug}/{filename}"
            
            logger.info(f"Uploading image: {filename}")
            logger.info(f"Full R2 path: r2://{self.bucket_name}/{R2_key}")
            
            for attempt in range(3):
                try:
                    self.R2_client.put_object(
                        Bucket=self.bucket_name,
                        Key=R2_key,
                        Body=image_data,
                        ContentType='image/jpeg'
                    )
                    
                    logger.info(f"[OK] Successfully uploaded: {filename}")
                    return R2_key
                    
                except Exception as e:
                    logger.warning(f"Image upload attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        import time
                        time.sleep(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error uploading image {image_url}: {e}")
            return None
    
    def generate_R2_url(self, R2_key: str) -> str:
        """
        Generate public R2 URL for a key
        
        Args:
            R2_key: R2 object key
        
        Returns:
            Full R2 URL
        """
        _ep = CF_R2_ENDPOINT_URL.rstrip("/").removesuffix("/" + self.bucket_name)
        return f"{_ep}/{self.bucket_name}/{R2_key}"
