# Others Category Scraper

Web scraper for Q84Sale "Others" category listings with AWS S3 integration.

## Overview

This scraper collects listing data from the Q84Sale "Others" category and uploads it to AWS S3 with organized partitioning. Each subcategory gets its own Excel file with an Info summary sheet.

## Subcategories Scraped

1. **Currencies, Stamps & Antiques** (`currencies-stamps-and-antiques`)
2. **Books** (`books`)
3. **Wholesale** (`wholesale`)
4. **Stickers** (`stickers`)
5. **Lost and Found** (`lost-and-found`)
6. **Other Miscellaneous** (`other-miscellaneous`)

## Features

- ✅ **Separate Excel Files**: Each subcategory gets its own Excel file
- ✅ **Info Summary Sheet**: Each Excel file includes an Info sheet with metadata
- ✅ **Image Downloading**: Downloads and uploads images to S3
- ✅ **S3 Partitioning**: Organized by date (year/month/day)
- ✅ **Automatic Pagination**: Scrapes all available pages
- ✅ **Rate Limiting**: Prevents overwhelming the server
- ✅ **Yesterday's Data**: Filters listings from yesterday by default

## S3 Structure

```
s3://bucket-name/
└── 4sale-data/
    └── others/
        └── year=2025/
            └── month=12/
                └── day=25/
                    ├── excel-files/
                    │   ├── currencies-stamps-and-antiques.xlsx
                    │   ├── books.xlsx
                    │   ├── wholesale.xlsx
                    │   ├── stickers.xlsx
                    │   ├── lost-and-found.xlsx
                    │   └── other-miscellaneous.xlsx
                    ├── json-files/
                    │   └── summary_20251225.json
                    └── images/
                        ├── currencies-stamps-and-antiques/
                        │   ├── 20456076_0.jpg
                        │   └── 20456076_1.jpg
                        ├── books/
                        └── ...
```

## Excel File Structure

Each Excel file contains:

### 1. Info Sheet
- Project name
- Subcategory information (slug, Arabic name, English name)
- Total listings count
- Total pages scraped
- Data scraped date
- Saved to S3 date

### 2. Data Sheet
- All listing details with columns:
  - Basic Info: id, title, slug, description, price
  - Dates: date_published, date_created, date_expired
  - Images: images, s3_images, images_count
  - Location: address, full_address, longitude, latitude
  - User Info: user_name, user_email, user_phone, user_type
  - Contact: phone, is_hide_my_number
  - Attributes: specification_en, specification_ar (+ flattened columns)

## Installation

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure AWS credentials** (for local development):
   ```bash
   export AWS_ACCESS_KEY_ID=your-access-key
   export AWS_SECRET_ACCESS_KEY=your-secret-key
   export AWS_REGION=us-east-1
   export S3_BUCKET_NAME=data-collection-dl
   ```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/others.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`
   ```

## Usage

Run the scraper:

```bash
python main.py
```

The scraper will:
1. Fetch all 6 subcategories
2. Scrape all pages for each subcategory (filtering yesterday's data)
3. Download detailed listing information
4. Download and upload images to S3
5. Create separate Excel files for each subcategory
6. Upload everything to S3 with date partitioning

## Configuration

### Date Filtering
- **Scrape Date**: Yesterday's data (`datetime.now() - timedelta(days=1)`)
- **Save Date**: Today's date for S3 partitioning (`datetime.now()`)

### Rate Limiting
- 0.1s between image downloads
- 0.5s between listing detail fetches
- 1s between pages
- 2s between subcategories

### Retry Logic
- File uploads: 3 retries with exponential backoff

## Output Files

### Excel Files (per subcategory)
- `currencies-stamps-and-antiques.xlsx`
- `books.xlsx`
- `wholesale.xlsx`
- `stickers.xlsx`
- `lost-and-found.xlsx`
- `other-miscellaneous.xlsx`

### JSON Summary
```json
{
  "scraped_at": "2025-12-25T10:30:00",
  "data_scraped_date": "2025-12-24",
  "saved_to_s3_date": "2025-12-25",
  "total_subcategories": 6,
  "total_listings": 150,
  "subcategories": [
    {
      "name_ar": "عملات و طوابع و تحف قديمه",
      "name_en": "Currencies, Stamps & Antiques",
      "slug": "currencies-stamps-and-antiques",
      "listings_count": 25,
      "total_pages_scraped": 2
    }
  ]
}
```

## Architecture

### Files
- **`json_scraper.py`**: Core scraping logic using BeautifulSoup
- **`main.py`**: Orchestrates scraping and S3 uploads
- **`s3_helper.py`**: AWS S3 operations with partitioning
- **`requirements.txt`**: Python dependencies

### Key Classes

1. **OthersJsonScraper**
   - Extracts JSON from `__NEXT_DATA__` script tag
   - Handles pagination
   - Fetches listing details
   - Downloads images

2. **OthersScraperOrchestrator**
   - Manages scraping workflow
   - Coordinates S3 uploads
   - Creates Excel files with Info sheets
   - Handles cleanup

3. **S3Helper**
   - AWS S3 client management
   - Date-based partitioning
   - File and image uploads
   - URL generation

## Error Handling

- Retries on network failures
- Graceful handling of missing data
- Comprehensive logging
- Automatic cleanup of temporary files

## Logging

Logs include:
- Scraping progress
- S3 upload status
- Error messages with stack traces
- Summary statistics

## AWS Configuration

AWS credentials are set via environment variables:
- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
- `AWS_REGION`: AWS region (default: us-east-1)
- `S3_BUCKET_NAME`: Target S3 bucket name

## Notes

- Scrapes listings from yesterday by default
- Each subcategory is saved in a separate Excel file
- Info sheet provides quick overview of each file
- Images are organized by subcategory in S3
- All timestamps are in local timezone

## Dependencies

- Python 3.8+
- boto3 (AWS SDK)
- aiohttp (async HTTP)
- requests (HTTP client)
- beautifulsoup4 (HTML parsing)
- pandas (data manipulation)
- openpyxl (Excel files)
- python-dateutil (date parsing)

## License

Internal use only.
