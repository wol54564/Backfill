"""
Download gifts data from Cloudflare R2 to local directory
"""
import asyncio
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s3_helper import R2Helper
from scraper_utils import random_delay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class R2DataDownloader:
    """
    Download gifts data from Cloudflare R2 to local directory
    """
    
    def __init__(self, bucket_name: str, download_dir: str = "downloaded_data"):
        self.bucket_name = bucket_name
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.R2_helper = None
        logger.info(f"Download directory: {self.download_dir.absolute()}")
        
    async def initialize(self):
        """Initialize R2 client"""
        try:
            self.R2_helper = R2Helper(bucket_name=self.bucket_name)
            logger.info("Successfully initialized R2 client")
        except Exception as e:
            logger.error(f"Failed to initialize R2 client: {e}")
            raise
    
    def list_available_dates(self, prefix: str = "4sale-data/gifts") -> List[dict]:
        """
        List all available date partitions in R2
        
        Returns:
            List of dicts with year, month, day info
        """
        try:
            # List all objects with the prefix
            response = self.R2_helper.R2_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter="/"
            )
            
            available_dates = []
            
            if 'CommonPrefixes' in response:
                for year_prefix in response['CommonPrefixes']:
                    year_path = year_prefix['Prefix']
                    # Extract year
                    year = year_path.split('=')[-1].rstrip('/')
                    
                    # List months
                    months_response = self.R2_helper.R2_client.list_objects_v2(
                        Bucket=self.bucket_name,
                        Prefix=year_path,
                        Delimiter="/"
                    )
                    
                    if 'CommonPrefixes' in months_response:
                        for month_prefix in months_response['CommonPrefixes']:
                            month_path = month_prefix['Prefix']
                            month = month_path.split('=')[-1].rstrip('/')
                            
                            # List days
                            days_response = self.R2_helper.R2_client.list_objects_v2(
                                Bucket=self.bucket_name,
                                Prefix=month_path,
                                Delimiter="/"
                            )
                            
                            if 'CommonPrefixes' in days_response:
                                for day_prefix in days_response['CommonPrefixes']:
                                    day_path = day_prefix['Prefix']
                                    day = day_path.split('=')[-1].rstrip('/')
                                    
                                    available_dates.append({
                                        'year': year,
                                        'month': month,
                                        'day': day,
                                        'path': day_path
                                    })
            
            available_dates.sort(key=lambda x: (x['year'], x['month'], x['day']), reverse=True)
            return available_dates
            
        except Exception as e:
            logger.error(f"Error listing available dates: {e}")
            return []
    
    def download_files_from_partition(self, partition_path: str, local_subdir: str = "") -> int:
        """
        Download all files from a specific partition
        
        Args:
            partition_path: R2 partition path (e.g., "4sale-data/gifts/year=2024/month=12/day=15")
            local_subdir: Subdirectory name for organization
        
        Returns:
            Number of files downloaded
        """
        try:
            # List all files in partition
            response = self.R2_helper.R2_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=partition_path
            )
            
            if 'Contents' not in response:
                logger.warning(f"No files found in partition: {partition_path}")
                return 0
            
            files = response['Contents']
            downloaded_count = 0
            
            # Create local directory structure
            if local_subdir:
                local_dir = self.download_dir / local_subdir
            else:
                local_dir = self.download_dir
            
            local_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Downloading {len(files)} files from {partition_path}...")
            
            for obj in files:
                key = obj['Key']
                
                # Skip if it's a directory marker
                if key.endswith('/'):
                    continue
                
                # Extract filename from key
                filename = key.split('/')[-1]
                local_file = local_dir / filename
                
                try:
                    logger.info(f"Downloading: {filename}...")
                    response = self.R2_helper.R2_client.get_object(
                        Bucket=self.bucket_name,
                        Key=key
                    )
                    
                    with open(local_file, 'wb') as f:
                        f.write(response['Body'].read())
                    
                    logger.info(f"✓ Downloaded: {local_file}")
                    downloaded_count += 1
                    
                    # Rate limiting
                    random_delay(0.5, 1.5)
                    
                except Exception as e:
                    logger.error(f"Error downloading {filename}: {e}")
            
            return downloaded_count
            
        except Exception as e:
            logger.error(f"Error downloading from partition: {e}")
            return 0
    
    async def download_latest_data(self, num_days: int = 1) -> bool:
        """
        Download latest N days of data
        
        Args:
            num_days: Number of latest days to download (default 1 = yesterday)
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"Fetching latest {num_days} day(s) of data...")
            
            # List available dates
            available_dates = self.list_available_dates()
            
            if not available_dates:
                logger.warning("No data found in R2")
                return False
            
            logger.info(f"Found {len(available_dates)} available date(s)")
            
            # Download latest N days
            total_downloaded = 0
            for i, date_info in enumerate(available_dates[:num_days]):
                date_str = f"{date_info['year']}-{date_info['month']}-{date_info['day']}"
                local_subdir = f"{date_info['year']}/{date_info['month']}/{date_info['day']}"
                
                logger.info(f"\n[{i+1}/{min(num_days, len(available_dates))}] Downloading data for {date_str}...")
                count = self.download_files_from_partition(date_info['path'], local_subdir)
                total_downloaded += count
                
                await asyncio.sleep(1)  # Rate limiting between partitions
            
            logger.info(f"\n{'='*50}")
            logger.info(f"Total files downloaded: {total_downloaded}")
            logger.info(f"Download location: {self.download_dir.absolute()}")
            logger.info(f"{'='*50}")
            
            return total_downloaded > 0
            
        except Exception as e:
            logger.error(f"Error downloading latest data: {e}")
            return False
    
    async def download_by_date_range(self, start_date: str, end_date: str) -> bool:
        """
        Download data for a specific date range
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"Downloading data from {start_date} to {end_date}...")
            
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            
            # List available dates
            available_dates = self.list_available_dates()
            
            if not available_dates:
                logger.warning("No data found in R2")
                return False
            
            # Filter dates in range
            matching_dates = []
            for date_info in available_dates:
                date_obj = datetime(
                    int(date_info['year']),
                    int(date_info['month']),
                    int(date_info['day'])
                )
                
                if start <= date_obj <= end:
                    matching_dates.append(date_info)
            
            if not matching_dates:
                logger.warning(f"No data found for date range {start_date} to {end_date}")
                return False
            
            logger.info(f"Found {len(matching_dates)} date(s) in range")
            
            # Download all matching dates
            total_downloaded = 0
            for i, date_info in enumerate(matching_dates):
                date_str = f"{date_info['year']}-{date_info['month']}-{date_info['day']}"
                local_subdir = f"{date_info['year']}/{date_info['month']}/{date_info['day']}"
                
                logger.info(f"\n[{i+1}/{len(matching_dates)}] Downloading data for {date_str}...")
                count = self.download_files_from_partition(date_info['path'], local_subdir)
                total_downloaded += count
                
                await asyncio.sleep(1)
            
            logger.info(f"\n{'='*50}")
            logger.info(f"Total files downloaded: {total_downloaded}")
            logger.info(f"Download location: {self.download_dir.absolute()}")
            logger.info(f"{'='*50}")
            
            return total_downloaded > 0
            
        except Exception as e:
            logger.error(f"Error downloading by date range: {e}")
            return False


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Download gifts data from Cloudflare R2")
    parser.add_argument(
        "--bucket",
        required=False,
        default=os.getenv("R2_BUCKET_NAME", "4sale"),
        help="R2 bucket name (default: from R2_BUCKET_NAME env var or '4sale')"
    )
    parser.add_argument(
        "--output",
        default="downloaded_data",
        help="Local output directory (default: downloaded_data)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of latest days to download (default: 1)"
    )
    parser.add_argument(
        "--start-date",
        help="Start date for range download (YYYY-MM-DD), overrides --days"
    )
    parser.add_argument(
        "--end-date",
        help="End date for range download (YYYY-MM-DD), required with --start-date"
    )
    parser.add_argument(
        "--list-dates",
        action="store_true",
        help="List available dates and exit"
    )
    
    args = parser.parse_args()
    
    # Initialize downloader
    downloader = R2DataDownloader(
        bucket_name=args.bucket,
        download_dir=args.output
    )
    
    await downloader.initialize()
    
    # List available dates if requested
    if args.list_dates:
        logger.info("Available dates in R2:")
        available_dates = downloader.list_available_dates()
        if available_dates:
            for date_info in available_dates[:10]:  # Show first 10
                date_str = f"{date_info['year']}-{date_info['month']}-{date_info['day']}"
                logger.info(f"  - {date_str}")
            if len(available_dates) > 10:
                logger.info(f"  ... and {len(available_dates) - 10} more")
        else:
            logger.info("  No dates found")
        return
    
    # Download by date range or latest days
    if args.start_date and args.end_date:
        success = await downloader.download_by_date_range(args.start_date, args.end_date)
    else:
        success = await downloader.download_latest_data(args.days)
    
    if not success:
        logger.error("Download failed!")
        exit(1)
    
    logger.info("Download completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
