# Contracting Folder Update - Completion Summary

## ✅ Completed Tasks

### 1. Created `Contracting/json_scraper.py`
- **Class Name**: `ContractingJsonScraper` 
- **Base URL**: `https://www.q84sale.com/ar/contracting`
- **Features**: Same functionality as Services folder
  - Extracts JSON from __NEXT_DATA__ script tag
  - Fetches subcategories, districts, listings
  - Extracts detailed listing information (15+ fields)
  - Downloads and manages images
  - Date filtering for yesterday's data
  - All 434 lines of code included

### 2. Created/Updated `Contracting/main.py`
- **Class Name**: `ContractingScraperOrchestrator`
- **Imports**: Uses `ContractingJsonScraper` from json_scraper.py
- **Features**:
  - Async scraping orchestration
  - Separate `scrape_date` (yesterday) and `save_date` (today)
  - Batch fetching of listing details with image processing
  - District-based scraping
  - Excel and JSON export with date tracking
  - S3 upload integration
  - 443 lines of production-ready code

### 3. Created/Updated `Contracting/s3_helper.py`
- **Class Name**: `S3Helper`
- **AWS Authentication**: SSO profile-based (no access keys)
- **Configuration**:
  - AWS_PROFILE_NAME = "PowerUserAccess-235010163908"
  - AWS_REGION = "us-east-1"
  - Default bucket = "data-collection-dl"
- **Features**:
  - ID-based image naming (listing_id_0.jpg, listing_id_1.jpg, etc.)
  - Automatic date-based partitioning (year/month/day)
  - Upload retry logic with exponential backoff
  - S3 URL generation
  - File listing and deletion methods
  - Comprehensive logging
  - 264 lines of code

### 4. Kept `Contracting/s3_upload.py`
- Now contains the same `S3Helper` class as `s3_helper.py`
- Can be deleted if desired (main.py imports from s3_helper.py)

## 📋 File Structure

```
Contracting/
├── json_scraper.py      ✓ (NEW - ContractingJsonScraper with contracting URL)
├── main.py              ✓ (UPDATED - Full orchestrator with S3 integration)
├── s3_helper.py         ✓ (NEW - SSO-based S3 operations)
├── s3_upload.py         (OLD - Can be removed)
└── details_scraping.py  (OLD - Can be removed)
```

## 🚀 How to Use

### Prerequisites
1. AWS SSO configured: `aws sso login --profile PowerUserAccess-235010163908`
2. Python packages: `pip install playwright pandas boto3 aiohttp python-dateutil`

### Running the Scraper

```bash
cd Contracting
python main.py
```

Optional environment variables:
```bash
export S3_BUCKET_NAME="data-collection-dl"
export AWS_PROFILE="PowerUserAccess-235010163908"
python main.py
```

## 📊 Data Flow

1. **Initialization**
   - Creates `ContractingJsonScraper` instance
   - Initializes `S3Helper` with SSO authentication
   - Sets `scrape_date` = today - 1 day (for data filtering)
   - Sets `save_date` = today (for S3 folder structure)

2. **Scraping**
   - Fetches all contracting subcategories
   - For each subcategory:
     - Gets main listings from https://www.q84sale.com/ar/contracting
     - Fetches all districts
     - Scrapes listings from each district
     - Filters for yesterday's data only

3. **Data Processing**
   - Fetches detailed info for each listing
   - Downloads all images
   - Uploads images to S3 with naming: `{listing_id}_{index}.jpg`
   - Generates Excel files per category
   - Creates JSON summary with metadata

4. **S3 Organization**
   - Partitioning path: `4sale-data/services/year=YYYY/month=MM/day=DD/`
   - Excel files: `excel-files/{category_slug}.xlsx`
   - Images: `images/{category_slug}/{listing_id}_{index}.jpg`
   - JSON: `json-files/summary_YYYYMMDD.json`

## 🔍 Key Differences from Services Folder

| Aspect | Services | Contracting |
|--------|----------|-------------|
| Base URL | `https://www.q84sale.com/ar/services` | `https://www.q84sale.com/ar/contracting` |
| Class Name | `ServicesJsonScraper` | `ContractingJsonScraper` |
| Data Source | Services category | Contracting category |
| Import in main.py | `from json_scraper import ServicesJsonScraper` | `from json_scraper import ContractingJsonScraper` |
| S3 Path | Same (services/) | Same (services/) |
| Logic | Identical | Identical |

## ✨ Features Included

- ✅ Async/await for concurrent operations
- ✅ AWS SSO authentication (no hardcoded keys)
- ✅ ID-based image naming with logging
- ✅ Date separation for scraping vs storage
- ✅ Retry logic with exponential backoff
- ✅ Comprehensive logging at every step
- ✅ Error handling and graceful cleanup
- ✅ Batch processing for efficiency
- ✅ Excel export with multiple sheets per district
- ✅ JSON metadata export with date tracking

## 🧹 Cleanup (Optional)

You can safely delete these old files:
- `Contracting/details_scraping.py`
- `Contracting/s3_upload.py` (duplicate of s3_helper.py)

## 📝 Notes

- Both Services and Contracting folders now use identical architecture
- Only the `base_url` differs between them
- Each folder can be run independently
- S3 paths are shared (both use `4sale-data/services/` prefix)
- If separate S3 paths are desired, update `get_partition_prefix()` in s3_helper.py

