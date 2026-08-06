# Rest Automotive Part 3 Scraper

Comprehensive scraper for Q84Sale automotive categories with AWS S3 integration. Handles three main categories:

1. **Dealerships** (`https://www.q84sale.com/ar/businesses/dealerships`)
2. **Car Offices** (`https://www.q84sale.com/ar/businesses/car-offices`)
3. **Car Rental** (`https://www.q84sale.com/ar/automotive/car-rental`)

## Features

- ✅ **Multi-Category Support**: Handles different URL structures and data formats
  - `businessesData` structure for dealerships and car-offices
  - `subcategories` structure for car-rental
- ✅ **Automatic Pagination**: Scrapes all available pages for each subcategory
- ✅ **Image Upload**: Downloads and uploads images to S3 with organized structure
- ✅ **Excel Organization**: Creates separate Excel files per category with subcategory sheets
- ✅ **AWS S3 Integration**: Automatic upload with date-based partitioning
- ✅ **Date Filtering**: Filters listings from yesterday by default
- ✅ **Detailed Information**: Extracts complete listing details including attributes

## Project Structure

```
Rest-Automotive-Part3/
├── main.py                 # Main orchestrator script
├── json_scraper.py         # Web scraper implementation
├── s3_helper.py            # AWS S3 upload helper
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Installation

### 1. Prerequisites

- Python 3.8 or higher
- AWS CLI configured with SSO
- Valid AWS credentials with S3 access

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure AWS Credentials (for local development)

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=data-collection-dl
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/rest-automotive-part3.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

## Usage

### Run the Scraper

```bash
python main.py
```

The scraper will:

1. **Initialize** AWS S3 connection
2. **Scrape** all three categories sequentially:
   - Dealerships (businesses structure)
   - Car Offices (businesses structure)
   - Car Rental (subcategories structure)
3. **Download** listing images
4. **Upload** everything to S3 with date partitioning

### Environment Variables

You can override defaults using environment variables:

```bash
# Set S3 bucket name
export S3_BUCKET_NAME=your-bucket-name

# Set AWS profile
export AWS_PROFILE=your-profile-name
```

## Data Structure

### Categories

#### 1. Dealerships & Car Offices

- **Main Page**: Lists all businesses
- **Business Page**: Lists all listings for that business
- **Details Page**: Full listing information

**URL Pattern**:
- Main: `https://www.q84sale.com/ar/businesses/{category}/`
- Business Listings: `https://www.q84sale.com/ar/businesses/{category}/{business-slug}/all`
- Details: `https://www.q84sale.com/ar/listing/{listing-slug}`

#### 2. Car Rental

- **Main Page**: Lists all subcategories
- **Subcategory Page**: Lists all listings with pagination
- **Details Page**: Full listing information

**URL Pattern**:
- Main: `https://www.q84sale.com/ar/automotive/car-rental`
- Listings: `https://www.q84sale.com/ar/automotive/car-rental/{subcategory-slug}/{page}`
- Details: `https://www.q84sale.com/ar/listing/{listing-slug}`

### S3 Upload Structure

```
s3://bucket-name/4sale-data/rest-automotive-part3/year=YYYY/month=MM/day=DD/
├── excel-files/
│   ├── dealerships.xlsx          # All dealerships data
│   ├── car-offices.xlsx          # All car offices data
│   └── car-rental.xlsx           # All car rental data
├── json-files/
│   ├── dealerships_summary_YYYYMMDD.json
│   ├── car-offices_summary_YYYYMMDD.json
│   └── car-rental_summary_YYYYMMDD.json
└── images/
    ├── {business-slug}/
    │   └── {listing_id}_{index}.jpg
    └── {subcategory-slug}/
        └── {listing_id}_{index}.jpg
```

### Excel File Structure

Each Excel file contains:

- **Info Sheet**: Summary of scraping session
  - Project name
  - Total subcategories/businesses
  - Total listings
  - Scrape date
  - S3 upload date

- **Individual Sheets**: One sheet per subcategory/business
  - Sheet name: Business/Subcategory name (max 31 chars)
  - Content: All listing details with attributes

## Data Fields

Each listing includes:

### Basic Information
- ID, slug, title, description
- Price, phone, contacts
- Publication dates
- Status

### User Information
- User name, email, phone
- User type, verification status
- Membership date
- Total ads count

### Location Information
- Address (Arabic)
- Full address (Arabic & English)
- Longitude, latitude

### Media
- Images (original URLs)
- S3 uploaded images
- Images count

### Attributes
- Specification (English & Arabic JSON)
- Individual flattened attributes:
  - Year, Color, Mileage
  - Body Type, Fuel Type
  - Transmission, Cylinders
  - And more...

### Business Information
- Business profile slug
- Business category slug
- Referer URL

## Logging

The scraper provides detailed logging:

```
2025-12-27 12:00:00 - INFO - Scraping data for date: 2025-12-26
2025-12-27 12:00:00 - INFO - Saving to S3 with date: 2025-12-27
2025-12-27 12:00:01 - INFO - SCRAPING CATEGORY: DEALERSHIPS
2025-12-27 12:00:02 - INFO - Found 5 businesses
2025-12-27 12:00:03 - INFO - Processing: Kuwait Finance House
...
```

## Error Handling

The scraper includes robust error handling:

- **Retry Logic**: Automatic retries for failed requests (3 attempts)
- **Rate Limiting**: Delays between requests to avoid blocking
- **Graceful Degradation**: Continues on individual failures
- **Cleanup**: Automatic cleanup of temporary files

## Filtering

By default, the scraper filters listings from **yesterday**. This is controlled by:

```python
self.scrape_date = datetime.now() - timedelta(days=1)  # Yesterday's data
```

To change the filtering behavior, modify the `filter_yesterday` parameter in the scraper calls.

## Performance

- **Parallel Operations**: Images downloaded asynchronously
- **Efficient Pagination**: Stops when no more data available
- **Optimized Storage**: Temporary files cleaned up automatically
- **Smart Naming**: Images named by listing ID for easy reference

## Troubleshooting

### AWS Authentication Issues

```bash
# Verify AWS credentials are set
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY

# Check S3 bucket access
aws s3 ls s3://your-bucket-name
```

### Connection Errors

- Check internet connection
- Verify website accessibility
- Check for rate limiting (increase delays)

### S3 Upload Failures

- Verify S3 bucket permissions
- Check bucket name in configuration
- Ensure sufficient disk space for temporary files

## Dependencies

- `boto3==1.26.137` - AWS SDK
- `aiohttp==3.9.1` - Async HTTP requests
- `requests==2.31.0` - Sync HTTP requests
- `beautifulsoup4==4.12.2` - HTML parsing
- `pandas==2.1.1` - Data manipulation
- `openpyxl==3.1.2` - Excel file creation
- `python-dateutil==2.8.2` - Date utilities

## Output

After successful execution:

```
============================================================
ALL CATEGORIES COMPLETED
============================================================

DEALERSHIPS:
  Total Listings: 150
  Excel File: dealerships.xlsx
  S3 URL: https://bucket.s3.region.amazonaws.com/...

CAR-OFFICES:
  Total Listings: 200
  Excel File: car-offices.xlsx
  S3 URL: https://bucket.s3.region.amazonaws.com/...

CAR-RENTAL:
  Total Listings: 180
  Excel File: car-rental.xlsx
  S3 URL: https://bucket.s3.region.amazonaws.com/...
```

## Notes

- The scraper uses BeautifulSoup to extract `__NEXT_DATA__` JSON from pages
- No Selenium/browser automation needed - faster and more reliable
- Images are uploaded with consistent naming: `{listing_id}_{index}.jpg`
- Each category gets its own Excel file with multiple sheets
- Data is partitioned by date in S3 for easy organization

## Support

For issues or questions, check the logs for detailed error messages. Common issues are usually related to:
- AWS authentication
- Network connectivity
- Rate limiting from the website

## License

Internal use only - Q84Sale data scraping project
