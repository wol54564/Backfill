import asyncio
import pandas as pd
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from json_scraper import RestAutomotiveJsonScraper
from s3_helper import R2Helper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RestAutomotiveScraperOrchestrator:
    """
    Orchestrates the scraping of Rest-Automative-Part1 data with AWS R2 integration
    Scrapes categories: Watercraft, Spare Parts, Automotive Accessories, CMVs, Rentals
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
        self.scraper = RestAutomotiveJsonScraper()
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
    
    async def fetch_listing_details_batch(self, listings: List[Dict], category_slug: str, category_name: str) -> List[Dict]:
        """
        Fetch detailed information for each listing from the listings page and download images
        
        Args:
            listings: List of basic listing info from listings page
            category_slug: Category slug for organizing images
            category_name: Category name (e.g., 'Watercraft') for folder structure
        
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
                                        "rest-automotive-part1",
                                        category_name
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
    
    async def scrape_subcategory(self, category: Dict, subcategory: Dict) -> Dict:
        """
        Scrape a Rest-Automative subcategory with listings and detailed information
        Automatically scrapes all available pages returned by the API
        
        Args:
            category: Parent category dictionary with slug, name_ar, name_en
            subcategory: Subcategory dictionary with slug, name_ar, name_en, etc.
            
        Returns:
            Dictionary with scraped data organized by subcategory
        """
        cat_slug = category["slug"]
        subcat_slug = subcategory["slug"]
        logger.info(f"\nProcessing: {subcategory['name_ar']}")
        
        result = {
            "category": category,
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
                    cat_slug,
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
                    detailed_listings = await self.fetch_listing_details_batch(yesterday_listings, subcat_slug, category["name_en"])
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
    
    async def scrape_all_categories(self) -> List[Dict]:
        """
        Scrape all Rest-Automative categories with their subcategories
        Automatically discovers and scrapes all available pages
        """
        try:
            logger.info("Fetching Rest-Automative categories...")
            categories = await self.scraper.get_rest_categories()
            
            if not categories:
                logger.error("No categories found!")
                return []
            
            logger.info(f"Found {len(categories)} categories")
            
            all_results = []
            for i, category in enumerate(categories, 1):
                cat_slug = category["slug"]
                logger.info(f"\n[{i}/{len(categories)}] Processing: {category['name_ar']} ({cat_slug})")
                
                # Get subcategories for this category
                subcategories = await self.scraper.get_subcategories(cat_slug)
                
                if not subcategories:
                    logger.warning(f"No subcategories found for {category['name_ar']}")
                    continue
                
                logger.info(f"Found {len(subcategories)} subcategories")
                
                # Scrape each subcategory
                for j, subcat in enumerate(subcategories, 1):
                    logger.info(f"  [{j}/{len(subcategories)}] Scraping: {subcat['name_ar']}")
                    result = await self.scrape_subcategory(category, subcat)
                    if result["listings"]:
                        all_results.append(result)
                    
                    if j < len(subcategories):
                        await asyncio.sleep(1)  # Rate limiting between subcategories
            
            return all_results
            
        except Exception as e:
            logger.error(f"Error scraping categories: {e}")
            return []
    
    async def save_all_to_R2(self, results: List[Dict]) -> Dict:
        """
        Save all data to R2 with proper partitioning
        Creates separate Excel files for each category: Watercraft.xlsx, Spare Parts.xlsx, etc.
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
            
            # Group results by parent category
            categories_dict = {}
            for result in results:
                category = result["category"]
                cat_slug = category["slug"]
                
                if cat_slug not in categories_dict:
                    categories_dict[cat_slug] = {
                        "category": category,
                        "subcategories": []
                    }
                
                categories_dict[cat_slug]["subcategories"].append(result)
            
            # Create one Excel file per parent category
            for cat_slug, cat_data in categories_dict.items():
                category = cat_data["category"]
                subcategories = cat_data["subcategories"]
                
                if not subcategories:
                    continue
                
                total_listings_in_cat = sum(len(sub["listings"]) for sub in subcategories)
                
                if total_listings_in_cat > 0:
                    # Use category English name for filename
                    category_filename = category["name_en"]
                    logger.info(f"Creating Excel file for {category_filename} with {len(subcategories)} subcategories...")
                    
                    # Create Excel file with category name
                    temp_excel = self.temp_dir / f"{cat_slug}_temp.xlsx"
                    with pd.ExcelWriter(temp_excel, engine='openpyxl') as writer:
                        # Info sheet
                        info_data = [{
                            "Category (Arabic)": category["name_ar"],
                            "Category (English)": category["name_en"],
                            "Total Subcategories": len(subcategories),
                            "Total Listings": total_listings_in_cat,
                            "Data Scraped Date": self.scrape_date.strftime('%Y-%m-%d'),
                            "Saved to R2 Date": self.save_date.strftime('%Y-%m-%d'),
                        }]
                        pd.DataFrame(info_data).to_excel(writer, sheet_name='Info', index=False)
                        
                        # Create a sheet for each subcategory
                        for sub_result in subcategories:
                            subcat = sub_result["subcategory"]
                            listings = sub_result["listings"]
                            
                            if listings:
                                # Use subcategory Arabic name for sheet name (max 31 chars in Excel)
                                sheet_name = subcat["name_ar"][:31] if len(subcat["name_ar"]) <= 31 else subcat["name_ar"][:28] + "..."
                                df = pd.DataFrame(listings)
                                df.to_excel(writer, sheet_name=sheet_name, index=False)
                                logger.info(f"  Sheet created: {sheet_name} ({len(listings)} listings)")
                    
                    # Upload to R2 with correct folder name
                    R2_excel_path = await asyncio.to_thread(
                        self.R2_helper.upload_file,
                        str(temp_excel),
                        f"excel-files/{category_filename}.xlsx",
                        self.save_date,
                        retries=3,
                        folder_name="rest-automotive-part1"
                    )
                    
                    if R2_excel_path:
                        R2_url = self.R2_helper.generate_R2_url(R2_excel_path)
                        
                        # Add category info to summary
                        subcategories_info = [
                            {
                                "name": sub["subcategory"]["name_ar"],
                                "listings": len(sub["listings"])
                            }
                            for sub in subcategories if sub["listings"]
                        ]
                        
                        upload_summary["excel_files"].append({
                            "category": category["name_ar"],
                            "category_en": category_filename,
                            "slug": cat_slug,
                            "subcategories_count": len(subcategories_info),
                            "total_listings": total_listings_in_cat,
                            "subcategories": subcategories_info,
                            "R2_path": R2_excel_path,
                            "R2_url": R2_url
                        })
                        logger.info(f"[OK] Uploaded: {category_filename}.xlsx ({total_listings_in_cat} listings across {len(subcategories)} subcategories)")

                    json_version_payload = {
                        "category": category,
                        "subcategories": [
                            {
                                "subcategory": sub_result["subcategory"],
                                "listings": sub_result["listings"],
                            }
                            for sub_result in subcategories
                            if sub_result["listings"]
                        ],
                    }
                    temp_json_version = self.temp_dir / f"{cat_slug}_temp.json"
                    with open(temp_json_version, 'w', encoding='utf-8') as jf:
                        json.dump(json_version_payload, jf, ensure_ascii=False, indent=2)

                    R2_json_version_path = await asyncio.to_thread(
                        self.R2_helper.upload_file,
                        str(temp_json_version),
                        f"json version/{category_filename}.json",
                        self.save_date,
                        retries=3,
                        folder_name="rest-automotive-part1"
                    )
                    if R2_json_version_path:
                        upload_summary["json_files"].append(R2_json_version_path)
                        logger.info(f"[OK] Uploaded JSON version: {category_filename}.json")
                    temp_json_version.unlink(missing_ok=True)
                    
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
                "total_categories": len(categories_dict),
                "total_excel_files": len(upload_summary["excel_files"]),
                "total_listings": total_listings,
                "categories": [],
                "request_metrics": {
                    "requests_total": effective_requests_total,
                    "requests_failed": effective_requests_failed,
                    "error_rate_pct": round(error_rate_pct, 2),
                    "requests_per_min": round(requests_per_min, 2),
                    "duration_sec": round(duration_sec, 2),
                },
            }
            
            for cat_data in categories_dict.values():
                category = cat_data["category"]
                json_summary["categories"].append({
                    "name_ar": category["name_ar"],
                    "name_en": category["name_en"],
                    "slug": category["slug"],
                    "subcategories_count": len(cat_data["subcategories"]),
                    "subcategories": [
                        {
                            "name_ar": sub["subcategory"]["name_ar"],
                            "name_en": sub["subcategory"]["name_en"],
                            "slug": sub["subcategory"]["slug"],
                            "listings_count": len(sub["listings"]),
                        }
                        for sub in cat_data["subcategories"] if sub["listings"]
                    ],
                })
            
            temp_json = self.temp_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(temp_json, 'w', encoding='utf-8') as f:
                json.dump(json_summary, f, ensure_ascii=False, indent=2)
            
            R2_json_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(temp_json),
                f"json-files/summary_{self.save_date.strftime('%Y%m%d')}.json",
                self.save_date,
                folder_name="rest-automotive-part1"
            )
            
            if R2_json_path:
                upload_summary["json_files"].append(R2_json_path)
                logger.info(f"[OK] Uploaded JSON summary")
            
            temp_json.unlink(missing_ok=True)
            
        except Exception as e:
            logger.error(f"Error in R2 upload: {e}")
        
        return upload_summary


async def main():
    """Main entry point for the rest-automative scraper"""
    orchestrator = None
    
    try:
        bucket_name = os.environ.get("CF_R2_BUCKET_NAME")
        profile_name = os.environ.get("AWS_PROFILE", None)
        
        logger.info("\n" + "="*60)
        logger.info("REST-AUTOMATIVE SCRAPER STARTING")
        logger.info("="*60)
        logger.info(f"Bucket: {bucket_name}")
        logger.info(f"Mode: Scrape ALL available pages per subcategory")
        
        orchestrator = RestAutomotiveScraperOrchestrator(bucket_name=bucket_name, profile_name=profile_name)
        await orchestrator.initialize()
        orchestrator.start_time = time.time()
        
        logger.info("\nStarting scraping...")
        results = await orchestrator.scrape_all_categories()
        
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
                logger.info(f"  - {excel_file['category_en']}: {excel_file['total_listings']} listings")
            
        else:
            logger.error("Scraping failed - no results!")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        
    finally:
        if orchestrator:
            await orchestrator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())


