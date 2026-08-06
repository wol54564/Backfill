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
    Partitions data by date: others/year=YYYY/month=MM/day=DD/
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
        Format: 4sale-data/others/year=YYYY/month=MM/day=DD/
        
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
        
        return f"4sale-data/others/year={year}/month={month}/day={day}"
    
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
                logger.info(f"Uploading {local_file_path} to R2://{self.bucket_name}/{R2_key} (attempt {attempt + 1}/{retries})")
                
                # Detect content type
                content_type, _ = mimetypes.guess_type(local_file_path)
                if content_type is None:
                    content_type = 'application/octet-stream'
                
                # Upload file
                self.R2_client.upload_file(
                    local_file_path,
                    self.bucket_name,
                    R2_key,
                    ExtraArgs={'ContentType': content_type}
                )
                
                logger.info(f"Successfully Uploaded to R2://{self.bucket_name}/{R2_key}")
                return R2_key
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to upload {local_file_path} after {retries} attempts")
                    return None
    
    def upload_image(self, image_url: str, image_data: bytes, subcategory_slug: str,
                    target_date: datetime, listing_id: int, image_index: int) -> Optional[str]:
        """
        Upload an image to R2 with organized structure
        Path: 4sale-data/others/year=YYYY/month=MM/day=DD/images/subcategory_slug/listing_id_index.jpg
        
        Args:
            image_url: Original image URL (for extension detection)
            image_data: Image binary data
            subcategory_slug: Subcategory slug (e.g., 'currencies-stamps-and-antiques')
            target_date: Date for partitioning
            listing_id: Listing ID
            image_index: Image index in listing
        
        Returns:
            Full R2 path or None if failed
        """
        try:
            # Determine file extension
            ext = Path(image_url).suffix or '.jpg'
            
            # Build R2 key with partitioning and organization
            partition = self.get_partition_prefix(target_date)
            filename = f"{listing_id}_{image_index}{ext}"
            R2_key = f"{partition}/images/{subcategory_slug}/{filename}"
            
            # Upload directly from memory
            self.R2_client.put_object(
                Bucket=self.bucket_name,
                Key=R2_key,
                Body=image_data,
                ContentType='image/jpeg'
            )
            
            logger.debug(f"Uploaded image to R2://{self.bucket_name}/{R2_key}")
            return R2_key
            
        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            return None
    
    def generate_R2_url(self, R2_key: str) -> str:
        """
        Generate public R2 URL for a given key
        
        Args:
            R2_key: R2 object key
        
        Returns:
            Public R2 URL
        """
        _ep = CF_R2_ENDPOINT_URL.rstrip("/").removesuffix("/" + self.bucket_name)
        return f"{_ep}/{self.bucket_name}/{R2_key}"
    
    def list_files(self, prefix: str = "", max_keys: int = 1000) -> list:
        """
        List files in R2 bucket with given prefix
        
        Args:
            prefix: R2 key prefix to filter (e.g., '4sale-data/others/')
            max_keys: Maximum number of keys to return
        
        Returns:
            List of R2 object keys
        """
        try:
            response = self.R2_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            else:
                logger.info(f"No objects found with prefix: {prefix}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def download_file(self, R2_key: str, local_path: str) -> bool:
        """
        Download a file from R2
        
        Args:
            R2_key: R2 object key
            local_path: Local destination path
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Downloading R2://{self.bucket_name}/{R2_key} to {local_path}")
            
            # Create parent directories if needed
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.R2_client.download_file(
                self.bucket_name,
                R2_key,
                local_path
            )
            
            logger.info(f"Successfully downloaded to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {R2_key}: {e}")
            return False
    
    def delete_file(self, R2_key: str) -> bool:
        """
        Delete a file from R2
        
        Args:
            R2_key: R2 object key to delete
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Deleting R2://{self.bucket_name}/{R2_key}")
            
            self.R2_client.delete_object(
                Bucket=self.bucket_name,
                Key=R2_key
            )
            
            logger.info(f"Successfully deleted {R2_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete {R2_key}: {e}")
            return False
    
    def get_file_metadata(self, R2_key: str) -> Optional[dict]:
        """
        Get metadata for an R2 object
        
        Args:
            R2_key: R2 object key
        
        Returns:
            Metadata dict or None if failed
        """
        try:
            response = self.R2_client.head_object(
                Bucket=self.bucket_name,
                Key=R2_key
            )
            
            return {
                'size': response['ContentLength'],
                'last_modified': response['LastModified'],
                'content_type': response.get('ContentType'),
                'etag': response.get('ETag')
            }
            
        except Exception as e:
            logger.error(f"Failed to get metadata for {R2_key}: {e}")
            return None
    
    def check_file_exists(self, R2_key: str) -> bool:
        """
        Check if a file exists in R2
        
        Args:
            R2_key: R2 object key
        
        Returns:
            True if exists, False otherwise
        """
        try:
            self.R2_client.head_object(
                Bucket=self.bucket_name,
                Key=R2_key
            )
            return True
        except:
            return False
    
    def copy_file(self, source_key: str, dest_key: str) -> bool:
        """
        Copy a file within R2
        
        Args:
            source_key: Source R2 object key
            dest_key: Destination R2 object key
        
        Returns:
            True if successful, False otherwise
        """
        try:
            copy_source = {
                'Bucket': self.bucket_name,
                'Key': source_key
            }
            
            self.R2_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=dest_key
            )
            
            logger.info(f"Copied {source_key} to {dest_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy {source_key} to {dest_key}: {e}")
            return False
    
    def get_partition_stats(self, target_date: datetime = None) -> dict:
        """
        Get statistics for a specific date partition
        
        Args:
            target_date: Date to check (defaults to yesterday)
        
        Returns:
            Dictionary with partition statistics
        """
        partition_prefix = self.get_partition_prefix(target_date)
        
        try:
            response = self.R2_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=partition_prefix
            )
            
            if 'Contents' in response:
                total_size = sum(obj['Size'] for obj in response['Contents'])
                file_count = len(response['Contents'])
                
                return {
                    'partition': partition_prefix,
                    'file_count': file_count,
                    'total_size_bytes': total_size,
                    'total_size_mb': round(total_size / (1024 * 1024), 2),
                    'files': [obj['Key'] for obj in response['Contents']]
                }
            else:
                return {
                    'partition': partition_prefix,
                    'file_count': 0,
                    'total_size_bytes': 0,
                    'total_size_mb': 0,
                    'files': []
                }
                
        except Exception as e:
            logger.error(f"Failed to get partition stats: {e}")
            return {
                'partition': partition_prefix,
                'error': str(e)
            }
