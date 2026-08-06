import json
import asyncio
import requests
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import get_random_headers, random_delay, rotate_user_agent, configure_session_proxy, create_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutomotiveServicesJsonScraper:
    """
    Scrapes automotive services subcategories and listings from q84sale.com
    URL: https://www.q84sale.com/ar/automotive/automotive-services
    
    Structure:
    1. Fetch subcategories from main category page
    2. For each subcategory, fetch listings
    3. For each listing, fetch details
    """
    
    def __init__(self):
        self.base_url = "https://www.q84sale.com/ar"
        self.main_category_url = "https://www.q84sale.com/ar/automotive/automotive-services"
        self.session = create_session()
    
    async def close_browser(self):
        """Cleanup session"""
        if self.session:
            self.session.close()
    
    async def get_page_json_data(self, url: str) -> Optional[Dict]:
        """
        Extract JSON data from __NEXT_DATA__ script tag
        
        Args:
            url: URL to fetch
        
        Returns:
            Dictionary containing JSON data from __NEXT_DATA__
        """
        try:
            logger.info(f"Fetching {url}...")
            random_delay(1.0, 3.0)  # Random delay before request
            rotate_user_agent(self.session)  # Rotate user agent
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if script and script.string:
                data = json.loads(script.string)
                logger.info(f"Successfully extracted JSON data from {url}")
                return data
            
            logger.warning(f"No __NEXT_DATA__ found on {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    async def get_subcategories(self) -> List[Dict]:
        """
        Fetch subcategories from the main automotive-services category page
        
        Returns:
            List of subcategory dictionaries with id, slug, name_ar, name_en, etc.
        """
        try:
            logger.info("Fetching subcategories from main category page...")
            data = await self.get_page_json_data(self.main_category_url)
            
            if not data:
                logger.error("Could not fetch main category page")
                return []
            
            # Extract subcategories from pageProps
            subcategories = data.get("props", {}).get("pageProps", {}).get("subcategories", [])
            
            logger.info(f"Found {len(subcategories)} subcategories")
            for subcat in subcategories:
                logger.info(f"  - {subcat.get('name_en')} ({subcat.get('slug')}): {subcat.get('listings_count')} listings")
            
            return subcategories
            
        except Exception as e:
            logger.error(f"Error getting subcategories: {e}")
            return []
    
    async def get_listings_for_subcategory(self, subcategory_slug: str, page: int = 1, 
                                               filter_yesterday: bool = False) -> Optional[Dict]:
        """
        Fetch listings for a specific subcategory
        
        Args:
            subcategory_slug: Slug of the subcategory (e.g., "car-services")
            page: Page number (defaults to 1)
            filter_yesterday: If True, only returns listings from yesterday
        
        Returns:
            Dictionary containing listings data
        """
        try:
            url = f"{self.base_url}/automotive/automotive-services/{subcategory_slug}/{page}"
            logger.info(f"Fetching listings from {subcategory_slug} (page {page})...")
            
            data = await self.get_page_json_data(url)
            
            if not data:
                return None
            
            # Extract listings data
            listings_data = data.get("props", {}).get("pageProps", {})
            listings = listings_data.get("listings", [])
            total_pages = listings_data.get("totalPages", 1)
            
            # Get yesterday's date for filtering
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            # Filter by yesterday if requested
            filtered_listings = []
            for listing in listings:
                if filter_yesterday:
                    date_published = listing.get("date_published", "")
                    if date_published and not date_published.startswith(yesterday):
                        continue
                filtered_listings.append(listing)
            
            logger.info(f"Found {len(filtered_listings)} listings on page {page}/{total_pages}")
            if filter_yesterday:
                logger.info(f"  (Filtered to yesterday's date: {yesterday})")
            
            return {
                "listings": filtered_listings,
                "total_pages": total_pages,
                "current_page": page
            }
            
        except Exception as e:
            logger.error(f"Error getting listings for {subcategory_slug} page {page}: {e}")
            return None
    
    async def get_all_listings_for_subcategory(self, subcategory_slug: str, 
                                               max_pages: Optional[int] = None,
                                               filter_yesterday: bool = False) -> List[Dict]:
        """
        Fetch all listings for a subcategory across all pages
        
        Args:
            subcategory_slug: Slug of the subcategory
            max_pages: Maximum pages to fetch (None for all)
            filter_yesterday: If True, only returns listings from yesterday
        
        Returns:
            List of all listings
        """
        all_listings = []
        page = 1
        
        while True:
            result = await self.get_listings_for_subcategory(subcategory_slug, page, 
                                                             filter_yesterday=filter_yesterday)
            
            if not result:
                logger.warning(f"Failed to fetch page {page} for {subcategory_slug}")
                break
            
            all_listings.extend(result.get("listings", []))
            total_pages = result.get("total_pages", 1)
            
            if page >= total_pages:
                break
            
            if max_pages and page >= max_pages:
                logger.info(f"Reached max_pages limit ({max_pages})")
                break
            
            page += 1
            await asyncio.sleep(1)  # Be nice to the server
        
        logger.info(f"Total {len(all_listings)} listings fetched for {subcategory_slug}")
        if filter_yesterday:
            logger.info(f"  (Filtered to yesterday's date only)")
        return all_listings
    
    async def get_listing_details(self, listing_slug: str, status: str = "normal") -> Optional[Dict]:
        """
        Get detailed information for a specific listing from the listing details page
        Uses the slug to construct the URL (e.g., 'services-20423682')
        
        Args:
            listing_slug: Listing slug (e.g., 'services-20423682')
            status: Listing status (normal/pinned etc.)
        
        Returns:
            Detailed listing information or None if failed
        """
        try:
            url = f"{self.base_url}/listing/{listing_slug}"
            logger.info(f"Fetching listing details: {listing_slug}...")
            
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
            
            # Extract attributes
            attrs_and_vals = listing.get("attrsAndVals", [])
            
            # Return detailed listing information
            result = {
                "id": listing.get("user_adv_id"),
                "slug": listing.get("slug"),
                "title": listing.get("title"),
                "description": listing.get("description"),
                "price": listing.get("price"),
                "phone": listing.get("phone"),
                "date_published": date_published,
                "date_created": listing.get("date_created"),
                "date_expired": listing.get("date_expired"),
                "date_sort": listing.get("date_sort"),
                "images": images,
                "district": listing.get("district", {}),
                "user": listing.get("user", {}),
                "category": listing.get("category", {}),
                "attributes": attrs_and_vals,
                "contacts": listing.get("contacts", []),
                "is_private_message_enabled": listing.get("is_private_message_enabled"),
                "lat": listing.get("lat"),
                "lon": listing.get("lon"),
                "status": status
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting details for {listing_slug}: {e}")
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
            response = self.session.get(image_url, timeout=60)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading image {image_url}: {e}")
            return None
