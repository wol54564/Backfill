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
    
    async def scrape_subcategory(self, subcategory: Dict, max_pages: int = 15) -> Dict:
        """Scrape a subcategory with listings and detailed information, handling child categories if present"""
        subcat_slug = subcategory["slug"]
        logger.info(f"\nProcessing: {subcategory['name_ar']}")
        
        result = {
            "subcategory": subcategory,
            "listings_by_category": {},  # Changed to organize by category
            "all_listings": [],
            "has_children": False,
            "total_pages": 0
        }
        
        try:
            # Check for child categories
            child_categories = await self.scraper.get_catchilds(subcat_slug)
            
            if child_categories:
                logger.info(f"Found {len(child_categories)} child categories, scraping each...")
                result["has_children"] = True
                
                for child in child_categories:
                    child_slug = child["slug"]
                    logger.info(f"  Scraping child: {child['name_ar']} ({child_slug})")
                    
                    child_listings = []
                    page_num = 1
                    
                    while page_num <= max_pages:
                        listings = await self.scraper.get_listings(
                            subcat_slug,
                            page_num=page_num,
                            child_slug=child_slug,
                            filter_yesterday=False
                        )
                        
                        if not listings:
                            logger.info(f"  No listings found on page {page_num} for {child['name_ar']}, stopping pagination")
                            break
                        
                        if listings:
                            logger.info(f"  Fetching detailed information for {len(listings)} listings on page {page_num}...")
                            detailed_listings = await self.fetch_listing_details_batch(listings, subcat_slug)
                            child_listings.extend(detailed_listings)
                        
                        page_num += 1
                        await asyncio.sleep(1)  # Rate limiting between pages
                    
                    if child_listings:
                        result["listings_by_category"][child["name_ar"]] = child_listings
                        result["all_listings"].extend(child_listings)
                        logger.info(f"  Found {len(child_listings)} listings for {child['name_ar']}")
                    
                    await asyncio.sleep(1)
            else:
                logger.info(f"No child categories found, scraping main category...")
                
                # Fetch multiple pages for main category
                page_num = 1
                main_listings = []
                while page_num <= max_pages:
                    listings = await self.scraper.get_listings(
                        subcat_slug, 
                        page_num=page_num,
                        filter_yesterday=False
                    )
                    
                    if not listings:
                        logger.info(f"No listings found on page {page_num}, stopping pagination")
                        break
                    
                    if listings:
                        logger.info(f"Fetching detailed information for {len(listings)} listings on page {page_num}...")
                        detailed_listings = await self.fetch_listing_details_batch(listings, subcat_slug)
                        main_listings.extend(detailed_listings)
                    
                    page_num += 1
                    await asyncio.sleep(2)  # Rate limiting between pages
                
                if main_listings:
                    result["listings_by_category"]["Main"] = main_listings
                    result["all_listings"] = main_listings
                
                result["total_pages"] = page_num - 1
            
            logger.info(f"Total listings for {subcategory['name_ar']}: {len(result['all_listings'])}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing {subcategory['name_ar']}: {e}")
            return result
    
    async def scrape_all_subcategories(self, max_pages: int = 15) -> List[Dict]:
        """Scrape all animal subcategories"""
        try:
            logger.info("Fetching all subcategories...")
            subcategories = await self.scraper.get_subcategories()
            
            if not subcategories:
                logger.error("No subcategories found!")
                return []
            
            logger.info(f"Found {len(subcategories)} subcategories")
            
            all_results = []
            for i, subcategory in enumerate(subcategories, 1):
                logger.info(f"[{i}/{len(subcategories)}] Processing...")
                result = await self.scrape_subcategory(subcategory, max_pages=max_pages)
                all_results.append(result)
                
                if i < len(subcategories):
                    await asyncio.sleep(2)
            
            return all_results
            
        except Exception as e:
            logger.error(f"Error scraping subcategories: {e}")
            return []
    
    async def save_all_to_R2(self, results: List[Dict]) -> Dict:
        """Save all data to R2 with proper partitioning"""
        upload_summary = {
            "excel_files": [],
            "json_files": [],
            "total_listings": 0,
            "upload_time": datetime.now().isoformat()
        }
        
        try:
            total_listings = sum(len(r["all_listings"]) for r in results)
            upload_summary["total_listings"] = total_listings
            
            if total_listings == 0:
                logger.warning("No data to upload!")
                return upload_summary
            
            logger.info("\nUploading to AWS R2...")
            
            for result in results:
                try:
                    subcategory = result["subcategory"]
                    slug = subcategory["slug"]
                    listings_count = len(result["all_listings"])
                    
                    if listings_count > 0:
                        logger.info(f"Creating Excel for {subcategory['name_ar']}...")
                        
                        temp_excel = self.temp_dir / f"{slug}_temp.xlsx"
                        with pd.ExcelWriter(temp_excel, engine='openpyxl') as writer:
                            info_data = [{
                                "Category (Arabic)": subcategory["name_ar"],
                                "Category (English)": subcategory["name_en"],
                                "Total Listings": listings_count,
                                "Has Subcategories": result.get("has_children", False),
                                "Subcategories Count": len(result["listings_by_category"]),
                                "Data Scraped Date": self.scrape_date.strftime('%Y-%m-%d'),
                                "Saved to R2 Date": self.save_date.strftime('%Y-%m-%d'),
                            }]
                            pd.DataFrame(info_data).to_excel(writer, sheet_name='Info', index=False)
                            
                            # Create sheets for each category (or Main if no children)
                            for category_name, listings in result["listings_by_category"].items():
                                if listings:
                                    # Sanitize sheet name (max 31 chars)
                                    sheet_name = category_name[:31] if len(category_name) <= 31 else category_name[:28] + "..."
                                    df = pd.DataFrame(listings)
                                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                        
                        R2_excel_path = await asyncio.to_thread(
                            self.R2_helper.upload_file,
                            str(temp_excel),
                            f"excel-files/{slug}.xlsx",
                            self.save_date,
                            retries=3
                        )
                        if R2_excel_path:
                            R2_url = self.R2_helper.generate_R2_url(R2_excel_path)
                            upload_summary["excel_files"].append({
                                "category": subcategory["name_ar"],
                                "slug": slug,
                                "listings": listings_count,
                                "has_subcategories": result.get("has_children", False),
                                "subcategories_count": len(result["listings_by_category"]),
                                "R2_path": R2_excel_path,
                                "R2_url": R2_url
                            })
                            logger.info(f"[OK] Uploaded: {slug}.xlsx ({listings_count} listings)")
                        
                        temp_excel.unlink(missing_ok=True)
                
                except Exception as e:
                    logger.error(f"Error processing {subcategory['name_ar']}: {e}")
                    continue
            
            logger.info("Uploading JSON summary...")
            json_summary = {
                "scraped_at": datetime.now().isoformat(),
                "data_scraped_date": self.scrape_date.strftime('%Y-%m-%d'),
                "saved_to_R2_date": self.save_date.strftime('%Y-%m-%d'),
                "total_subcategories": len(results),
                "total_listings": total_listings,
                "subcategories": []
            }
            
            for result in results:
                if result["all_listings"]:
                    json_summary["subcategories"].append({
                        "name_ar": result["subcategory"]["name_ar"],
                        "name_en": result["subcategory"]["name_en"],
                        "slug": result["subcategory"]["slug"],
                        "listings_count": len(result["all_listings"]),
                        "has_subcategories": result.get("has_children", False),
                        "subcategories": list(result["listings_by_category"].keys()) if result.get("has_children") else []
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
    """Main entry point for the scraper"""
    orchestrator = None
    
    try:
        bucket_name = os.environ.get("CF_R2_BUCKET_NAME", "data-collection-dl")  # Update with your actual bucket name
        profile_name = os.environ.get("AWS_PROFILE", None)
        max_pages = int(os.environ.get("MAX_PAGES", "15"))  # Max pages per category
        
        logger.info("\n" + "="*60)
        logger.info("GIFTS SCRAPER STARTING")
        logger.info("="*60)
        logger.info(f"Bucket: {bucket_name}")
        logger.info(f"Max pages per category: {max_pages}")
        
        orchestrator = GiftsScraperOrchestrator(bucket_name=bucket_name, profile_name=profile_name)
        await orchestrator.initialize()
        
        logger.info("\nStarting scraping...")
        results = await orchestrator.scrape_all_subcategories(max_pages=max_pages)
        
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
                logger.info(f"  - {excel_file['category']}: {excel_file['listings']} listings")
            
        else:
            logger.error("Scraping failed - no results!")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        
    finally:
        if orchestrator:
            await orchestrator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
