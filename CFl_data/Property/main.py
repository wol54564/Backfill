import asyncio
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import logging
import requests
from bs4 import BeautifulSoup
from details_scraping import PropertyDetailsScraper
from s3_uploader import R2Uploader
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import get_random_headers, random_delay, rotate_user_agent, configure_session_proxy, create_session

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Metrics tracking for monitoring
start_time = None
requests_total = 0
requests_failed = 0

YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
YEAR, MONTH, DAY = datetime.now().year, datetime.now().month, datetime.now().day

AWS_BUCKET = os.environ.get("CF_R2_BUCKET_NAME", "data-collection-dl")
R2 = R2Uploader(AWS_BUCKET)

BASE_URL = "https://www.q84sale.com/ar/property"
SESSION = create_session()

async def get_property_subcategories():
    logger.info(f"Fetching property subcategories from {BASE_URL}")
    try:
        random_delay(1.0, 3.0)  # Random delay before request
        rotate_user_agent(SESSION)  # Rotate user agent
        response = SESSION.get(BASE_URL, timeout=60)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        script = soup.find('script', {'id': '__NEXT_DATA__'})
        
        data = json.loads(script.string)
        page_props = data["props"]["pageProps"]
        subcats = (
            page_props.get("verticalSubcats")
            or page_props.get("propertySubcats")
            or []
        )
        logger.info(f"Found {len(subcats)} property subcategories")
        return subcats
    except Exception as e:
        logger.error(f"Error fetching subcategories: {e}")
        return []

async def get_business_listings(url):
    try:
        random_delay(1.0, 3.0)  # Random delay before request
        rotate_user_agent(SESSION)  # Rotate user agent
        response = SESSION.get(url, timeout=60)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        script = soup.find('script', {'id': '__NEXT_DATA__'})

        if not script:
            return []

        data = json.loads(script.string)

        return (
            data.get("props", {})
                .get("pageProps", {})
                .get("businessListings", {})
                .get("data", {})
                .get("listings", {})
                .get("normal_items", [])
        )
    except Exception as e:
        logger.error(f"Error getting business listings from {url}: {e}")
        return []

async def scrape_subcategory(subcat):
    name = subcat["name_en"]
    slug = subcat["slug"]
    logger.info(f"Starting scrape for subcategory: {name} ({slug})")

    base_url = f"https://www.q84sale.com/ar/property/{slug}/{{}}"

    # Load first page
    try:
        random_delay(1.0, 3.0)  # Random delay before request
        rotate_user_agent(SESSION)  # Rotate user agent
        response = SESSION.get(base_url.format(1), timeout=60)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        script = soup.find('script', {'id': '__NEXT_DATA__'})
        
        data = json.loads(script.string)
    except Exception as e:
        logger.error(f"Error loading first page for {slug}: {e}")
        return

    page_props = data.get("props", {}).get("pageProps", {})
    sub_subcats = page_props.get("subcategories", [])
    businesses = page_props.get("businessesData", {}).get("data", [])

    results = []

    # ---------------------------------------------------
    # CASE 1: SALE / RENT (has subcategories)
    # ---------------------------------------------------
    if sub_subcats:
        logger.info(f"Found {len(sub_subcats)} sub-subcategories for {name}")

        for sub in sub_subcats:
            sub_name = sub["name_en"]
            sub_slug = sub["slug"]
            total_pages = sub.get("totalPages", 1)
            sub_url = f"https://www.q84sale.com/ar/property/{slug}/{sub_slug}/{{}}"

            logger.info(f"Processing {sub_name} ({total_pages} pages)")

            for page_no in range(1, total_pages + 1):
                scraper = PropertyDetailsScraper(sub_url.format(page_no))
                listings = await scraper.get_listings()

                listings = [
                    {**l, "sheet": sub_name}
                    for l in listings
                    if l.get("date_published")
                    and l["date_published"].split(" ")[0] == YESTERDAY
                ]

                for l in listings:
                    R2_paths = []
                    for idx, img in enumerate(l.get("images", [])):
                        img_url = img if isinstance(img, str) else img.get("url", "")
                        if img_url:
                            path = (
                                f"4sale-data/property/year={YEAR}/month={MONTH}/day={DAY}/"
                                f"images/{slug}/{sub_slug}/{l['id']}_{idx}.jpg"
                            )
                            result = await R2.upload_image(img_url, path)
                            if result:
                                R2_paths.append(path)
                    l["r2_images_paths"] = R2_paths

                results.extend(listings)

    # ---------------------------------------------------
    # CASE 2: PROPERTY OFFICES / 4SALE REALTY (businesses)
    # ---------------------------------------------------
    elif businesses:
        logger.info(f"{name} has {len(businesses)} businesses")

        for biz in businesses:
            biz_slug = biz["slug"]
            biz_name = biz["name"]
            page_no = 1

            while True:
                biz_url = (
                    f"https://www.q84sale.com/ar/businesses/"
                    f"{slug}/{biz_slug}/all?page={page_no}"
                )

                raw_listings = await get_business_listings(biz_url)
                if not raw_listings:
                    break

                for item in raw_listings:
                    if not item.get("date_published"):
                        continue
                    if item["date_published"].split(" ")[0] != YESTERDAY:
                        continue

                    details_url = f"https://www.q84sale.com/ar/listing/{item['slug']}"
                    details = PropertyDetailsScraper(details_url)
                    data = await details.get_listings()

                    if not data:
                        continue

                    record = data[0]
                    record["sheet"] = biz_name

                    R2_paths = []
                    for idx, img in enumerate(record.get("images", [])):
                        img_url = img if isinstance(img, str) else img.get("url", "")
                        if img_url:
                            path = (
                                f"4sale-data/property/year={YEAR}/month={MONTH}/day={DAY}/"
                                f"images/{slug}/{biz_slug}/{record['id']}_{idx}.jpg"
                            )
                            result = await R2.upload_image(img_url, path)
                            if result:
                                R2_paths.append(path)

                    record["r2_images_paths"] = R2_paths
                    results.append(record)

                page_no += 1
    # ---------------------------------------------------
    # CASE 3: DIRECT LISTINGS (exchange, international...)
    # ---------------------------------------------------
    else:
        total_pages = page_props.get("totalPages", 1)
        logger.info(f"No subcategories. Processing {total_pages} pages")

        for page_no in range(1, total_pages + 1):
            scraper = PropertyDetailsScraper(base_url.format(page_no))
            listings = await scraper.get_listings()

            listings = [
                {**l, "sheet": "All Listings"}
                for l in listings
                if l.get("date_published")
                and l["date_published"].split(" ")[0] == YESTERDAY
            ]

            for l in listings:
                R2_paths = []
                for idx, img in enumerate(l.get("images", [])):
                    img_url = img if isinstance(img, str) else img.get("url", "")
                    if img_url:
                        path = (
                            f"4sale-data/property/year={YEAR}/month={MONTH}/day={DAY}/"
                            f"images/{slug}/all/{l['id']}_{idx}.jpg"
                        )
                        result = await R2.upload_image(img_url, path)
                        if result:
                            R2_paths.append(path)
                l["r2_images_paths"] = R2_paths

            results.extend(listings)

    # ---------------------------------------------------
    # SAVE EXCEL (MULTI-SHEET, CORRECTLY LABELED)
    # ---------------------------------------------------
    if not results:
        logger.warning(f"No listings found for {slug} from {YESTERDAY}")
        return {
            "slug": slug,
            "name": name,
            "listings_count": 0,
            "sheets_count": 0
        }

    temp_file = f"temp_{slug}.xlsx"
    excel_path = f"4sale-data/property/year={YEAR}/month={MONTH}/day={DAY}/excel-files/{slug}.xlsx"

    with pd.ExcelWriter(temp_file, engine="openpyxl") as writer:
        for sheet in sorted(set(r["sheet"] for r in results)):
            rows = [r for r in results if r["sheet"] == sheet]
            pd.DataFrame(rows).to_excel(
                writer, index=False, sheet_name=sheet[:31]
            )

    with open(temp_file, "rb") as f:
        await R2.upload_fileobj(f, excel_path)

    json_version_path = f"4sale-data/property/year={YEAR}/month={MONTH}/day={DAY}/json version/{slug}.json"
    temp_json_version = f"temp_{slug}.json"
    with open(temp_json_version, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(temp_json_version, 'rb') as f:
        await R2.upload_fileobj(f, json_version_path)
    logger.info(f"[OK] {slug} JSON version uploaded to {json_version_path}")

    os.remove(temp_json_version)

    sheets_count = len(set(r["sheet"] for r in results))
    logger.info(f"[OK] {slug} saved to R2 with {sheets_count} sheets")
    
    # Return summary for aggregation
    return {
        "slug": slug,
        "name": name,
        "listings_count": len(results),
        "sheets_count": sheets_count
    }


async def main():
    logger.info("="*50)
    logger.info("Starting Property Scraper")
    logger.info(f"Scraping for date: {YESTERDAY}")
    logger.info("="*50)
    
    start_time = time.time()
    
    try:
        subcategories = await get_property_subcategories()
        logger.info(f"Creating tasks for {len(subcategories)} subcategories")
        tasks = [scrape_subcategory(sub) for sub in subcategories]
        results = await asyncio.gather(*tasks)
        logger.info("All scraping tasks completed successfully")
        
        # Filter out None results
        results = [r for r in results if r is not None]
        
        # Aggregate results
        total_listings = sum(r["listings_count"] for r in results)
        total_sheets = sum(r["sheets_count"] for r in results)
        
        # Create and upload JSON summary
        logger.info("\nUploading JSON summary...")
        duration_sec = time.time() - start_time
        requests_total = int(getattr(SESSION, "request_count", 0) or 0)
        requests_failed = 0
        error_rate_pct = (requests_failed / requests_total * 100.0) if requests_total > 0 else 0.0
        requests_per_min = (requests_total / (duration_sec / 60.0)) if duration_sec > 0 else 0.0
        
        json_summary = {
            "scraped_at": datetime.now().isoformat(),
            "data_scraped_date": YESTERDAY,
            "saved_to_R2_date": f"{YEAR}-{MONTH:02d}-{DAY:02d}",
            "total_subcategories": len(results),
            "total_listings": total_listings,
            "total_sheets": total_sheets,
            "subcategories": results,
            "request_metrics": {
                "requests_total": requests_total,
                "requests_failed": requests_failed,
                "error_rate_pct": round(error_rate_pct, 2),
                "requests_per_min": round(requests_per_min, 2),
                "duration_sec": round(duration_sec, 2),
            },
        }
        
        # Save JSON summary to R2
        json_filename = f"property_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_path = f"4sale-data/property/year={YEAR}/month={MONTH}/day={DAY}/json-files/{json_filename}"
        
        temp_json = json_filename
        with open(temp_json, 'w', encoding='utf-8') as f:
            json.dump(json_summary, f, ensure_ascii=False, indent=2)
        
        with open(temp_json, 'rb') as f:
            await R2.upload_fileobj(f, json_path)
        
        logger.info(f"[OK] Uploaded JSON summary to {json_path}")
        
        import os
        os.remove(temp_json)
        
    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
    
    logger.info("="*50)
    logger.info("Property Scraper finished")
    logger.info("="*50)

if __name__ == "__main__":
    asyncio.run(main())