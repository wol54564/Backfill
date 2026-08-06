import asyncio
import pandas as pd
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from json_scraper import WantedCarsJsonScraper
from s3_helper import R2Helper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class WantedCarsScraperOrchestrator:
    """
    Orchestrates the scraping of wanted-cars data with AWS R2 integration
    Scrapes subcategories: Wanted American Cars, Wanted European Car, Wanted Asian Cars
    """
    
    def __init__(self, bucket_name: str, profile_name: Optional[str] = None, temp_dir: str = "temp_data"):
        self.scraper = None
        self.R2_helper = None
        self.bucket_name = bucket_name
        self.profile_name = profile_name
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self.scrape_date = datetime.now() - timedelta(days=1)  # Yesterday's data for scraping
        self.save_date = datetime.now()  # Today's date for R2 folder partitioning
        self.start_time = None
        self.requests_total = 0
        self.requests_failed = 0
        logger.info(f"Scraping data for date: {self.scrape_date.strftime('%Y-%m-%d')}")
        logger.info(f"Saving to R2 with date: {self.save_date.strftime('%Y-%m-%d')}")
        logger.info("Mode: Scrape ALL available pages (no limit)")
        
    async def initialize(self):
        """Initialize the scraper and R2 client"""
        self.scraper = WantedCarsJsonScraper()
        # No browser initialization needed with BeautifulSoup
        
        try:
            self.R2_helper = R2Helper(
                bucket_name=self.bucket_name,
                profile_name=self.profile_name
            )
        except Exception as e:
            logger.error(f"Failed to initialize R2: {e}")
            raise
        
    async def cleanup(self):
        """Clean up resources"""
        if self.scraper:
            await self.scraper.close_browser()
        
        try:
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Error cleaning up temp directory: {e}")
    
    async def fetch_listing_details_batch(self, listings: List[Dict], subcategory_slug: str) -> List[Dict]:
        """
        Fetch detailed information for each listing from the listings page and download images
        
        Args:
            listings: List of basic listing info from listings page
            subcategory_slug: Category slug for organizing images
        
        Returns:
            List of detailed listing information with R2 image URLs
        """
        detailed_listings = []
        
        for listing in listings:
            try:
                slug = listing.get("slug")
                status = listing.get("status")
                
                if not slug:
                    logger.warning("Listing without slug, skipping...")
                    continue
                
                logger.info(f"Fetching details for {slug}...")
                
                details = await self.scraper.get_listing_details(slug, status=status)
                
                if details:
                    # Download and upload images if available
                    images = details.get("images", [])
                    listing_id = details.get("id")
                    
                    if images:
                        logger.info(f"Processing {len(images)} images for {slug} (ID: {listing_id})...")
                        R2_image_urls = []
                        
                        for img_index, image_url in enumerate(images):
                            try:
                                image_data = await self.scraper.download_image(image_url)
                                if image_data:
                                    R2_path = await asyncio.to_thread(
                                        self.R2_helper.upload_image,
                                        image_url,
                                        image_data,
                                        subcategory_slug,
                                        self.save_date,
                                        listing_id,
                                        img_index
                                    )
                                    if R2_path:
                                        R2_url = self.R2_helper.generate_R2_url(R2_path)
                                        R2_image_urls.append(R2_url)
                                        logger.info(f"  Image {img_index}: {listing_id}_{img_index}.jpg [OK]")
                                
                                await asyncio.sleep(0.1)
                            except Exception as e:
                                logger.warning(f"Failed to download/upload image {image_url}: {e}")
                                continue
                        
                        # Add R2 image URLs to details
                        details["r2_images"] = R2_image_urls
                        logger.info(f"Successfully uploaded {len(R2_image_urls)} images")
                    
                    detailed_listings.append(details)
                    logger.debug(f"[OK] Retrieved details for {slug}")
                else:
                    logger.warning(f"Failed to get details for {slug}")
                
                await asyncio.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error fetching details for listing: {e}")
                continue
        
        logger.info(f"Successfully fetched {len(detailed_listings)}/{len(listings)} detailed listings")
        return detailed_listings
    
    async def scrape_subcategory(self, subcategory: Dict) -> Dict:
        """
        Scrape a wanted-cars subcategory with listings and detailed information
        Automatically scrapes all available pages returned by the API
        
        Args:
            subcategory: Subcategory dictionary with slug, name_ar, name_en, etc.
            
        Returns:
            Dictionary with scraped data organized by subcategory
        """
        subcat_slug = subcategory["slug"]
        logger.info(f"\nProcessing: {subcategory['name_ar']}")
        
        result = {
            "subcategory": subcategory,
            "listings": [],
            "total_pages": 0
        }
        
        try:
            # Fetch all pages for this subcategory
            page_num = 1
            subcat_listings = []
            total_pages = 0
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            while True:
                listings, total_pages = await self.scraper.get_listings(
                    subcat_slug, 
                    page_num=page_num,
                    filter_yesterday=False
                )
                
                if not listings:
                    logger.info(f"No listings found on page {page_num}, stopping pagination")
                    break
                
                yesterday_listings = [l for l in listings if l.get("date_published", "").startswith(yesterday)]
                found_older = any(l.get("date_published", "")[:10] < yesterday for l in listings if l.get("date_published", ""))
                
                if yesterday_listings:
                    logger.info(f"Fetching detailed information for {len(yesterday_listings)} listings on page {page_num}/{total_pages}...")
                    detailed_listings = await self.fetch_listing_details_batch(yesterday_listings, subcat_slug)
                    subcat_listings.extend(detailed_listings)
                
                if found_older or page_num >= total_pages:
                    break
                
                page_num += 1
                await asyncio.sleep(1)  # Rate limiting between pages
            
            result["listings"] = subcat_listings
            result["total_pages"] = total_pages
            
            logger.info(f"Total listings for {subcategory['name_ar']}: {len(subcat_listings)} (across {page_num - 1} pages)")
            return result
            
        except Exception as e:
            logger.error(f"Error processing {subcategory['name_ar']}: {e}")
            return result
    
    async def scrape_all_subcategories(self) -> List[Dict]:
        """
        Scrape all wanted-cars subcategories from the main page
        Automatically discovers and scrapes all available pages: Wanted American Cars, Wanted European Car, Wanted Asian Cars
        """
        try:
            logger.info("Fetching wanted-cars subcategories...")
            subcategories = await self.scraper.get_subcategories()
            
            if not subcategories:
                logger.error("No subcategories found!")
                return []
            
            logger.info(f"Found {len(subcategories)} subcategories")
            
            all_results = []
            for i, subcat in enumerate(subcategories, 1):
                logger.info(f"\n[{i}/{len(subcategories)}] Processing: {subcat['name_ar']} ({subcat['slug']})")
                
                result = await self.scrape_subcategory(subcat)
                all_results.append(result)
                
                if len(subcategories) > i:
                    await asyncio.sleep(2)  # Rate limiting between subcategories
            
            return all_results
            
        except Exception as e:
            logger.error(f"Error scraping subcategories: {e}")
            return []
    
    async def save_all_to_R2(self, results: List[Dict]) -> Dict:
        """
        Save all data to R2 with proper partitioning
        Creates an Excel file named 'wanted-cars' with sheets for each subcategory
        """
        upload_summary = {
            "excel_files": [],
            "json_files": [],
            "total_listings": 0,
            "upload_time": datetime.now().isoformat()
        }
        
        try:
            total_listings = sum(len(r["listings"]) for r in results)
            upload_summary["total_listings"] = total_listings
            
            if total_listings == 0:
                logger.warning("No data to upload!")
                return upload_summary
            
            logger.info("\nUploading to AWS R2...")
            
            # Create single Excel file with sheets for each subcategory
            logger.info("Creating Excel file 'wanted-cars' with subcategory sheets...")
            
            temp_excel = self.temp_dir / "wanted-cars_temp.xlsx"
            with pd.ExcelWriter(temp_excel, engine='openpyxl') as writer:
                # Create Info sheet with summary
                info_data = [{
                    "Project": "Wanted Cars",
                    "Total Subcategories": len(results),
                    "Total Listings": total_listings,
                    "Data Scraped Date": self.scrape_date.strftime('%Y-%m-%d'),
                    "Saved to R2 Date": self.save_date.strftime('%Y-%m-%d'),
                }]
                pd.DataFrame(info_data).to_excel(writer, sheet_name='Info', index=False)
                
                # Create a sheet for each subcategory
                for result in results:
                    if result["listings"]:
                        subcategory = result["subcategory"]
                        # Sanitize sheet name (max 31 chars in Excel)
                        sheet_name = subcategory["name_ar"][:31] if len(subcategory["name_ar"]) <= 31 else subcategory["name_ar"][:28] + "..."
                        
                        df = pd.DataFrame(result["listings"])
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        logger.info(f"  Created sheet: {sheet_name} ({len(result['listings'])} listings)")
            
            # Upload excel to R2
            R2_excel_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(temp_excel),
                f"excel-files/wanted-cars.xlsx",
                self.save_date,
                retries=3
            )
            
            if R2_excel_path:
                R2_url = self.R2_helper.generate_R2_url(R2_excel_path)
                upload_summary["excel_files"].append({
                    "name": "wanted-cars",
                    "subcategories_count": len(results),
                    "total_listings": total_listings,
                    "R2_path": R2_excel_path,
                    "R2_url": R2_url
                })
                logger.info(f"[OK] Uploaded: wanted-cars.xlsx ({total_listings} listings across {len(results)} subcategories)")

            json_version_payload = [
                {
                    "subcategory": result["subcategory"],
                    "listings": result["listings"],
                }
                for result in results
                if result["listings"]
            ]
            json_version_file = self.temp_dir / "wanted-cars_json_version_temp.json"
            with open(json_version_file, 'w', encoding='utf-8') as jf:
                json.dump(json_version_payload, jf, ensure_ascii=False, indent=2)

            R2_json_version_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(json_version_file),
                f"json version/wanted-cars.json",
                self.save_date,
                retries=3
            )
            if R2_json_version_path:
                upload_summary["json_files"].append(R2_json_version_path)
                logger.info("[OK] Uploaded JSON version: wanted-cars.json")
            json_version_file.unlink(missing_ok=True)
            
            temp_excel.unlink(missing_ok=True)
            
            # Upload JSON summary
            logger.info("Uploading JSON summary...")
            duration_sec = time.time() - self.start_time if self.start_time else 0
            session_requests_total = int(getattr(getattr(self.scraper, "session", None), "request_count", 0) or 0)
            effective_requests_total = max(getattr(self, "requests_total", 0), session_requests_total)
            effective_requests_failed = getattr(self, "requests_failed", 0)
            error_rate_pct = (effective_requests_failed / effective_requests_total * 100.0) if effective_requests_total > 0 else 0.0
            requests_per_min = (effective_requests_total / (duration_sec / 60.0)) if duration_sec > 0 else 0.0
            json_summary = {
                "scraped_at": datetime.now().isoformat(),
                "data_scraped_date": self.scrape_date.strftime('%Y-%m-%d'),
                "saved_to_R2_date": self.save_date.strftime('%Y-%m-%d'),
                "total_subcategories": len(results),
                "total_listings": total_listings,
                "subcategories": [],
                "request_metrics": {
                    "requests_total": effective_requests_total,
                    "requests_failed": effective_requests_failed,
                    "error_rate_pct": round(error_rate_pct, 2),
                    "requests_per_min": round(requests_per_min, 2),
                    "duration_sec": round(duration_sec, 2),
                },
            }
            
            for result in results:
                if result["listings"]:
                    subcategory = result["subcategory"]
                    json_summary["subcategories"].append({
                        "name_ar": subcategory["name_ar"],
                        "name_en": subcategory["name_en"],
                        "slug": subcategory["slug"],
                        "listings_count": len(result["listings"]),
                        "total_pages_scraped": result.get("total_pages", 0),
                    })
            
            temp_json = self.temp_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(temp_json, 'w', encoding='utf-8') as f:
                json.dump(json_summary, f, ensure_ascii=False, indent=2)
            
            R2_json_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(temp_json),
                f"json-files/summary_{self.save_date.strftime('%Y%m%d')}.json",
                self.save_date
            )
            
            if R2_json_path:
                upload_summary["json_files"].append(R2_json_path)
                logger.info(f"[OK] Uploaded JSON summary")
            
            temp_json.unlink(missing_ok=True)
            
        except Exception as e:
            logger.error(f"Error in R2 upload: {e}")
        
        return upload_summary


async def main():
    """Main entry point for the wanted-cars scraper"""
    orchestrator = None
    
    try:
        bucket_name = os.environ.get("CF_R2_BUCKET_NAME")
        profile_name = os.environ.get("AWS_PROFILE", None)
        
        logger.info("\n" + "="*60)
        logger.info("WANTED CARS SCRAPER STARTING")
        logger.info("="*60)
        logger.info(f"Bucket: {bucket_name}")
        logger.info(f"Mode: Scrape ALL available pages per subcategory")
        
        orchestrator = WantedCarsScraperOrchestrator(bucket_name=bucket_name, profile_name=profile_name)
        await orchestrator.initialize()
        orchestrator.start_time = time.time()
        
        logger.info("\nStarting scraping...")
        results = await orchestrator.scrape_all_subcategories()
        
        if results:
            logger.info("\n" + "="*60)
            logger.info("UPLOADING TO R2")
            logger.info("="*60)
            
            upload_summary = await orchestrator.save_all_to_R2(results)
            
            logger.info("\n" + "="*60)
            logger.info("SCRAPING COMPLETED")
            logger.info("="*60)
            logger.info(f"Excel files uploaded: {len(upload_summary['excel_files'])}")
            logger.info(f"Total listings: {upload_summary['total_listings']}")
            
            for excel_file in upload_summary['excel_files']:
                logger.info(f"  - {excel_file['name']}: {excel_file['total_listings']} listings")
            
        else:
            logger.error("Scraping failed - no results!")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        
    finally:
        if orchestrator:
            await orchestrator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())


