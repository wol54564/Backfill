# Dalil Kuwait Directory Scraper

This scraper extracts business listings from the Dalil Kuwait directory (directory.q84sale.com) and saves them to AWS S3.

## Features

- **16 Categories**: Scrapes all 16 Dalil categories (restaurants, healthcare, beauty, automotive, etc.)
- **Automatic Pagination**: Detects and scrapes all pages for each category (e.g., 26 pages for restaurants-cafes)
- **Comprehensive Data**: Extracts business details, branches, reviews, working hours, and media
- **Image Download**: Downloads and uploads all business images (logos, covers, gallery, menus) to S3
- **Excel Output**: Creates a single Excel file with multiple sheets (one per category)
- **S3 Integration**: Automatically uploads data to S3 with date partitioning
- **JSON Summary**: Generates summary stats in JSON format

## Categories Scraped

1. Restaurants & Cafes (`restaurants-cafes`)
2. Healthcare (`healthcare`)
3. Beauty & Spa (`beauty-spa`)
4. Automotive (`automotive`)
5. Fashion (`fashion`)
6. Technology (`technology`)
7. Education (`education`)
8. Real Estate (`real-estate`)
9. Home Services (`home-services`)
10. Professional & Business Services (`professional-business-services`)
11. Entertainment (`entertainment`)
12. Fitness & Sports (`fitness-sports`)
13. Pet Services (`pet-services`)
14. Travel & Tourism (`travel-tourism`)
15. Grocery & Supermarkets (`grocery-supermarkets`)
16. Shopping (`shopping`)

## Data Structure

### Excel File
- **One sheet per category**
- **Columns include**:
  - Business info: ID, name, slug, category
  - Ratings: average rating, rating count, reviews count
  - Contact: phone numbers, website, social media
  - Location: main branch address, coordinates
  - Branches: count and detailed JSON
  - Working hours: formatted schedule
  - Amenities: delivery, takeaway, dine-in, parking, WiFi, wheelchair accessible
  - Media: logos, covers, gallery images, menus
  - **S3 Images**: `s3_images_paths` column with S3 URLs, `s3_images_paths_json` with detailed metadata
  - Reviews: recent reviews in JSON format

### S3 Structure
```
s3://bucket-name/4sale-data/Dalil/year=YYYY/month=MM/day=DD/
├── dalil_directory_YYYYMMDD.xlsx          # Main Excel file
├── dalil_summary_YYYYMMDD.json            # Summary statistics
└── images/                                 # Business images
    ├── restaurants-cafes/
    │   ├── business_135_image_1234.jpg
    │   └── ...
    ├── healthcare/
    └── ...
```

## Setup

### Prerequisites
- Python 3.8+
- AWS credentials configured (environment variables)
- S3 bucket access

### Installation

```bash
pip install -r requirements.txt
```

### Environment Variables

```bash
export S3_BUCKET_NAME="your-bucket-name"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"  # Optional, defaults to us-east-1
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/dalil.yml`):
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

### Workflow

1. **Category Scraping**: Fetches business listings from each category page (with automatic pagination)
2. **Pagination Detection**: Automatically detects total pages and scrapes all pages per category
3. **Detail Scraping**: Retrieves detailed data for each business
4. **Image Filtering**: Validates media tab status and filters out protected Google URLs
5. **Image Processing**: Downloads and uploads valid images to S3 (organized by category)
6. **Excel Generation**: Creates multi-sheet Excel file with all data
7. **S3 Upload**: Uploads Excel file and JSON summary to S3

## Output

### Excel File Sheets
Each category becomes a sheet with columns including:
- **s3_images_paths**: Pipe-separated list of S3 URLs for images
- **s3_images_paths_json**: Detailed JSON with image metadata (type, original URL, S3 path)
- **branches_json**: Detailed branch information in JSON
- **recent_reviews_json**: Recent customer reviews in JSON

### JSON Summary
```json
{
  "scraped_at": "2026-02-16T10:30:00",
  "saved_to_s3_date": "2026-02-16",
  "total_categories": 16,
  "total_businesses": 250,
  "total_images": 1500,
  "categories": [
    {
      "slug": "restaurants-cafes",
      "name": "المطاعم والمقاهي",
      "total_businesses": 50
    },
    ...
  ]
}
```

## Key Files

- **json_scraper.py**: Core scraping logic for Dalil directory
- **s3_helper.py**: AWS S3 operations and image handling
- **main.py**: Orchestration and data processing
- **requirements.txt**: Python dependencies

## Image Processing

### Smart Image Filtering
The scraper includes intelligent image filtering to avoid download failures:

- **Media Tab Check**: Only extracts images if the business's media tab is enabled
- **Google URL Filtering**: Automatically skips Google protected image URLs that return 403 errors:
  - `lh3.googleusercontent.com` (Google Photos)
  - `gps-cs-s` (Google Place Service)
  - `gps-proxy` (Google Proxy)
- **Valid URL Validation**: Ensures URLs start with http:// or https://

This prevents unnecessary retry attempts and keeps the scraping process efficient.

## Error Handling

- Retries on failed HTTP requests (3 attempts with exponential backoff)
- Graceful handling of missing data
- Skips inaccessible or protected images
- Continues processing even if individual items fail
- Detailed logging of all operations
- Continues scraping even if individual businesses fail

## Logging

The scraper provides detailed logging:
- Category progress
- Business scraping status
- Image upload results
- S3 upload confirmations
- Error messages with context

## Notes

- **Rate Limiting**: Built-in delays to respect server limits (0.5s between businesses, 1s between categories)
- **Image Organization**: Images stored in S3 by category for easy management
- **Data Freshness**: Include scrape timestamp in all outputs
- **Multiple Branches**: Full branch data preserved in JSON format
- **Reviews**: Recent reviews included for business insights

## Maintenance

### Updating Categories
To add/remove categories, edit the `categories` list in `json_scraper.py`:

```python
self.categories = [
    "restaurants-cafes",
    "healthcare",
    # Add new categories here
]
```

### Adjusting Image Processing
Modify batch size in `main.py` to control concurrent image downloads:

```python
batch_size = 10  # Adjust based on network capacity
```

## Troubleshooting

### Common Issues

1. **S3 Upload Fails**: Check AWS credentials and bucket permissions
2. **Missing Images**: Check network connectivity and image URLs
3. **Empty Excel**: Verify category URLs are accessible
4. **Slow Performance**: Increase delays or reduce batch size

### Debug Mode

Enable debug logging by modifying the logging level:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Support

For issues or questions, check the logs for detailed error messages. The scraper is designed to be fault-tolerant and will continue processing even if individual items fail.
