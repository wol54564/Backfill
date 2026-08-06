# Rest-Automotive-Part2: Automotive Services Scraper

Scrapes automotive services subcategories, listings, and details from [q84sale.com](https://www.q84sale.com/ar/automotive/automotive-services) and exports them to an Excel file with subcategories as sheet names.

## Features

- **Scrapes automotive-services subcategories** (Car Services, Remote Programming, Washing & Waxing, etc.)
- **Fetches all listings** for each subcategory across all pages
- **Downloads detailed information** for each listing
- **Downloads and uploads images** to AWS S3
- **Creates single Excel file** with one sheet per subcategory
- **AWS S3 integration** with automatic date-based partitioning

## Project Structure

```
Rest-Automotive-Part2/
├── main.py                 # Main orchestrator
├── json_scraper.py        # Web scraper for q84sale API
├── s3_helper.py           # AWS S3 helper functions
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Setup

### Prerequisites

- Python 3.8 or higher
- AWS credentials configured (SSO profile recommended)
- Internet connection

### Installation

1. Navigate to the project directory:
```bash
cd Rest-Automotive-Part2
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### AWS Configuration (for local development)

1. Configure AWS credentials:
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=data-collection-dl
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/rest-automotive-part2.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

## Usage

### Run the scraper:

```bash
python main.py
```

### For testing with limited data:

Edit `main.py` and uncomment the line:
```python
MAX_LISTINGS = 5  # Scrape only 5 listings per subcategory (good for testing)
```

## Output

### Excel File
- **Location**: S3 bucket under `4sale-data/rest-automotives-part2/year=YYYY/month=MM/day=DD/excel-files/automotive-services.xlsx`
- **Structure**: One sheet per subcategory (Car Services, Remote Programming, etc.)
- **Columns**:
  - ID
  - Title
  - Phone
  - User
  - User ID
  - Description
  - Price
  - Date Published
  - Images Count
  - District
  - Slug

### Images
- **Location**: S3 bucket under `4sale-data/rest-automotives-part2/year=YYYY/month=MM/day=DD/images/{subcategory_slug}/`
- **Naming**: `{listing_id}_{image_index}.jpg`

## Data Structure

### Main Category
- **URL**: https://www.q84sale.com/ar/automotive/automotive-services

### Subcategories (12 total)
1. Services (خدمات المعدات) - 12 listings
2. Car Services (خدمات السيارات) - 389 listings
3. Remote Programming (برمجة ريموت) - 395 listings
4. Washing & Waxing (الغسيل والتلميع) - 263 listings
5. Cars Tinting & Protection (تظليل حراري وحماية) - 11 listings
6. Crane (سطحات) - 374 listings
7. Insurance (التأمين) - 3 listings
8. Shipment (شحن خارجي) - 34 listings
9. Driving Lessons (تعليم قيادة) - 79 listings
10. Watercraft Services (خدمات قوارب) - 41 listings
11. Mechanic & Electronic Cars (ميكانيك وكهرباء سيارات) - 177 listings

### Sample Listing Structure
Each listing contains:
- ID, title, phone, user information
- Description (both English and Arabic)
- Price
- Publication date
- Multiple images with URLs
- Category and district information
- Contact details

## How It Works

1. **Fetch Subcategories**: Extracts subcategory list from the main category page
2. **Fetch Listings**: For each subcategory, fetches all listings across all pages
3. **Fetch Details**: For each listing, downloads detailed information
4. **Create Excel**: Consolidates all data into a single Excel file with sheets per subcategory
5. **Upload Files**: Uploads Excel file and images to AWS S3 with automatic partitioning

## Error Handling

The scraper includes:
- Automatic retry logic for failed requests (up to 3 attempts)
- Graceful handling of missing data
- Detailed logging of all operations
- Session management to avoid connection issues

## Performance

- **Typical runtime**: 30-60 minutes (depends on number of listings and image count)
- **Image downloads**: ~0.2 seconds per image (configurable)
- **API calls**: Includes delays to be respectful to the server

## Logging

All operations are logged with timestamps. Output includes:
- Progress information
- Errors and warnings
- Statistics (listings fetched, images uploaded, etc.)
- S3 upload URLs

## Troubleshooting

### S3 Connection Issues
- Verify AWS credentials are configured correctly
- Check environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
- Check bucket name is correct
- Verify IAM permissions for the profile

### Network Issues
- Check internet connection
- The script will retry up to 3 times on failure
- Consider running during off-peak hours

### Excel File Issues
- Ensure openpyxl is installed: `pip install openpyxl`
- Check disk space for temporary files
- Sheet names are automatically limited to 31 characters (Excel limit)

## Development

### Adding custom filters
Edit the `get_all_listings_for_subcategory` call in `main.py` to add filters.

### Modifying Excel structure
Update `convert_listings_to_dataframe` in `main.py` to change columns or formatting.

### Adjusting delays
Modify the `await asyncio.sleep()` values in `main.py` to speed up or slow down execution.

## Notes

- The scraper respects rate limiting with delays between requests
- Data is partitioned by date in S3 automatically
- Both Arabic and English data is preserved
- Images are stored with listing ID for easy reference

## License

Internal use only.
