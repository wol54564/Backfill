import asyncio
import pandas as pd
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from json_scraper import AutomotiveServicesJsonScraper
from s3_helper import R2Helper
from io import BytesIO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AutomotiveServicesScraperOrchestrator:
    """
    Orchestrates the scraping of automotive services subcategories with AWS R2 integration
    
    Flow:
    1. Fetch all subcategories from automotive-services category
    2. For each subcategory, fetch all listings
    3. For each listing, fetch detailed information
    4. Organize data into one Excel file with subcategories as sheet names
    5. Upload Excel file and images to R2
    """
    
    def __init__(self, bucket_name: str, profile_name: Optional[str] = None, 
                 temp_dir: str = "temp_data", max_listings_per_subcategory: Optional[int] = None):
        self.scraper = None
        self.R2_helper = None
        self.bucket_name = bucket_name
        self.profile_name = profile_name
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self.max_listings_per_subcategory = max_listings_per_subcategory
        self.scrape_date = datetime.now() - timedelta(days=1)
        self.save_date = datetime.now()
        self.start_time = None
        self.requests_total = 0
        self.requests_failed = 0
        
        logger.info(f"Scraping data for date: {self.scrape_date.strftime('%Y-%m-%d')}")
        logger.info(f"Saving to R2 with date: {self.save_date.strftime('%Y-%m-%d')}")
        if max_listings_per_subcategory:
            logger.info(f"Max listings per subcategory: {max_listings_per_subcategory}")
        else:
            logger.info("Mode: Scrape ALL available listings")
    
    async def initialize(self):
        """Initialize the scraper and R2 client"""
        self.scraper = AutomotiveServicesJsonScraper()
        
        try:
            self.R2_helper = R2Helper(
                bucket_name=self.bucket_name,
                profile_name=self.profile_name
            )
            logger.info(f"R2Helper initialized for bucket: {self.bucket_name}")
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
    
    async def fetch_and_process_subcategory(self, subcategory: Dict, 
                                            filter_yesterday: bool = False) -> Dict:
        """
        Fetch and process all listings for a subcategory with image upload
        
        Args:
            subcategory: Subcategory dictionary
            filter_yesterday: If True, only fetch listings from yesterday
        
        Returns:
            Dictionary with processed subcategory data
        """
        subcategory_slug = subcategory.get("slug")
        subcategory_name = subcategory.get("name_en", "Unknown")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing subcategory: {subcategory_name} ({subcategory_slug})")
        logger.info(f"{'='*60}")
        
        # Fetch all listings for this subcategory
        listings = await self.scraper.get_all_listings_for_subcategory(
            subcategory_slug,
            max_pages=self.max_listings_per_subcategory,
            filter_yesterday=filter_yesterday
        )
        
        if not listings:
            logger.warning(f"No listings found for {subcategory_name}")
            return {
                "subcategory": subcategory,
                "listings": []
            }
        
        logger.info(f"Fetching details for {len(listings)} listings...")
        
        # Fetch detailed information for each listing with image uploads
        detailed_listings = []
        for idx, listing in enumerate(listings):
            slug = listing.get("slug")
            if not slug:
                continue
            
            logger.info(f"  [{idx+1}/{len(listings)}] Fetching details for {slug}...")
            details = await self.scraper.get_listing_details(slug)
            
            if details:
                # Download and upload images if available
                images = details.get("images", [])
                listing_id = details.get("id")
                
                if images:
                    logger.info(f"    Processing {len(images)} images for {slug} (ID: {listing_id})...")
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
                                    logger.info(f"      Image {img_index}: {listing_id}_{img_index}.jpg [OK]")
                            
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            logger.warning(f"      Failed to download/upload image {image_url}: {e}")
                            continue
                    
                    # Add R2 image URLs to details
                    details["r2_images"] = R2_image_urls
                    logger.info(f"    Successfully uploaded {len(R2_image_urls)} images")
                
                detailed_listings.append(details)
                await asyncio.sleep(0.5)  # Be nice to server
            else:
                # Use the basic listing info if details fetch fails
                detailed_listings.append(listing)
        
        logger.info(f"Successfully fetched {len(detailed_listings)} detailed listings for {subcategory_name}")
        
        return {
            "subcategory": subcategory,
            "listings": detailed_listings
        }
    
    def convert_listings_to_dataframe(self, detailed_listings: List[Dict]) -> pd.DataFrame:
        """
        Convert detailed listings to a pandas DataFrame
        
        Args:
            detailed_listings: List of detailed listing dictionaries
        
        Returns:
            DataFrame with listing information
        """
        if not detailed_listings:
            return pd.DataFrame()
        
        rows = []
        for listing in detailed_listings:
            # Handle both detail response format and basic listing format
            listing_id = listing.get("id") or listing.get("user_adv_id")
            title = listing.get("title")
            phone = listing.get("phone") or listing.get("contact")
            description = listing.get("description") or listing.get("desc_en")
            price = listing.get("price")
            date_published = listing.get("date_published")
            date_created = listing.get("date_created")
            date_expired = listing.get("date_expired")
            date_sort = listing.get("date_sort")
            
            user_name = ""
            user_id = ""
            user_email = ""
            
            if listing.get("user"):
                user_info = listing.get("user")
                user_name = user_info.get("name", "") or user_info.get("first_name", "")
                user_id = user_info.get("user_id") or user_info.get("id", "")
                user_email = user_info.get("email", "")
            
            images = listing.get("images", [])
            image_count = len(images) if isinstance(images, list) else 0
            image_urls = ",".join(images) if images else ""
            
            # Get location info
            district_name = ""
            if listing.get("district"):
                district_info = listing.get("district")
                district_name = district_info.get("name", "")
            elif listing.get("district_name_localize"):
                district_localize = listing.get("district_name_localize")
                district_name = district_localize.get("en", "")
            
            # Get category info
            category_name = ""
            if listing.get("category"):
                category_info = listing.get("category")
                category_name = category_info.get("name", "")
            
            # Get contacts
            contacts = listing.get("contacts", [])
            contacts_str = ",".join(contacts) if contacts else ""
            
            # Get coordinates
            lat = listing.get("lat", "")
            lon = listing.get("lon", "")
            
            # Get other fields
            slug = listing.get("slug", "")
            status = listing.get("status", "")
            is_pm_enabled = listing.get("is_private_message_enabled", False)
            
            row = {
                "ID": listing_id,
                "Title": title,
                "Phone": phone,
                "User": user_name,
                "User ID": user_id,
                "User Email": user_email,
                "Description": description,
                "Price": price,
                "Date Published": date_published,
                "Date Created": date_created,
                "Date Expired": date_expired,
                "Date Sort": date_sort,
                "Images Count": image_count,
                "Image URLs": image_urls,
                "District": district_name,
                "Category": category_name,
                "Contacts": contacts_str,
                "PM Enabled": is_pm_enabled,
                "Latitude": lat,
                "Longitude": lon,
                "Slug": slug,
                "Status": status,
            }
            
            rows.append(row)
        
        return pd.DataFrame(rows)
    
    async def create_excel_with_subcategories(self, all_data: List[Dict]) -> Optional[Path]:
        """
        Create a single Excel file with Info sheet and subcategory sheets
        
        Args:
            all_data: List of processed subcategory data
        
        Returns:
            Path to the Excel file or None if failed
        """
        try:
            output_file = self.temp_dir / "automotive-services.xlsx"
            
            logger.info(f"\nCreating Excel file: {output_file}")
            
            total_listings = sum(len(d.get("listings", [])) for d in all_data)
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Create Info sheet with summary
                info_data = [{
                    "Project": "Automotive Services",
                    "Total Subcategories": len(all_data),
                    "Total Listings": total_listings,
                    "Data Scraped Date": self.scrape_date.strftime('%Y-%m-%d'),
                    "Saved to R2 Date": self.save_date.strftime('%Y-%m-%d'),
                }]
                pd.DataFrame(info_data).to_excel(writer, sheet_name='Info', index=False)
                logger.info(f"  Created sheet: Info")
                
                # Create a sheet for each subcategory
                for subcat_data in all_data:
                    subcategory = subcat_data.get("subcategory", {})
                    listings = subcat_data.get("listings", [])
                    
                    if listings:
                        subcategory_name = subcategory.get("name_en", "Unknown")
                        sheet_name = subcategory_name[:31]  # Excel sheet name limit is 31 chars
                        
                        logger.info(f"  Creating sheet: {sheet_name} with {len(listings)} listings")
                        
                        # Convert to DataFrame
                        df = self.convert_listings_to_dataframe(listings)
                        
                        # Write to sheet
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            logger.info(f"[OK] Excel file created successfully: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Error creating Excel file: {e}")
            return None
    
    async def upload_excel_to_R2(self, excel_path: Path) -> Optional[str]:
        """
        Upload Excel file to R2
        
        Args:
            excel_path: Path to the Excel file
        
        Returns:
            R2 key or None if failed
        """
        try:
            R2_key = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(excel_path),
                "excel-files/automotive-services.xlsx",
                target_date=self.save_date
            )
            
            if R2_key:
                R2_url = self.R2_helper.generate_R2_url(R2_key)
                logger.info(f"[OK] Excel file Uploaded to R2: {R2_url}")
                return R2_key
            else:
                logger.error("Failed to upload Excel file to R2")
                return None
                
        except Exception as e:
            logger.error(f"Error uploading Excel to R2: {e}")
            return None
    
    async def run(self, filter_yesterday: bool = False):
        """
        Run the complete scraping and processing workflow
        
        Args:
            filter_yesterday: If True, only scrape listings from yesterday
        """
        try:
            await self.initialize()
            self.start_time = time.time()
            
            # Step 1: Fetch subcategories
            logger.info("\n" + "="*60)
            logger.info("STEP 1: Fetching subcategories...")
            logger.info("="*60)
            if filter_yesterday:
                logger.info("MODE: Scraping YESTERDAY'S listings only")
            else:
                logger.info("MODE: Scraping ALL current listings")
            
            subcategories = await self.scraper.get_subcategories()
            
            if not subcategories:
                logger.error("No subcategories found. Exiting.")
                return
            
            # Step 2: Fetch and process each subcategory
            logger.info("\n" + "="*60)
            logger.info("STEP 2: Processing subcategories...")
            logger.info("="*60)
            
            all_data = []
            for idx, subcategory in enumerate(subcategories, 1):
                logger.info(f"\n[{idx}/{len(subcategories)}]")
                subcat_data = await self.fetch_and_process_subcategory(subcategory, 
                                                                       filter_yesterday=filter_yesterday)
                all_data.append(subcat_data)
                await asyncio.sleep(2)  # Be nice to server
            
            # Step 3: Create Excel file
            logger.info("\n" + "="*60)
            logger.info("STEP 3: Creating Excel file...")
            logger.info("="*60)
            
            excel_path = await self.create_excel_with_subcategories(all_data)
            
            if not excel_path:
                logger.error("Failed to create Excel file")
                return
            
            # Step 4: Upload excel to R2
            logger.info("\n" + "="*60)
            logger.info("STEP 4: Uploading Excel to R2...")
            logger.info("="*60)
            
            await self.upload_excel_to_R2(excel_path)

            json_version_payload = {
                "subcategories": [
                    {
                        "subcategory": d.get("subcategory", {}),
                        "listings": d.get("listings", []),
                    }
                    for d in all_data
                    if d.get("listings")
                ]
            }
            temp_json_version = self.temp_dir / "automotive-services_json_version.json"
            with open(temp_json_version, 'w', encoding='utf-8') as jf:
                json.dump(json_version_payload, jf, ensure_ascii=False, indent=2)
            R2_json_version_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(temp_json_version),
                "json version/automotive-services.json",
                self.save_date
            )
            if R2_json_version_path:
                logger.info("[OK] Uploaded JSON version: automotive-services.json")
            temp_json_version.unlink(missing_ok=True)

            total_listings = sum(len(d.get("listings", [])) for d in all_data)
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
                "total_subcategories": len(all_data),
                "total_listings": total_listings,
                "subcategories": [
                    {
                        "name_ar": d.get("subcategory", {}).get("name_ar"),
                        "name_en": d.get("subcategory", {}).get("name_en"),
                        "slug": d.get("subcategory", {}).get("slug"),
                        "listings_count": len(d.get("listings", [])),
                    }
                    for d in all_data
                    if d.get("listings")
                ],
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
            R2_json_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(temp_json),
                f"json-files/summary_{self.save_date.strftime('%Y%m%d')}.json",
                self.save_date
            )
            if R2_json_path:
                logger.info("[OK] Uploaded JSON summary")
            temp_json.unlink(missing_ok=True)
            
            logger.info("\n" + "="*60)
            logger.info("[OK] ALL TASKS COMPLETED SUCCESSFULLY!")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"Fatal error during scraping: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    try:
        # Configuration
        BUCKET_NAME = os.environ.get("CF_R2_BUCKET_NAME")
        
        # Uncomment to limit listings per subcategory (useful for testing)
        # MAX_LISTINGS = 5
        MAX_LISTINGS = None  # Scrape all listings
        
        # Set to True to only scrape yesterday's listings
        FILTER_YESTERDAY = True
        
        orchestrator = AutomotiveServicesScraperOrchestrator(
            bucket_name=BUCKET_NAME,
        )
        
        await orchestrator.run(filter_yesterday=FILTER_YESTERDAY)
        
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())


