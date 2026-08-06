import asyncio
import pandas as pd
import json
import logging
import os
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from json_scraper_used_cars import UsedCarsJsonScraper
from s3_helper import R2Helper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class UsedCarsScraperOrchestrator:
    """
    Orchestrates the scraping of used-cars data with AWS R2 integration
    Creates Excel files organized by:
    - Main categories (files): Toyota.xlsx, Lexus.xlsx, etc.
    - Subcategories (sheets): Land Cruiser, Camry, etc. within each file
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
        self.scraper = UsedCarsJsonScraper()
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
    
    async def fetch_listing_details_batch(self, listings: List[Dict], main_category_slug: str, 
                                         subcategory_slug: str) -> List[Dict]:
        """
        Fetch detailed information for each listing from the listings page and download images
        
        Args:
            listings: List of basic listing info from listings page
            main_category_slug: Main category slug for organizing images
            subcategory_slug: Subcategory slug for organizing images
        
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
                                        f"{main_category_slug}/{subcategory_slug}",
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
    
    async def fetch_all_listings_for_subcategory(self, main_category_slug: str,
                                                 subcategory_slug: str) -> List[Dict]:
        """
        Fetch all listings for a specific subcategory across all pages
        
        Args:
            main_category_slug: Main category slug (e.g., 'toyota')
            subcategory_slug: Subcategory slug (e.g., 'land-cruiser')
        
        Returns:
            List of all listings for the subcategory
        """
        all_listings = []
        page_num = 1
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")

        while True:
            # Fetch WITHOUT filter_yesterday so we can inspect all dates on the page
            # and decide correctly whether to continue or stop
            listings, total_pages = await self.scraper.get_listings(
                main_category_slug,
                subcategory_slug,
                page_num,
                filter_yesterday=False
            )

            if not listings:
                logger.info(f"No more listings found for {main_category_slug}/{subcategory_slug}")
                break

            yesterday_listings = []
            found_today = False
            found_older = False
            for listing in listings:
                date_pub = listing.get("date_published", "")
                date_only = date_pub[:10] if date_pub else ""
                if date_pub.startswith(yesterday):
                    yesterday_listings.append(listing)
                elif date_only == today:
                    found_today = True
                elif date_only and date_only < yesterday:
                    found_older = True

            all_listings.extend(yesterday_listings)
            logger.info(
                f"Page {page_num}/{total_pages}: {len(yesterday_listings)} yesterday listings "
                f"(page total: {len(listings)})"
            )

            # Stop only when the page has no today/yesterday listings AND has older ones -
            # meaning we have fully passed the yesterday window in the sort order.
            if (not found_today and len(yesterday_listings) == 0 and found_older) or page_num >= total_pages:
                break

            page_num += 1
            await asyncio.sleep(0.5)  # Be gentle with the server

        return all_listings
    
    def format_listings_for_excel(self, listings: List[Dict]) -> List[Dict]:
        """
        Format listings data for Excel export
        
        Args:
            listings: List of listing dictionaries
        
        Returns:
            List of formatted dictionaries suitable for Excel
        """
        formatted = []
        for listing in listings:
            # Convert R2_images list to pipe-separated string
            R2_images = listing.get("r2_images", [])
            if isinstance(R2_images, list):
                R2_images_str = " | ".join(R2_images)
            else:
                R2_images_str = R2_images if R2_images else ""
            
            formatted.append({
                "Listing ID": listing.get("id"),
                "Title": listing.get("title"),
                "Slug": listing.get("slug"),
                "Price": listing.get("price"),
                "Phone": listing.get("phone"),
                "User Name": listing.get("user_name"),
                "User Email": listing.get("user_email"),
                "User Phone": listing.get("user_phone"),
                "User Type": listing.get("user_type"),
                "Date Published": listing.get("date_published"),
                "Date Relative": listing.get("date_relative"),
                "Address": listing.get("address"),
                "Full Address": listing.get("full_address"),
                "Status": listing.get("status"),
                "Images Count": listing.get("images_count"),
                "R2 Images": R2_images_str,
                "Description": listing.get("description", ""),
                "Category": listing.get("category"),
                "Views": listing.get("views_no"),
                "Latitude": listing.get("latitude"),
                "Longitude": listing.get("longitude"),
                "Specification (EN)": listing.get("specification_en", ""),
                "Specification (AR)": listing.get("specification_ar", ""),
            })
        
        return formatted
    
    def create_excel_file(self, excel_path: str, category_data: Dict[str, List[Dict]]):
        """
        Create an Excel file with multiple sheets, one for each subcategory
        
        Args:
            excel_path: Path to save the Excel file
            category_data: Dictionary with subcategory slugs as keys and listings as values
        """
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            sheets_created = 0
            
            for subcategory_slug, listings in category_data.items():
                if not listings:
                    logger.warning(f"No listings found for {subcategory_slug}")
                    continue
                
                # Format subcategory name for sheet title
                sheet_name = subcategory_slug.replace("-", " ").title()[:31]  # Excel has 31 char limit
                
                logger.info(f"Creating sheet: {sheet_name} with {len(listings)} listings")
                
                formatted = self.format_listings_for_excel(listings)
                df = pd.DataFrame(formatted)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                sheets_created += 1
                logger.info(f"  [OK] Created sheet: {sheet_name}")
            
            # If no sheets were created, add a "No Data" sheet
            if sheets_created == 0:
                logger.warning("No sheets were created, adding a 'No Data' sheet")
                pd.DataFrame([{"Message": "No listings found for this category"}]).to_excel(
                    writer, sheet_name="No Data", index=False
                )
        
        logger.info(f"Successfully created Excel file: {excel_path} with {sheets_created} sheet(s)")
    
    async def scrape_category(self, main_category: Dict) -> Tuple[Dict[str, List[Dict]], List[Dict[str, Any]]]:
        """
        Scrape all subcategories and listings for a main category
        
        Args:
            main_category: Dictionary containing main category info
        
        Returns:
            Dictionary with subcategory slugs as keys and listings as values
        """
        main_slug = main_category.get("slug")
        main_name_en = main_category.get("name_en")
        main_name_ar = main_category.get("name_ar")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Scraping category: {main_name_en} ({main_name_ar})")
        logger.info(f"{'='*60}")
        
        category_data = {}
        subcategory_summary: List[Dict[str, Any]] = []
        
        # Get subcategories
        subcategories = await self.scraper.get_subcategories(main_slug)
        
        if not subcategories:
            logger.warning(f"No subcategories found for {main_name_en}")
            return category_data, subcategory_summary
        
        # Fetch listings for each subcategory
        for subcategory in subcategories:
            sub_slug = subcategory.get("slug")
            sub_name_en = subcategory.get("name_en")
            sub_listings_count = subcategory.get("listings_count", 0)
            
            if sub_listings_count == 0:
                logger.info(f"  - {sub_name_en}: 0 listings (skipping)")
                continue
            
            logger.info(f"  - {sub_name_en}: {sub_listings_count} listings")
            
            # Fetch all listings for this subcategory
            listings = await self.fetch_all_listings_for_subcategory(main_slug, sub_slug)
            
            if listings:
                # Fetch detailed information for each listing including images
                logger.info(f"Fetching detailed information for {len(listings)} listings...")
                detailed_listings = await self.fetch_listing_details_batch(
                    listings, 
                    main_slug, 
                    sub_slug
                )
                
                if detailed_listings:
                    category_data[sub_slug] = detailed_listings
                    subcategory_summary.append({
                        "slug": sub_slug,
                        "name_en": sub_name_en,
                        "name_ar": subcategory.get("name_ar"),
                        "listings_count": len(detailed_listings),
                    })
                    logger.info(f"    [OK] Fetched {len(detailed_listings)} detailed listings with images")
                else:
                    logger.warning(f"    [OK] No detailed listings retrieved for {sub_name_en}")
            
            await asyncio.sleep(0.3)  # Be gentle with the server
        
        return category_data, subcategory_summary
    
    async def run_scraper(self, max_categories: Optional[int] = None):
        """
        Main scraper orchestrator
        
        Args:
            max_categories: Maximum number of categories to scrape (None for all)
        """
        try:
            await self.initialize()
            self.start_time = time.time()
            
            # Fetch all main categories
            main_categories = await self.scraper.get_main_categories()
            
            if not main_categories:
                logger.error("Failed to fetch main categories")
                return
            
            logger.info(f"Found {len(main_categories)} main categories")
            
            # Limit categories if specified
            if max_categories:
                main_categories = main_categories[:max_categories]
                logger.info(f"Limiting to {max_categories} categories")
            
            # Process each main category
            upload_results = []
            total_listings = 0
            for idx, category in enumerate(main_categories, 1):
                try:
                    logger.info(f"\n[{idx}/{len(main_categories)}] Processing: {category['name_en']}")
                    
                    # Scrape category data
                    category_data, subcategory_summary = await self.scrape_category(category)
                    
                    if not category_data:
                        logger.warning(f"No data collected for {category['name_en']}")
                        continue
                    
                    category_listings = sum(len(listings) for listings in category_data.values())
                    total_listings += category_listings
                    
                    # Create Excel file
                    excel_filename = f"{category['name_en']}.xlsx"
                    excel_path = self.temp_dir / excel_filename
                    
                    self.create_excel_file(str(excel_path), category_data)
                    
                    # Upload to R2 with excel-files folder structure
                    if self.R2_helper:
                        R2_excel_key = f"excel-files/{excel_filename}"
                        R2_path = self.R2_helper.upload_file(
                            str(excel_path),
                            R2_excel_key,
                            self.save_date
                        )

                        json_payload = {
                            "category": {
                                "name_en": category.get("name_en"),
                                "name_ar": category.get("name_ar"),
                                "slug": category.get("slug"),
                            },
                            "subcategories": [
                                {
                                    "slug": sub_slug,
                                    "listings": listings,
                                }
                                for sub_slug, listings in category_data.items()
                                if listings
                            ],
                        }
                        temp_json_version = self.temp_dir / f"{category['name_en']}_json_version.json"
                        with open(temp_json_version, 'w', encoding='utf-8') as jf:
                            json.dump(json_payload, jf, ensure_ascii=False, indent=2)
                        R2_json_version_key = f"json version/{category['name_en']}.json"
                        R2_json_version_path = self.R2_helper.upload_file(
                            str(temp_json_version),
                            R2_json_version_key,
                            self.save_date
                        )
                        if R2_json_version_path:
                            logger.info(f"[OK] Uploaded JSON version: {R2_json_version_path}")
                        temp_json_version.unlink(missing_ok=True)
                        
                        if R2_path:
                            logger.info(f"[OK] Uploaded to R2: {R2_path}")
                            upload_results.append({
                                "name_en": category["name_en"],
                                "slug": category.get("slug"),
                                "listings_count": category_listings,
                                "subcategories_count": len(subcategory_summary),
                                "subcategories": subcategory_summary,
                            })
                        else:
                            logger.error(f"[OK] Failed to upload {excel_filename} to R2")
                    
                    await asyncio.sleep(0.5)  # Be gentle with the server
                    
                except Exception as e:
                    logger.error(f"Error processing category {category['name_en']}: {e}", exc_info=True)
                    continue

            if self.R2_helper and total_listings > 0:
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
                    "saved_to_s3_date": self.save_date.strftime('%Y-%m-%d'),
                    "total_categories": len(upload_results),
                    "total_listings": total_listings,
                    "categories": upload_results,
                    "request_metrics": {
                        "requests_total": effective_requests_total,
                        "requests_failed": effective_requests_failed,
                        "error_rate_pct": round(error_rate_pct, 2),
                        "requests_per_min": round(requests_per_min, 2),
                        "duration_sec": round(duration_sec, 2),
                    },
                }
                temp_json = self.temp_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(temp_json, 'w', encoding='utf-8') as f:
                    json.dump(json_summary, f, ensure_ascii=False, indent=2)
                R2_json_path = self.R2_helper.upload_file(
                    str(temp_json),
                    f"json-files/summary_{self.save_date.strftime('%Y%m%d')}.json",
                    self.save_date
                )
                if R2_json_path:
                    logger.info("[OK] Uploaded JSON summary")
                temp_json.unlink(missing_ok=True)
            
            logger.info("\n" + "="*60)
            logger.info("Scraping completed successfully!")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"Fatal error in scraper: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()


async def main():
    """
    Main entry point for the scraper
    """
    BUCKET_NAME = os.getenv("CF_R2_BUCKET_NAME")
    PROFILE_NAME = None  # Optional AWS profile name
    MAX_CATEGORIES = None  # None to scrape all categories, or set a number like 5
    
    logger.info(f"Using R2 bucket: {BUCKET_NAME}")
    
    # Initialize and run scraper
    orchestrator = UsedCarsScraperOrchestrator(
        bucket_name=BUCKET_NAME,
        profile_name=PROFILE_NAME
    )
    
    await orchestrator.run_scraper(max_categories=MAX_CATEGORIES)


if __name__ == "__main__":
    asyncio.run(main())


