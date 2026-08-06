import asyncio
import pandas as pd
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from json_scraper import BikesJsonScraper
from s3_helper import R2Helper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BikesScraperOrchestrator:
    """
    Orchestrates the scraping of bikes data with AWS R2 integration
    
    Key features:
    - Scrapes main subcategories: motorbikes-sport, quad-bikes, bicycles, scooter, wanted-bikes
    - Handles two cases:
      1. Subcategories with catChilds (e.g., motorbikes-sport -> BMW, Honda)
      2. Direct listings (e.g., bicycles -> direct listing page)
    - Each main subcategory gets its own Excel file
    - If subcategory has catChilds, each catChild becomes a separate sheet
    - Saves to R2 in bikes folder
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
        self.scraper = BikesJsonScraper()
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
    
    async def fetch_listing_details_batch(self, listings: List[Dict], category_slug: str, main_subcategory: str = None) -> List[Dict]:
        """
        Fetch detailed information for each listing from the listings page and download images
        
        Args:
            listings: List of basic listing info from listings page
            category_slug: Category slug for organizing images
            main_subcategory: Main subcategory folder name (e.g., 'motorbikes-sport')
        
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
                                        category_slug,
                                        self.save_date,
                                        listing_id,
                                        img_index,
                                        main_subcategory
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
    
    async def scrape_category_listings(self, slug_url: str, category_name: str, main_subcategory: str = None) -> Dict:
        """
        Scrape all listings for a category (catChild or direct subcategory)
        Automatically scrapes all available pages
        
        Args:
            slug_url: Full slug URL for the category
            category_name: Human-readable name for logging
            main_subcategory: Main subcategory folder name (e.g., 'motorbikes-sport')
            
        Returns:
            Dictionary with listings and metadata
        """
        logger.info(f"\nFetching listings for: {category_name}")
        
        result = {
            "category_name": category_name,
            "listings": [],
            "total_pages": 0
        }
        
        try:
            page_num = 1
            all_listings = []
            total_pages = 0
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            while True:
                listings, total_pages = await self.scraper.get_listings(
                    slug_url, 
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
                    detailed_listings = await self.fetch_listing_details_batch(yesterday_listings, slug_url.replace('/', '_'), main_subcategory)
                    all_listings.extend(detailed_listings)
                
                if found_older or page_num >= total_pages:
                    break
                
                page_num += 1
                await asyncio.sleep(1)  # Rate limiting between pages
            
            result["listings"] = all_listings
            result["total_pages"] = total_pages
            
            logger.info(f"Total listings for {category_name}: {len(all_listings)} (across {page_num - 1} pages)")
            return result
            
        except Exception as e:
            logger.error(f"Error processing {category_name}: {e}")
            return result
    
    async def scrape_subcategory(self, subcategory: Dict) -> Dict:
        """
        Scrape a main subcategory with two possible cases:
        1. Has catChilds (e.g., motorbikes-sport): Scrape each catChild separately
        2. Direct listings (e.g., bicycles): Scrape listings directly
        
        Args:
            subcategory: Main subcategory dictionary
            
        Returns:
            Dictionary with scraped data organized by subcategory
        """
        subcat_slug = subcategory["slug"]
        subcat_name = subcategory["name_ar"]
        is_leaf = subcategory["is_leaf"]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing Main Subcategory: {subcat_name}")
        logger.info(f"Slug: {subcat_slug}")
        logger.info(f"Is Leaf (Direct Listings): {is_leaf}")
        logger.info(f"{'='*60}")
        
        result = {
            "subcategory": subcategory,
            "cat_childs_data": [],  # Will contain data for each catChild (if any)
            "direct_listings": None,  # Will contain listings if is_leaf=True
        }
        
        try:
            if is_leaf:
                # Case 2: Direct listings (e.g., bicycles)
                logger.info(f"This is a leaf category - scraping direct listings")
                slug_url = subcategory["slug_url"]
                listings_data = await self.scrape_category_listings(slug_url, subcat_name, subcat_slug)
                result["direct_listings"] = listings_data
            else:
                # Case 1: Has catChilds (e.g., motorbikes-sport)
                logger.info(f"This category has catChilds - fetching them...")
                cat_childs = await self.scraper.get_cat_childs(subcat_slug)
                
                if not cat_childs:
                    logger.warning(f"No catChilds found for {subcat_name}")
                    return result
                
                logger.info(f"Found {len(cat_childs)} catChilds, scraping each...")
                
                for i, child in enumerate(cat_childs, 1):
                    logger.info(f"\n[{i}/{len(cat_childs)}] Processing catChild: {child['name_ar']}")
                    
                    child_slug_url = child["slug_url"]
                    child_name = child["name_ar"]
                    
                    listings_data = await self.scrape_category_listings(child_slug_url, child_name, subcat_slug)
                    
                    result["cat_childs_data"].append({
                        "cat_child": child,
                        "listings_data": listings_data
                    })
                    
                    if len(cat_childs) > i:
                        await asyncio.sleep(2)  # Rate limiting between catChilds
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing subcategory {subcat_name}: {e}")
            return result
    
    async def scrape_all_subcategories(self) -> List[Dict]:
        """
        Scrape all bikes subcategories from the main page
        Automatically discovers and scrapes: motorbikes-sport, quad-bikes, bicycles, scooter, wanted-bikes
        """
        try:
            logger.info("Fetching bikes subcategories...")
            subcategories = await self.scraper.get_subcategories()
            
            if not subcategories:
                logger.error("No subcategories found!")
                return []
            
            logger.info(f"Found {len(subcategories)} main subcategories")
            
            all_results = []
            for i, subcat in enumerate(subcategories, 1):
                logger.info(f"\n{'*'*80}")
                logger.info(f"[{i}/{len(subcategories)}] Processing Main Subcategory: {subcat['name_ar']} ({subcat['slug']})")
                logger.info(f"{'*'*80}")
                
                result = await self.scrape_subcategory(subcat)
                all_results.append(result)
                
                if len(subcategories) > i:
                    await asyncio.sleep(3)  # Rate limiting between main subcategories
            
            return all_results
            
        except Exception as e:
            logger.error(f"Error scraping subcategories: {e}")
            return []
    
    async def save_all_to_R2(self, results: List[Dict]) -> Dict:
        """
        Save all data to R2 with proper partitioning
        
        Strategy:
        - Each main subcategory gets its own Excel file (e.g., motorbikes-sport.xlsx, bicycles.xlsx)
        - If subcategory has catChilds: Each catChild becomes a separate sheet
        - If subcategory is direct listings: One sheet with all listings
        """
        upload_summary = {
            "excel_files": [],
            "json_files": [],
            "total_listings": 0,
            "upload_time": datetime.now().isoformat()
        }
        
        try:
            # Calculate total listings across all subcategories
            total_listings = 0
            for result in results:
                if result["direct_listings"]:
                    total_listings += len(result["direct_listings"]["listings"])
                else:
                    for child_data in result["cat_childs_data"]:
                        total_listings += len(child_data["listings_data"]["listings"])
            
            upload_summary["total_listings"] = total_listings
            
            if total_listings == 0:
                logger.warning("No data to upload!")
                return upload_summary
            
            logger.info("\nUploading to AWS R2...")
            
            # Process each main subcategory
            for result in results:
                subcategory = result["subcategory"]
                subcat_slug = subcategory["slug"]
                subcat_name = subcategory["name_ar"]
                
                # Count listings for this subcategory
                subcat_listings_count = 0
                if result["direct_listings"]:
                    subcat_listings_count = len(result["direct_listings"]["listings"])
                else:
                    for child_data in result["cat_childs_data"]:
                        subcat_listings_count += len(child_data["listings_data"]["listings"])
                
                if subcat_listings_count == 0:
                    logger.info(f"Skipping {subcat_name} - no listings")
                    continue
                
                logger.info(f"\nCreating Excel file for: {subcat_name} ({subcat_listings_count} listings)")
                
                # Create Excel file for this subcategory
                temp_excel = self.temp_dir / f"{subcat_slug}_temp.xlsx"
                
                with pd.ExcelWriter(temp_excel, engine='openpyxl') as writer:
                    # Create Info sheet
                    info_data = [{
                        "Main Subcategory": subcat_name,
                        "Slug": subcat_slug,
                        "Total Listings": subcat_listings_count,
                        "Data Scraped Date": self.scrape_date.strftime('%Y-%m-%d'),
                        "Saved to R2 Date": self.save_date.strftime('%Y-%m-%d'),
                    }]
                    pd.DataFrame(info_data).to_excel(writer, sheet_name='Info', index=False)
                    
                    if result["direct_listings"]:
                        # Direct listings - one sheet
                        listings = result["direct_listings"]["listings"]
                        if listings:
                            sheet_name = "Listings"
                            df = pd.DataFrame(listings)
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                            logger.info(f"  Created sheet: {sheet_name} ({len(listings)} listings)")
                    else:
                        # CatChilds - each gets its own sheet
                        for child_data in result["cat_childs_data"]:
                            child = child_data["cat_child"]
                            listings = child_data["listings_data"]["listings"]
                            
                            if listings:
                                # Sanitize sheet name (max 31 chars in Excel)
                                sheet_name = child["name_ar"]
                                if len(sheet_name) > 31:
                                    sheet_name = sheet_name[:28] + "..."
                                
                                df = pd.DataFrame(listings)
                                df.to_excel(writer, sheet_name=sheet_name, index=False)
                                logger.info(f"  Created sheet: {sheet_name} ({len(listings)} listings)")
                
                # Upload excel to R2
                R2_excel_path = await asyncio.to_thread(
                    self.R2_helper.upload_file,
                    str(temp_excel),
                    f"excel-files/{subcat_slug}.xlsx",
                    self.save_date,
                    retries=3
                )
                
                if R2_excel_path:
                    R2_url = self.R2_helper.generate_R2_url(R2_excel_path)
                    upload_summary["excel_files"].append({
                        "name": subcat_name,
                        "slug": subcat_slug,
                        "total_listings": subcat_listings_count,
                        "R2_path": R2_excel_path,
                        "R2_url": R2_url
                    })
                    logger.info(f"[OK] Uploaded: {subcat_slug}.xlsx ({subcat_listings_count} listings)")

                if result["direct_listings"]:
                    json_version_payload = result["direct_listings"]["listings"]
                else:
                    json_version_payload = {
                        child_data["cat_child"]["slug"]: child_data["listings_data"]["listings"]
                        for child_data in result["cat_childs_data"]
                        if child_data["listings_data"]["listings"]
                    }
                json_version_file = self.temp_dir / f"{subcat_slug}_json_version_temp.json"
                with open(json_version_file, 'w', encoding='utf-8') as jf:
                    json.dump(json_version_payload, jf, ensure_ascii=False, indent=2)

                R2_json_version_path = await asyncio.to_thread(
                    self.R2_helper.upload_file,
                    str(json_version_file),
                    f"json version/{subcat_slug}.json",
                    self.save_date,
                    retries=3
                )
                if R2_json_version_path:
                    upload_summary["json_files"].append(R2_json_version_path)
                    logger.info(f"[OK] Uploaded JSON version: {subcat_slug}.json")
                json_version_file.unlink(missing_ok=True)
                
                temp_excel.unlink(missing_ok=True)
            
            # Upload JSON summary
            logger.info("\nUploading JSON summary...")
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
                "total_main_subcategories": len(results),
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
                subcategory = result["subcategory"]
                subcat_listings_count = 0
                cat_childs_info = []
                
                if result["direct_listings"]:
                    subcat_listings_count = len(result["direct_listings"]["listings"])
                else:
                    for child_data in result["cat_childs_data"]:
                        child = child_data["cat_child"]
                        child_listings = child_data["listings_data"]["listings"]
                        subcat_listings_count += len(child_listings)
                        cat_childs_info.append({
                            "name_ar": child["name_ar"],
                            "name_en": child["name_en"],
                            "slug": child["slug"],
                            "listings_count": len(child_listings)
                        })
                
                json_summary["subcategories"].append({
                    "name_ar": subcategory["name_ar"],
                    "name_en": subcategory["name_en"],
                    "slug": subcategory["slug"],
                    "is_leaf": subcategory["is_leaf"],
                    "total_listings": subcat_listings_count,
                    "cat_childs": cat_childs_info if cat_childs_info else None
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
    """Main entry point for the bikes scraper"""
    orchestrator = None
    
    try:
        bucket_name = os.environ.get("CF_R2_BUCKET_NAME")
        profile_name = os.environ.get("AWS_PROFILE", None)
        
        logger.info("\n" + "="*60)
        logger.info("BIKES SCRAPER STARTING")
        logger.info("="*60)
        logger.info(f"Bucket: {bucket_name}")
        logger.info(f"Mode: Scrape ALL available pages per category")
        
        orchestrator = BikesScraperOrchestrator(bucket_name=bucket_name, profile_name=profile_name)
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


