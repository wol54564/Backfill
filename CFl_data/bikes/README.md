# Bikes Scraper - Q84Sale

Scraper for the bikes category on Q84Sale (https://www.q84sale.com/ar/automotive/bikes)

## Overview

This scraper handles the bikes category which has a unique structure with two types of subcategories:

1. **Subcategories with catChilds** (e.g., motorbikes-sport, quad-bikes)
   - These have additional subcategories (catChilds) like BMW, Honda, Yamaha
   - Each catChild becomes a separate sheet in the Excel file

2. **Direct Listings** (e.g., bicycles, scooter, wanted-bikes)
   - These go directly to listings without additional subcategories
   - All listings are in a single sheet

## Features

- **Automatic subcategory detection**: Identifies whether a subcategory has catChilds or direct listings
- **Separate Excel files**: Each main subcategory (motorbikes-sport, quad-bikes, bicycles, etc.) gets its own Excel file
- **Multi-sheet support**: Subcategories with catChilds have each catChild as a separate sheet
- **Image download and S3 upload**: Downloads all images and uploads to S3
- **AWS S3 integration**: Partitioned by date (bikes/year=YYYY/month=MM/day=DD/)

## Structure

### Main Subcategories (as of December 2024)

1. **motorbikes-sport** (Has catChilds)
   - BMW
   - Honda
   - Yamaha
   - Ducati
   - Harley Davidson
   - Suzuki
   - Kawazaki
   - Can-Am
   - Vespa
   - MV Agusta
   - KTM
   - Aprilia
   - Moto Guzzi
   - Other Motorbikes

2. **quad-bikes** (Has catChilds)
   - Various brands

3. **bicycles** (Direct Listings)

4. **scooter** (Direct Listings)

5. **wanted-bikes** (Direct Listings)

## Files

- `json_scraper.py`: Core scraper using BeautifulSoup4 to extract JSON from __NEXT_DATA__
- `main.py`: Orchestrator that coordinates scraping and S3 uploads
- `s3_helper.py`: AWS S3 integration with automatic partitioning
- `requirements.txt`: Python dependencies

## Usage

### Prerequisites

For local development:

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

### GitHub Actions

This scraper runs automatically via GitHub Actions (`.github/workflows/bikes.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch
- **Credentials**: Set via GitHub Secrets (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME)

### Running the Scraper

```bash
python main.py
```

### Environment Variables

- `S3_BUCKET_NAME`: S3 bucket name (default: data-collection-dl)
- `AWS_PROFILE`: AWS profile name (optional)

## Output Structure

### Excel Files

Each main subcategory gets its own Excel file:

- `motorbikes-sport.xlsx`
  - Info sheet (summary)
  - BMW sheet
  - Honda sheet
  - Yamaha sheet
  - ... (one sheet per catChild)

- `bicycles.xlsx`
  - Info sheet (summary)
  - Listings sheet (all listings)

### S3 Structure

```
4sale-data/bikes/year=2024/month=12/day=27/
├── excel-files/
│   ├── motorbikes-sport.xlsx
│   ├── quad-bikes.xlsx
│   ├── bicycles.xlsx
│   ├── scooter.xlsx
│   └── wanted-bikes.xlsx
├── images/
│   ├── motorbikes-sport/
│   │   ├── automotive_bikes_motorbikes-sport_bmw-2397_1/
│   │   │   ├── 20500958_0.jpg
│   │   │   ├── 20500958_1.jpg
│   │   │   └── ...
│   │   └── automotive_bikes_motorbikes-sport_honda-2398_1/
│   │       └── ...
│   └── bicycles/
│       └── automotive_bikes_bicycles_1/
│           ├── 20504479_0.jpg
│           └── ...
└── json-files/
    └── summary_20241227.json
```

## Data Fields

Each listing includes:

- **Basic Info**: id, title, slug, description, price
- **Contact**: phone, user info, contact details
- **Location**: district, coordinates
- **Media**: images, S3 image URLs
- **Dates**: published, created, expired
- **Attributes**: Year, Color, Mileage, Model, etc. (varies by category)
- **User Info**: name, email, membership, verification status
- **Statistics**: views, ads count

## Technical Details

### Scraping Method

Uses BeautifulSoup4 to extract JSON data from the `__NEXT_DATA__` script tag in the HTML:
- Fast and reliable
- No need for Playwright/Selenium
- Direct access to structured data

### Rate Limiting

- 0.5 seconds between listings
- 1 second between pages
- 2 seconds between catChilds
- 3 seconds between main subcategories

### Data Filtering

- Scrapes listings from yesterday by default
- Filters by date_published field
- Skips ad boxes automatically

## Logging

Comprehensive logging at INFO level:
- Subcategory discovery
- Page scraping progress
- Image downloads
- S3 uploads
- Error tracking

## Error Handling

- Retry logic for S3 uploads (3 attempts)
- Graceful handling of missing data
- Detailed error logging
- Temporary file cleanup

## Notes

- The `is_leaf` field determines if a subcategory has catChilds or direct listings
- catChilds are only fetched if is_leaf=False
- Each main subcategory is independent and can be scraped separately
- S3 partitioning uses the save date (today) not the scrape date (yesterday)
