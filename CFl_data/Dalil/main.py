import asyncio
import pandas as pd
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from json_scraper import DalilJsonScraper
from s3_helper import R2Helper
import re
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DalilScraperOrchestrator:
    """
    Orchestrates the scraping of Dalil directory data with AWS R2 integration
    Creates Excel file with multiple sheets (one per category)
    Downloads and uploads images to R2
    """
    
    def __init__(self, bucket_name: str, profile_name: Optional[str] = None, temp_dir: str = "temp_data"):
        self.scraper = None
        self.R2_helper = None
        self.bucket_name = bucket_name
        self.profile_name = profile_name
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self.save_date = datetime.now()
        self.start_time = None
        self.requests_total = 0
        self.requests_failed = 0
        logger.info(f"Saving to R2 with date: {self.save_date.strftime('%Y-%m-%d')}")
        
    async def initialize(self):
        """Initialize the scraper and R2 client"""
        self.scraper = DalilJsonScraper()
        await self.scraper.init_browser()
        
        try:
            self.R2_helper = R2Helper(
                bucket_name=self.bucket_name,
                profile_name=self.profile_name
            )
        except Exception as e:
            logger.error(f"Failed to initialize R2: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.scraper:
            await self.scraper.close_browser()
        
        # Clean up temp directory
        try:
            for file in self.temp_dir.iterdir():
                if file.is_file():
                    file.unlink()
        except Exception as e:
            logger.warning(f"Error cleaning temp directory: {e}")
    
    def generate_filename_from_url(self, url: str, business_id: str, index: int = 0) -> str:
        """
        Generate a safe filename from an image URL
        
        Args:
            url: Image URL
            business_id: Business ID
            index: Image index
        
        Returns:
            Safe filename
        """
        # Extract extension from URL
        parsed = urlparse(url)
        path = parsed.path
        ext = Path(path).suffix
        
        if not ext or len(ext) > 5:
            ext = '.jpg'  # Default extension
        
        # Clean extension
        ext = ext.lower()
        
        # Create filename
        filename = f"business_{business_id}_image_{index}{ext}"
        
        return filename
    
    async def download_and_upload_images(self, businesses: List[Dict], category_slug: str) -> None:
        """
        Download images for all businesses and Upload to R2
        Updates businesses list with R2 image paths
        
        Args:
            businesses: List of business dictionaries
            category_slug: Category slug for organizing images
        """
        logger.info(f"Processing images for {len(businesses)} businesses in {category_slug}...")
        
        tasks = []
        image_mapping = []  # (business_index, image_urls, business_id)
        
        for idx, business in enumerate(businesses):
            business_id = business.get("id", f"unknown_{idx}")
            
            # Collect all image URLs
            image_urls = []
            
            # Logo
            if business.get("logo"):
                image_urls.append(("logo", business["logo"]))
            
            # Cover image
            if business.get("cover_image") and business.get("cover_image") != "media":
                image_urls.append(("cover", business["cover_image"]))
            
            # Media URLs (gallery and menu)
            media_urls_str = business.get("media_urls", "")
            if media_urls_str:
                media_urls = [url.strip() for url in media_urls_str.split("|") if url.strip()]
                for i, url in enumerate(media_urls):
                    image_urls.append((f"media_{i}", url))
            
            if image_urls:
                image_mapping.append((idx, image_urls, business_id))
        
        # Process images in batches to avoid overwhelming the system
        batch_size = 10
        for i in range(0, len(image_mapping), batch_size):
            batch = image_mapping[i:i+batch_size]
            batch_tasks = []
            
            for business_idx, image_urls, business_id in batch:
                for img_type, img_url in image_urls:
                    # Generate R2 path
                    image_filename = self.generate_filename_from_url(
                        img_url, 
                        str(business_id), 
                        hash(img_url) % 10000
                    )
                    R2_path = f"images/{category_slug}/{image_filename}"
                    
                    # Create task
                    task = self.R2_helper.download_and_upload_image(
                        img_url,
                        R2_path,
                        self.save_date
                    )
                    batch_tasks.append((business_idx, img_type, img_url, R2_path, task))
            
            # Execute batch
            if batch_tasks:
                results = await asyncio.gather(
                    *[task for _, _, _, _, task in batch_tasks],
                    return_exceptions=True
                )
                
                # Process results
                for (business_idx, img_type, img_url, R2_path, _), result in zip(batch_tasks, results):
                    if isinstance(result, str):  # Success - got R2 key
                        # Add to business's r2_images_paths
                        if "r2_images_paths" not in businesses[business_idx]:
                            businesses[business_idx]["r2_images_paths"] = []
                        
                        businesses[business_idx]["r2_images_paths"].append({
                            "type": img_type,
                            "original_url": img_url,
                            "R2_path": result,
                            "R2_url": self.R2_helper.generate_R2_url(result)
                        })
                    elif isinstance(result, Exception):
                        logger.warning(f"Failed to upload image {img_url}: {result}")
                
                # Small delay between batches
                await asyncio.sleep(0.5)
        
        # Format r2_images_paths as a JSON string for each business
        for business in businesses:
            if "r2_images_paths" in business:
                business["r2_images_paths_json"] = json.dumps(
                    business["r2_images_paths"], 
                    ensure_ascii=False
                )
                # Create a simple string list of R2 paths for easy viewing
                business["r2_images_paths"] = " | ".join([
                    img["R2_url"] for img in business["r2_images_paths"]
                ])
            else:
                business["r2_images_paths"] = ""
                business["r2_images_paths_json"] = "[]"
        
        logger.info(f"[OK] Completed image processing for {category_slug}")
    
    def create_excel_with_sheets(self, categories_data: List[Dict]) -> Path:
        """
        Create an Excel file with multiple sheets (one per category)
        
        Args:
            categories_data: List of category data dictionaries
        
        Returns:
            Path to created Excel file
        """
        timestamp = self.save_date.strftime('%Y%m%d_%H%M%S')
        excel_file = self.temp_dir / f"dalil_directory_{timestamp}.xlsx"
        
        logger.info(f"Creating Excel file with {len(categories_data)} sheets...")
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            for category_data in categories_data:
                category_slug = category_data.get("category_slug", "unknown")
                category_name = category_data.get("category_name", category_slug)
                businesses = category_data.get("businesses", [])
                
                if not businesses:
                    logger.warning(f"No businesses for category: {category_slug}")
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(businesses)
                
                # Reorder columns for better readability
                desired_columns = [
                    "id", "name", "slug", "category_name", "category_slug",
                    "rating_average", "rating_count", "reviews_count",
                    "logo", "cover_image", "about",
                    "contact_numbers", "website", "social_media",
                    "main_branch_address", "main_branch_phone",
                    "main_branch_latitude", "main_branch_longitude",
                    "branches_count", "branches_json",
                    "working_hours",
                    "delivery", "takeaway", "dine_in", "parking", "wifi", "wheelchair_accessible",
                    "media_count", "media_urls", "gallery_urls", "menu_urls",
                    "r2_images_paths", "r2_images_paths_json",
                    "recent_reviews_json",
                    "view_count", "status",
                    "created_at", "updated_at"
                ]
                
                # Only include columns that exist
                columns = [col for col in desired_columns if col in df.columns]
                df = df[columns]
                
                # Use category slug as sheet name (truncate if too long for Excel)
                sheet_name = category_slug[:31] if len(category_slug) > 31 else category_slug
                
                # Write to sheet
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                logger.info(f"  [OK] Sheet '{sheet_name}': {len(df)} businesses")
        
        logger.info(f"Excel file created: {excel_file}")
        return excel_file
    
    async def scrape_all_categories(self) -> List[Dict]:
        """
        Scrape all Dalil categories
        
        Returns:
            List of category data dictionaries
        """
        logger.info("\n" + "="*80)
        logger.info("STARTING DALIL SCRAPING")
        logger.info("="*80 + "\n")
        
        results = await self.scraper.scrape_all_categories()
        
        return results
    
    async def save_to_R2(self, categories_data: List[Dict]) -> Dict:
        """
        Save all data to R2
        - Creates Excel file with multiple sheets
        - Downloads and uploads images
        - Uploads Excel and JSON summary
        
        Args:
            categories_data: List of category data dictionaries
        
        Returns:
            Upload summary dictionary
        """
        upload_summary = {
            "excel_file": None,
            "json_summary": None,
            "total_categories": len(categories_data),
            "total_businesses": 0,
            "total_images": 0,
        }
        
        try:
            # Download and upload images for each category
            logger.info("\n" + "="*80)
            logger.info("DOWNLOADING AND UPLOADING IMAGES")
            logger.info("="*80 + "\n")
            
            for category_data in categories_data:
                if category_data.get("businesses"):
                    await self.download_and_upload_images(
                        category_data["businesses"],
                        category_data["category_slug"]
                    )
                    
                    # Count images
                    for business in category_data["businesses"]:
                        if business.get("r2_images_paths_json"):
                            try:
                                images = json.loads(business["r2_images_paths_json"])
                                upload_summary["total_images"] += len(images)
                            except:
                                pass
            
            # Create Excel file
            logger.info("\n" + "="*80)
            logger.info("CREATING EXCEL FILE")
            logger.info("="*80 + "\n")
            
            excel_file = self.create_excel_with_sheets(categories_data)
            
            # Upload excel to R2
            logger.info("\n" + "="*80)
            logger.info("UPLOADING TO R2")
            logger.info("="*80 + "\n")
            
            R2_excel_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(excel_file),
                f"dalil_directory_{self.save_date.strftime('%Y%m%d')}.xlsx",
                self.save_date
            )
            
            if R2_excel_path:
                upload_summary["excel_file"] = {
                    "R2_path": R2_excel_path,
                    "R2_url": self.R2_helper.generate_R2_url(R2_excel_path)
                }
                logger.info(f"[OK] Uploaded Excel file: {R2_excel_path}")

            temp_json_version = self.temp_dir / "dalil_directory_json_version.json"
            with open(temp_json_version, 'w', encoding='utf-8') as jf:
                json.dump(categories_data, jf, ensure_ascii=False, indent=2)
            R2_json_version_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(temp_json_version),
                "json version/dalil_directory.json",
                self.save_date
            )
            if R2_json_version_path:
                upload_summary["json_version"] = {
                    "R2_path": R2_json_version_path,
                    "R2_url": self.R2_helper.generate_R2_url(R2_json_version_path)
                }
                logger.info(f"[OK] Uploaded JSON version: {R2_json_version_path}")
            temp_json_version.unlink(missing_ok=True)
            
            excel_file.unlink(missing_ok=True)
            
            # Create and upload JSON summary
            total_businesses = sum(len(cat.get("businesses", [])) for cat in categories_data)
            upload_summary["total_businesses"] = total_businesses
            
            duration_sec = time.time() - self.start_time if self.start_time else 0
            session_requests_total = int(getattr(getattr(self.scraper, "session", None), "request_count", 0) or 0)
            effective_requests_total = max(getattr(self, "requests_total", 0), session_requests_total)
            effective_requests_failed = getattr(self, "requests_failed", 0)
            error_rate_pct = (effective_requests_failed / effective_requests_total * 100.0) if effective_requests_total > 0 else 0.0
            requests_per_min = (effective_requests_total / (duration_sec / 60.0)) if duration_sec > 0 else 0.0
            json_summary = {
                "scraped_at": datetime.now().isoformat(),
                "saved_to_R2_date": self.save_date.strftime('%Y-%m-%d'),
                "total_categories": len(categories_data),
                "total_businesses": total_businesses,
                "total_images": upload_summary["total_images"],
                "categories": [],
                "request_metrics": {
                    "requests_total": effective_requests_total,
                    "requests_failed": effective_requests_failed,
                    "error_rate_pct": round(error_rate_pct, 2),
                    "requests_per_min": round(requests_per_min, 2),
                    "duration_sec": round(duration_sec, 2),
                },
            }
            
            for category_data in categories_data:
                if category_data.get("businesses"):
                    json_summary["categories"].append({
                        "slug": category_data["category_slug"],
                        "name": category_data.get("category_name", ""),
                        "total_businesses": len(category_data["businesses"]),
                    })
            
            temp_json = self.temp_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(temp_json, 'w', encoding='utf-8') as f:
                json.dump(json_summary, f, ensure_ascii=False, indent=2)
            
            R2_json_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(temp_json),
                f"dalil_summary_{self.save_date.strftime('%Y%m%d')}.json",
                self.save_date
            )
            
            if R2_json_path:
                upload_summary["json_summary"] = {
                    "R2_path": R2_json_path,
                    "R2_url": self.R2_helper.generate_R2_url(R2_json_path)
                }
                logger.info(f"[OK] Uploaded JSON summary: {R2_json_path}")
            
            temp_json.unlink(missing_ok=True)
            
        except Exception as e:
            logger.error(f"Error in R2 save: {e}", exc_info=True)
        
        return upload_summary


async def main():
    """Main entry point for the Dalil scraper"""
    orchestrator = None
    
    try:
        bucket_name = os.environ.get("CF_R2_BUCKET_NAME")
        profile_name = os.environ.get("AWS_PROFILE", None)
        
        logger.info("\n" + "="*80)
        logger.info("DALIL DIRECTORY SCRAPER STARTING")
        logger.info("="*80)
        logger.info(f"Bucket: {bucket_name}")
        logger.info(f"Categories: 16 (restaurants, healthcare, beauty, etc.)")
        
        orchestrator = DalilScraperOrchestrator(bucket_name=bucket_name, profile_name=profile_name)
        await orchestrator.initialize()
        orchestrator.start_time = time.time()
        
        # Scrape all categories
        categories_data = await orchestrator.scrape_all_categories()
        
        if categories_data:
            # Save to R2
            upload_summary = await orchestrator.save_to_R2(categories_data)
            
            # Print summary
            logger.info("\n" + "="*80)
            logger.info("SCRAPING COMPLETED SUCCESSFULLY")
            logger.info("="*80)
            logger.info(f"Total categories: {upload_summary['total_categories']}")
            logger.info(f"Total businesses: {upload_summary['total_businesses']}")
            logger.info(f"Total images: {upload_summary['total_images']}")
            
            if upload_summary.get("excel_file"):
                logger.info(f"\nExcel file: {upload_summary['excel_file']['R2_url']}")
            
            if upload_summary.get("json_summary"):
                logger.info(f"JSON summary: {upload_summary['json_summary']['R2_url']}")
            
        else:
            logger.error("Scraping failed - no data!")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        
    finally:
        if orchestrator:
            await orchestrator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())


