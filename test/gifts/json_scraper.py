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


class GiftsJsonScraper:
    """
    Scrapes Q84Sale gifts listings using JSON data from __NEXT_DATA__ script tag
    This approach is fast and reliable using BeautifulSoup4 to extract JSON from HTML
    Structure: Main category -> Subcategories (verticalSubcats) -> Listings (with pagination) -> Details
    """
    
    def __init__(self):
        self.base_url = "https://www.q84sale.com/ar/gifts"
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
    
    async def get_subcategories(self) -> List[Dict]:
        """
        Get all subcategories from the gifts main page
        Returns verticalSubcats: Men Clothes, Men Shoes, Ladies Clothes, etc.
        """
        try:
            logger.info("Fetching gifts subcategories...")
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
                logger.warning("No verticalSubcats found in gifts page")
                return []
            
            subcategories = []
            for subcat in vertical_subcats:
                subcategories.append({
                    "id": subcat.get("id"),
                    "slug": subcat.get("slug"),
                    "name_ar": subcat.get("name_ar"),
                    "name_en": subcat.get("name_en"),
                    "listings_count": subcat.get("listings_count"),
                    "parent_slug": subcat.get("category_parent_slug"),
                    "slug_url": subcat.get("slug_url"),
                    "image": subcat.get("image"),
                    "featured_image": subcat.get("featured_image"),
                    "category_type": subcat.get("category_type"),
                })
            
            logger.info(f"Found {len(subcategories)} subcategories")
            for subcat in subcategories:
                logger.info(f"  - {subcat['name_ar']} ({subcat['slug']}) - {subcat['listings_count']} listings")
            
            return subcategories
            
        except Exception as e:
            logger.error(f"Error getting subcategories: {e}")
            return []
    
    async def get_listings(self, subcategory_slug: str, page_num: int = 1, 
                          filter_yesterday: bool = False) -> tuple:
        """
        Get all listings for a specific gifts subcategory
        
        Args:
            subcategory_slug: The slug of the subcategory (e.g., 'men-clothes')
            page_num: Page number (default 1)
            filter_yesterday: If True, only returns listings from yesterday
        
        Returns:
            Tuple of (listings, total_pages)
        """
        try:
            # Build URL using the gifts parent slug
            url = f"{self.base_url}/{subcategory_slug}/{page_num}"
            logger.info(f"Fetching listings for {subcategory_slug} page {page_num}...")
            
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
                })
            
            logger.info(f"Found {len(formatted_listings)} listings on page {page_num} (Total Pages: {total_pages})")
            return formatted_listings, total_pages
            
        except Exception as e:
            logger.error(f"Error getting listings for {subcategory_slug}: {e}")
            return [], 0
    
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
    
    def extract_attributes(self, attrs_list: List[Dict]) -> Dict:
        """
        Extract and format attributes from listings
        
        Args:
            attrs_list: List of attribute dictionaries from the listing
        
        Returns:
            Dictionary with:
            - specification_en: Nested English attributes
            - specification_ar: Nested Arabic attributes
            - Plus individual flattened columns for each attribute
        """
        spec_en = {}
        spec_ar = {}
        flat_output = {}
        
        for item in attrs_list:
            attr = item.get("attrData", {})
            val = item.get("valData")
            name_en = attr.get("name_en")
            name_ar = attr.get("name_ar")
            attr_type = attr.get("type", "")
            
            value_en = None
            value_ar = None
            
            # Handle different value types
            if isinstance(val, dict):
                # Dictionary values (e.g., location objects)
                value_en = val.get("name_en")
                value_ar = val.get("name_ar")
            elif isinstance(val, str):
                # Check if attribute is numeric type
                if attr_type == "number":
                    value_en = val
                    value_ar = val
                else:
                    # For other string types, treat as boolean
                    value_en = "Yes" if val == "1" else "No"
                    value_ar = "???" if val == "1" else "??"
            else:
                continue
            
            if value_en and name_en:
                spec_en[name_en] = value_en
                flat_output[name_en] = value_en
            if value_ar and name_ar:
                spec_ar[name_ar] = value_ar
                flat_output[name_ar] = value_ar
        
        # Return nested columns + flattened individual columns
        result = {
            "specification_en": json.dumps(spec_en, ensure_ascii=False),
            "specification_ar": json.dumps(spec_ar, ensure_ascii=False),
        }
        # Add all flattened attributes
        result.update(flat_output)
        
        return result
    
    async def get_listing_details(self, slug: str, status: str = "normal") -> Optional[Dict]:
        """
        Get detailed information for a specific listing from the listing details page
        Uses the slug to construct the URL (e.g., men-clothes-20494669)
        
        Args:
            slug: Listing slug (e.g., 'men-clothes-20494669')
            status: Listing status (normal/pinned etc.)
        
        Returns:
            Detailed listing information or None if failed
        """
        try:
            url = f"https://www.q84sale.com/ar/listing/{slug}"
            logger.info(f"Fetching details from {url}")
            
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.warning(f"No data found for {url}")
                return None
            
            # Extract listing from the JSON structure
            listing = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("listing", {})
            )
            
            if not listing:
                logger.warning(f"No listing data found in {url}")
                return None
            
            # Extract images
            images = listing.get("images", [])
            
            # Get date information
            date_published = listing.get("date_published")
            relative_date = self.format_relative_date(date_published) if date_published else "Unknown"
            
            # Extract attributes with better formatting
            attrs_and_vals = listing.get("attrsAndVals", [])
            attributes = self.extract_attributes(attrs_and_vals)
            
            # Return detailed listing information
            result = {
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
            # Add attributes (both nested columns and flattened individual columns)
            result.update(attributes)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting listing details for {slug}: {e}")
            return None
    
    async def download_image(self, image_url: str) -> Optional[bytes]:
        """
        Download image from URL
        
        Args:
            image_url: URL of the image
        
        Returns:
            Image bytes or None if failed
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=30) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.warning(f"Failed to download image {image_url}: Status {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading image {image_url}: {e}")
            return None
