# Commercials Scraper

Scraper for Q84Sale commercials section that extracts all commercial ads across different categories and saves them to AWS S3 with images.

## Overview

This scraper:
- Fetches all categories from the commercials section
- Scrapes commercial ads from each category (with pagination support)
- Downloads ad images and uploads them to S3
- Saves ad details to Excel files partitioned by date
- Uploads Excel files to S3 with organized folder structure

## Features

- **Category Discovery**: Automatically discovers all commercial categories
- **Pagination**: Handles multiple pages per category
- **Image Processing**: Downloads and uploads ad images to S3
- **S3 Partitioning**: Organizes data by date (year/month/day)
- **Excel Output**: Saves ad details in Excel format for each category
- **Rate Limiting**: Built-in delays to avoid overwhelming the server
- **Error Handling**: Robust error handling and retry logic

## Data Structure

### Categories
The scraper fetches categories from: `https://www.q84sale.com/ar/commercials/all`

Each category contains:
- `id`: Category ID
- `name`: Category name (Arabic)
- `slug`: URL-friendly category identifier
- `icon`: Category icon URL
- `total_pages`: Number of pages in the category

### Ads Data

For each ad, the scraper collects:
- `id`: Unique ad identifier
- `title`: Ad title
- `phone`: Contact phone number
- `whatsapp_phone`: WhatsApp contact number
- `image`: Original image URL
- `s3_image_path`: S3 path to uploaded image
- `views_count`: Number of views
- `category_id`: Category ID
- `category_slug`: Category slug
- `target_url`: External URL (if applicable)
- `open_target_url`: Whether to open URL in new window
- `is_landing`: Landing page flag
- `url`: URL to the ad details page

## S3 Structure

Data is organized in S3 with the following structure:

```
s3://your-bucket/4sale-data/commercials/
└── year=2026/
    └── month=01/
        └── day=08/
            ├── excel files/
            │   ├── commercials_property_20260108.xlsx
            │   ├── commercials_car-rental_20260108.xlsx
            │   └── ...
            └── images/
                ├── property_3865_0.jpg
                ├── property_8068_0.jpg
                └── ...
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up AWS credentials as environment variables:
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
export AWS_S3_BUCKET="your-bucket-name"
```

## Usage

### Local Execution

Run the scraper:
```bash
python main.py
```

### GitHub Actions

This scraper runs automatically via GitHub Actions (`.github/workflows/commercials.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

## How It Works

1. **Fetch Categories**: Retrieves all categories from the main commercials page
2. **Iterate Categories**: For each category:
   - Fetches all pages of ads
   - For each ad:
     - Fetches detailed information
     - Downloads the ad image
     - Uploads image to S3
3. **Save Results**: 
   - Creates Excel file with all ads for the category
   - Uploads Excel file to S3
4. **Cleanup**: Removes temporary files

## File Structure

```
Commercials/
├── json_scraper.py      # Core scraping logic
├── s3_helper.py         # S3 upload utilities
├── main.py              # Main orchestrator
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Example Output

### Console Output
```
===========================================================
STEP 1: Fetching Categories
===========================================================
Found 17 categories to scrape

===========================================================
CATEGORY 1/17
===========================================================
Processing Category: عقارات (property)
Total Pages: 1

Fetching page 1/1 for عقارات...
Found 5 ads on page 1
Fetching details for 5 ads...
✓ Uploaded image to s3://bucket/4sale-data/commercials/year=2026/month=01/day=08/images/property_3865_0.jpg
...
✓ Category عقارات: Total 5 ads collected
✓ Saved 5 ads to temp_commercials/commercials_property_20260108.xlsx
✓ Uploaded Excel to: s3://bucket/4sale-data/commercials/year=2026/month=01/day=08/excel files/commercials_property_20260108.xlsx
```

### Excel Columns
- id
- title
- category_slug
- category_id
- phone
- whatsapp_phone
- views_count
- image
- s3_image_path
- target_url
- open_target_url
- is_landing
- url

## Configuration

### Rate Limiting
- 0.5 seconds between ads
- 1 second between pages
- 0.1 seconds between image downloads

### Retry Logic
- S3 uploads: 3 retry attempts
- Image downloads: 1 attempt (logged and skipped on failure)

## Error Handling

The scraper includes comprehensive error handling:
- Network errors are logged and retried
- Missing data is handled gracefully
- Failed image downloads don't stop the scraper
- Failed uploads are logged with details

## Logging

Logs include:
- Category processing progress
- Page-by-page scraping status
- Image upload confirmations
- Excel file creation and upload status
- Error details and warnings
- Final summary with statistics

## Notes

- The scraper uses BeautifulSoup to extract JSON from `__NEXT_DATA__` script tags
- All dates are partitioned by the script execution date
- Images are named: `{category_slug}_{ad_id}_{index}.jpg`
- Excel files are named: `commercials_{category_slug}_{YYYYMMDD}.xlsx`

## Troubleshooting

**No categories found:**
- Check internet connection
- Verify the website structure hasn't changed

**S3 upload failures:**
- Verify AWS credentials are set correctly
- Check IAM permissions for S3 access
- Ensure bucket exists and is accessible

**Image download failures:**
- Some images may be unavailable or moved
- Check image URLs in the logs
- Failed images are skipped, scraping continues

## Support

For issues or questions, check the logs for detailed error messages.
