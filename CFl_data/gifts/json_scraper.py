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
    Scrapes Q84Sale gifts using JSON data from __NEXT_DATA__ script tag
    This approach is fast and reliable as it doesn't depend on dynamic CSS classes
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
        Get all gift subcategories from the main gifts page
        Returns list of subcategories with their info
        """
        try:
            logger.info("Fetching subcategories...")
            json_data = await self.get_page_json_data(self.base_url)
            
            if not json_data:
                logger.error("Failed to fetch main page JSON")
                return []
            
            # Extract verticalSubcats from the JSON structure
            vertical_subcats = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("verticalSubcats", [])
            )
            
            subcategories = []
            for subcat in vertical_subcats:
                subcategories.append({
                    "id": subcat.get("id"),
                    "slug": subcat.get("slug"),
                    "name_ar": subcat.get("name_ar"),
                    "name_en": subcat.get("name_en"),
                    "listings_count": subcat.get("listings_count"),
                    "has_districts": subcat.get("category_type") == "listings_district_filteration",
                    "slug_url": subcat.get("slug_url"),
                })
            
            logger.info(f"Found {len(subcategories)} subcategories")
            return subcategories
            
        except Exception as e:
            logger.error(f"Error getting subcategories: {e}")
            return []
    
    async def get_catchilds(self, subcategory_slug: str) -> List[Dict]:
        """
        Get child subcategories (catChilds) from a listings page
        Returns list of child subcategories if available
        """
        try:
            url = f"{self.base_url}/{subcategory_slug}/1"
            logger.info(f"Checking for child categories in {subcategory_slug}...")
            
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                return []
            
            # Extract catChilds from the JSON structure
            cat_childs = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("catChilds", [])
            )
            
            if cat_childs:
                logger.info(f"Found {len(cat_childs)} child categories")
                formatted_childs = []
                for child in cat_childs:
                    formatted_childs.append({
                        "id": child.get("id"),
                        "slug": child.get("slug"),
                        "name_ar": child.get("name_ar"),
                        "name_en": child.get("name_en"),
                        "listings_count": child.get("listings_count"),
                        "parent_slug": child.get("category_parent_slug"),
                    })
                return formatted_childs
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting child categories for {subcategory_slug}: {e}")
            return []
    
    async def get_listings(self, subcategory_slug: str, page_num: int = 1, 
                           child_slug: Optional[str] = None, district_slug: Optional[str] = None, 
                           filter_yesterday: bool = False) -> Dict:
        """
        Get all listings for a specific subcategory and optional child/district
        
        Args:
            subcategory_slug: The slug of the subcategory (e.g., 'dogs')
            page_num: Page number (default 1)
            child_slug: Optional child category slug (e.g., 'chickens' for birds category)
            district_slug: Optional district slug for filtering
            filter_yesterday: If True, only returns listings from yesterday (default False for gifts)
        
        Returns:
            Dict with 'listings' and 'pagination' info
        """
        try:
            if child_slug and district_slug:
                url = f"{self.base_url}/{subcategory_slug}/{child_slug}/{page_num}/{district_slug}"
                logger.info(f"Fetching listings for {subcategory_slug}/{child_slug}/{district_slug} page {page_num}...")
            elif child_slug:
                url = f"{self.base_url}/{subcategory_slug}/{child_slug}/{page_num}"
                logger.info(f"Fetching listings for {subcategory_slug}/{child_slug} page {page_num}...")
            elif district_slug:
                url = f"{self.base_url}/{subcategory_slug}/{page_num}/{district_slug}"
                logger.info(f"Fetching listings for {subcategory_slug}/{district_slug} page {page_num}...")
            else:
                url = f"{self.base_url}/{subcategory_slug}/{page_num}"
                logger.info(f"Fetching listings for {subcategory_slug} page {page_num}...")
            
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.warning(f"No data found for {url}")
                return {"listings": [], "pagination": {}}
            
            # Extract pagination info
            page_props = json_data.get("props", {}).get("pageProps", {})
            pagination = {
                "total_pages": page_props.get("total_pages", 1),
                "current_page": page_props.get("current_page", page_num),
                "total_count": page_props.get("total_count", 0)
            }
            
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
                    "title_ar": listing.get("title"),
                    "phone": listing.get("phone"),
                    "contact": listing.get("contact"),
                    "slug": listing.get("slug"),
                    "description_ar": listing.get("desc_ar"),
                    "description_en": listing.get("desc_en"),
                    "price": listing.get("price"),
                    "user_id": listing.get("user", {}).get("user_id"),
                    "user_name": listing.get("user", {}).get("name"),
                    "user_type": listing.get("user_type"),
                    "category_ar": listing.get("cat_ar_name"),
                    "category_en": listing.get("cat_en_name"),
                    "status": listing.get("status"),
                    "date_published": listing.get("date_published"),
                    "image_url": listing.get("image"),
                    "thumb_url": listing.get("thumb"),
                    "is_premium": listing.get("is_prem"),
                    "views_count": listing.get("views_count"),
                    "reactions": listing.get("reactions", {}).get("total_count", 0),
                    "district_name_ar": listing.get("district_name_localize", {}).get("ar"),
                    "district_name_en": listing.get("district_name_localize", {}).get("en"),
                    "images_count": listing.get("images_count"),
                    "all_images": listing.get("thumbs", []),  # All image URLs
                })
            
            logger.info(f"Found {len(formatted_listings)} listings on page {page_num}/{pagination['total_pages']} (filtered by yesterday={filter_yesterday})")
            return {"listings": formatted_listings, "pagination": pagination}
            
        except Exception as e:
            logger.error(f"Error getting listings from {url}: {e}")
            return {"listings": [], "pagination": {}}
    
    async def get_listing_details(self, listing_slug: str, status: Optional[str] = None) -> Optional[Dict]:
        """
        Get full details for a specific listing
        
        Args:
            listing_slug: The slug of the listing (e.g., 'dogs-20407319')
            status: Status from listings page (optional)
        
        Returns:
            Detailed listing information with attributes and metadata
        """
        try:
            url = f"https://www.q84sale.com/ar/listing/{listing_slug}"
            logger.info(f"Fetching details for {listing_slug}...")
            
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.warning(f"No data found for {listing_slug}")
                return None
            
            # Extract listing details from the JSON structure
            listing = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("listing", {})
            )
            
            if not listing:
                return None
            
            # Extract date and format relative date
            date_published = listing.get("date_published")
            relative_date = self.format_relative_date(date_published)
            
            # Extract images list
            images_list = listing.get("images", [])
            
            # Build base info
            base_info = {
                "id": listing.get("user_adv_id"),
                "date_published": date_published,
                "relative_date": relative_date,
                "date_sort": listing.get('date_sort'),
                "date_expired": listing.get("date_expired"),
                "title": listing.get("title"),
                "description": listing.get("description"),
                "link": url,
                "images": images_list,
                "price": listing.get("price"),
                "address": listing.get("district", {}).get("name"),
                "full_address": listing.get("district", {}).get("full_path"),
                "views_no": listing.get("user_view_count"),
                "longitude": listing.get("lon"),
                "latitude": listing.get("lat"),
                "user_name": listing.get("user", {}).get("first_name"),
                "user_email": listing.get("user", {}).get("email"),
                "user_ads": f"{listing.get('user', {}).get('listings_count')} ads",
                "user_image": listing.get("user", {}).get("image"),
                "user_type": listing.get("user", {}).get("user_type"),
                "membership": listing.get("user", {}).get("member_since", "").split("T")[0],
                "is_verified": listing.get("user", {}).get("is_verified"),
                "phone": listing.get("phone"),
                "status": status,  # Status from listings page
            }
            
            logger.debug(f"[OK] Successfully extracted all details from {url}")
            return base_info
            
        except Exception as e:
            logger.error(f"Error scraping detail page {url}: {e}", exc_info=True)
            return None
    
    def format_relative_date(self, date_str):
        """
        Format date string as relative time (e.g., "2 days ago")
        
        Args:
            date_str: Date string in format "YYYY-MM-DD HH:MM:SS"
        
        Returns:
            Relative date string
        """
        try:
            published = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except:
            return "Unknown"
        
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
    
    async def download_image(self, image_url: str) -> Optional[bytes]:
        """
        Download image from URL and return bytes
        
        Args:
            image_url: URL of the image
        
        Returns:
            Image bytes or None if failed
        """
        try:
            if not image_url:
                return None
            
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.warning(f"Failed to download image {image_url}: status {response.status}")
                        return None
                        
        except Exception as e:
            logger.warning(f"Error downloading image {image_url}: {e}")
            return None
    
    async def download_images_batch(self, image_urls: List[str]) -> Dict[str, bytes]:
        """
        Download multiple images concurrently
        
        Args:
            image_urls: List of image URLs
        
        Returns:
            Dict mapping URL to image bytes
        """
        results = {}
        tasks = []
        
        for url in image_urls:
            if url:
                tasks.append(self._download_with_url(url, results))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def _download_with_url(self, url: str, results: dict):
        """Helper to download and store image"""
        try:
            data = await self.download_image(url)
            if data:
                results[url] = data
        except Exception as e:
            logger.warning(f"Error in batch download for {url}: {e}")
