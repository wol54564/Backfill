import json
import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import get_random_headers, random_delay, rotate_user_agent, configure_session_proxy, create_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CommercialsJsonScraper:
    """
    Scrapes Q84Sale commercials listings using JSON data from __NEXT_DATA__ script tag
    
    Structure:
    - Main page: /commercials/all - contains all categories
    - Category pages: /commercials/{category_slug} - contains commercialAds
    - Ad details: /commercials/listing/{ad_id} - contains full ad details
    """
    
    def __init__(self):
        self.base_url = "https://www.q84sale.com/ar/commercials"
        self.session = create_session()
        
    async def init_browser(self):
        """Compatibility method - not needed with BeautifulSoup"""
        pass
    
    async def close_browser(self):
        """Cleanup session"""
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
    
    async def download_image(self, image_url: str) -> Optional[bytes]:
        """
        Download image from URL
        
        Args:
            image_url: URL of the image
            
        Returns:
            Image data as bytes or None if failed
        """
        try:
            response = self.session.get(image_url, timeout=60)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading image {image_url}: {e}")
            return None
    
    async def get_categories(self) -> List[Dict]:
        """
        Get all categories from the commercials main page
        
        Returns:
            List of category dictionaries with id, name, slug, icon, total_pages
        """
        try:
            logger.info("Fetching commercials categories...")
            url = f"{self.base_url}/all"
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.error("Failed to fetch commercials page JSON")
                return []
            
            # Extract categories from the JSON structure
            categories = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("categories", [])
            )
            
            if not categories:
                logger.warning("No categories found in commercials page")
                return []
            
            formatted_categories = []
            for cat in categories:
                # Skip the "all" category as it's just a collection
                if cat.get("slug") == "all":
                    continue
                    
                formatted_categories.append({
                    "id": cat.get("id"),
                    "name": cat.get("name"),
                    "slug": cat.get("slug"),
                    "icon": cat.get("icon"),
                    "total_pages": cat.get("total_pages", 1),
                })
            
            logger.info(f"Found {len(formatted_categories)} categories")
            for cat in formatted_categories:
                logger.info(f"  - {cat['name']} ({cat['slug']}) - {cat['total_pages']} pages")
            
            return formatted_categories
            
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []
    
    async def get_category_ads(self, category_slug: str, page_num: int = 1) -> Tuple[List[Dict], int]:
        """
        Get all commercial ads for a specific category
        
        Args:
            category_slug: The slug of the category (e.g., 'property', 'car-rental')
            page_num: Page number (default 1)
        
        Returns:
            Tuple of (ads_list, total_pages)
        """
        try:
            # Build URL
            url = f"{self.base_url}/{category_slug}"
            if page_num > 1:
                url = f"{url}/{page_num}"
                
            logger.info(f"Fetching ads for {category_slug} page {page_num}...")
            
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.warning(f"No data found for {url}")
                return [], 0
            
            # Extract data from the JSON response
            page_props = json_data.get("props", {}).get("pageProps", {})
            commercial_ads = page_props.get("commercialAds", [])
            
            # Get total_pages from the category data if available
            categories = page_props.get("categories", [])
            total_pages = 1
            for cat in categories:
                if cat.get("slug") == category_slug:
                    total_pages = cat.get("total_pages", 1)
                    break
            
            formatted_ads = []
            for ad in commercial_ads:
                formatted_ads.append({
                    "id": ad.get("id"),
                    "title": ad.get("title"),
                    "image": ad.get("image"),
                    "phone": ad.get("phone"),
                    "whatsapp_phone": ad.get("whatsapp_phone"),
                    "target_url": ad.get("target_url"),
                    "open_target_url": ad.get("open_target_url"),
                    "category_id": ad.get("category", {}).get("id"),
                    "category_slug": ad.get("category", {}).get("slug"),
                    "is_landing": ad.get("is_landing"),
                    "views_count": ad.get("views_count"),
                })
            
            logger.info(f"Found {len(formatted_ads)} ads on page {page_num} (Total Pages: {total_pages})")
            return formatted_ads, total_pages
            
        except Exception as e:
            logger.error(f"Error getting ads for {category_slug}: {e}")
            return [], 0
    
    async def get_ad_details(self, ad_id: int) -> Optional[Dict]:
        """
        Get detailed information for a specific ad
        
        Args:
            ad_id: The ID of the ad
        
        Returns:
            Dictionary with detailed ad information or None if failed
        """
        try:
            url = f"{self.base_url}/listing/{ad_id}"
            logger.info(f"Fetching details for ad {ad_id}...")
            
            json_data = await self.get_page_json_data(url)
            
            if not json_data:
                logger.warning(f"No data found for ad {ad_id}")
                return None
            
            # Extract ad details from the JSON structure
            ad_details = (
                json_data.get("props", {})
                .get("pageProps", {})
                .get("adDetails", {})
            )
            
            if not ad_details:
                logger.warning(f"No ad details found for {ad_id}")
                return None
            
            formatted_details = {
                "id": ad_details.get("id"),
                "title": ad_details.get("title"),
                "image": ad_details.get("image"),
                "phone": ad_details.get("phone"),
                "whatsapp_phone": ad_details.get("whatsapp_phone"),
                "target_url": ad_details.get("target_url"),
                "open_target_url": ad_details.get("open_target_url"),
                "category_id": ad_details.get("category", {}).get("id"),
                "category_slug": ad_details.get("category", {}).get("slug"),
                "is_landing": ad_details.get("is_landing"),
                "views_count": ad_details.get("views_count"),
                "url": url,
            }
            
            logger.info(f"[OK] Retrieved details for ad {ad_id} - {formatted_details['title']}")
            return formatted_details
            
        except Exception as e:
            logger.error(f"Error getting details for ad {ad_id}: {e}")
            return None
