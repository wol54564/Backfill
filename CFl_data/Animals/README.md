# Q84Sale Animals Scraper

Scrapes animal listings from Q84Sale (https://www.q84sale.com/ar/animals) and exports data to Excel files stored in AWS S3.

## Features

- **JSON-based scraping**: Extracts data from `__NEXT_DATA__` script tags (fast and reliable)
- **All subcategories**: Dogs, Cats, Birds, Horses, Sheep, Camels, Animal Equipment, and Pet Food
- **Detailed listings**: Scrapes title, description, price, location, user info, images, and more
- **Image upload**: Downloads and uploads product images to S3
- **Excel export**: Creates organized Excel files with listings data
- **S3 integration**: AWS S3 storage with automatic date-based partitioning
- **Async operations**: Fast concurrent scraping and uploads

## Subcategories

- Dogs (كلاب)
- Cats (قطط)
- Birds (طيور)
- Horses (الخيل)
- Sheep (الماشيه)
- Camels (الابل)
- Animal & Pet Equipment (معدات الحيوانات والطيور)
- Animal & Pet Food (أعلاف)

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions:
- **Schedule**: Daily at 3:00 AM UTC (`.github/workflows/animals.yml`)
- **Manual trigger**: Available via workflow_dispatch
- **AWS credentials**: Configured via GitHub Secrets

### Required GitHub Secrets

- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `S3_BUCKET_NAME`: S3 bucket name (e.g., "data-collection-dl")

## Local Development Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure AWS Credentials

Set environment variables:

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=data-collection-dl
```

## Usage

### Run Locally

```bash
python main.py
```

### Run via GitHub Actions

- **Automatic**: Runs daily via cron schedule
- **Manual**: Go to Actions → Animals Scraper → Run workflow

### Output

- **Excel files**: `4sale-data/animals/year=YYYY/month=MM/day=DD/excel-files/`
- **Images**: `4sale-data/animals/year=YYYY/month=MM/day=DD/images/`
- **Summary JSON**: `4sale-data/animals/year=YYYY/month=MM/day=DD/json-files/`

## Data Structure

### Excel Sheets

Each category gets an Excel file with:
- **Info sheet**: Category name, total listings, scrape date
- **Listings sheet**: All listing details including:
  - ID, Title, Description
  - Price, User info, Contact
  - Images (S3 URLs), Location
  - Publish date, Status

## File Structure

```
Animals/
├── main.py              # Main orchestrator
├── json_scraper.py      # JSON extraction logic
├── s3_helper.py         # AWS S3 operations
├── requirements.txt     # Python dependencies
├── README.md            # This file
└── temp_data/          # Temporary files (cleaned after run)
```

## Details

- **Base URL**: https://www.q84sale.com/ar/animals
- **Subcategories URL**: `https://www.q84sale.com/ar/animals/{slug}/1`
- **Listing Details URL**: `https://www.q84sale.com/ar/listing/{slug}`
- **Data source**: `__NEXT_DATA__` JSON script tag in HTML
- **Pagination**: Supports multiple pages per category

## Notes

- Images are uploaded to S3 with naming: `{listing_id}_{index}.jpg`
- All dates use ISO 8601 format
- Rate limiting: 0.5-2 seconds between requests
- Temporary files are cleaned up after S3 upload

## Troubleshooting

### Authentication Error

- Verify AWS credentials are set correctly
- Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables
- Ensure S3 bucket permissions are configured properly

### No Data Found

- Check website structure at https://www.q84sale.com/ar/animals
- Verify Playwright chromium installation: `playwright install chromium`

### S3 Upload Fails

- Verify AWS credentials and S3 bucket access
- Check bucket name in environment variable
- Ensure bucket policy allows PutObject operations
