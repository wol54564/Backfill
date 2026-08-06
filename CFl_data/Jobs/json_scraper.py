import json
import asyncio
import aiohttp
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import get_random_headers, random_delay, rotate_user_agent, configure_session_proxy, create_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobsJsonScraper:
    """
    Scrapes Q84Sale jobs listings using JSON data from __NEXT_DATA__ script tag
    This approach is fast and reliable using BeautifulSoup4 to extract JSON from HTML
    Handles two main subcategories: Job Openings and Job Seeker
    Each has multiple catChilds (subcategories like Part Time Job, Accounting, etc.)
    """
    
    def __init__(self):
        self.base_url = "https://www.q84sale.com/ar/jobs"
        self.session = create_session()
        
    async def init_browser(self):
        """Compatibility method - not needed with BeautifulSoup"""
        pass
    
    async def close_browser(self):
        """Compatibility method - cleanup session"""
        if self.session:
            self.session.close()
    
    async def get_page_json_data(self, url: str) -> Optional[Dict]:
        """
        Extract JSON data from __NEXT_DATA__ script tag using BeautifulSoup
        Returns parsed JSON or None if not found
        """
        try:
            logger.info(f"Fetching {url}...")
            random_delay(1.0, 3.0)  # Random delay before request
            rotate_user_agent(self.session)  # Rotate user agent
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the __NEXT_DATA__ script tag
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if script and script.string:
                return json.loads(script.string)
            
            logger.warning(f"No __NEXT_DATA__ found on {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching JSON from {url}: {e}")
            return None
    
    async def get_main_subcategories(self) -> List[Dict]:
        """
        Get the main subcategories from the jobs main page
        Returns verticalSubcats: Job Openings and Job Seeker
        """
        try:
            logger.info("Fetching jobs main subcategories...")
            url = self.base_url  # Main page is not paginated
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.error("Failed to fetch main page JSON")
                return []
            
            # Extract verticalSubcats from the JSON structure
            vertical_subcats = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("verticalSubcats", [])
            )
            
            if not vertical_subcats:
                logger.warning("No verticalSubcats found in jobs page")
                return []
            
            subcategories = []
            for subcat in vertical_subcats:
                subcategories.append({
                    "id": subcat.get("id"),
                    "slug": subcat.get("slug"),
                    "name_ar": subcat.get("name_ar"),
                    "name_en": subcat.get("name_en"),
                    "listings_count": subcat.get("listings_count"),
                    "slug_url": subcat.get("slug_url"),
                    "category_parent_slug": subcat.get("category_parent_slug"),
                })
            
            logger.info(f"Found {len(subcategories)} main subcategories")
            for subcat in subcategories:
                logger.info(f"  - {subcat['name_ar']} ({subcat['slug']}) - {subcat['listings_count']} listings")
            
            return subcategories
            
        except Exception as e:
            logger.error(f"Error getting main subcategories: {e}")
            return []
    
    async def get_category_children(self, subcategory_slug: str) -> List[Dict]:
        """
        Get child categories (catChilds) for a specific main subcategory
        
        Args:
            subcategory_slug: The slug of the main category (e.g., 'job-openings')
        
        Returns:
            List of child categories
        """
        try:
            url = f"{self.base_url}/{subcategory_slug}/1"
            logger.info(f"Fetching child categories for {subcategory_slug}...")
            
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.warning(f"No data found for {url}")
                return []
            
            # Extract catChilds from the JSON response
            cat_childs = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("catChilds", [])
            )
            
            if not cat_childs:
                logger.warning(f"No catChilds found for {subcategory_slug}")
                return []
            
            children = []
            for child in cat_childs:
                children.append({
                    "id": child.get("id"),
                    "parent_id": child.get("parent_id"),
                    "slug": child.get("slug"),
                    "name_ar": child.get("name_ar"),
                    "name_en": child.get("name_en"),
                    "listings_count": child.get("listings_count"),
                    "slug_url": child.get("slug_url"),
                    "category_parent_slug": child.get("category_parent_slug"),
                })
            
            logger.info(f"Found {len(children)} child categories for {subcategory_slug}")
            for child in children:
                logger.info(f"  - {child['name_ar']} ({child['slug']}) - {child['listings_count']} listings")
            
            return children
            
        except Exception as e:
            logger.error(f"Error getting category children for {subcategory_slug}: {e}")
            return []
    
    async def get_listings(self, category_slug: str, page_num: int = 1, 
                          filter_yesterday: bool = False) -> tuple:
        """
        Get all listings for a specific jobs category
        
        Args:
            category_slug: The slug of the category (e.g., 'jobs/job-openings/part-time-job')
            page_num: Page number (default 1)
            filter_yesterday: If True, only returns listings from yesterday
        
        Returns:
            Tuple of (listings, total_pages)
        """
        try:
            # Build URL using the category slug
            url = f"{self.base_url}/{category_slug}/{page_num}"
            logger.info(f"Fetching listings for {category_slug} page {page_num}...")
            
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.warning(f"No data found for {url}")
                return [], 0
            
            # Extract totalPages from the JSON response
            page_props = json_data.get("props", {}).get("pageProps", {})
            total_pages = page_props.get("totalPages", 0)
            
            # Extract listings from the JSON structure
            listings = page_props.get("listings", [])
            
            # Get yesterday's date for filtering
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            formatted_listings = []
            for listing in listings:
                # Skip ad boxes
                if listing.get("adBoxId"):
                    continue
                
                # Filter by yesterday if requested
                if filter_yesterday:
                    date_published = listing.get("date_published", "")
                    if not date_published.startswith(yesterday):
                        continue
                
                formatted_listings.append({
                    "id": listing.get("id"),
                    "title": listing.get("title"),
                    "slug": listing.get("slug"),
                    "price": listing.get("price"),
                    "image": listing.get("image"),
                    "date_published": listing.get("date_published"),
                    "cat_id": listing.get("cat_id"),
                    "cat_name_en": listing.get("cat_en_name"),
                    "cat_name_ar": listing.get("cat_ar_name"),
                    "user_id": listing.get("user", {}).get("user_id"),
                    "user_name": listing.get("user", {}).get("name"),
                    "phone": listing.get("phone"),
                    "contact_no": listing.get("contact_no"),
                    "district_name": listing.get("district_name"),
                    "status": listing.get("status"),
                    "images_count": listing.get("images_count"),
                    "description": listing.get("description"),
                    "desc_en": listing.get("desc_en"),
                    "desc_ar": listing.get("desc_ar"),
                })
            
            logger.info(f"Found {len(formatted_listings)} listings on page {page_num} (Total Pages: {total_pages})")
            return formatted_listings, total_pages
            
        except Exception as e:
            logger.error(f"Error getting listings for {category_slug}: {e}")
            return [], 0
    
    async def get_listing_details(self, listing_slug: str, status: str = "normal") -> Optional[Dict]:
        """
        Get detailed information for a specific listing
        
        Args:
            listing_slug: The slug of the listing
            status: Status of the listing
        
        Returns:
            Dictionary with listing details or None if failed
        """
        try:
            # Listing detail pages use /ar/listing/ not /ar/jobs/
            url = f"https://www.q84sale.com/ar/listing/{listing_slug}"
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.warning(f"No data found for {url}")
                return None
            
            # Extract listing from the JSON response
            listing = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("listing", {})
            )
            
            if not listing:
                logger.warning(f"No listing data found for {listing_slug}")
                return None
            
            # Extract and format the details - matching Wanted Cars format
            date_published = listing.get("date_published", "")
            relative_date = self.format_relative_date(date_published) if date_published else "Unknown"
            images = listing.get("images", [])
            
            details = {
                "id": listing.get("user_adv_id"),
                "slug": listing.get("slug"),
                "title": listing.get("title"),
                "description": listing.get("description"),
                "price": listing.get("price"),
                "phone": listing.get("phone"),
                "date_published": date_published,
                "date_relative": relative_date,
                "date_created": listing.get("date_created"),
                "date_expired": listing.get("date_expired"),
                "date_sort": listing.get("date_sort"),
                "images": images,
                "images_count": len(images),
                "address": listing.get("district", {}).get("name"),
                "full_address": listing.get("district", {}).get("full_path"),
                "full_address_en": listing.get("district", {}).get("full_path_en"),
                "views_no": listing.get("user_view_count"),
                "longitude": listing.get("lon"),
                "latitude": listing.get("lat"),
                "user_name": listing.get("user", {}).get("first_name"),
                "user_email": listing.get("user", {}).get("email"),
                "user_phone": listing.get("user", {}).get("phone"),
                "user_ads": f"{listing.get('user', {}).get('listings_count')} ads",
                "user_image": listing.get("user", {}).get("image"),
                "user_type": listing.get("user", {}).get("user_type"),
                "membership": listing.get("user", {}).get("member_since", "").split("T")[0],
                "is_verified": listing.get("user", {}).get("is_verified"),
                "is_private_message_enabled": listing.get("is_private_message_enabled"),
                "is_hide_my_number": listing.get("is_hide_my_number"),
                "category": listing.get("category", {}).get("name"),
                "status": status,
            }
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting listing details for {listing_slug}: {e}")
            return None
    
    async def download_image(self, image_url: str) -> Optional[bytes]:
        """
        Download image data from URL
        
        Args:
            image_url: URL of the image
        
        Returns:
            Image data or None if failed
        """
        try:
            response = self.session.get(image_url, timeout=60)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.warning(f"Failed to download image from {image_url}: {e}")
            return None
    
    def format_relative_date(self, date_str: str) -> str:
        """
        Format a date string to relative format (e.g., '2 days ago')
        
        Args:
            date_str: Date string in format 'YYYY-MM-DD HH:MM:SS'
        
        Returns:
            Relative date string
        """
        try:
            published = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            diff = relativedelta(now, published)
            
            if diff.years > 0:
                return f"{diff.years} year{'s' if diff.years > 1 else ''} ago"
            if diff.months > 0:
                return f"{diff.months} month{'s' if diff.months > 1 else ''} ago"
            if diff.days > 0:
                return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
            if diff.hours > 0:
                return f"{diff.hours} hour{'s' if diff.hours > 1 else ''} ago"
            if diff.minutes > 0:
                return f"{diff.minutes} minute{'s' if diff.minutes > 1 else ''} ago"
            return "Just now"
        except Exception as e:
            logger.warning(f"Error formatting date {date_str}: {e}")
            return "Unknown"
