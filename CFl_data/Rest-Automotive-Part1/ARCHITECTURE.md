# Rest-Automative-Part1 Scraper - Project Architecture

## Project Structure

```
Rest-Automative-Part1/
├── json_scraper.py                  (RestAutomotiveJsonScraper)
├── s3_helper.py                     (S3Helper for rest-automative)
├── main.py                          (RestAutomotiveScraperOrchestrator)
├── requirements.txt
├── README.md
├── QUICKSTART.md
├── ARCHITECTURE.md
├── CONFIG_EXAMPLES.md
└── SETUP_SUMMARY.md
```

## Key Components

### 1. json_scraper.py - RestAutomotiveJsonScraper

**Purpose**: Fetch and parse data from Q84Sale.com

**Key Methods**:
```python
class RestAutomotiveJsonScraper:
    # Category management
    async def get_rest_categories() -> List[Dict]
        # Returns: watercraft, spare-parts, automotive-accessories, cmvs, rentals
    
    async def get_subcategories(category_slug) -> List[Dict]
        # Fetches subcategories from category page
        
    # Listings
    async def get_listings(category_slug, subcategory_slug, page_num, filter_yesterday) -> tuple
        # Returns: (listings, total_pages)
        
    async def get_listing_details(slug, status) -> Optional[Dict]
        # Returns complete listing data with all fields
        
    # Utilities
    async def get_page_json_data(url) -> Optional[Dict]
        # Extracts JSON from __NEXT_DATA__ script tag
        
    async def download_image(image_url) -> Optional[bytes]
        # Async image download using aiohttp
        
    def format_relative_date(date_str) -> str
        # Converts dates to relative format (e.g., "2 days ago")
        
    def extract_attributes(attrs_list) -> Dict
        # Extracts and formats item attributes
```

**Features**:
- Async/await for concurrent operations
- BeautifulSoup for HTML parsing
- JSON extraction from script tags
- Rate limiting support
- Error handling and recovery
- Image download with aiohttp

### 2. s3_helper.py - S3Helper

**Purpose**: Handle AWS S3 operations

**Key Methods**:
```python
class S3Helper:
    def __init__(bucket_name, profile_name)
        # Initialize S3 client with SSO profile
    
    def get_partition_prefix(target_date) -> str
        # Returns: 4sale-data/rest-automative/year=YYYY/month=MM/day=DD/
    
    def upload_file(local_file_path, s3_filename, target_date, ...) -> Optional[str]
        # Upload Excel, JSON, and other files
        
    def upload_image(image_url, image_data, category_slug, ...) -> Optional[str]
        # Upload images with ID-based naming
        
    def generate_s3_url(s3_key) -> str
        # Convert S3 key to public URL
```

**S3 Partition Structure**:
```
4sale-data/rest-automative/year=2024/month=12/day=21/
├── excel-files/
│   └── rest-automative.xlsx
├── json-files/
│   └── summary_20241221.json
└── images/
    ├── watercraft/{listing_id}_{index}.jpg
    ├── spare-parts/{listing_id}_{index}.jpg
    ├── automotive-accessories/{listing_id}_{index}.jpg
    ├── cmvs/{listing_id}_{index}.jpg
    └── rentals/{listing_id}_{index}.jpg
```

### 3. main.py - RestAutomotiveScraperOrchestrator

**Purpose**: Orchestrate the complete scraping workflow

**Key Methods**:
```python
class RestAutomotiveScraperOrchestrator:
    async def initialize()
        # Initialize scraper and S3 client
    
    async def cleanup()
        # Clean up temporary files and resources
    
    async def fetch_listing_details_batch(listings, category_slug) -> List[Dict]
        # Fetch details and download images for batch of listings
    
    async def scrape_subcategory(category, subcategory) -> Dict
        # Scrape all pages for a subcategory
    
    async def scrape_all_categories() -> List[Dict]
        # Discover and scrape all categories
    
    async def save_all_to_s3(results) -> Dict
        # Create Excel file and upload to S3
```

**Workflow**:
```
1. Load categories (5 predefined)
2. For each category:
   - Fetch subcategories
   - For each subcategory:
     - Fetch all listing pages
     - For each listing:
       - Fetch detailed info
       - Download images
       - Upload to S3
3. Create single Excel file with all data
4. Create JSON summary
5. Upload both to S3
```

## Data Flow

### Main Execution Flow

```
main()
  ↓
Initialize RestAutomotiveScraperOrchestrator
  ├─ Create scraper (RestAutomotiveJsonScraper)
  └─ Create S3 helper (S3Helper)
  ↓
scrape_all_categories()
  ├─ Get 5 categories
  └─ For each category:
      ├─ Get subcategories
      └─ For each subcategory:
          ├─ Get first page (to determine total pages)
          └─ For each page:
              ├─ Get listings
              └─ fetch_listing_details_batch()
                  ├─ Get listing details
                  ├─ Download images
                  └─ Upload images to S3
  ↓
save_all_to_s3(results)
  ├─ Create Excel file with all subcategories
  ├─ Create JSON summary
  └─ Upload both to S3
  ↓
cleanup()
  └─ Remove temp files
```

### API Data Extraction

**Step 1: Category Discovery**
```
GET https://www.q84sale.com/ar/automotive/watercraft/1
↓
BeautifulSoup extracts __NEXT_DATA__ script
↓
JSON data contains catChilds array with subcategories
```

**Step 2: Listing Fetch**
```
GET https://www.q84sale.com/ar/automotive/{category}/{subcategory}/{page}
↓
JSON contains listings array + totalPages
↓
Each listing has: id, title, slug, price, image, date_published, etc.
```

**Step 3: Detail Fetch**
```
GET https://www.q84sale.com/ar/listing/{slug}
↓
JSON contains full listing object
↓
Extract: description, all images, attributes, user info, dates
```

## Excel Output Structure

**Files**: `Watercraft.xlsx`, `Spare Parts.xlsx`, `Automotive Accessories.xlsx`, `CMVs.xlsx`, `Rentals.xlsx`

Each file structure:
```
{CategoryName}.xlsx
├── Info
│   ├── Category (Arabic): "..."
│   ├── Category (English): "..."
│   ├── Total Subcategories: X
│   ├── Total Listings: Y
│   ├── Data Scraped Date: YYYY-MM-DD
│   └── Saved to S3 Date: YYYY-MM-DD
│
├── Subcategory 1 Name (in Arabic)
│   ├── id, title, slug, price, phone
│   ├── date_published, date_relative
│   ├── description, user_name, user_email
│   ├── images, s3_images
│   ├── attributes (nested JSON)
│   └── ... (more fields)
│
└── Subcategory 2 Name (in Arabic)
    └── (same structure)
```

## JSON Summary Structure

**File**: `summary_YYYYMMDD.json`

```json
{
  "scraped_at": "2024-12-21T14:45:23.123456",
  "data_scraped_date": "2024-12-20",
  "saved_to_s3_date": "2024-12-21",
  "total_categories": 5,
  "total_excel_files": 5,
  "total_listings": X,
  "categories": [
    {
      "name_ar": "المركبات المائية",
      "name_en": "Watercraft",
      "slug": "watercraft",
      "subcategories_count": X,
      "subcategories": [
        {
          "name_ar": "...",
          "name_en": "...",
          "slug": "...",
          "listings_count": X
        }
      ]
    },
    {
      "name_ar": "قطع الغيار",
      "name_en": "Spare Parts",
      "slug": "spare-parts",
      ...
    },
    ...
  ]
}
```

## Configuration

### Environment Variables

```bash
S3_BUCKET_NAME      # AWS S3 bucket name (default: data-collection-dl)
AWS_PROFILE         # AWS profile for SSO (default: None - uses default)
```

### Date Handling

```python
scrape_date = datetime.now() - timedelta(days=1)  # Yesterday's data
save_date = datetime.now()                        # Today's date
```

The scraper uses:
- `scrape_date` for filtering listings (usually yesterday)
- `save_date` for S3 partition and file organization (today)

## Categories & Subcategories

**Fixed Categories** (5 total):
1. Watercraft (watercraft) - المركبات المائية
2. Spare Parts (spare-parts) - قطع الغيار
3. Automotive Accessories (automotive-accessories) - إكسسوارات سيارات
4. CMVs (cmvs) - المركبات التجارية
5. Rentals (rentals) - تأجير

**Subcategories**: Dynamically discovered from each category page via catChilds

## Error Handling

```
Fetch Error
  ├─ Retry with backoff
  ├─ Log warning/error
  └─ Continue with next item

Upload Error
  ├─ Retry up to 3 times
  ├─ Log failure
  └─ Continue with next file

Detail Fetch Failure
  ├─ Log warning
  ├─ Skip images
  └─ Continue with next listing
```

## Rate Limiting

```python
- Between pages: 1 second delay
- Between listings: 0.5 second delay
- Between images: 0.1 second delay
- Between subcategories: 1 second delay
- Between categories: Handled by natural delays
```

## Performance

### Expected Times (typical run)
- Category discovery: ~5 seconds per category
- Listings fetch: ~2 seconds per page
- Detail fetch: ~5 seconds per listing
- Image download: ~2 seconds per image
- Upload: ~5 seconds per file

### Estimated Totals
- 5 categories, 20+ subcategories
- 200+ listings (varies by day)
- 500+ images
- Total time: 20-40 minutes

## Comparison with Wanted-Cars

| Aspect | Wanted-Cars | Rest-Automative |
|--------|-------------|-----------------|
| Base URL | /wanted-cars | /automotive/{category} |
| Categories | Dynamic (3) | Fixed (5) |
| Subcategories | Per category | Per category |
| Excel Output | Single file | Single file |
| S3 Folder | wanted-cars | rest-automative |
| Pagination | Unlimited | Unlimited |
| Image Handling | aiohttp | aiohttp |
| Date Formatting | relativedelta | relativedelta |
| Error Recovery | Yes | Yes |

## Improvements Made

✅ Renamed from `json_scraper_rest.py` to `json_scraper.py`
✅ Added async image downloading with aiohttp
✅ Added `format_relative_date()` for better dates
✅ Added `dateutil.relativedelta` support
✅ Improved attribute extraction
✅ Better error handling
✅ Cleaner method naming
✅ **Creates separate Excel files per category** (Watercraft.xlsx, Spare Parts.xlsx, etc.)
✅ **Passes folder_name="rest-automative"** to S3 operations for correct path
✅ Better logging and monitoring
✅ Rate limiting for responsible scraping
