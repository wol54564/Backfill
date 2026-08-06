# Q84Sale Property Scraper

Scrapes property listings from Q84Sale (https://www.q84sale.com/ar/property) and exports data to Excel files stored in AWS S3.

## Features

- **Property listings**: Scrapes real estate listings including apartments, houses, land, and commercial properties
- **Detailed information**: Extracts property details, location, price, size, amenities, and more
- **Image collection**: Downloads and uploads property images to S3
- **Excel export**: Creates organized Excel files with property data
- **S3 integration**: AWS S3 storage with automatic date-based partitioning
- **Async operations**: Fast concurrent scraping and uploads

## Project Structure

```
Property/
├── details_scraping.py    # Property details scraper
├── main.py               # Main orchestrator
├── s3_uploader.py       # AWS S3 upload functionality
└── README.md           # This file
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions:
- **Schedule**: Daily at 3:00 AM UTC (`.github/workflows/property.yml`)
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
- **Manual**: Go to Actions → Property Scraper → Run workflow

### How It Works

1. **Fetch subcategories**: Retrieves all property subcategories from the main property page
2. **Scrape listings**: Collects listing summaries from each subcategory
3. **Extract details**: Gets detailed information for each listing
4. **Download images**: Downloads property images
5. **Upload to S3**: Uploads Excel files and images to S3

## Output Format

### Excel Files
- **Naming**: Based on subcategory and date
- **Location**: `4sale-data/property/year=YYYY/month=MM/day=DD/`
- **Columns**: Title, Description, Price, Location, Property Type, Size, Amenities, Images, Contact Info, etc.

### Images
- **Location**: `4sale-data/property/year=YYYY/month=MM/day=DD/images/`
- **Format**: Original format preserved (JPEG, PNG, etc.)
- **Naming**: `{listing_id}_{image_index}.{extension}`

## Property Categories

Common property subcategories include:
- Apartments for Sale (شقق للبيع)
- Houses for Sale (بيوت للبيع)
- Land for Sale (أراضي للبيع)
- Commercial Properties (عقارات تجارية)
- Properties for Rent (عقارات للإيجار)

## Logging

The scraper provides detailed logging:
- INFO: Progress updates, subcategories found, listings scraped
- WARNING: Missing data, failed downloads
- ERROR: Failed requests, S3 upload errors

## Error Handling

- **Session management**: Maintains persistent session for better performance
- **User-Agent headers**: Mimics browser requests
- **Graceful failures**: Continues scraping even if individual listings fail
- **Retry logic**: Handles temporary network issues

## Notes

- Scrapes data from yesterday's date by default
- Uses BeautifulSoup for HTML parsing
- Respects website rate limits
- Automatically handles pagination
- Date-based partitioning in S3 for easy data organization
