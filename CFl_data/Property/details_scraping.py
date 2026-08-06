import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import get_random_headers, random_delay, rotate_user_agent, configure_session_proxy, create_session

logger = logging.getLogger(__name__)

class PropertyDetailsScraper:
    def __init__(self, listing_page_url, browser=None):
        self.listing_page_url = listing_page_url
        self.browser = browser
        self.session = create_session()

    async def get_listings(self):
        listings_data = []
        try:
            random_delay(1.0, 3.0)  # Random delay before request
            rotate_user_agent(self.session)  # Rotate user agent
            response = self.session.get(self.listing_page_url, timeout=60)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if not script:
                logger.warning(f"No __NEXT_DATA__ found on {self.listing_page_url}")
                return []

            data = json.loads(script.string)
            page_props = data.get("props", {}).get("pageProps", {})
            listings = page_props.get("listings", [])
            logger.debug(f"Found {len(listings)} listings on page")

            # Check if this is a detail page (single listing) instead of listing page
            if not listings:
                single_listing = page_props.get("listing", {})
                if single_listing:
                    logger.info(f"Processing single detail page: {self.listing_page_url}")
                    result = await self._scrape_detail_page(self.listing_page_url, is_detail_page=True)
                    if result:
                        listings_data.append(result)
                        logger.debug(f"[OK] Extracted details from detail page")
                    return listings_data

            for idx, listing_summary in enumerate(listings):
                # Get slug for details page
                slug = listing_summary.get("slug")
                
                # Skip sponsored/ad listings that don't have a slug
                if not slug:
                    logger.info(f"[{idx+1}/{len(listings)}] SKIPPED (no slug) - Listing Summary Keys: {list(listing_summary.keys())}")
                    continue
                
                detail_url = f"https://www.q84sale.com/ar/listing/{slug}"
                # Get pin/status from listing page
                pin_status = listing_summary.get("status", "Not Pinned")
                
                logger.info(f"[{idx+1}/{len(listings)}] Processing from listing page: {self.listing_page_url}")
                logger.info(f"    Listing Summary Keys: {list(listing_summary.keys())}")
                logger.info(f"    Slug: {slug}")
                logger.info(f"    Detail URL: {detail_url}")
                
                # Fetch full details
                details = await self._scrape_detail_page(detail_url)
                if details:
                    details["pin"] = pin_status
                    listings_data.append(details)
                    logger.debug(f"[OK] Extracted details for listing: {slug}")
                else:
                    logger.debug(f"[OK] Failed to extract details for listing: {slug}")

        except Exception as e:
            logger.error(f"Error scraping {self.listing_page_url}: {e}", exc_info=True)

        logger.info(f"Successfully scraped {len(listings_data)} listing details from {self.listing_page_url}")
        return listings_data

    async def _scrape_detail_page(self, url, is_detail_page=False):
        try:
            if is_detail_page:
                logger.debug(f"Fetching detail page (single listing): {url}")
            else:
                logger.debug(f"Fetching detail page: {url}")
            
            random_delay(1.0, 3.0)  # Random delay before request
            rotate_user_agent(self.session)  # Rotate user agent
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if not script:
                logger.warning(f"No __NEXT_DATA__ found on detail page: {url}")
                return None

            data = json.loads(script.string)
            listing = data.get("props", {}).get("pageProps", {}).get("listing", {})

            if not listing:
                logger.warning(f"No listing data found on: {url}")
                logger.debug(f"Available pageProps keys were: {list(data.get('props', {}).get('pageProps', {}).keys())}")
                return None

            # Prepare details
            date_published = listing.get("date_published")
            relative_date = self.format_relative_date(date_published)
            attributes = self.extract_attributes(listing.get("attrsAndVals", []))
            images_list = listing.get("images", [])

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
            }

            logger.debug(f"[OK] Successfully extracted all details from {url}")
            return {**base_info, **attributes}

        except Exception as e:
            logger.error(f"Error scraping detail page {url}: {e}", exc_info=True)
            return None

    def extract_attributes(self, attrs_list):
        spec_en, spec_ar, flat_output = {}, {}, {}
        for item in attrs_list:
            attr = item.get("attrData", {})
            val = item.get("valData")
            name_en = attr.get("name_en")
            name_ar = attr.get("name_ar")
            attr_type = attr.get("type", "")

            # Handle different value types
            if isinstance(val, dict):
                # Dictionary values (e.g., location objects)
                value_en = val.get("name_en")
                value_ar = val.get("name_ar")
            elif isinstance(val, str):
                # Check if attribute is numeric type
                if attr_type == "number":
                    # Keep numeric values as-is
                    value_en = val
                    value_ar = val
                else:
                    # For other string types, treat as boolean
                    value_en = "Yes" if val == "1" else "No"
                    value_ar = "???" if val == "1" else "??"
            else:
                continue

            if name_en:
                spec_en[name_en] = value_en
                flat_output[name_en] = value_en
            if name_ar:
                spec_ar[name_ar] = value_ar
                flat_output[name_ar] = value_ar

        return {
            "specification_en": spec_en,
            "specification_ar": spec_ar,
            **flat_output
        }

    def format_relative_date(self, date_str):
        try:
            published = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except:
            return "Unknown"

        now = datetime.now()
        diff = relativedelta(now, published)
        if diff.years > 0: return f"{diff.years} year{'s' if diff.years>1 else ''} ago"
        if diff.months > 0: return f"{diff.months} month{'s' if diff.months>1 else ''} ago"
        if diff.days > 0: return f"{diff.days} day{'s' if diff.days>1 else ''} ago"
        if diff.hours > 0: return f"{diff.hours} hour{'s' if diff.hours>1 else ''} ago"
        if diff.minutes > 0: return f"{diff.minutes} minute{'s' if diff.minutes>1 else ''} ago"
        return "Just now"
