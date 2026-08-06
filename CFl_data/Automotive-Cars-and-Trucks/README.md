# Q84Sale Automotive Scraper

This project scrapes automotive listings from Q84Sale (https://www.q84sale.com) and uploads the data to AWS S3.

## Features

- **JSON-based scraping**: Extracts data from `__NEXT_DATA__` script tags using BeautifulSoup4
- **Fast & lightweight**: Uses BeautifulSoup4 instead of Playwright for much faster scraping
- **AWS S3 integration**: Uploads data with automatic date-based partitioning
- **Multi-category support**: Handles main categories, subcategories, and child categories
- **Image handling**: Downloads and uploads listing images to S3
- **Excel export**: Creates formatted Excel files with detailed listings
- **Error handling**: Robust error handling with retries and logging

## URLs Handled

The scraper handles these URL patterns:

- Main category: `https://www.q84sale.com/ar/automotive/{category-slug}/{page-number}`
- Child category: `https://www.q84sale.com/ar/automotive/{category-slug}/{child-slug}/{page-number}`
- District filtered: `https://www.q84sale.com/ar/automotive/{category-slug}/{page-number}/{district-slug}`
- Listing details: `https://www.q84sale.com/ar/listing/{listing-slug}`

## JSON Response Structure

The scraper extracts data from the `__NEXT_DATA__` script tag which contains:

```json
{
  "props": {
    "pageProps": {
      "verticalSubcats": [...],
      "catChilds": [...],
      "listings": [
        {
          "id": 20487561,
          "title": "...",
          "slug": "...",
          "price": 4700,
          "image": "...",
          "images_count": 16,
          "date_published": "2025-12-19 20:35:14",
          "...": "..."
        }
      ],
      "totalPages": 11
    }
  }
}
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/automative-cars-and-trucks.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch
- **Credentials**: Set via GitHub Secrets

## Local Development Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure AWS credentials:
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=data-collection-dl
```

## Usage

Run the scraper:
```bash
python main.py
```

Or with environment variables:
```bash
export S3_BUCKET_NAME="data-collection-dl"
export MAX_PAGES=5
python main.py
```

## Environment Variables

- `S3_BUCKET_NAME`: Target S3 bucket name (default: `data-collection-dl`)
- `MAX_PAGES`: Maximum pages to scrape per category (default: 5)
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key

## S3 Structure

Data is organized with date-based partitioning:

```
4sale-data/automative-cars-and-trucks/
  year=2025/
    month=12/
      day=20/
        excel-files/
          classic-cars.xlsx
          junk-cars.xlsx
          food-trucks.xlsx
        json-files/
          summary_20251220.json
        images/
          classic-cars/
            20487561_0.jpg
            20487561_1.jpg
          junk-cars/
            ...
```

## File Descriptions

### main.py
Main orchestrator that coordinates the scraping process and S3 uploads.

### json_scraper.py
Handles all web scraping using Playwright to extract JSON data from pages.

### s3_helper.py
AWS S3 client wrapper with partition management and file upload utilities.

## Classes

### AutomotiveJsonScraper
- `init_browser()`: Initialize Playwright browser
- `get_page_json_data(url)`: Extract JSON from `__NEXT_DATA__` script
- `get_subcategories()`: Get all automotive subcategories
- `get_catchilds(subcategory_slug)`: Get child categories
- `get_listings(subcategory_slug, page_num, child_slug, district_slug)`: Get listings
- `get_listing_details(slug)`: Get detailed listing info
- `download_image(image_url)`: Download image bytes
- `get_districts(subcategory_slug)`: Get available districts

### AutomotiveScraperOrchestrator
- `initialize()`: Setup scraper and S3 client
- `fetch_listing_details_batch(listings, subcategory_slug)`: Fetch and process listings
- `scrape_subcategory(subcategory, max_pages)`: Scrape a subcategory
- `scrape_all_subcategories(max_pages)`: Scrape all categories
- `save_all_to_s3(results)`: Upload results to S3

### S3Helper
- `upload_file(local_file_path, s3_filename)`: Upload file
- `upload_image(image_url, image_data, subcategory_slug)`: Upload image
- `upload_json_data(data, s3_filename)`: Upload JSON
- `generate_s3_url(s3_key)`: Generate public S3 URL
- `get_partition_prefix(target_date)`: Get date-based partition path

## Output

- **Excel Files**: One file per subcategory with info sheet + listings sheets
- **JSON Summary**: Complete metadata about scraped data
- **Images**: Original listing images organized by category
- **Logging**: Detailed logs of the scraping process

## Notes

- The scraper uses date-based partitioning (yesterday's data)
- Images are named as `{listing_id}_{image_index}.jpg`
- Category slugs like `classic-cars`, `junk-cars`, `food-trucks` are derived from URLs
- Rate limiting is applied between requests to avoid overwhelming the server
