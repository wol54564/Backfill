import json
import asyncio
import aiohttp
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import get_random_headers, random_delay, rotate_user_agent, configure_session_proxy, create_session

# Set to INFO for normal runs, DEBUG for troubleshooting
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DalilJsonScraper:
    """
    Scrapes Dalil Kuwait directory listings from directory.q84sale.com
    Extracts business data from JSON-LD structured data and Next.js page props
    """
    
    def __init__(self):
        self.base_url = "https://directory.q84sale.com/ar"
        self.session = create_session()
        
        # All category slugs
        self.categories = [
            "restaurants-cafes",
            "healthcare",
            "beauty-spa",
            "automotive",
            "fashion",
            "technology",
            "education",
            "real-estate",
            "home-services",
            "professional-business-services",
            "entertainment",
            "fitness-sports",
            "pet-services",
            "travel-tourism",
            "grocery-supermarkets",
            "shopping"
        ]
    
    async def init_browser(self):
        """Compatibility method - not needed with requests"""
        pass
    
    async def close_browser(self):
        """Cleanup session"""
        if self.session:
            self.session.close()
    
    def get_page_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from a URL
        Returns HTML string or None if failed
        """
        try:
            logger.info(f"Fetching {url}...")
            random_delay(1.0, 3.0)  # Random delay before request
            rotate_user_agent(self.session)  # Rotate user agent
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            return response.text
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def extract_json_ld(self, html: str, target_type: str = None) -> Optional[Dict]:
        """
        Extract JSON-LD structured data from HTML
        If target_type is specified, finds the JSON-LD with that @type
        Returns parsed JSON or None if not found
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all JSON-LD script tags
            scripts = soup.find_all('script', {'type': 'application/ld+json'})
            
            if not scripts:
                logger.warning("No JSON-LD scripts found on page")
                return None
            
            logger.debug(f"Found {len(scripts)} JSON-LD script(s)")
            
            # If target_type specified, find the matching one
            if target_type:
                for i, script in enumerate(scripts):
                    if script.string:
                        try:
                            data = json.loads(script.string)
                            script_type = data.get("@type")
                            logger.debug(f"JSON-LD script #{i+1} @type: {script_type}")
                            
                            if script_type == target_type:
                                logger.debug(f"[OK] Found JSON-LD with @type: {target_type}")
                                return data
                        except json.JSONDecodeError as e:
                            logger.debug(f"JSON-LD script #{i+1}: Invalid JSON - {e}")
                            continue
                
                logger.warning(f"No JSON-LD found with @type: {target_type}")
                return None
            
            # Otherwise return the first valid one
            for script in scripts:
                if script.string:
                    try:
                        return json.loads(script.string)
                    except json.JSONDecodeError:
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting JSON-LD: {e}")
            return None
    
    def extract_next_data(self, html: str) -> Optional[Dict]:
        """
        Extract __NEXT_DATA__ from Next.js page
        Returns parsed JSON or None if not found
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find __NEXT_DATA__ script tag
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if script and script.string:
                return json.loads(script.string)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting __NEXT_DATA__: {e}")
            return None
    
    def detect_total_pages(self, html: str) -> int:
        """
        Detect total number of pages from pagination HTML
        Looks for pagination links in the nav element
        Returns total pages or 1 if pagination not found
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all pagination links
            page_links = soup.find_all('a', class_=re.compile('pageLink'))
            
            if not page_links:
                logger.debug("No pagination found, assuming single page")
                return 1
            
            # Extract page numbers from links
            page_numbers = []
            for link in page_links:
                href = link.get('href', '')
                # Extract page number from URL like "?page=5"
                match = re.search(r'page=(\d+)', href)
                if match:
                    page_numbers.append(int(match.group(1)))
            
            if page_numbers:
                total_pages = max(page_numbers)
                logger.info(f"Detected {total_pages} pages")
                return total_pages
            
            return 1
            
        except Exception as e:
            logger.warning(f"Error detecting pagination: {e}")
            return 1
    
    def get_category_businesses_single_page(self, category_slug: str, page: int = 1) -> Dict:
        """
        Get businesses from a single page of a category
        Returns dict with category info and business list
        """
        try:
            # Build URL with page parameter
            if page == 1:
                url = f"{self.base_url}/{category_slug}"
            else:
                url = f"{self.base_url}/{category_slug}?page={page}"
            
            html = self.get_page_html(url)
            
            if not html:
                logger.error(f"Failed to fetch category page: {category_slug} (page {page})")
                return {"category_slug": category_slug, "businesses": [], "error": True, "page": page}
            
            # Try __NEXT_DATA__ first (more reliable for Next.js sites)
            next_data = self.extract_next_data(html)
            
            if next_data:
                logger.debug(f"Found __NEXT_DATA__ for {category_slug} page {page}")
                result = self._parse_next_data_category(next_data, category_slug)
                
                # If __NEXT_DATA__ parsing succeeded, use it
                if not result.get("error") and result.get("businesses"):
                    result["page"] = page
                    result["html"] = html  # Include HTML for pagination detection
                    return result
                
                logger.debug(f"__NEXT_DATA__ had no businesses, trying JSON-LD...")
            
            # Fallback to JSON-LD (this is where the actual data is for this site)
            logger.debug(f"Parsing JSON-LD for {category_slug} page {page}")
            json_ld = self.extract_json_ld(html, target_type="CollectionPage")
            
            if not json_ld:
                logger.warning(f"No CollectionPage JSON-LD found for category: {category_slug} page {page}")
                return {"category_slug": category_slug, "businesses": [], "error": True, "page": page, "html": html}
            
            result = self._parse_json_ld_category(json_ld, category_slug)
            result["page"] = page
            result["html"] = html  # Include HTML for pagination detection
            return result
            
        except Exception as e:
            logger.error(f"Error getting businesses for {category_slug} page {page}: {e}")
            return {"category_slug": category_slug, "businesses": [], "error": True, "page": page}
    
    async def get_category_businesses(self, category_slug: str) -> Dict:
        """
        Get all businesses for a category from all pages
        Automatically detects and scrapes all pagination pages
        Returns dict with category info and complete business list
        """
        try:
            logger.info(f"Fetching page 1 to detect pagination...")
            
            # Get first page
            first_page_result = self.get_category_businesses_single_page(category_slug, page=1)
            
            if first_page_result.get("error"):
                return first_page_result
            
            # Detect total pages from first page HTML
            html = first_page_result.get("html", "")
            total_pages = self.detect_total_pages(html) if html else 1
            
            # Remove HTML from result (not needed in final output)
            first_page_result.pop("html", None)
            
            # If only one page, return immediately
            if total_pages == 1:
                logger.info(f"Category {category_slug}: 1 page, {len(first_page_result.get('businesses', []))} businesses")
                return first_page_result
            
            logger.info(f"Category {category_slug} has {total_pages} pages. Fetching all pages...")
            
            # Collect all businesses from first page
            all_businesses = first_page_result.get("businesses", [])
            category_info = {
                "category_slug": first_page_result.get("category_slug"),
                "category_name": first_page_result.get("category_name"),
                "category_description": first_page_result.get("category_description"),
                "category_image": first_page_result.get("category_image"),
            }
            
            # Fetch remaining pages
            for page_num in range(2, total_pages + 1):
                logger.info(f"  Fetching page {page_num}/{total_pages}...")
                
                page_result = self.get_category_businesses_single_page(category_slug, page=page_num)
                
                if not page_result.get("error"):
                    page_businesses = page_result.get("businesses", [])
                    all_businesses.extend(page_businesses)
                    logger.debug(f"  Page {page_num}: {len(page_businesses)} businesses")
                else:
                    logger.warning(f"  Failed to fetch page {page_num}")
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.3)
            
            logger.info(f"Category {category_slug}: {total_pages} pages, {len(all_businesses)} total businesses")
            
            return {
                "category_slug": category_info["category_slug"],
                "category_name": category_info["category_name"],
                "category_description": category_info["category_description"],
                "category_image": category_info["category_image"],
                "total_businesses": len(all_businesses),
                "total_pages": total_pages,
                "businesses": all_businesses,
                "error": False
            }
            
        except Exception as e:
            logger.error(f"Error getting businesses for {category_slug}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {"category_slug": category_slug, "businesses": [], "error": True}
    
    def _parse_next_data_category(self, next_data: Dict, category_slug: str) -> Dict:
        """Parse category data from __NEXT_DATA__"""
        try:
            page_props = next_data.get("props", {}).get("pageProps", {})
            
            # The category page structure based on the provided example
            # Does NOT contain businesses in pageProps directly
            # Businesses are in the JSON-LD, not in __NEXT_DATA__
            # So we return empty and let it fall back to JSON-LD
            
            logger.debug(f"__NEXT_DATA__ pageProps keys: {list(page_props.keys())}")
            
            # Check if there's any business data
            businesses_data = page_props.get("businesses", [])
            if not businesses_data:
                businesses_data = page_props.get("items", [])
            if not businesses_data:
                businesses_data = page_props.get("listings", [])
            
            if not businesses_data:
                logger.debug(f"No businesses in __NEXT_DATA__ for {category_slug}, will try JSON-LD")
                # Return error to trigger fallback to JSON-LD
                return {"category_slug": category_slug, "businesses": [], "error": True}
            
            # Extract category info if available
            category_info = page_props.get("category", {})
            category_name = category_info.get("name", category_info.get("title", ""))
            category_description = category_info.get("description", "")
            category_image = category_info.get("image", "")
            
            # Parse businesses
            businesses_summary = []
            for idx, business in enumerate(businesses_data, 1):
                businesses_summary.append({
                    "position": idx,
                    "name": business.get("name", ""),
                    "url": f"https://directory.q84sale.com/ar/{category_slug}/{business.get('slug', '')}",
                    "slug": business.get("slug", ""),
                    "price_range": business.get("priceRange", business.get("price_range", "")),
                    "image": business.get("logo", business.get("image", "")),
                })
            
            logger.info(f"Found {len(businesses_summary)} businesses in {category_slug} from __NEXT_DATA__")
            
            return {
                "category_slug": category_slug,
                "category_name": category_name,
                "category_description": category_description,
                "category_image": category_image,
                "total_businesses": len(businesses_summary),
                "businesses": businesses_summary,
                "error": False
            }
            
        except Exception as e:
            logger.error(f"Error parsing __NEXT_DATA__ for {category_slug}: {e}")
            return {"category_slug": category_slug, "businesses": [], "error": True}
    
    def _parse_json_ld_category(self, json_ld: Dict, category_slug: str) -> Dict:
        """Parse category data from JSON-LD (CollectionPage structure)"""
        try:
            # Verify this is a CollectionPage
            if json_ld.get("@type") != "CollectionPage":
                logger.warning(f"JSON-LD is not CollectionPage, got: {json_ld.get('@type')}")
                return {"category_slug": category_slug, "businesses": [], "error": True}
            
            # Parse category data from CollectionPage
            category_name = json_ld.get("name", "")
            category_description = json_ld.get("description", "")
            
            # Handle image - can be dict or string
            category_image = ""
            if isinstance(json_ld.get("image"), dict):
                category_image = json_ld.get("image", {}).get("url", "")
            elif isinstance(json_ld.get("image"), str):
                category_image = json_ld.get("image", "")
            
            # Parse business items from mainEntity.itemListElement
            main_entity = json_ld.get("mainEntity", {})
            if not main_entity:
                logger.warning(f"No mainEntity in JSON-LD for {category_slug}")
                return {"category_slug": category_slug, "businesses": [], "error": True}
            
            # Verify mainEntity is an ItemList
            if main_entity.get("@type") != "ItemList":
                logger.warning(f"mainEntity is not ItemList, got: {main_entity.get('@type')}")
            
            item_list = main_entity.get("itemListElement", [])
            num_items = main_entity.get("numberOfItems", 0)
            
            logger.debug(f"Expected {num_items} items, found {len(item_list)} in itemListElement")
            
            if not item_list:
                logger.warning(f"No itemListElement in mainEntity for {category_slug}")
                return {"category_slug": category_slug, "businesses": [], "error": True}
            
            # Parse each business from the list
            businesses_summary = []
            for item in item_list:
                if not isinstance(item, dict):
                    continue
                    
                business_data = item.get("item", {})
                if not business_data:
                    continue
                
                # Extract image URL
                business_image = ""
                if isinstance(business_data.get("image"), dict):
                    business_image = business_data.get("image", {}).get("url", "")
                elif isinstance(business_data.get("image"), str):
                    business_image = business_data.get("image", "")
                
                # Extract URL and slug
                business_url = business_data.get("url", "")
                business_slug = ""
                if business_url:
                    # Extract slug from URL (last part after the final /)
                    parts = business_url.rstrip('/').split('/')
                    business_slug = parts[-1] if parts else ""
                
                businesses_summary.append({
                    "position": item.get("position"),
                    "name": business_data.get("name", ""),
                    "url": business_url,
                    "slug": business_slug,
                    "price_range": business_data.get("priceRange", ""),
                    "image": business_image,
                })
            
            logger.info(f"Found {len(businesses_summary)} businesses in {category_slug} from JSON-LD")
            
            return {
                "category_slug": category_slug,
                "category_name": category_name,
                "category_description": category_description,
                "category_image": category_image,
                "total_businesses": len(businesses_summary),
                "businesses": businesses_summary,
                "error": False
            }
            
        except Exception as e:
            logger.error(f"Error parsing JSON-LD for {category_slug}: {e}")
            return {"category_slug": category_slug, "businesses": [], "error": True}
    
    def get_business_details(self, business_url: str, category_slug: str) -> Optional[Dict]:
        """
        Get detailed information for a specific business
        Returns complete business data including branches, reviews, media, etc.
        """
        try:
            html = self.get_page_html(business_url)
            
            if not html:
                logger.error(f"Failed to fetch business page: {business_url}")
                return None
            
            # Extract __NEXT_DATA__
            next_data = self.extract_next_data(html)
            
            if not next_data:
                logger.warning(f"No __NEXT_DATA__ found for: {business_url}")
                return None
            
            # Extract business data from pageProps
            page_props = next_data.get("props", {})
            if not page_props:
                page_props = {}
            
            page_props = page_props.get("pageProps", {})
            if not page_props:
                page_props = {}
            
            business = page_props.get("business", {})
            if not business:
                business = {}
            
            tabs = page_props.get("tabs", {})
            if not tabs:
                tabs = {}
            
            if not business:
                logger.warning(f"No business data found for: {business_url}")
                return None
            
            # Extract main business info with safe defaults
            business_info = {
                "id": business.get("id"),
                "name": business.get("name", ""),
                "slug": business.get("slug", ""),
                "category_slug": category_slug,
                "category_name": business.get("category", {}).get("name", "") if isinstance(business.get("category"), dict) else "",
                "logo": business.get("logo", "") if self.is_valid_image_url(business.get("logo", "")) else "",
                "cover_image": business.get("cover_image", "") if self.is_valid_image_url(business.get("cover_image", "")) else "",
                "about": business.get("about", ""),
                "rating_average": business.get("rating", {}).get("average", 0) if isinstance(business.get("rating"), dict) else 0,
                "rating_count": business.get("rating", {}).get("count", 0) if isinstance(business.get("rating"), dict) else 0,
                "view_count": business.get("view_count", 0),
                "status": business.get("status", ""),
                "display_title": business.get("display_title", ""),
                "display_description": business.get("display_description", ""),
                "created_at": business.get("created_at", ""),
                "updated_at": business.get("updated_at", ""),
            }
            
            # Extract contact info with safe defaults
            contact_info = business.get("contact_info", {})
            if not isinstance(contact_info, dict):
                contact_info = {}
            
            contact_numbers = contact_info.get("contact_numbers", [])
            if not isinstance(contact_numbers, list):
                contact_numbers = []
            
            business_info["contact_numbers"] = ", ".join(contact_numbers)
            business_info["website"] = contact_info.get("website", "")
            
            # Extract social media with safe defaults
            social_media = business.get("social_media", [])
            if not isinstance(social_media, list):
                social_media = []
            
            social_urls = [s.get("url", "") for s in social_media if isinstance(s, dict) and s.get("url")]
            business_info["social_media"] = ", ".join(social_urls)
            
            # Extract working hours (formatted) with safe defaults
            working_hours = business.get("working_hours", [])
            if not isinstance(working_hours, list):
                working_hours = []
            
            working_hours_formatted = []
            for wh in working_hours:
                if isinstance(wh, dict):
                    day = wh.get('day_name', '')
                    open_time = wh.get('open_time', '')
                    close_time = wh.get('close_time', '')
                    if day and open_time and close_time:
                        working_hours_formatted.append(f"{day}: {open_time}-{close_time}")
            business_info["working_hours"] = " | ".join(working_hours_formatted)
            
            # Extract attributes (selected important ones) with safe defaults
            attributes = business.get("attributes", {})
            if not isinstance(attributes, dict):
                attributes = {}
            
            business_info["delivery"] = attributes.get("delivery", False)
            business_info["takeaway"] = attributes.get("takeaway", False)
            business_info["dine_in"] = attributes.get("dine_in", False)
            business_info["parking"] = attributes.get("parking", False)
            business_info["wifi"] = attributes.get("wi_fi", False)
            business_info["wheelchair_accessible"] = attributes.get("wheelchair_accessible_entrance", False)
            
            # Extract branches with safe navigation
            branches_data = []
            if isinstance(tabs, dict):
                about_tab = tabs.get("about", {})
                if isinstance(about_tab, dict):
                    about_data = about_tab.get("data", {})
                    if isinstance(about_data, dict):
                        branches_data = about_data.get("branches", [])
                        if not isinstance(branches_data, list):
                            branches_data = []
            
            branches_list = []
            for branch in branches_data:
                if isinstance(branch, dict):
                    branches_list.append({
                        "name": branch.get("name", ""),
                        "address": branch.get("address", ""),
                        "phone": branch.get("phone", ""),
                        "latitude": branch.get("latitude"),
                        "longitude": branch.get("longitude"),
                        "is_main": branch.get("is_main", False),
                    })
            
            business_info["branches_count"] = len(branches_list)
            business_info["branches_json"] = json.dumps(branches_list, ensure_ascii=False)
            
            # Format main branch info
            main_branch = next((b for b in branches_list if b["is_main"]), branches_list[0] if branches_list else None)
            if main_branch:
                business_info["main_branch_address"] = main_branch.get("address", "")
                business_info["main_branch_phone"] = main_branch.get("phone", "")
                business_info["main_branch_latitude"] = main_branch.get("latitude")
                business_info["main_branch_longitude"] = main_branch.get("longitude")
            else:
                business_info["main_branch_address"] = ""
                business_info["main_branch_phone"] = ""
                business_info["main_branch_latitude"] = None
                business_info["main_branch_longitude"] = None
            
            # Extract reviews with safe navigation
            reviews_data = []
            reviews_summary = {}
            if isinstance(tabs, dict):
                reviews_tab = tabs.get("reviews", {})
                if isinstance(reviews_tab, dict):
                    review_data_obj = reviews_tab.get("data", {})
                    if isinstance(review_data_obj, dict):
                        reviews_data = review_data_obj.get("reviews", [])
                        if not isinstance(reviews_data, list):
                            reviews_data = []
                    
                    reviews_summary = reviews_tab.get("summary", {})
                    if not isinstance(reviews_summary, dict):
                        reviews_summary = {}
            
            business_info["reviews_count"] = reviews_summary.get("total_reviews", 0)
            business_info["reviews_average"] = reviews_summary.get("average_rating", 0)
            
            # Format recent reviews
            reviews_list = []
            for review in reviews_data[:5]:  # Top 5 reviews
                if isinstance(review, dict):
                    reviews_list.append({
                        "rating": review.get("rating"),
                        "comment": review.get("comment", ""),
                        "user_name": review.get("user_name", ""),
                        "created_at": review.get("created_at", ""),
                    })
            business_info["recent_reviews_json"] = json.dumps(reviews_list, ensure_ascii=False)
            
            # Check if media tab is enabled before extracting media
            media_tab_enabled = False
            business_tabs = business.get("tabs", [])
            if isinstance(business_tabs, list):
                for tab in business_tabs:
                    if isinstance(tab, dict) and tab.get("slug") == "media" and tab.get("enabled"):
                        media_tab_enabled = True
                        break
            
            # Extract media only if tab is enabled
            media_urls = []
            gallery_urls = []
            menu_urls = []
            
            if media_tab_enabled:
                logger.debug(f"Media tab is enabled for {business.get('name', '')}, extracting media...")
                media_data = []
                if isinstance(tabs, dict):
                    media_tab = tabs.get("media", {})
                    if isinstance(media_tab, dict):
                        media_data_obj = media_tab.get("data", {})
                        if isinstance(media_data_obj, dict):
                            media_data = media_data_obj.get("media", [])
                            if not isinstance(media_data, list):
                                media_data = []
                
                for media in media_data:
                    if isinstance(media, dict):
                        media_url = media.get("url", "")
                        media_category = media.get("media_category", "")
                        
                        # Only add valid, accessible image URLs
                        if media_url and self.is_valid_image_url(media_url):
                            media_urls.append(media_url)
                            
                            if media_category == "gallery":
                                gallery_urls.append(media_url)
                            elif media_category == "menu":
                                menu_urls.append(media_url)
            else:
                logger.debug(f"Media tab is disabled for {business.get('name', '')}, skipping media extraction")
            
            business_info["media_count"] = len(media_urls)
            business_info["media_urls"] = " | ".join(media_urls)
            business_info["gallery_urls"] = " | ".join(gallery_urls)
            business_info["menu_urls"] = " | ".join(menu_urls)
            
            return business_info
            
        except Exception as e:
            logger.error(f"Error getting business details for {business_url}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    async def scrape_category(self, category_slug: str) -> Dict:
        """
        Scrape all businesses in a category with full details
        Handles pagination automatically
        Returns category data with all business details
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"SCRAPING CATEGORY: {category_slug}")
        logger.info(f"{'='*60}")
        
        # Get category listing (with pagination)
        category_data = await self.get_category_businesses(category_slug)
        
        if category_data.get("error"):
            logger.error(f"Failed to get category listing: {category_slug}")
            return category_data
        
        total_pages = category_data.get("total_pages", 1)
        logger.info(f"Total pages: {total_pages}, Total businesses: {len(category_data.get('businesses', []))}")
        
        # Get details for each business
        businesses_with_details = []
        businesses_summary = category_data.get("businesses", [])
        
        logger.info(f"Scraping details for {len(businesses_summary)} businesses...")
        
        for i, business_summary in enumerate(businesses_summary, 1):
            business_url = business_summary.get("url", "")
            
            if not business_url:
                logger.warning(f"Skipping business {i}: No URL")
                continue
            
            logger.info(f"  [{i}/{len(businesses_summary)}] {business_summary.get('name', 'Unknown')}")
            
            business_details = self.get_business_details(business_url, category_slug)
            
            if business_details:
                # Merge summary and details
                business_full = {**business_summary, **business_details}
                businesses_with_details.append(business_full)
            else:
                logger.warning(f"  Failed to get details for: {business_url}")
                # Add summary only
                businesses_with_details.append(business_summary)
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        category_data["businesses"] = businesses_with_details
        category_data["total_scraped"] = len(businesses_with_details)
        
        logger.info(f"[OK] Category {category_slug}: Scraped {len(businesses_with_details)} businesses")
        
        return category_data
    
    def is_valid_image_url(self, url: str) -> bool:
        """
        Check if an image URL is valid and accessible (not a Google protected URL)
        Returns True if the URL should be downloaded, False otherwise
        """
        if not url or not isinstance(url, str):
            return False
        
        # Filter out Google protected image URLs that return 403
        blocked_domains = [
            'lh3.googleusercontent.com',
            'lh4.googleusercontent.com',
            'lh5.googleusercontent.com',
            'gps-cs-s',
            'gps-proxy',
        ]
        
        url_lower = url.lower()
        for domain in blocked_domains:
            if domain in url_lower:
                logger.debug(f"Skipping Google protected URL: {url}")
                return False
        
        # Also check for invalid URLs
        if not url.startswith(('http://', 'https://')):
            return False
        
        return True
    
    async def scrape_all_categories(self) -> List[Dict]:
        """
        Scrape all categories
        Returns list of category data dictionaries
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"STARTING DALIL SCRAPER - {len(self.categories)} CATEGORIES")
        logger.info(f"{'='*80}\n")
        
        results = []
        
        for i, category_slug in enumerate(self.categories, 1):
            logger.info(f"\n[{i}/{len(self.categories)}] Processing: {category_slug}")
            
            category_data = await self.scrape_category(category_slug)
            results.append(category_data)
            
            # Small delay between categories
            await asyncio.sleep(1)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"SCRAPING COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Categories scraped: {len(results)}")
        total_businesses = sum(len(cat.get("businesses", [])) for cat in results)
        logger.info(f"Total businesses: {total_businesses}")
        
        return results
