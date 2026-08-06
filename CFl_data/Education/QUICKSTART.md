# Education Scraper - Quick Start Guide

## Project Overview

The Education scraper is designed to extract educational listings from Q84Sale with intelligent handling of category structures:

```
Q84Sale Education Page
        ↓
Discover verticalSubcats (7 categories)
        ↓
For each category:
    ├─ Check for catChilds
    │
    ├─ Case 1: No children (Direct Listings)
    │   └─ Scrape all pages → Create single Excel file
    │
    └─ Case 2: Has children (Child Categories)
        └─ For each child: Scrape all pages → Create Excel with sheet per child
        
Upload to S3 with date partitioning
```

## File Structure

```
Education/
├── json_scraper.py              # Web scraping logic
├── main.py                      # Main orchestrator
├── s3_helper.py                 # AWS S3 operations
├── requirements.txt             # Dependencies
├── README.md                    # Full documentation
├── IMPLEMENTATION_SUMMARY.md    # Differences from Wanted Cars
└── temp_data/                  # Temporary files (auto-created)
    └── *.xlsx                  # Excel files before S3 upload
```

## Quick Start

### 1. Setup (First Time Only)

```bash
cd Education

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Login to AWS
aws sso login --profile PowerUserAccess-235010163908
```

### 2. Run the Scraper

```bash
python main.py
```

### 3. Monitor Progress

The scraper will show:
- Category discovery
- Pagination progress (page X of Y)
- Image upload counts
- Excel file creation
- S3 upload status
- Final summary

## Expected Output

### Excel Files (in S3)
One per vertical subcategory:

1. **`school-supplies.xlsx`** (Case 1)
   - Sheet: Info → Summary
   - Sheet: Listings → 3 listings

2. **`languages.xlsx`** (Case 2)
   - Sheet: Info → Summary with 3 child categories
   - Sheet: تدريس لغة عربية → 103 listings
   - Sheet: تدريس لغة انجليزية → 113 listings
   - Sheet: تدريس لغة فرنسية → 24 listings

3. **`all-science.xlsx`** (Case 2)
   - Similar structure with multiple child categories

... and so on for other categories

### S3 Folder Structure

```
4sale-data/education/
└── year=2025/
    └── month=12/
        └── day=24/
            ├── excel-files/
            │   ├── school-supplies.xlsx
            │   ├── languages.xlsx
            │   ├── all-science.xlsx
            │   └── ...
            ├── json-files/
            │   └── summary_20251224.json
            └── images/
                ├── school-supplies/
                ├── languages/
                └── ...
```

## How It Detects Cases

### Case 1 Detection (Direct Listings)
```python
get_child_categories(slug) → returns []
→ Scrape direct listings for this category
→ Create Excel with single "Listings" sheet
```

**Examples**: school-supplies, other-subjects, teaching-services

### Case 2 Detection (Child Categories)
```python
get_child_categories(slug) → returns [child1, child2, ...]
→ For each child: Scrape listings
→ Create Excel with sheet per child + Info sheet
```

**Examples**: languages (3 children), all-science (multiple children), etc.

## Handling Both Cases in Excel

### Direct Listings Example (school-supplies.xlsx)

| Sheet | Content |
|-------|---------|
| Info | Project: Education<br>Subcategory: اللوازم المدرسية<br>Type: Direct Listings<br>Total Listings: 3<br>Date: 2025-12-24 |
| Listings | id\|title\|slug\|price\|...<br>20487486\|مدرس لغه...\|school-supplies-20487486\|7\|...<br>20484314\|معلم كيمياء\|school-supplies-20484314\|null\|... |

### Child Categories Example (languages.xlsx)

| Sheet | Content |
|-------|---------|
| Info | Project: Education<br>Subcategory: تعليم لغات<br>Type: Has Child Categories<br>Child Categories Count: 3<br>Total Listings: 240<br>Date: 2025-12-24 |
| تدريس لغة عربية | id\|title\|slug\|price\|...<br>(103 listings for Arabic Teaching) |
| تدريس لغة انجليزية | id\|title\|slug\|price\|...<br>(113 listings for English Teaching) |
| تدريس لغة فرنسية | id\|title\|slug\|price\|...<br>(24 listings for French Teaching) |

## Key Features Explained

### 1. Automatic Pagination
```
For each category:
  page = 1
  while page <= totalPages:
    fetch listings from page
    get details for each listing
    download and upload images
    page += 1
```

### 2. Image Management
```
For each listing image:
  1. Download from Q84Sale
  2. Upload to S3: /year=2025/month=12/day=24/images/{category}/{listing_id}/{index}.jpg
  3. Generate S3 URL
  4. Store URL in Excel
```

### 3. Error Recovery
- Retries failed S3 uploads (3 attempts)
- Continues scraping if individual listings fail
- Logs all issues for review

### 4. Rate Limiting
- 0.5 sec between listing detail fetches
- 1 sec between page requests
- 1 sec between child category requests
- 2 sec between subcategory requests

## Log Output Examples

### Successful Run
```
INFO - Fetching education vertical subcategories...
INFO - Found 7 vertical subcategories
INFO - [1/7] Processing: اللوازم المدرسية (school-supplies)
INFO - No child categories found - scraping direct listings
INFO - Fetching listings for school-supplies page 1/1...
INFO - Found 3 listings on page 1
INFO - Creating Excel file for: اللوازم المدرسية...
INFO - Uploading to AWS S3...
✓ Uploaded: school-supplies.xlsx (3 listings)
```

### Category with Children
```
INFO - [2/7] Processing: تعليم لغات (languages)
INFO - Found 3 child categories
INFO - [1/3] Processing child category: تدريس لغة عربية (arabic-teaching)
INFO - Fetching listings for languages/arabic-teaching page 1/1...
INFO - Found 103 listings
INFO - Creating Excel file for: تعليم لغات...
INFO - Created sheet: تدريس لغة عربية (103 listings)
INFO - Created sheet: تدريس لغة انجليزية (113 listings)
INFO - Created sheet: تدريس لغة فرنسية (24 listings)
```

## Data Fields in Listings

Each listing includes:
```
id              - Unique identifier
title           - Arabic/English title
slug            - URL-friendly identifier
price           - Listing price
image           - Main image URL
date_published  - Publication timestamp
cat_id          - Category ID
cat_name_ar/en  - Category names
user_id         - Posted by user ID
user_name       - Posted by user name
phone           - Contact phone
contact_no      - Contact numbers (array)
district_name   - Geographic district
status          - Listing status (normal, etc.)
desc_ar/en      - Description in Arabic/English
s3_images       - Array of S3 image URLs
```

## Environment Variables (Optional)

```bash
# Set custom S3 bucket
export S3_BUCKET_NAME=my-bucket

# Set custom AWS profile
export AWS_PROFILE=my-profile

# Then run
python main.py
```

## Troubleshooting

### Issue: "No verticalSubcats found"
**Solution**: The website structure may have changed. Check the main page HTML for the correct data structure.

### Issue: "Failed to initialize S3 client"
**Solution**: Ensure AWS SSO is logged in:
```bash
aws sso login --profile PowerUserAccess-235010163908
```

### Issue: Excel files not uploading
**Solution**: Check AWS permissions and S3 bucket exists:
```bash
aws s3 ls s3://data-collection-dl --profile PowerUserAccess-235010163908
```

## Performance Notes

- Typical run time: 30-60 minutes depending on listing count
- Network bandwidth: ~100-500 MB for images
- Local disk usage: ~50 MB for temporary files
- S3 objects created: ~1000-5000 (listings + images)

## Next Steps

After the first successful run:

1. Check S3 console for uploaded files
2. Download and verify Excel files locally
3. Review JSON summary for metadata
4. Adjust logging level if needed (see main.py)
5. Schedule regular runs (daily, weekly, etc.)

## Support Files

- `README.md` - Complete documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical differences from Wanted Cars
- This file - Quick start guide

For detailed information, refer to the full README.md
