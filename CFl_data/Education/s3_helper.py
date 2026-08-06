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
    Helper class for Cloudflare R2 operations with partition structure
    Partitions data by date: education/year=YYYY/month=MM/day=DD/
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
        Format: 4sale-data/education/year=YYYY/month=MM/day=DD/
        
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
        
        return f"4sale-data/education/year={year}/month={month}/day={day}"
    
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
                logger.info(f"UPLOADING TO R2: {R2_key} (Attempt {attempt + 1}/{retries})...")
                
                with open(local_file_path, 'rb') as f:
                    self.R2_client.upload_fileobj(
                        f,
                        self.bucket_name,
                        R2_key,
                        ExtraArgs={'ContentType': self._get_content_type(local_file_path)}
                    )
                
                logger.info(f"[OK] Successfully uploaded: {R2_key}")
                return R2_key
                
            except Exception as e:
                logger.warning(f"Upload attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"Failed to upload file after {retries} attempts: {local_file_path}")
        return None
    
    def upload_image(self, image_url: str, image_data: bytes, subcategory_slug: str,
                    target_date: datetime = None, listing_id: int = None, 
                    image_index: int = 0, category_name: str = None) -> Optional[str]:
        """
        Upload image data to R2 with organized folder structure
        
        Args:
            image_url: Original image URL
            image_data: Image file bytes
            subcategory_slug: Subcategory slug for folder organization
            target_date: Date for partitioning
            listing_id: ID of the listing
            image_index: Index of the image
            category_name: Parent category name for folder organization (optional)
        
        Returns:
            R2 key path or None if failed
        """
        partition = self.get_partition_prefix(target_date)
        
        # Determine file extension from URL
        extension = 'jpg'
        if '.' in image_url.split('/')[-1]:
            extension = image_url.split('.')[-1]
        
        # Create R2 key with structure: partition/images/category_name/subcategory/listing_id_image_index.ext
        if category_name:
            R2_key = f"{partition}/images/{category_name}/{subcategory_slug}/{listing_id}_{image_index}.{extension}"
        else:
            R2_key = f"{partition}/images/{subcategory_slug}/{listing_id}_{image_index}.{extension}"
        
        try:
            logger.debug(f"Uploading image to R2: {R2_key}...")
            
            self.R2_client.put_object(
                Bucket=self.bucket_name,
                Key=R2_key,
                Body=image_data,
                ContentType=f'image/{extension}'
            )
            
            logger.debug(f"[OK] Image uploaded: {R2_key}")
            return R2_key
            
        except Exception as e:
            logger.error(f"Error uploading image to R2: {e}")
            return None
    
    def generate_R2_url(self, R2_key: str) -> str:
        """
        Generate public HTTPS URL for R2 object
        
        Args:
            R2_key: R2 key/path
        
        Returns:
            HTTPS URL to access the object
        """
        _ep = CF_R2_ENDPOINT_URL.rstrip("/").removesuffix("/" + self.bucket_name)
        return f"{_ep}/{self.bucket_name}/{R2_key}"
    
    def _get_content_type(self, file_path: str) -> str:
        """
        Determine MIME type from file path
        
        Args:
            file_path: Path to file
        
        Returns:
            MIME type string
        """
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or 'application/octet-stream'
