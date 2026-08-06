# Electronics Scraper - Q84Sale

A powerful scraper for collecting electronics listings from Q84Sale with automatic category structure detection and AWS S3 integration.

## Features

- **Automatic Category Structure Detection**: Intelligently detects three different category types:
  - **Case 1**: Categories with catChilds (e.g., Mobile Phones with brands: iPhone, Samsung, Huawei)
  - **Case 2**: Categories with subcategories (e.g., Cameras with types: Monitoring, Digital, Professional)
  - **Case 3**: Direct listings categories (no sub-levels)

- **Complete Listing Details**: Scrapes both listing summaries and detailed information
- **Image Handling**: Downloads and uploads images to AWS S3
- **Excel Export**: Creates organized Excel files with separate sheets for each subcategory
- **AWS S3 Integration**: Automatic partitioning by date (year/month/day)
- **Rate Limiting**: Built-in delays to respect server resources
- **Error Handling**: Robust error handling with retry mechanisms

## Project Structure

```
Electronics/
├── json_scraper.py      # Core scraping logic
├── main.py             # Orchestrator and execution
├── s3_helper.py        # AWS S3 helper functions
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Category Structure

The scraper handles three different category structures on the website:

### Case 1: Categories with catChilds
Example: **Mobile Phones and Accessories**
- Main category: `mobile-phones-and-accessories`
- Children: iPhone, Samsung, Huawei, Other Phones, Accessories
- URL pattern: `https://www.q84sale.com/ar/electronics/mobile-phones-and-accessories/{child-slug}/1`

### Case 2: Categories with Subcategories
Example: **Cameras**
- Main category: `cameras`
- Subcategories: Monitoring Cameras, Digital Cameras, Professional Cameras
- URL pattern: `https://www.q84sale.com/ar/electronics/{main-slug}/{sub-slug}/1`

### Case 3: Direct Listings
Example: **Smartwatches**
- Main category: `smartwatches`
- No children - direct listings
- URL pattern: `https://www.q84sale.com/ar/electronics/{main-slug}/1`

## Output Format

### Excel Files
- **Naming**: One file per main category (e.g., `mobile-phones-and-accessories.xlsx`)
- **Sheets**: 
  - `Info` sheet with summary statistics
  - One sheet per child category/subcategory with listing data
- **Location**: Uploaded to S3 at `4sale-data/electronics/year=YYYY/month=MM/day=DD/excel-files/`

### JSON Summary
- Contains metadata about the scraping session
- Lists all main categories and their statistics
- Location: `4sale-data/electronics/year=YYYY/month=MM/day=DD/json-files/`

### Images
- Organized by category slug
- Named as: `{listing_id}_{image_index}.jpg`
- Location: `4sale-data/electronics/year=YYYY/month=MM/day=DD/images/{category-slug}/`

## Data Extraction

### Listing Information
Each listing includes:
- **Basic Info**: ID, title, slug, price, date published
- **Images**: URLs and count
- **User Info**: Name, phone, email, verification status
- **Location**: District name, full address, coordinates
- **Attributes**: Specifications with both English and Arabic values
- **Status**: Normal, pinned, etc.

### Detail Pages
For each listing, the scraper fetches:
- Full description (Arabic and English)
- All images (downloaded and uploaded to S3)
- Detailed attributes and specifications
- Contact information
- Seller/business profile information

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or manually install required packages
pip install pandas openpyxl boto3 requests beautifulsoup4 aiohttp python-dateutil
```

## Configuration

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/electronics.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

### Local Development Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set AWS credentials as environment variables:
   ```bash
   export AWS_ACCESS_KEY_ID=your-access-key
   export AWS_SECRET_ACCESS_KEY=your-secret-key
   export AWS_REGION=us-east-1
   export S3_BUCKET_NAME=data-collection-dl
   ```

## Usage

### Run the Scraper
```bash
python main.py
```

### Options
The scraper automatically:
- Scrapes ALL available pages per category (no limit)
- Detects category structure automatically
- Creates separate sheets for children/subcategories
- Organizes Excel files by main category
- Uploads images and data to S3

## Data Flow

1. **Fetch Main Categories**: Get all electronics subcategories from the main page
2. **Detect Structure**: For each category, determine if it has catChilds, subcategories, or direct listings
3. **Scrape Listings**: For each child/category, get all listings across all pages
4. **Fetch Details**: Get detailed information and images for each listing
5. **Upload Images**: Download and upload images to S3
6. **Create Excel**: Organize data into Excel files with proper sheet structure
7. **Upload Files**: Upload Excel files and JSON summary to S3

## Performance

- **Rate Limiting**: 0.5-2 second delays between requests
- **Image Downloads**: Parallel processing with asyncio
- **Batch Operations**: Efficient bulk uploads to S3
- **Memory Efficient**: Processes and uploads data in batches

## Logging

The scraper provides detailed logging:
- Fetching progress
- Category structure detection
- Listing count per category
- Image upload status
- S3 upload results

Check console output for real-time progress updates.

## API Response Structure

### Main Categories Response
```json
{
  "props": {
    "pageProps": {
      "verticalSubcats": [
        {
          "id": 99,
          "slug": "mobile-phones-and-accessories",
          "name_ar": "موبايلات و إكسسوارات",
          "name_en": "Mobile Phones & Accessories",
          ...
        }
      ]
    }
  }
}
```

### Listings Response
```json
{
  "props": {
    "pageProps": {
      "totalPages": 19,
      "listings": [...]
    }
  }
}
```

### Details Response
```json
{
  "props": {
    "pageProps": {
      "listing": {
        "user_adv_id": 20494872,
        "title": "...",
        "description": "...",
        ...
      }
    }
  }
}
```

## Troubleshooting

### No data found
- Check internet connection
- Verify website is accessible
- Check if the main electronics page URL is correct

### S3 upload fails
- Verify AWS credentials are configured
- Check S3 bucket name and permissions
- Ensure AWS profile is correctly set up

### Missing images
- Check image URLs in the response
- Verify image download attempts in logs
- Check S3 bucket storage permissions

## S3 Structure

After running, your S3 bucket will have this structure:
```
4sale-data/
└── electronics/
    └── year=2024/
        └── month=12/
            └── day=22/
                ├── excel-files/
                │   ├── mobile-phones-and-accessories.xlsx
                │   ├── cameras.xlsx
                │   └── ...
                ├── json-files/
                │   └── electronics_summary_20241222.json
                └── images/
                    ├── mobile-phones-and-accessories/
                    │   ├── 20494872_0.jpg
                    │   ├── 20494872_1.jpg
                    │   └── ...
                    ├── cameras/
                    │   └── ...
                    └── ...
```

## Notes

- The scraper respects the website's server by using rate limiting
- Images are verified before upload
- Duplicate detection based on listing ID
- Date partitioning makes it easy to organize historical data
- Each run creates a complete snapshot of the electronics category

## License

[Add your license here]

## Support

For issues or questions, please contact [your contact info]
