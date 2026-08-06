import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import get_random_headers, random_delay, rotate_user_agent, configure_session_proxy, create_session

class DetailsScraping:
    def __init__(self, url, browser=None):
        self.url = url
        self.browser = browser
        self.session = create_session()

    async def get_car_details(self):
        cars = []
        try:
            random_delay(1.0, 3.0)  # Random delay before request
            rotate_user_agent(self.session)  # Rotate user agent
            response = self.session.get(self.url, timeout=60)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if not script:
                print(f"No __NEXT_DATA__ found on {self.url}")
                return []

            data = json.loads(script.string)
            page_props = data.get("props", {}).get("pageProps", {})
            listings = page_props.get("listing", {})

            details = await self.scrape_listing_details(listings, self.url)
            cars.append(details)

        except Exception as e:
            print(f"Error scraping page {self.url}: {e}")

        return cars

    async def scrape_listing_details(self, listing, type_url):
        date_published = listing.get("date_published")
        relative_date = self.format_relative_date(date_published)
        attributes = self.extract_attributes(listing.get("attrsAndVals", []))

        base_info = {
            "id": listing.get("user_adv_id"),
            "date_published": date_published,
            "relative_date": relative_date,
            "pin": listing.get("pinned-today", "Not Pinned"),
            "title": listing.get("title"),
            "description": listing.get("description"),
            "link": type_url,
            "image": listing.get("images")[0] if listing.get("images") else None,
            "image_filename": f"{listing.get('title')}_image_{listing.get('user_adv_id')}.jpg",
            "price": listing.get("price"),
            "address": listing.get("district", {}).get("name"),
            "views_no": listing.get("user_view_count"),
            "submitter": listing.get("user", {}).get("first_name"),
            "user_email": listing.get("user", {}).get("email"),
            "ads": f"{listing.get('user_ads',0)} ads",
            "membership": listing.get("user", {}).get("member_since", "").split("T")[0],
            "phone": listing.get("phone"),
        }

        return {**base_info, **attributes}

    def extract_attributes(self, attrs_list):
        spec_en, spec_ar, flat_output = {}, {}, {}
        for item in attrs_list:
            attr = item.get("attrData", {})
            val = item.get("valData")

            name_en = attr.get("name_en")
            name_ar = attr.get("name_ar")

            if isinstance(val, str):
                value_en = "Yes" if val == "1" else "No"
                value_ar = "???" if val == "1" else "??"
            elif isinstance(val, dict):
                value_en = val.get("name_en")
                value_ar = val.get("name_ar")
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
