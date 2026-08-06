import json
import requests
from bs4 import BeautifulSoup
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import get_random_headers, random_delay, rotate_user_agent, configure_session_proxy, create_session

class CarScraper:
    def __init__(self, url):
        self.url = url
        self.base_url = "https://www.q84sale.com"
        self.session = create_session()
        self.data = []

    async def scrape_brands_and_types(self):
        try:
            # Fetch main page
            random_delay(1.0, 3.0)  # Random delay before request
            rotate_user_agent(self.session)  # Rotate user agent
            response = self.session.get(self.url, timeout=60)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if not script:
                print("No __NEXT_DATA__ script tag found")
                return []

            data = json.loads(script.string)
            brands_list = data.get('props', {}).get('pageProps', {}).get('brands', [])

            for brand in brands_list:
                title_ar = brand.get('name_ar')
                title_en = brand.get('name_en')
                brand_slug_url = brand.get('slug_url')
                listings_count = brand.get('listings_count')
                full_brand_link = f"{self.base_url}/ar/{brand_slug_url}" if brand_slug_url else None

                types_data = []
                if full_brand_link:
                    types_data = await self.scrape_types(full_brand_link)

                self.data.append({
                    'brand_ar': title_ar,
                    'brand': title_en,
                    'brand_link': full_brand_link,
                    'listings_count': listings_count,
                    'types': types_data
                })

        except Exception as e:
            print(f"Error scraping brands: {e}")
        
        return self.data

    async def scrape_types(self, brand_link):
        try:
            random_delay(1.0, 3.0)  # Random delay before request
            rotate_user_agent(self.session)  # Rotate user agent
            response = self.session.get(brand_link, timeout=60)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if not script: 
                return []

            data = json.loads(script.string)
            subcategories = data.get('props', {}).get('pageProps', {}).get('subcategories', [])

            types_data = []
            for t in subcategories:
                if isinstance(t, dict):
                    title_ar = t.get('name_ar')
                    title_en = t.get('name_en')
                    type_slug_url = t.get('slug_url')
                    full_type_link = f"{self.base_url}/{type_slug_url}" if type_slug_url else None
                    types_data.append({
                        'title_ar': title_ar,
                        'title': title_en,
                        'type_link': full_type_link,
                        'listings_count': t.get('listings_count', 0)
                    })
            return types_data

        except Exception as e:
            print(f"Failed to scrape types from {brand_link}: {e}")
            return []
