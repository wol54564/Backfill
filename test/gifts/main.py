import asyncio
import pandas as pd
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from json_scraper import GiftsJsonScraper
from s3_helper import R2Helper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GiftsScraperOrchestrator:
    """
    Orchestrates the scraping of gifts data with AWS R2 integration
    Scrapes subcategories: Men Clothes, Men Shoes, Ladies Clothes, Women Accessories, etc.
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
        logger.info(f"Scraping data for date: {self.scrape_date.strftime('%Y-%m-%d')}")
        logger.info(f"Saving to R2 with date: {self.save_date.strftime('%Y-%m-%d')}")
        logger.info("Mode: Scrape ALL available pages (no limit)")
        
    async def initialize(self):
        """Initialize the scraper and R2 client"""
        self.scraper = GiftsJsonScraper()
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
        Scrape a gifts subcategory with listings and detailed information
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
        Scrape all gifts subcategories from the main page
        Automatically discovers and scrapes all available pages
        """
        try:
            logger.info("Fetching gifts subcategories...")
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
        Creates an Excel file named 'gifts' with sheets for each subcategory
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
            logger.info("Creating Excel file 'gifts' with subcategory sheets...")
            
            temp_excel = self.temp_dir / "gifts_temp.xlsx"
            with pd.ExcelWriter(temp_excel, engine='openpyxl') as writer:
                # Create Info sheet with summary
                info_data = [{
                    "Project": "Gifts",
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
                f"excel-files/gifts.xlsx",
                self.save_date,
                retries=3
            )
            
            if R2_excel_path:
                R2_url = self.R2_helper.generate_R2_url(R2_excel_path)
                upload_summary["excel_files"].append({
                    "name": "gifts",
                    "subcategories_count": len(results),
                    "total_listings": total_listings,
                    "R2_path": R2_excel_path,
                    "R2_url": R2_url
                })
                logger.info(f"[OK] Uploaded: gifts.xlsx ({total_listings} listings across {len(results)} subcategories)")
            
            temp_excel.unlink(missing_ok=True)
            
            # Create and upload JSON file
            logger.info("Creating JSON file with summary...")
            json_file = self.temp_dir / "gifts_temp.json"
            
            # Build subcategories summary
            subcategories_summary = []
            for result in results:
                subcat = result["subcategory"]
                subcategories_summary.append({
                    "name_ar": subcat.get("name_ar"),
                    "name_en": subcat.get("name_en"),
                    "slug": subcat.get("slug"),
                    "listings_count": len(result["listings"]),
                    "total_pages_scraped": result["total_pages"]
                })
            
            json_data = {
                "scraped_at": datetime.now().isoformat(),
                "data_scraped_date": self.scrape_date.strftime('%Y-%m-%d'),
                "saved_to_R2_date": self.save_date.strftime('%Y-%m-%d'),
                "total_subcategories": len(results),
                "total_listings": total_listings,
                "subcategories": subcategories_summary
            }
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            # Upload JSON to R2
            R2_json_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(json_file),
                f"json-files/gifts.json",
                self.save_date,
                retries=3
            )
            
            if R2_json_path:
                R2_url = self.R2_helper.generate_R2_url(R2_json_path)
                upload_summary["json_files"].append({
                    "name": "gifts",
                    "total_listings": total_listings,
                    "R2_path": R2_json_path,
                    "R2_url": R2_url
                })
                logger.info(f"[OK] Uploaded: gifts.json ({total_listings} listings)")
            
            json_file.unlink(missing_ok=True)
            
        except Exception as e:
            logger.error(f"Error UPLOADING TO R2: {e}")
        
        return upload_summary
    
    async def run(self) -> Dict:
        """Main orchestration method"""
        try:
            await self.initialize()
            
            logger.info("=" * 80)
            logger.info("GIFTS SCRAPER ORCHESTRATOR")
            logger.info("=" * 80)
            
            # Scrape all subcategories with their listings
            results = await self.scrape_all_subcategories()
            
            if not results:
                logger.error("Failed to scrape any data!")
                return {
                    "status": "failed",
                    "message": "No data scraped"
                }
            
            # Save to R2
            upload_summary = await self.save_all_to_R2(results)
            
            logger.info("\n" + "=" * 80)
            logger.info("SCRAPING COMPLETED")
            logger.info("=" * 80)
            logger.info(json.dumps(upload_summary, indent=2, ensure_ascii=False))
            
            return {
                "status": "success",
                "upload_summary": upload_summary
            }
            
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            return {
                "status": "failed",
                "message": str(e)
            }
        finally:
            await self.cleanup()


async def main():
    """Entry point for the scraper"""
    # Configuration
    BUCKET_NAME = os.environ.get("CF_R2_BUCKET_NAME")
    
    orchestrator = GiftsScraperOrchestrator(
        bucket_name=BUCKET_NAME,
    )
    
    result = await orchestrator.run()
    
    # Return exit code based on status
    exit_code = 0 if result["status"] == "success" else 1
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
