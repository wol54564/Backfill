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


class EducationJsonScraper:
    """
    Scrapes Q84Sale education listings using JSON data from __NEXT_DATA__ script tag
    Handles two cases:
    - Case 1: Categories with direct listings (e.g., school-supplies)
    - Case 2: Categories with child categories (e.g., languages ? arabic-teaching, english-teaching, etc.)
    """
    
    def __init__(self):
        self.base_url = "https://www.q84sale.com/ar/education"
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
    
    async def get_vertical_subcategories(self) -> List[Dict]:
        """
        Get all vertical subcategories from the education main page
        Returns verticalSubcats
        """
        try:
            logger.info("Fetching education vertical subcategories...")
            url = self.base_url
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
                logger.warning("No verticalSubcats found in education page")
                return []
            
            subcategories = []
            for child in vertical_subcats:
                subcategories.append({
                    "id": child.get("id"),
                    "slug": child.get("slug"),
                    "name_ar": child.get("name_ar"),
                    "name_en": child.get("name_en"),
                    "listings_count": child.get("listings_count"),
                    "slug_url": child.get("slug_url"),
                    "category_type": child.get("category_type"),
                })
            
            logger.info(f"Found {len(subcategories)} vertical subcategories")
            for subcat in subcategories:
                logger.info(f"  - {subcat['name_ar']} ({subcat['slug']}) - {subcat['listings_count']} listings - Type: {subcat['category_type']}")
            
            return subcategories
            
        except Exception as e:
            logger.error(f"Error getting vertical subcategories: {e}")
            return []
    
    async def get_child_categories(self, subcategory_slug: str) -> List[Dict]:
        """
        Get child categories (catChilds) for a specific subcategory
        
        Args:
            subcategory_slug: The slug of the category (e.g., 'languages')
            
        Returns:
            List of child categories or empty list if none found
        """
        try:
            url = f"{self.base_url}/{subcategory_slug}/1"
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.warning(f"Failed to fetch data for {subcategory_slug}")
                return []
            
            # Extract catChilds from the JSON structure
            cat_childs = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("catChilds", [])
            )
            
            if not cat_childs:
                logger.info(f"No catChilds found for {subcategory_slug} (direct listings case)")
                return []
            
            children = []
            for child in cat_childs:
                children.append({
                    "id": child.get("id"),
                    "slug": child.get("slug"),
                    "name_ar": child.get("name_ar"),
                    "name_en": child.get("name_en"),
                    "listings_count": child.get("listings_count"),
                    "slug_url": child.get("slug_url"),
                    "category_type": child.get("category_type"),
                    "category_parent_slug": child.get("category_parent_slug"),
                })
            
            logger.info(f"Found {len(children)} child categories for {subcategory_slug}")
            for child in children:
                logger.info(f"  - {child['name_ar']} ({child['slug']}) - {child['listings_count']} listings")
            
            return children
            
        except Exception as e:
            logger.error(f"Error getting child categories for {subcategory_slug}: {e}")
            return []
    
    async def get_listings(self, category_slug: str, page_num: int = 1, filter_yesterday: bool = False) -> tuple:
        """
        Get all listings for a specific category (either direct or child category)
        
        Args:
            category_slug: The slug of the category
            page_num: Page number (default 1)
            filter_yesterday: If True, only returns listings from yesterday
        
        Returns:
            Tuple of (listings, total_pages)
        """
        try:
            # Build URL - check if it's a child category (contains slash) or direct category
            if "/" in category_slug:
                # Child category like "education/languages/arabic-teaching/1"
                url = f"{self.base_url}/{category_slug}/{page_num}"
            else:
                # Direct category like "education/school-supplies/1"
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
                    "desc_ar": listing.get("desc_ar"),
                    "desc_en": listing.get("desc_en"),
                })
            
            logger.info(f"Found {len(formatted_listings)} listings on page {page_num} (Total Pages: {total_pages})")
            return formatted_listings, total_pages
            
        except Exception as e:
            logger.error(f"Error getting listings for {category_slug}: {e}")
            return [], 0
    
    async def get_listing_details(self, slug: str, status: str = "normal") -> Optional[Dict]:
        """
        Get detailed information for a specific listing
        Extracts comprehensive data including user info, district, and all attributes
        
        Args:
            slug: The slug of the listing
            status: Status of the listing (e.g., 'normal')
        
        Returns:
            Dictionary with detailed listing information or None
        """
        try:
            # Build URL for listing details
            url = f"https://www.q84sale.com/ar/listing/{slug}"
            
            logger.info(f"Fetching details from {url}...")
            
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.warning(f"Failed to fetch details for {slug}")
                return None
            
            # Extract listing details from pageProps
            listing = json_data.get("props", {}).get("pageProps", {}).get("listing", {})
            
            if not listing:
                logger.warning(f"No listing details found for {slug}")
                return None
            
            # Extract images - directly from images field
            images = listing.get("images", [])
            
            if not images:
                # Try alternative field names
                images = listing.get("thumbs", []) or listing.get("thumbs_list", [])
                if images and isinstance(images[0], str) and "resize450" in images[0]:
                    # Convert resize450 to resize1000 for full size
                    images = [img.replace("resize450", "resize1000") if isinstance(img, str) else img for img in images]
            
            logger.info(f"Found {len(images)} images for {slug}")
            
            # Get date information
            date_published = listing.get("date_published")
            relative_date = self.format_relative_date(date_published) if date_published else "Unknown"
            
            # Return comprehensive detailed listing information
            # Use user_adv_id as the primary ID (like Wanted Cars does)
            listing_id = listing.get("user_adv_id") or listing.get("id")
            
            result = {
                "id": listing_id,
                "user_adv_id": listing_id,
                "title": listing.get("title"),
                "slug": listing.get("slug"),
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
                "user_name": listing.get("user", {}).get("first_name") or listing.get("user", {}).get("name"),
                "user_email": listing.get("user", {}).get("email"),
                "user_phone": listing.get("user", {}).get("phone"),
                "user_id": listing.get("user", {}).get("user_id"),
                "user_ads": f"{listing.get('user', {}).get('listings_count')} ads",
                "user_image": listing.get("user", {}).get("image"),
                "user_type": listing.get("user", {}).get("user_type"),
                "membership": listing.get("user", {}).get("member_since", "").split("T")[0] if listing.get("user", {}).get("member_since") else None,
                "is_verified": listing.get("user", {}).get("is_verified"),
                "is_private_message_enabled": listing.get("is_private_message_enabled"),
                "is_hide_my_number": listing.get("is_hide_my_number"),
                "category": listing.get("category", {}).get("name"),
                "status": status,
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting listing details for {slug}: {e}")
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
    
    async def download_image(self, image_url: str) -> Optional[bytes]:
        """
        Download an image from URL using aiohttp
        
        Args:
            image_url: URL of the image to download
            
        Returns:
            Image bytes or None if failed
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=30) as response:
                    if response.status == 200:
                        logger.debug(f"Downloaded image: {image_url}")
                        return await response.read()
                    else:
                        logger.warning(f"Failed to download image {image_url}: Status {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading image {image_url}: {e}")
            return None
