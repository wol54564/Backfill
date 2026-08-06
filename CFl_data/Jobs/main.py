import asyncio
import pandas as pd
import json
import logging
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from json_scraper import JobsJsonScraper
from s3_helper import R2Helper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class JobsScraperOrchestrator:
    """
    Orchestrates the scraping of jobs data with AWS R2 integration
    Scrapes main subcategories: Job Openings, Job Seeker
    Each main subcategory has multiple child categories (Part Time Job, Accounting, etc.)
    Creates separate Excel files for each main subcategory with sheets for each child category
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
        self.scraper = JobsJsonScraper()
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
    
    async def scrape_child_category(self, main_subcat: Dict, child_category: Dict) -> Dict:
        """
        Scrape a child category with listings and detailed information
        Automatically scrapes all available pages returned by the API
        
        Args:
            main_subcat: Main subcategory dictionary (Job Openings, Job Seeker)
            child_category: Child category dictionary
            
        Returns:
            Dictionary with scraped data
        """
        # Build the full slug path: jobs/job-openings/part-time-job
        full_slug = f"{main_subcat['slug']}/{child_category['slug']}"
        logger.info(f"  Processing: {child_category['name_ar']} ({full_slug})")
        
        result = {
            "child_category": child_category,
            "listings": [],
            "total_pages": 0
        }
        
        try:
            # Fetch all pages for this child category
            page_num = 1
            child_listings = []
            total_pages = 0
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            while True:
                listings, total_pages = await self.scraper.get_listings(
                    full_slug, 
                    page_num=page_num,
                    filter_yesterday=False
                )
                
                if not listings:
                    logger.info(f"  No listings found on page {page_num}, stopping pagination")
                    break
                
                yesterday_listings = [l for l in listings if l.get("date_published", "").startswith(yesterday)]
                found_older = any(l.get("date_published", "")[:10] < yesterday for l in listings if l.get("date_published", ""))
                
                if yesterday_listings:
                    logger.info(f"  Fetching detailed information for {len(yesterday_listings)} listings on page {page_num}/{total_pages}...")
                    # Pass only the main category slug for image organization (not the full nested path)
                    detailed_listings = await self.fetch_listing_details_batch(yesterday_listings, main_subcat['slug'])
                    child_listings.extend(detailed_listings)
                
                if found_older or page_num >= total_pages:
                    break
                
                page_num += 1
                await asyncio.sleep(1)  # Rate limiting between pages
            
            result["listings"] = child_listings
            result["total_pages"] = total_pages
            
            logger.info(f"  Total listings for {child_category['name_ar']}: {len(child_listings)} (across {page_num - 1} pages)")
            return result
            
        except Exception as e:
            logger.error(f"Error processing {child_category['name_ar']}: {e}")
            return result
    
    async def scrape_main_subcategory(self, main_subcat: Dict) -> Dict:
        """
        Scrape a main subcategory with all its child categories
        
        Args:
            main_subcat: Main subcategory dictionary (Job Openings, Job Seeker)
            
        Returns:
            Dictionary with main subcategory and all child categories data
        """
        logger.info(f"\nProcessing Main Subcategory: {main_subcat['name_ar']} ({main_subcat['slug']})")
        
        result = {
            "main_subcategory": main_subcat,
            "child_categories": [],
            "total_listings": 0
        }
        
        try:
            # Get child categories for this main subcategory
            logger.info(f"Fetching child categories for {main_subcat['name_ar']}...")
            child_categories = await self.scraper.get_category_children(main_subcat['slug'])
            
            if not child_categories:
                logger.warning(f"No child categories found for {main_subcat['name_ar']}")
                return result
            
            logger.info(f"Found {len(child_categories)} child categories")
            
            # Scrape each child category
            all_child_results = []
            for i, child_cat in enumerate(child_categories, 1):
                logger.info(f"\n[{i}/{len(child_categories)}] Processing child category...")
                
                child_result = await self.scrape_child_category(main_subcat, child_cat)
                all_child_results.append(child_result)
                
                if i < len(child_categories):
                    await asyncio.sleep(1)  # Rate limiting between categories
            
            result["child_categories"] = all_child_results
            result["total_listings"] = sum(len(r["listings"]) for r in all_child_results)
            
            logger.info(f"\nCompleted {main_subcat['name_ar']}: {result['total_listings']} total listings across {len(all_child_results)} child categories")
            return result
            
        except Exception as e:
            logger.error(f"Error scraping main subcategory {main_subcat['name_ar']}: {e}")
            return result
    
    async def scrape_all_subcategories(self) -> List[Dict]:
        """
        Scrape all jobs main subcategories with their child categories
        Main subcategories: Job Openings, Job Seeker
        """
        try:
            logger.info("Fetching jobs main subcategories...")
            main_subcategories = await self.scraper.get_main_subcategories()
            
            if not main_subcategories:
                logger.error("No main subcategories found!")
                return []
            
            logger.info(f"Found {len(main_subcategories)} main subcategories")
            
            all_results = []
            for i, main_subcat in enumerate(main_subcategories, 1):
                logger.info(f"\n[{i}/{len(main_subcategories)}] {main_subcat['name_ar']}")
                
                result = await self.scrape_main_subcategory(main_subcat)
                all_results.append(result)
                
                if i < len(main_subcategories):
                    await asyncio.sleep(2)  # Rate limiting between main subcategories
            
            return all_results
            
        except Exception as e:
            logger.error(f"Error scraping main subcategories: {e}")
            return []
    
    async def save_all_to_R2(self, results: List[Dict]) -> Dict:
        """
        Save all data to R2 with proper partitioning
        Creates separate Excel files for each main subcategory
        Each Excel file has sheets for each child category with summary
        """
        upload_summary = {
            "excel_files": [],
            "json_files": [],
            "total_listings": 0,
            "total_main_subcategories": len(results),
            "upload_time": datetime.now().isoformat()
        }
        
        try:
            total_listings = sum(r["total_listings"] for r in results)
            upload_summary["total_listings"] = total_listings
            
            if total_listings == 0:
                logger.warning("No data to upload!")
                return upload_summary
            
            logger.info("\nUploading to AWS R2...")
            
            # Create separate Excel file for each main subcategory
            for result in results:
                if result["total_listings"] == 0:
                    logger.warning(f"No listings for {result['main_subcategory']['name_ar']}, skipping...")
                    continue
                
                main_subcat = result["main_subcategory"]
                main_subcat_name = main_subcat["name_ar"]
                main_subcat_slug = main_subcat["slug"]
                
                logger.info(f"\nCreating Excel file for '{main_subcat_name}'...")
                
                temp_excel = self.temp_dir / f"{main_subcat_slug}_temp.xlsx"
                
                with pd.ExcelWriter(temp_excel, engine='openpyxl') as writer:
                    # Create Info sheet with summary
                    info_data = [{
                        "Project": "Jobs",
                        "Main Category": main_subcat_name,
                        "Main Category (EN)": main_subcat["name_en"],
                        "Total Child Categories": len(result["child_categories"]),
                        "Total Listings": result["total_listings"],
                        "Data Scraped Date": self.scrape_date.strftime('%Y-%m-%d'),
                        "Saved to R2 Date": self.save_date.strftime('%Y-%m-%d'),
                    }]
                    pd.DataFrame(info_data).to_excel(writer, sheet_name='Info', index=False)
                    
                    # Create a sheet for each child category
                    for child_result in result["child_categories"]:
                        if child_result["listings"]:
                            child_cat = child_result["child_category"]
                            # Sanitize sheet name (max 31 chars in Excel)
                            sheet_name = child_cat["name_ar"][:31] if len(child_cat["name_ar"]) <= 31 else child_cat["name_ar"][:28] + "..."
                            
                            df = pd.DataFrame(child_result["listings"])
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                            logger.info(f"  Created sheet: {sheet_name} ({len(child_result['listings'])} listings)")
                
                # Upload excel to R2
                excel_filename = f"{main_subcat_slug}.xlsx"
                R2_excel_path = await asyncio.to_thread(
                    self.R2_helper.upload_file,
                    str(temp_excel),
                    f"excel-files/{excel_filename}",
                    self.save_date,
                    retries=3
                )
                
                if R2_excel_path:
                    R2_url = self.R2_helper.generate_R2_url(R2_excel_path)
                    upload_summary["excel_files"].append({
                        "name": main_subcat_slug,
                        "main_category": main_subcat_name,
                        "child_categories_count": len(result["child_categories"]),
                        "total_listings": result["total_listings"],
                        "R2_path": R2_excel_path,
                        "R2_url": R2_url
                    })
                    logger.info(f"[OK] Uploaded: {excel_filename} ({result['total_listings']} listings across {len(result['child_categories'])} child categories)")

                json_version_payload = {
                    "main_subcategory": result.get("main_subcategory", {}),
                    "child_categories": [
                        {
                            "child_category": child_result.get("child_category", {}),
                            "listings": child_result.get("listings", []),
                        }
                        for child_result in result.get("child_categories", [])
                        if child_result.get("listings")
                    ],
                }
                json_version_file = self.temp_dir / f"{main_subcat_slug}_json_version_temp.json"
                with open(json_version_file, 'w', encoding='utf-8') as jf:
                    json.dump(json_version_payload, jf, ensure_ascii=False, indent=2)

                R2_json_version_path = await asyncio.to_thread(
                    self.R2_helper.upload_file,
                    str(json_version_file),
                    f"json version/{main_subcat_slug}.json",
                    self.save_date,
                    retries=3
                )
                if R2_json_version_path:
                    upload_summary["json_files"].append(R2_json_version_path)
                    logger.info(f"[OK] Uploaded JSON version: {main_subcat_slug}.json")
                json_version_file.unlink(missing_ok=True)
                
                temp_excel.unlink(missing_ok=True)
            
            # Save upload summary as JSON
            duration_sec = time.time() - self.start_time if self.start_time else 0
            session_requests_total = int(getattr(getattr(self.scraper, "session", None), "request_count", 0) or 0)
            effective_requests_total = max(getattr(self, "requests_total", 0), session_requests_total)
            effective_requests_failed = getattr(self, "requests_failed", 0)
            error_rate_pct = (effective_requests_failed / effective_requests_total * 100.0) if effective_requests_total > 0 else 0.0
            requests_per_min = (effective_requests_total / (duration_sec / 60.0)) if duration_sec > 0 else 0.0
            upload_summary["request_metrics"] = {
                "requests_total": effective_requests_total,
                "requests_failed": effective_requests_failed,
                "error_rate_pct": round(error_rate_pct, 2),
                "requests_per_min": round(requests_per_min, 2),
                "duration_sec": round(duration_sec, 2),
            }
            summary_file = self.temp_dir / "upload_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(upload_summary, f, indent=2, ensure_ascii=False)
            
            R2_summary_path = await asyncio.to_thread(
                self.R2_helper.upload_file,
                str(summary_file),
                "json-files/upload-summary.json",
                self.save_date,
                retries=3
            )
            
            if R2_summary_path:
                upload_summary["summary_json"] = {
                    "R2_path": R2_summary_path,
                    "R2_url": self.R2_helper.generate_R2_url(R2_summary_path)
                }
                logger.info(f"[OK] Uploaded: upload-summary.json")
            
            summary_file.unlink(missing_ok=True)
            
            # Print final summary
            logger.info("\n" + "="*60)
            logger.info("UPLOAD SUMMARY")
            logger.info("="*60)
            logger.info(f"Total Excel Files: {len(upload_summary['excel_files'])}")
            logger.info(f"Total Listings: {upload_summary['total_listings']}")
            logger.info(f"Main Subcategories: {upload_summary['total_main_subcategories']}")
            logger.info(f"Upload Time: {upload_summary['upload_time']}")
            logger.info("="*60)
            
            return upload_summary
            
        except Exception as e:
            logger.error(f"Error Saving to R2: {e}")
            return upload_summary
    
    async def run(self) -> Dict:
        """
        Main execution method - orchestrates the entire scraping and uploading process
        """
        try:
            await self.initialize()
            self.start_time = time.time()
            
            # Scrape all data
            logger.info("Starting Jobs scraper...")
            results = await self.scrape_all_subcategories()
            
            if not results:
                logger.error("No results to save!")
                return {"error": "No data scraped"}
            
            # Save to R2
            upload_summary = await self.save_all_to_R2(results)
            
            return upload_summary
            
        except Exception as e:
            logger.error(f"Error in main execution: {e}")
            return {"error": str(e)}
        
        finally:
            await self.cleanup()


async def main():
    """
    Main entry point - configure your R2 bucket name and AWS profile here
    """
    # Configure these values
    BUCKET_NAME = os.environ.get("CF_R2_BUCKET_NAME")
    
    orchestrator = JobsScraperOrchestrator(
        bucket_name=BUCKET_NAME,
    )
    
    result = await orchestrator.run()
    
    logger.info("\nFinal Result:")
    logger.info(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())


