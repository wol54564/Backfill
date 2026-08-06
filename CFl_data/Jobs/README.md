# Jobs Scraper - Q84Sale

Web scraper for Q84Sale jobs listings with AWS S3 integration.

## Overview

This scraper extracts job listings from [https://www.q84sale.com/ar/jobs](https://www.q84sale.com/ar/jobs) and saves them to AWS S3 as Excel files.

### Key Features

- **Hierarchical Category Structure**: Handles 2-level category hierarchy
  - Main Categories (verticalSubcats): Job Openings, Job Seeker
  - Child Categories (catChilds): Part Time Job, Accounting, Technology, etc.
- **Separate Excel Files**: Creates one Excel file per main category
- **Multiple Sheets**: Each Excel file has sheets for each child category
- **Summary Information**: Each Excel file includes an "Info" sheet with metadata
- **AWS S3 Integration**: Automatic upload with date-based partitioning
- **Image Handling**: Downloads and uploads images to S3
- **Pagination Support**: Automatically scrapes all pages for each category
- **Rate Limiting**: Built-in delays to respect server resources

## Architecture

### Main Components

1. **json_scraper.py** - `JobsJsonScraper` class
   - Extracts JSON data from `__NEXT_DATA__` script tags
   - Fetches main subcategories (verticalSubcats)
   - Fetches child categories (catChilds) for each main category
   - Fetches listings with pagination
   - Downloads image data

2. **main.py** - `JobsScraperOrchestrator` class
   - Orchestrates the scraping process
   - Creates Excel files with proper structure
   - Handles S3 uploads
   - Manages rate limiting and error handling

3. **s3_helper.py** - `S3Helper` class
   - AWS S3 operations (upload, list, delete)
   - Date-based partition management
   - Image upload with ID-based naming

## Category Structure

```
Jobs (Main)
├── Job Openings (verticalSubcat)
│   ├── Part Time Job (catChild)
│   ├── Accounting
│   ├── Technology & Engineering
│   ├── Architecture & Manufacturing
│   ├── Freelance
│   ├── Medical
│   ├── Restaurant Job
│   ├── Hospitality & Tourism
│   ├── Driver
│   ├── Law Enforcement
│   ├── Marketing
│   └── Other Jobs
└── Job Seeker (verticalSubcat)
    ├── [Similar child categories...]
```

## Output Structure

### Excel Files
- **job-openings.xlsx** - All Job Openings listings with sheets for each child category
- **job-seeker.xlsx** - All Job Seeker listings with sheets for each child category

### S3 Partition Structure
```
4sale-data/jobs/
  year=2025/
    month=12/
      day=25/
        excel-files/
          job-openings.xlsx
          job-seeker.xlsx
        images/
          job-openings/
            123456_0.jpg
            123456_1.jpg
          job-seeker/
            ...
        upload-summary.json
```

## Setup

### Prerequisites
- Python 3.8+
- AWS credentials configured
- Required packages (see requirements.txt)

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure AWS credentials (for local development):
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=data-collection-dl
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/jobs.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

## Usage

### Basic Execution
```bash
python main.py
```

### What It Does
1. Fetches main subcategories (Job Openings, Job Seeker)
2. For each main category, fetches all child categories
3. For each child category, fetches all listings (all pages)
4. Creates separate Excel files for each main category
5. Uploads Excel files and images to S3
6. Saves upload summary as JSON

### Output
- **Console**: Detailed logging of all operations
- **S3**: Excel files, images, and summary JSON
- **Local**: Temporary files in `temp_data/` folder (cleaned up automatically)

## Data Structure

### Listing Fields
- `id` - Listing ID
- `title` - Job title
- `slug` - URL slug
- `description` - Job description (Arabic)
- `desc_en` - Job description (English)
- `phone` - Contact phone
- `date_published` - Publication date
- `cat_id` - Category ID
- `cat_name_en` / `cat_name_ar` - Category name
- `user_id` / `user_name` - Poster information
- `district_name` - District/Location
- `price` - Salary or job value
- `images` - Image URLs
- `s3_images` - S3 image URLs after upload

### Excel Sheet Structure

**Info Sheet** (Summary):
- Project: "Jobs"
- Main Category: Category name
- Main Category (EN): English name
- Total Child Categories: Count
- Total Listings: Count
- Data Scraped Date: YYYY-MM-DD
- Saved to S3 Date: YYYY-MM-DD

**Child Category Sheets**:
- One row per listing
- All listing fields as columns

## Differences from Wanted Cars Scraper

| Aspect | Wanted Cars | Jobs |
|--------|-------------|------|
| URL Structure | Single level (catChilds) | Two levels (verticalSubcats → catChilds) |
| Excel Files | One file per project | One file per main category |
| S3 Partition | `wanted-cars/` | `jobs/` |
| Main Categories | 3 (American, European, Asian) | 2 (Job Openings, Job Seeker) |
| Child Categories | Direct | Nested under main categories |

## Error Handling

- Automatic retry for failed uploads (3 attempts)
- Skip listings without required data
- Continue scraping even if some listings fail
- Comprehensive error logging
- Clean temporary files on exit

## Rate Limiting

- 0.5 second delay between listing detail fetches
- 1 second delay between pagination requests
- 1-2 second delay between category scrapes
- Reduces server load and prevents IP blocking

## Logging

The scraper uses Python's logging module with INFO level. Output includes:
- Timestamp
- Log level (INFO, WARNING, ERROR)
- Detailed operation messages

## Troubleshooting

### S3 Connection Issues
- Verify AWS profile name in `s3_helper.py`
- Check AWS credentials: `aws sts get-caller-identity --profile <profile-name>`
- Verify S3 bucket exists and is accessible

### Empty Results
- Check if website structure has changed
- Verify internet connection
- Check for IP rate limiting (pause and retry later)

### Excel Creation Issues
- Ensure openpyxl is installed: `pip install openpyxl`
- Check available disk space for temporary files

## Performance

- Average scrape time: ~30-45 minutes (depending on listings count)
- Image processing: ~15-30 seconds per listing with images
- S3 upload: ~2-5 minutes for all files

## Dependencies

- **requests** - HTTP requests
- **beautifulsoup4** - HTML/JSON parsing
- **pandas** - Excel file creation
- **openpyxl** - Excel formatting
- **boto3** - AWS S3 API
- **aiohttp** - Async HTTP (for future enhancements)
- **python-dateutil** - Date utilities

## License

Proprietary - Q84Sale Data Collection

## Author

AI Assistant

## Last Updated

December 25, 2025
