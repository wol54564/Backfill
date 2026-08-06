# Q84Sale Camping Scraper

Scrapes camping-related listings from Q84Sale (https://www.q84sale.com/ar/camping) and exports data to Excel files stored in AWS S3.

## Features

- **JSON-based scraping**: Extracts data from `__NEXT_DATA__` script tags (fast and reliable)
- **All subcategories**: Trampoline for Rent, Camping Stuff, Tents, and more
- **Detailed listings**: Scrapes title, description, price, location, user info, images, and more
- **Image upload**: Downloads and uploads product images to S3
- **Excel export**: Creates organized Excel files with listings data
- **S3 integration**: AWS S3 storage with automatic date-based partitioning
- **Async operations**: Fast concurrent scraping and uploads

## Project Structure

```
Camping/
├── json_scraper.py      # Core scraping logic
├── main.py             # Orchestrator and execution
├── s3_helper.py        # AWS S3 helper functions
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions:
- **Schedule**: Daily at 2:30 AM UTC (`.github/workflows/camping.yml`)
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
- **Manual**: Go to Actions → Camping Scraper → Run workflow

## Output Format

### Excel Files
- **Naming**: One file per subcategory (e.g., `trampoline-for-rent.xlsx`)
- **Location**: Uploaded to S3 at `4sale-data/camping/year=YYYY/month=MM/day=DD/`
- **Columns**: Title, Description, Price, Location, User Info, Images, Date Posted, etc.

### Images
- **Location**: `4sale-data/camping/year=YYYY/month=MM/day=DD/images/`
- **Format**: Original format preserved (JPEG, PNG, etc.)
- **Naming**: `{listing_id}_{image_index}.{extension}`

## Logging

The scraper provides detailed logging:
- INFO: Progress updates, subcategories found, listings scraped
- WARNING: Missing data, failed image downloads
- ERROR: Failed requests, S3 upload errors

## Error Handling

- **Rate limiting**: Built-in delays between requests
- **Retry logic**: Automatic retries for failed requests
- **Graceful failures**: Continues scraping even if individual listings fail

## Notes

- Scrapes data from yesterday's date by default
- Uses Playwright for dynamic content loading
- Respects website rate limits
- Automatically handles pagination
