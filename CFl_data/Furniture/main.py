import asyncio
import pandas as pd
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from json_scraper import FurnitureJsonScraper
from s3_helper import R2Helper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FurnitureScraperOrchestrator:
    """
    Orchestrates the scraping of furniture data with AWS R2 integration
    Handles 3 cases:
    - Case 1: Subcategories with main page + district pages
    - Case 2: Subcategories with direct listings
    - Case 3: Subcategories with catChilds
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
        self.scraper = FurnitureJsonScraper()
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
    
    async def scrape_listings_pages(self, subcategory_slug: str, district_slug: str = None, 
                                   catchild_slug: str = None, label: str = "") -> List[Dict]:
        """
        Scrape all pages of listings for a subcategory, district, or catchild
        
        Args:
            subcategory_slug: Subcategory slug
            district_slug: Optional district slug (for Case 1)
            catchild_slug: Optional catchild slug (for Case 3)
            label: Label for logging
            
        Returns:
            List of detailed listings
        """
        page_num = 1
        all_listings = []
        total_pages = 0
        
        while True:
            listings, total_pages = await self.scraper.get_listings(
                subcategory_slug,
                page_num=page_num,
                filter_yesterday=True,
                district_slug=district_slug,
                catchild_slug=catchild_slug
            )
            
            if not listings:
                logger.info(f"{label}: No listings found on page {page_num}, stopping pagination")
                break
            
            logger.info(f"{label}: Fetching detailed information for {len(listings)} listings on page {page_num}/{total_pages}...")
            detailed_listings = await self.fetch_listing_details_batch(listings, subcategory_slug)
            all_listings.extend(detailed_listings)
            
            page_num += 1
            
            # Stop if we've reached the total pages
            if page_num > total_pages:
                logger.info(f"{label}: Reached total pages ({total_pages})")
                break
            
            await asyncio.sleep(1)  # Rate limiting between pages
        
        logger.info(f"{label}: Total listings: {len(all_listings)} (across {page_num - 1} pages)")
        return all_listings
    
    async def scrape_case1_district_filtration(self, subcategory: Dict) -> Dict:
        """
        Case 1: Subcategory with main page + district pages
        category_type: listings_district_filteration
        
        Creates Excel with sheets: Main, District1, District2, etc.
        """
        subcat_slug = subcategory["slug"]
        logger.info(f"\n[CASE 1] Processing: {subcategory['name_ar']} (District Filtration)")
        
        result = {
            "subcategory": subcategory,
            "main_listings": [],
            "district_data": [],
            "total_listings": 0
        }
        
        try:
            # Scrape main page
            logger.info(f"Scraping main page for {subcat_slug}...")
            main_listings = await self.scrape_listings_pages(
                subcat_slug,
                label=f"{subcategory['name_ar']} - Main"
            )
            result["main_listings"] = main_listings
            result["total_listings"] += len(main_listings)
            
            # Get districts
            districts = await self.scraper.get_districts(subcat_slug)
            
            # Scrape each district
            for district in districts:
                district_name_en = district.get("full_path_en", "").lower().replace(" ", "-")
                district_slug = f"{district_name_en}--district"
                district_name_ar = district.get("name_ar")
                
                logger.info(f"Scraping district: {district_name_ar} ({district_slug})...")
                district_listings = await self.scrape_listings_pages(
                    subcat_slug,
                    district_slug=district_slug,
                    label=f"{subcategory['name_ar']} - {district_name_ar}"
                )
                
                result["district_data"].append({
                    "district": district,
                    "listings": district_listings
                })
                result["total_listings"] += len(district_listings)
                
                await asyncio.sleep(1)
            
            logger.info(f"Total listings for {subcategory['name_ar']}: {result['total_listings']}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing {subcategory['name_ar']}: {e}")
            return result
    
    async def scrape_case2_direct_listings(self, subcategory: Dict) -> Dict:
        """
        Case 2: Subcategory with direct listings (no districts or catchilds)
        category_type: listings
        
        Creates Excel with single sheet: Listings
        """
        subcat_slug = subcategory["slug"]
        logger.info(f"\n[CASE 2] Processing: {subcategory['name_ar']} (Direct Listings)")
        
        result = {
            "subcategory": subcategory,
            "listings": [],
            "total_listings": 0
        }
        
        try:
            # Scrape all pages
            listings = await self.scrape_listings_pages(
                subcat_slug,
                label=subcategory['name_ar']
            )
            
            result["listings"] = listings
            result["total_listings"] = len(listings)
            
            logger.info(f"Total listings for {subcategory['name_ar']}: {result['total_listings']}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing {subcategory['name_ar']}: {e}")
            return result
    
    async def scrape_case3_catchilds(self, subcategory: Dict) -> Dict:
        """
        Case 3: Subcategory with catChilds
        Has catChilds array in response
        
        Creates Excel with sheets: CatChild1, CatChild2, etc.
        """
        subcat_slug = subcategory["slug"]
        logger.info(f"\n[CASE 3] Processing: {subcategory['name_ar']} (CatChilds)")
        
        result = {
            "subcategory": subcategory,
            "catchild_data": [],
            "total_listings": 0
        }
        
        try:
            # Get catchilds
            catchilds = await self.scraper.get_catchilds(subcat_slug)
            
            if not catchilds:
                logger.warning(f"No catChilds found for {subcat_slug}, treating as Case 2")
                # Fall back to Case 2
                return await self.scrape_case2_direct_listings(subcategory)
            
            # Scrape each catchild
            for catchild in catchilds:
                catchild_slug = catchild.get("slug")
                catchild_name_ar = catchild.get("name_ar")
                
                logger.info(f"Scraping catchild: {catchild_name_ar} ({catchild_slug})...")
                catchild_listings = await self.scrape_listings_pages(
                    subcat_slug,
                    catchild_slug=catchild_slug,
                    label=f"{subcategory['name_ar']} - {catchild_name_ar}"
                )
                
                result["catchild_data"].append({
                    "catchild": catchild,
                    "listings": catchild_listings
                })
                result["total_listings"] += len(catchild_listings)
                
                await asyncio.sleep(1)
            
            logger.info(f"Total listings for {subcategory['name_ar']}: {result['total_listings']}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing {subcategory['name_ar']}: {e}")
            return result
    
    async def scrape_subcategory(self, subcategory: Dict) -> Dict:
        """
        Determine the case and scrape accordingly
        """
        category_type = subcategory.get("category_type", "")
        
        # Check for Case 3 first (catChilds)
        catchilds = await self.scraper.get_catchilds(subcategory["slug"])
        if catchilds:
            return await self.scrape_case3_catchilds(subcategory)
        
        # Check for Case 1 (district filtration)
        if category_type == "listings_district_filteration" or category_type == "listings_full_filtration":
            return await self.scrape_case1_district_filtration(subcategory)
        
        # Default to Case 2 (direct listings)
        return await self.scrape_case2_direct_listings(subcategory)
    
    async def scrape_all_subcategories(self) -> List[Dict]:
        """
        Scrape all furniture subcategories from the main page
        """
        try:
            logger.info("Fetching furniture subcategories...")
            subcategories = await self.scraper.get_subcategories()
            
            if not subcategories:
                logger.error("No subcategories found!")
                return []
            
            logger.info(f"Found {len(subcategories)} subcategories")
            
            all_results = []
            for i, subcat in enumerate(subcategories, 1):
                logger.info(f"\n{'='*80}")
                logger.info(f"[{i}/{len(subcategories)}] Processing: {subcat['name_ar']} ({subcat['slug']})")
                logger.info(f"{'='*80}")
                
                result = await self.scrape_subcategory(subcat)
                all_results.append(result)
                
                if len(subcategories) > i:
                    await asyncio.sleep(2)  # Rate limiting between subcategories
            
            return all_results
            
        except Exception as e:
            logger.error(f"Error scraping subcategories: {e}")
            return []
    
    async def save_subcategory_to_excel(self, result: Dict) -> Optional[Dict]:
        """
        Save a single subcategory to its own Excel file
        Creates separate sheets for districts or catchilds
        
        Returns:
            Dictionary with upload info or None if failed
        """
        try:
            subcategory = result["subcategory"]
            subcat_slug = subcategory["slug"]
            subcat_name = subcategory["name_ar"]
            
            # Sanitize filename
            safe_filename = subcat_slug.replace("/", "-")
            temp_excel = self.temp_dir / f"{safe_filename}_temp.xlsx"
            
            with pd.ExcelWriter(temp_excel, engine='openpyxl') as writer:
                # Create Info sheet with summary
                info_data = [{
                    "Project": "Furniture",
                    "Category": subcat_name,
                    "Category Type": subcategory.get("category_type", ""),
                    "Total Listings": result.get("total_listings", 0),
                    "Data Scraped Date": self.scrape_date.strftime('%Y-%m-%d'),
                    "Saved to R2 Date": self.save_date.strftime('%Y-%m-%d'),
                }]
                pd.DataFrame(info_data).to_excel(writer, sheet_name='Info', index=False)
                logger.info(f"  Created sheet: Info")
                
                # Case 1: District filtration
                if "district_data" in result and result["district_data"]:
                    # Main sheet
                    if result.get("main_listings"):
                        df_main = pd.DataFrame(result["main_listings"])
                        df_main.to_excel(writer, sheet_name='Main', index=False)
                        logger.info(f"  Created sheet: Main ({len(result['main_listings'])} listings)")
                    
                    # District sheets
                    for district_data in result["district_data"]:
                        if district_data["listings"]:
                            district = district_data["district"]
                            sheet_name = district.get("name_ar", "District")[:31]
                            
                            df_district = pd.DataFrame(district_data["listings"])
                            df_district.to_excel(writer, sheet_name=sheet_name, index=False)
                            logger.info(f"  Created sheet: {sheet_name} ({len(district_data['listings'])} listings)")
                
                # Case 3: CatChilds
                elif "catchild_data" in result and result["catchild_data"]:
                    for catchild_data in result["catchild_data"]:
                        if catchild_data["listings"]:
                            catchild = catchild_data["catchild"]
                            sheet_name = catchild.get("name_ar", "CatChild")[:31]
                            
                            df_catchild = pd.DataFrame(catchild_data["listings"])
                            df_catchild.to_excel(writer, sheet_name=sheet_name, index=False)
                            logger.info(f"  Created sheet: {sheet_name} ({len(catchild_data['listings'])} listings)")
                
                # Case 2: Direct listings (single sheet)
                elif "listings" in result and result["listings"]:
                    df_listings = pd.DataFrame(result["listings"])
                    df_listings.to_excel(writer, sheet_name='Listings', index=False)
                    logger.info(f"  Created sheet: Listings ({len(result['listings'])} listings)")
            
            # Upload to R2
            R2_excel_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(temp_excel),
                f"excel-files/{safe_filename}.xlsx",
                self.save_date,
                retries=3
            )
            
            if R2_excel_path:
                R2_url = self.R2_helper.generate_R2_url(R2_excel_path)
                logger.info(f"[OK] Uploaded: {safe_filename}.xlsx ({result['total_listings']} listings)")

                json_version_payload = {
                    "subcategory": result.get("subcategory", {}),
                    "main_listings": result.get("main_listings", []),
                    "district_data": result.get("district_data", []),
                    "catchild_data": result.get("catchild_data", []),
                    "listings": result.get("listings", []),
                    "total_listings": result.get("total_listings", 0),
                }
                temp_json_version = self.temp_dir / f"{safe_filename}_temp.json"
                with open(temp_json_version, 'w', encoding='utf-8') as jf:
                    json.dump(json_version_payload, jf, ensure_ascii=False, indent=2)

                R2_json_version_path = await asyncio.to_thread(
                    self.R2_helper.upload_file,
                    str(temp_json_version),
                    f"json version/{safe_filename}.json",
                    self.save_date,
                    retries=3
                )
                if R2_json_version_path:
                    logger.info(f"[OK] Uploaded JSON version: {safe_filename}.json")
                temp_json_version.unlink(missing_ok=True)
                
                temp_excel.unlink(missing_ok=True)
                
                return {
                    "name": subcat_name,
                    "slug": subcat_slug,
                    "filename": f"{safe_filename}.xlsx",
                    "total_listings": result["total_listings"],
                    "R2_path": R2_excel_path,
                    "R2_url": R2_url,
                    "json_R2_path": R2_json_version_path,
                }
            
            temp_excel.unlink(missing_ok=True)
            return None
            
        except Exception as e:
            logger.error(f"Error saving Excel for {result['subcategory']['name_ar']}: {e}")
            return None
    
    async def save_all_to_R2(self, results: List[Dict]) -> Dict:
        """
        Save all data to R2 with proper partitioning
        Creates a separate Excel file for each subcategory
        """
        upload_summary = {
            "excel_files": [],
            "json_files": [],
            "total_subcategories": len(results),
            "total_listings": 0,
            "upload_time": datetime.now().isoformat()
        }
        
        try:
            total_listings = sum(r.get("total_listings", 0) for r in results)
            upload_summary["total_listings"] = total_listings
            
            if total_listings == 0:
                logger.warning("No data to upload!")
                return upload_summary
            
            logger.info("\nUploading to AWS R2...")
            
            # Create separate Excel file for each subcategory
            for result in results:
                if result.get("total_listings", 0) > 0:
                    logger.info(f"\nCreating Excel file for '{result['subcategory']['name_ar']}'...")
                    upload_info = await self.save_subcategory_to_excel(result)
                    if upload_info:
                        upload_summary["excel_files"].append(upload_info)
            
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
                if result.get("total_listings", 0) > 0:
                    subcategory = result["subcategory"]
                    json_summary["subcategories"].append({
                        "name_ar": subcategory["name_ar"],
                        "name_en": subcategory["name_en"],
                        "slug": subcategory["slug"],
                        "total_listings": result.get("total_listings", 0),
                        "category_type": subcategory.get("category_type"),
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
    """Main entry point for the furniture scraper"""
    orchestrator = None
    
    try:
        bucket_name = os.environ.get("CF_R2_BUCKET_NAME")
        profile_name = os.environ.get("AWS_PROFILE", None)
        
        logger.info("\n" + "="*80)
        logger.info("FURNITURE SCRAPER STARTING")
        logger.info("="*80)
        logger.info(f"Bucket: {bucket_name}")
        logger.info(f"Mode: Scrape ALL available pages per subcategory")
        logger.info(f"Each subcategory gets its own Excel file")
        logger.info(f"Districts/CatChilds appear as separate sheets")
        
        orchestrator = FurnitureScraperOrchestrator(bucket_name=bucket_name, profile_name=profile_name)
        await orchestrator.initialize()
        orchestrator.start_time = time.time()
        
        logger.info("\nStarting scraping...")
        results = await orchestrator.scrape_all_subcategories()
        
        if results:
            logger.info("\n" + "="*80)
            logger.info("UPLOADING TO R2")
            logger.info("="*80)
            
            upload_summary = await orchestrator.save_all_to_R2(results)
            
            logger.info("\n" + "="*80)
            logger.info("SCRAPING COMPLETED")
            logger.info("="*80)
            logger.info(f"Excel files uploaded: {len(upload_summary['excel_files'])}")
            logger.info(f"Total subcategories: {upload_summary['total_subcategories']}")
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


