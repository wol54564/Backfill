# Rest-Automative-Part1 Scraper - Setup Complete ✓

## Summary

I've successfully updated the Rest-Automative-Part1 scraper to match the architecture of the Wanted-Cars project with improved features.

## Files Updated

### 1. **json_scraper.py** - RestAutomotiveJsonScraper
   - Now includes async image downloading with aiohttp
   - Added `format_relative_date()` method for better date handling
   - Enhanced attribute extraction with nested JSON structure
   - Supports 5 categories:
     - Watercraft (المركبات المائية)
     - Spare Parts (قطع الغيار)
     - Automotive Accessories (إكسسوارات سيارات)
     - CMVs (المركبات التجارية)
     - Rentals (تأجير)
   - Fetches listings across multiple pages per subcategory
   - Retrieves detailed listing information from individual listing pages
   - Downloads all images associated with listings
   - Extracts item attributes (year, color, mileage, etc.)

### 2. **main.py** - RestAutomotiveScraperOrchestrator
   - Updated to use modern async patterns like Wanted-Cars
   - Automatically discovers all categories and subcategories
   - Scrapes each subcategory with unlimited pagination
   - **Excel Output**: Separate files for each category:
     - Watercraft.xlsx
     - Spare Parts.xlsx
     - Automotive Accessories.xlsx
     - CMVs.xlsx
     - Rentals.xlsx
   - Each Excel file contains:
     - Info sheet (summary statistics)
     - Sheets for each subcategory in that category
   - **JSON Output**: Single summary metadata file with category grouping
   - **Image Organization**: Organized by subcategory slug in S3
   - Handles cleanup and error recovery

## Key Features

✅ **Automatic Category Discovery**
- No hardcoding needed
- Dynamically fetches all 5 categories and their subcategories

✅ **Separate Excel Files Per Category**
- Watercraft.xlsx, Spare Parts.xlsx, Automotive Accessories.xlsx, CMVs.xlsx, Rentals.xlsx
- Each file contains its own subcategories as sheets
- Easier to organize and analyze by category

✅ **Complete Data Extraction**
- Title, description, price
- Contact information (phone, email)
- Listing date and relative date formatting
- User information and verification status
- Location (district, coordinates)
- Listing attributes (nested and flattened)
- All images with S3 URLs

✅ **Improved Image Handling**
- Async downloads using aiohttp
- Better error handling and retry logic
- Organized S3 structure by subcategory

✅ **Production Ready**
- Rate limiting between requests
- Comprehensive logging
- Error recovery
- Clean temporary files
- Configurable pagination

## S3 Partition Structure

```
4sale-data/rest-automative/year=2024/month=12/day=21/
├── excel-files/
│   ├── Watercraft.xlsx
│   ├── Spare Parts.xlsx
│   ├── Automotive Accessories.xlsx
│   ├── CMVs.xlsx
│   └── Rentals.xlsx
├── json-files/
│   └── summary_20241221.json
└── images/
    ├── watercraft/
    ├── spare-parts/
    ├── automotive-accessories/
    ├── cmvs/
    └── rentals/
```

## Excel Structure

```
Watercraft.xlsx
├── Sheet: Info (project summary for this category)
├── Sheet: Subcategory 1 Name (listings)
└── Sheet: Subcategory 2 Name (listings)

Spare Parts.xlsx
├── Sheet: Info
├── Sheet: Subcategory 1 Name (listings)
└── Sheet: Subcategory 2 Name (listings)

(Same for: Automotive Accessories.xlsx, CMVs.xlsx, Rentals.xlsx)
```

## How to Use

### Installation
```bash
cd Rest-Automative-Part1
pip install -r requirements.txt
```

### Configure AWS
```bash
aws configure sso
# Profile name: PowerUserAccess-235010163908
# Region: us-east-1
```

### Run Scraper
```bash
# Default (scrape all pages)
python main.py

# Custom S3 bucket
S3_BUCKET_NAME="my-bucket" python main.py

# Custom AWS profile
AWS_PROFILE="my-profile" python main.py
```

## Expected Results

### Typical Run
- **Duration**: 20-40 minutes (depends on internet and category sizes)
- **Listings**: 200+ across all 5 categories
- **Images**: Varies by listings
- **Excel File**: Single `rest-automative.xlsx`

### Output Summary
```
Excel files uploaded: 1
  - rest-automative: X listings

JSON files uploaded: 1
  - summary_YYYYMMDD.json
```

## Changes from Previous Version

✅ Renamed `json_scraper_rest.py` to `json_scraper.py` (matches Wanted-Cars)
✅ Updated imports in `main.py` to use `json_scraper`
✅ Added `aiohttp` for async image downloads
✅ Added `format_relative_date()` for better date formatting
✅ Added `dateutil.relativedelta` for relative date calculations
✅ Improved method names to match Wanted-Cars pattern
✅ Better error handling and logging
✅ Simplified pagination logic (no page limits)
✅ Creates separate Excel files for each category instead of one unified file
✅ Better attribute extraction and formatting

## Requirements

```
boto3==1.26.137
botocore==1.29.165
requests==2.31.0
beautifulsoup4==4.12.2
pandas==2.1.1
openpyxl==3.1.2
aiohttp==3.9.1
python-dateutil==2.8.2
```

All requirements already included in `requirements.txt`.
