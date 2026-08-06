# Wanted Cars Scraper

A high-performance web scraper for Q84Sale's wanted-cars listings with AWS S3 integration.

## Overview

This scraper fetches listings from the wanted-cars section of Q84Sale.com and automatically discovers subcategories:
- **Wanted American Cars** - مطلوب ونشتري سيارات امريكية
- **Wanted European Cars** - مطلوب ونشتري سيارات اوروبية
- **Wanted Asian Cars** - مطلوب ونشتري سيارات اسيوية

Each subcategory's listings are scraped across multiple pages, with detailed information and images fetched and uploaded to AWS S3.

## Features

✅ **Automatic Subcategory Discovery** - Fetches all wanted-cars subcategories dynamically
✅ **Multi-Page Scraping** - Configurable pagination support for each subcategory
✅ **Detailed Listings** - Fetches comprehensive listing information including:
- Title, description, price
- Contact details (phone, email)
- User information and verification status
- Car attributes (year, color, mileage, etc.)
- Images with automatic upload to S3

✅ **Image Download & Upload** - All listing images are automatically downloaded and uploaded to S3
✅ **Excel Export** - Single Excel file (`wanted-cars.xlsx`) with sheets for each subcategory
✅ **JSON Summary** - Metadata summary in JSON format
✅ **S3 Integration** - AWS S3 storage with date-based partitioning:
  ```
  4sale-data/wanted-cars/year=YYYY/month=MM/day=DD/
  ├── excel-files/wanted-cars.xlsx
  ├── json-files/summary_YYYYMMDD.json
  └── images/{subcategory}/{listing_id}_{index}.jpg
  ```

## Installation

### 1. Requirements
```bash
pip install -r requirements.txt
```

### 2. AWS Configuration (for local development)
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=data-collection-dl
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/wanted-cars.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

## Usage

### Basic Usage
```bash
python main.py
```

### Logging
The scraper provides detailed logging:
- **INFO**: General progress and milestones
- **WARNING**: Recoverable issues (failed images, missing data)
- **ERROR**: Critical failures

## Output

### Excel File: `wanted-cars.xlsx`
Located in S3 at: `4sale-data/wanted-cars/year=YYYY/month=MM/day=DD/excel-files/wanted-cars.xlsx`

Contains sheets for:
- **Info** - Summary statistics
- **مطلوب ونشتري سيارات امريكية** - Wanted American Cars listings
- **مطلوب ونشتري سيارات اوروبية** - Wanted European Cars listings
- **مطلوب ونشتري سيارات اسيوية** - Wanted Asian Cars listings

### JSON Summary
Located in S3 at: `4sale-data/wanted-cars/year=YYYY/month=MM/day=DD/json-files/summary_YYYYMMDD.json`

Contains:
- Timestamp of scrape
- Subcategories with listing counts
- Total statistics

### Images
Located in S3 at: `4sale-data/wanted-cars/year=YYYY/month=MM/day=DD/images/{subcategory}/{listing_id}_{index}.jpg`

## Data Structure

### Listing Fields
Each listing includes:
- `id` - Listing ID
- `slug` - URL slug
- `title` - Listing title (in Arabic)
- `description` - Full description
- `price` - Asking price
- `phone` / `contacts` - Contact information
- `date_published` - Publication date
- `date_relative` - Human-readable date (e.g., "2 days ago")
- `images` - List of image URLs
- `s3_images` - List of S3 URLs for downloaded images
- `address` / `full_address` - Location information
- `views_no` - View count
- `user_name` - Seller name
- `user_email` - Seller email
- `user_type` - Seller type (normal, business, etc.)
- `is_verified` - Verification status
- `attributes` - Car-specific attributes (year, color, mileage, etc.)
- `status` - Listing status (normal, pinned, etc.)

## Architecture

### Components

1. **json_scraper.py** - WantedCarsJsonScraper
   - Extracts JSON from HTML using BeautifulSoup
   - Fetches subcategories dynamically
   - Retrieves listings and detailed information
   - Downloads images

2. **s3_helper.py** - S3Helper
   - AWS S3 client initialization with SSO
   - Automatic date-based partitioning
   - File and image upload with retry logic
   - JSON data upload
   - File listing and deletion

3. **main.py** - WantedCarsScraperOrchestrator
   - Orchestrates the entire scraping workflow
   - Manages async operations
   - Creates Excel files and JSON summaries
   - Coordinates S3 uploads
   - Handles cleanup and error recovery

## Error Handling

The scraper includes comprehensive error handling:
- **Retries** - Failed uploads retry up to 3 times
- **Graceful Degradation** - Missing images don't stop the scraping
- **Rate Limiting** - Built-in delays between requests
- **Logging** - All issues logged for debugging

## Performance

- **Speed** - Uses BeautifulSoup for fast JSON extraction
- **Concurrency** - Async operations for parallel processing
- **Efficiency** - Only downloads necessary data
- **Scalability** - Can handle thousands of listings

## S3 Partition Structure

```
4sale-data/wanted-cars/
├── year=2024/
│   └── month=12/
│       └── day=21/
│           ├── excel-files/
│           │   └── wanted-cars.xlsx
│           ├── json-files/
│           │   └── summary_20241221.json
│           └── images/
│               ├── wanted-american-cars/
│               │   ├── 20476856_0.jpg
│               │   ├── 20449517_0.jpg
│               │   └── ...
│               ├── wanted-european-car/
│               │   ├── 20476255_0.jpg
│               │   └── ...
│               └── wanted-asian-cars/
│                   └── ...
```

## Troubleshooting

### AWS Connection Issues
- Verify AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- Check S3 bucket permissions
- Ensure AWS_REGION is set correctly

### Empty Results
- Verify internet connection
- Check if Q84Sale website is accessible
- Review logs for specific error messages

### S3 Upload Failures
- Verify S3 bucket exists and is accessible
- Check AWS credentials are valid (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- Ensure IAM permissions include S3 operations

## API Response Structure

### Subcategories Endpoint
`https://www.q84sale.com/ar/automotive/wanted-cars/1`

```json
{
  "props": {
    "pageProps": {
      "catChilds": [
        {
          "id": 581,
          "slug": "wanted-american-cars",
          "name_ar": "مطلوب ونشتري سيارات امريكية",
          "name_en": "Wanted American Cars",
          "listings_count": 111,
          ...
        }
      ]
    }
  }
}
```

### Listings Endpoint
`https://www.q84sale.com/ar/automotive/wanted-cars/{slug}/1`

```json
{
  "props": {
    "pageProps": {
      "totalPages": 7,
      "listings": [
        {
          "id": 20476856,
          "title": "...",
          "slug": "wanted-american-cars-20476856",
          "price": 1000,
          ...
        }
      ]
    }
  }
}
```

### Details Endpoint
`https://www.q84sale.com/ar/listing/{slug}`

```json
{
  "props": {
    "pageProps": {
      "listing": {
        "user_adv_id": 20476856,
        "title": "...",
        "description": "...",
        "images": ["..."],
        "attrsAndVals": [...],
        ...
      }
    }
  }
}
```

## Notes

- The scraper respects rate limiting with delays between requests
- Images are automatically optimized and uploaded to S3
- Excel sheets are created with proper formatting
- JSON summaries provide structured metadata for further processing
- All timestamps are in UTC

## License

This project is for data collection and analysis purposes.
