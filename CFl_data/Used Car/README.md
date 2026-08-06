# Used Cars Scraper - Q84Sale

## Overview

This scraper collects used car listings from Q84Sale (https://www.q84sale.com/ar/automotive/used-cars/) and organizes them into Excel files for easy analysis.

### Key Features

- **Hierarchical Data Structure**: Organizes data by make (Toyota, Lexus, etc.) and model (Land Cruiser, Camry, etc.)
- **Excel Organization**: Each main category gets its own Excel file, with subcategories as sheets
- **AWS S3 Integration**: Automatically uploads processed data to S3 with date-based partitioning
- **Full Page Scraping**: Fetches all available pages for each subcategory
- **Professional Formatting**: Styled Excel files with headers, borders, and optimized column widths

## Data Structure

```
Main Categories (Excel Files):
├── Toyota.xlsx
│   ├── Land Cruiser (sheet)
│   ├── Camry (sheet)
│   ├── Prado (sheet)
│   └── ...
├── Lexus.xlsx
│   ├── ES (sheet)
│   ├── RX (sheet)
│   └── ...
└── Chevrolet.xlsx
    └── ...
```

## Installation

### Prerequisites

- Python 3.8+
- AWS account with S3 access

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure AWS credentials (for local development):
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=data-collection-dl
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/used-car.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

## Usage

### Basic Usage

Run the scraper to collect all available used car listings:

```bash
python main_used_cars.py
```

### Configuration

Edit `main_used_cars.py` to customize:

```python
# Configuration
BUCKET_NAME = "4sale-data"  # Your S3 bucket name
PROFILE_NAME = None  # Optional AWS profile name
MAX_CATEGORIES = None  # None to scrape all categories, or set a number like 5
```

### Scraping Specific Categories

To limit scraping to the first 5 categories:

```python
MAX_CATEGORIES = 5
```

## Output Format

### Excel Files

Each Excel file contains:

| Column | Description |
|--------|-------------|
| Listing ID | Unique identifier |
| Title | Listing title |
| Slug | URL slug for the listing |
| Price | Price in KWD |
| Phone | Seller's phone number |
| User Name | Seller's name |
| Date Published | When the listing was posted |
| District | Location (Kuwait district) |
| Status | Listing status (pinned, normal, etc.) |
| Images Count | Number of images |
| Description (EN) | English description |
| Description (AR) | Arabic description |
| Category Name | Car model/category |

### S3 Storage

Files are organized with date-based partitioning:
```
s3://4sale-data/4sale-data/used-cars/year=2024/month=12/day=30/
├── Toyota.xlsx
├── Lexus.xlsx
├── Chevrolet.xlsx
└── ...
```

## API Reference

### UsedCarsJsonScraper

#### `get_main_categories()`
Fetches all main car brands (Toyota, Lexus, Chevrolet, etc.)

**Returns**: List of category dictionaries with:
- `id`: Category ID
- `slug`: URL slug
- `name_ar`: Arabic name
- `name_en`: English name
- `listings_count`: Total listings
- `slug_url`: Full URL slug

#### `get_subcategories(main_category_slug)`
Fetches all models for a specific brand.

**Args**:
- `main_category_slug` (str): The brand slug (e.g., 'toyota')

**Returns**: List of subcategory dictionaries with model information

#### `get_listings(category_slug, subcategory_slug=None, page_num=1)`
Fetches listings for a category or subcategory.

**Args**:
- `category_slug` (str): Main category slug
- `subcategory_slug` (str, optional): Model slug
- `page_num` (int): Page number (default 1)

**Returns**: Tuple of (listings_list, total_pages)

#### `get_listing_details(slug)`
Fetches detailed information for a specific listing.

**Args**:
- `slug` (str): Listing slug (format: 'model-id')

**Returns**: Dictionary with detailed listing info including images

### UsedCarsScraperOrchestrator

#### `run_scraper(max_categories=None)`
Main orchestrator method that:
1. Fetches all main categories
2. For each category, fetches all subcategories
3. For each subcategory, fetches all listings across all pages
4. Creates Excel file with proper styling
5. Uploads to S3

**Args**:
- `max_categories` (int, optional): Limit number of categories to scrape

### S3Helper

#### `upload_file(local_file_path, s3_filename, target_date=None)`
Uploads a file to S3 with automatic date-based partitioning.

**Args**:
- `local_file_path` (str): Local file path
- `s3_filename` (str): Filename in S3
- `target_date` (datetime, optional): Date for partitioning

**Returns**: S3 path or None if failed

#### `download_file(s3_filename, local_file_path, target_date=None)`
Downloads a file from S3.

**Args**:
- `s3_filename` (str): Filename in S3
- `local_file_path` (str): Where to save locally
- `target_date` (datetime, optional): Date for partitioning

**Returns**: True if successful, False otherwise

## Data Collection Flow

```
1. Fetch Main Categories
   └─→ Get list of brands (Toyota, Lexus, etc.)

2. For Each Main Category
   └─→ Fetch Subcategories
       └─→ Get list of models (Land Cruiser, Camry, etc.)

3. For Each Subcategory
   └─→ Fetch All Listings (All Pages)
       ├─→ Page 1, Page 2, ... until no more pages
       └─→ Collect listing details

4. Format Data
   └─→ Create Excel file with proper styling

5. Upload to S3
   └─→ Save to: 4sale-data/used-cars/year=YYYY/month=MM/day=DD/
```

## Example Data

### Sample Listing

```json
{
  "id": 20499635,
  "title": "صباح الناصر",
  "slug": "land-cruiser-20499635",
  "price": 1750,
  "phone": "96565555210",
  "user_name": "نايف العدواني",
  "date_published": "2025-12-24 09:55:42",
  "district_name": "الفروانية",
  "status": "pinned",
  "images_count": 9,
  "cat_name_en": "Land Cruiser",
  "cat_name_ar": "لاند كروزر",
  "desc_en": "For sale Land Cruiser automatic model 97...",
  "desc_ar": "للبيع لاندكروز تماتيك موديل 97..."
}
```

## Logging

The scraper provides detailed logging output:

```
2024-12-30 10:15:23 - INFO - Fetching used-cars main categories...
2024-12-30 10:15:24 - INFO - Found 67 main categories
2024-12-30 10:15:24 - INFO - [1/67] Processing: Toyota
2024-12-30 10:15:25 - INFO - Fetching subcategories for toyota...
2024-12-30 10:15:26 - INFO - Found 35 subcategories for toyota
2024-12-30 10:15:26 - INFO -   - Land Cruiser: 937 listings
...
```

## Error Handling

The scraper includes robust error handling:

- **Network Errors**: Automatically retries failed uploads (3 attempts)
- **Missing Data**: Logs warnings and continues processing
- **Empty Categories**: Skips categories with no listings
- **S3 Errors**: Falls back gracefully if S3 is unavailable

## Performance Notes

- **Request Rate**: 0.3-0.5 seconds between requests (to avoid overwhelming the server)
- **Page Limits**: No limit on pages per subcategory (fetches all available)
- **Memory**: Efficient streaming of data to Excel

## Troubleshooting

### AWS Credentials Not Found
```
ValueError: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables must be set
```
**Solution**: Set environment variables with your AWS credentials

### S3 Bucket Access Denied
```
Error initializing S3 client: An error occurred (AccessDenied)...
```
**Solution**: Verify your AWS credentials have S3 permissions

### No Data Scraped
**Possible Causes**:
- Website structure changed
- Network connectivity issues
- IP blocked (try with VPN)

**Solution**: 
1. Check logs for specific errors
2. Verify website is accessible: https://www.q84sale.com/ar/automotive/used-cars/1
3. Check for website maintenance

## File Details

- **main_used_cars.py**: Main orchestrator script
- **json_scraper_used_cars.py**: JSON extraction and scraping logic
- **s3_helper.py**: AWS S3 upload/download utilities
- **requirements.txt**: Python dependencies

## License

This scraper is part of the Q84Sale data collection project.

## Support

For issues or questions:
1. Check the logs for specific error messages
2. Verify all dependencies are installed
3. Confirm AWS credentials are properly configured
4. Check internet connectivity to the Q84Sale website
