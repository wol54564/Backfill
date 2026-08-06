# Furniture Scraper - Q84Sale

Web scraper for furniture listings from Q84Sale (https://www.q84sale.com/ar/furniture) with AWS S3 integration.

## Overview

This scraper handles the furniture category which has subcategories with 3 different structures:

### Case 1: District Filtration
- **Type**: `listings_district_filteration` or `listings_full_filtration`
- **Example**: Wanted Furniture
- **Structure**: Main page + district-specific pages
- **URL Pattern**: 
  - Main: `https://www.q84sale.com/ar/furniture/wanted-furniture/1`
  - District: `https://www.q84sale.com/ar/furniture/wanted-furniture/1/ahmadi--district`
- **Excel Output**: One file with sheets for Main and each District

### Case 2: Direct Listings
- **Type**: `listings`
- **Example**: Bedrooms, Living Room
- **Structure**: Direct listings without districts or subcategories
- **URL Pattern**: `https://www.q84sale.com/ar/furniture/bedrooms/1`
- **Excel Output**: One file with a single Listings sheet

### Case 3: CatChilds
- **Type**: Any type with `catChilds` array
- **Example**: Textiles (contains Curtains, Carpets, etc.)
- **Structure**: Parent category with child categories
- **URL Pattern**: `https://www.q84sale.com/ar/furniture/textiles/curtains/1`
- **Excel Output**: One file with sheets for each CatChild

## Features

- **Automatic Case Detection**: Identifies and handles all 3 cases automatically
- **Separate Excel Files**: Each subcategory gets its own Excel file
- **Multi-Sheet Support**: Districts and CatChilds appear as separate sheets
- **AWS S3 Integration**: Uploads data with date partitioning
- **Image Download**: Downloads and uploads listing images to S3
- **Detailed Logging**: Comprehensive logging for monitoring
- **Rate Limiting**: Built-in delays to avoid overwhelming the server

## Prerequisites

- Python 3.8+
- AWS Account with S3 access

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. For local development, configure AWS credentials:
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=data-collection-dl
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/furniture.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

## Usage

Run the scraper locally:
```bash
python main.py
```

The scraper will:
1. Fetch all subcategories from the furniture main page
2. Determine the case for each subcategory (1, 2, or 3)
3. Scrape all listings from all pages
4. Download listing images
5. Create separate Excel files for each subcategory
6. Upload everything to S3 with date partitioning

## Output Structure

### S3 Bucket Structure
```
4sale-data/furniture/
  year=2025/
    month=12/
      day=24/
        excel-files/
          wanted-furniture.xlsx
          bedrooms.xlsx
          textiles.xlsx
          ...
        images/
          wanted-furniture/
            20471662_0.jpg
            20471662_1.jpg
          bedrooms/
            20485791_0.jpg
        json-files/
          summary_20251224.json
```

### Excel File Structure

**Case 1 Example (wanted-furniture.xlsx):**
- Sheet: Main (main page listings)
- Sheet: الأحمدي (Ahmadi district listings)
- Sheet: الجهراء (Jahra district listings)
- ... (one sheet per district)

**Case 2 Example (bedrooms.xlsx):**
- Sheet: Listings (all listings)

**Case 3 Example (textiles.xlsx):**
- Sheet: الستائر (Curtains listings)
- Sheet: السجاد (Carpets listings)
- ... (one sheet per catchild)

## Data Fields

Each listing includes:

### Basic Information
- id, slug, title, description, price
- date_published, date_created, date_expired
- status, images_count

### User Information
- user_name, user_email, user_phone
- user_type, membership, is_verified

### Location
- address, full_address, full_address_en
- district_name, longitude, latitude

### Images
- images (array of original URLs)
- s3_images (array of S3 URLs)

### Specifications
- specification_en (JSON)
- specification_ar (JSON)
- Individual attribute columns

## Logging

The scraper provides detailed logging:
- Subcategory detection and case identification
- Page-by-page progress
- District/CatChild processing
- Image download and upload status
- Excel file creation
- S3 upload confirmation

## Error Handling

- Automatic retry for S3 uploads (3 attempts)
- Graceful handling of missing data
- Continues scraping even if individual listings fail
- Comprehensive error logging

## Monitoring

Check progress through console logs:
```
[1/11] Processing: نشتري الاثاث المستعمل (wanted-furniture)
[CASE 1] Processing: نشتري الاثاث المستعمل (District Filtration)
Scraping main page for wanted-furniture...
Found 6 districts for wanted-furniture
Scraping district: محافظة الأحمدي (ahmadi--district)...
✓ Uploaded: wanted-furniture.xlsx (518 listings)
```

## Files

- `main.py` - Main orchestrator handling 3 cases
- `json_scraper.py` - Scraper implementation with case logic
- `s3_helper.py` - AWS S3 integration for furniture
- `requirements.txt` - Python dependencies
- `README.md` - This file

## Troubleshooting

### No AWS credentials
- Verify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set
- Check environment variables are configured correctly
- Ensure S3 bucket permissions are properly configured

### Missing data
- Check if the website structure has changed
- Verify the __NEXT_DATA__ script tag is present
- Review logs for specific errors

### Upload failures
- Verify S3 bucket permissions
- Check network connectivity
- Review AWS credentials

## Notes

- Scrapes yesterday's data by default (configurable)
- Saves to S3 with today's date for partitioning
- Each subcategory gets its own Excel file
- Districts and CatChilds appear as separate sheets within the Excel file
- Automatically detects which case applies to each subcategory
- No manual configuration needed for different subcategories

## Author

Q84Sale Data Collection Project

## License

Internal use only
