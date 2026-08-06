# Education Web Scraper

A Python-based web scraper for the Education category on Q84Sale (https://www.q84sale.com/ar/education). This scraper handles both direct listings and nested category structures, automatically generates Excel files, and uploads everything to AWS S3.

## Features

- **Flexible Category Handling**:
  - **Case 1**: Categories with direct listings (e.g., school-supplies)
  - **Case 2**: Categories with child categories (e.g., languages → arabic-teaching, english-teaching, etc.)

- **Smart Data Organization**:
  - One Excel file created per vertical subcategory
  - Child categories become separate sheets within the Excel file
  - Summary information included in every Excel file

- **Image Management**:
  - Automatically downloads listing images
  - Uploads images to AWS S3 with organized folder structure
  - Generates S3 URLs for image tracking

- **Automatic Pagination**:
  - Scrapes all available pages for each category
  - Automatically detects total pages from API response
  - Rate limiting between requests

- **AWS S3 Integration**:
  - Saves data with automatic date-based partitioning
  - Partition structure: `4sale-data/education/year=YYYY/month=MM/day=DD/`
  - Credentials configured via environment variables

## Project Structure

```
Education/
├── json_scraper.py          # Web scraper using BeautifulSoup
├── main.py                  # Orchestrator and Excel file generator
├── s3_helper.py             # AWS S3 operations handler
├── requirements.txt         # Python dependencies
└── temp_data/              # Temporary directory for Excel files
```

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/Scripts/activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure AWS credentials (for local development):
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=data-collection-dl
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/education.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

## Usage

### Basic Usage

Run the scraper locally:
```bash
python main.py
```

### Expected Output

The scraper generates:

1. **Excel Files** (one per subcategory):
   - `school-supplies.xlsx` - Direct listings category
   - `languages.xlsx` - Category with sheets for each child (arabic-teaching, english-teaching, french-teaching, etc.)
   - Each Excel file includes:
     - **Info sheet**: Summary statistics
     - **Listing sheets**: Data for each category/child category

2. **JSON Summary**:
   - `summary_YYYYMMDD.json` - Metadata about the scraping job

3. **Images**: Organized by subcategory and listing ID in S3

## Data Schema

### Listing Fields

Each listing includes:
- `id` - Unique listing ID
- `title` - Listing title
- `slug` - URL slug
- `price` - Price
- `image` - Main image URL
- `date_published` - Publication date
- `cat_id` - Category ID
- `cat_name_en` / `cat_name_ar` - Category names
- `user_id` / `user_name` - User information
- `phone` / `contact_no` - Contact information
- `district_name` - District
- `status` - Listing status
- `desc_ar` / `desc_en` - Description in Arabic/English
- `s3_images` - Array of S3 image URLs

### Excel Structure Examples

**Direct Listings Category** (school-supplies):
```
Sheet: Info
- Project, Subcategory, Type (Direct Listings), Total Listings, Total Pages, Data Saved Date

Sheet: Listings
- All listing fields as columns
```

**Category with Children** (languages):
```
Sheet: Info
- Project, Subcategory, Type (Has Child Categories), Child Categories Count, Total Listings, Data Saved Date

Sheet: تدريس لغة عربية (Arabic Teaching)
- All listing fields for child category 1

Sheet: تدريس لغة انجليزية (English Teaching)
- All listing fields for child category 2

Sheet: تدريس لغة فرنسية (French Teaching)
- All listing fields for child category 3
```

## How It Works

1. **Discover Categories**: Fetches `verticalSubcats` from the main education page
2. **Check for Children**: For each category, checks if it has `catChilds`
3. **Handle Both Cases**:
   - **Case 1**: Scrapes direct listings if no children found
   - **Case 2**: Scrapes each child category's listings
4. **Fetch Details**: For each listing, fetches detailed information
5. **Process Images**: Downloads and uploads images to S3
6. **Generate Excel**: Creates organized Excel files with summaries
7. **Upload to S3**: Saves all files with date-based partitioning

## Logging

The scraper provides detailed logging:
- `INFO` level: Main progress updates
- `WARNING` level: Missing data or non-critical issues
- `ERROR` level: Failures that should be addressed
- `DEBUG` level: Detailed operation information (not shown by default)

## Error Handling

- Automatic retry logic for S3 uploads (3 attempts with exponential backoff)
- Graceful handling of missing listings or images
- Partial scraping continues even if individual listings fail
- Cleanup of temporary files even if errors occur

## Performance

- Asynchronous operations for faster data fetching
- Rate limiting to prevent overwhelming the server:
  - 0.5 seconds between listing detail fetches
  - 1 second between page requests
  - 1 second between child category requests
  - 2 seconds between subcategory requests

## Troubleshooting

### AWS S3 Connection Issues
```
Error: Failed to initialize S3 client
Solution: Verify AWS credentials are configured
$ echo $AWS_ACCESS_KEY_ID
$ echo $AWS_SECRET_ACCESS_KEY
```

### No Data Found
```
Warning: No verticalSubcats found in education page
Solution: Check if the URL structure has changed on Q84Sale website
```

### Excel File Not Created
```
Error: No data to upload
Solution: Check if listings were successfully scraped (check logs for listing count)
```

## API Response Structure

The scraper extracts data from JSON embedded in the page:
```html
<script id="__NEXT_DATA__" type="application/json">
{
    "props": {
        "pageProps": {
            "verticalSubcats": [...],  // Main categories
            "catChilds": [...],         // Child categories (if any)
            "listings": [...],          // Listings for the page
            "totalPages": 1             // Total pages available
        }
    }
}
</script>
```

## Notes

- The scraper only processes published and active listings
- Images are automatically resized for consistency
- S3 URLs are generated for all uploaded images
- Dates are automatically partitioned by year/month/day in S3
- All text supports both Arabic and English

## License

Internal use only

## Support

For issues or improvements, please refer to the project documentation or contact the development team.
