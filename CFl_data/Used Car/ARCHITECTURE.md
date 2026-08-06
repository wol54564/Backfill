# Used Cars Scraper - Architecture & Design

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Q84SALE WEBSITE                              │
│        https://www.q84sale.com/ar/automotive/used-cars/         │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP Requests
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  JSON SCRAPER                                   │
│           (json_scraper_used_cars.py)                           │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ UsedCarsJsonScraper                                        │ │
│  │ • get_main_categories()         [67 brands]               │ │
│  │ • get_subcategories(brand)      [1500+ models]            │ │
│  │ • get_listings(...)             [200k+ cars]              │ │
│  │ • get_listing_details(slug)     [full details]            │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │ Structured Data
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│               ORCHESTRATOR                                      │
│        (main_used_cars.py)                                      │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ UsedCarsScraperOrchestrator                                │ │
│  │ • run_scraper()                                            │ │
│  │ • scrape_category()                                        │ │
│  │ • fetch_all_listings_for_subcategory()                    │ │
│  │ • create_excel_file_with_styling()                         │ │
│  │ • format_listings_for_excel()                              │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │ Excel Files
                         ├─────────────────┬──────────────────────┐
                         ▼                 ▼                      ▼
            ┌──────────────────┐  ┌──────────────┐    ┌────────────────┐
            │  Toyota.xlsx     │  │  Lexus.xlsx  │    │ Chevrolet.xlsx │
            │  (35 sheets)     │  │  (15 sheets) │    │  (20 sheets)   │
            └──────────────────┘  └──────────────┘    └────────────────┘
                    │                   │                     │
                    └───────────────────┼─────────────────────┘
                                        │
                         Upload to S3   │
                         ▼──────────────▼
┌─────────────────────────────────────────────────────────────────┐
│                   S3 HELPER                                     │
│               (s3_helper.py)                                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ S3Helper                                                   │ │
│  │ • upload_file()                                            │ │
│  │ • download_file()                                          │ │
│  │ • get_partition_prefix()                                   │ │
│  │ • file_exists()                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │ Date-Partitioned Path
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AWS S3                                     │
│                   4sale-data bucket                             │
│                                                                  │
│  4sale-data/used-cars/year=2024/month=12/day=30/              │
│  ├── Toyota.xlsx                                               │
│  ├── Lexus.xlsx                                                │
│  ├── Chevrolet.xlsx                                            │
│  └── ... (67 files total)                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
START
  │
  ├─→ Initialize Scraper & S3
  │
  ├─→ Fetch Main Categories (67 brands)
  │   │
  │   ├─→ Toyota
  │   ├─→ Lexus
  │   ├─→ Chevrolet
  │   └─→ ... (67 total)
  │
  └─→ FOR EACH Brand:
      │
      ├─→ Fetch Subcategories (Models)
      │   │
      │   ├─→ Land Cruiser
      │   ├─→ Camry
      │   ├─→ Prado
      │   └─→ ... (35 for Toyota)
      │
      └─→ FOR EACH Model:
          │
          ├─→ Fetch Listings Page 1
          ├─→ Fetch Listings Page 2
          ├─→ ... (all pages)
          │
          ├─→ Format Data → Dictionary
          └─→ Add to Sheet
      │
      ├─→ Create Excel File
      │   (1 file = 1 brand)
      │   (Multiple sheets = models)
      │
      └─→ Upload to S3
          ✓ s3://4sale-data/4sale-data/used-cars/year=.../
  
  ├─→ Cleanup
  │
  └─→ END
     ✓ All brands processed
     ✓ All files uploaded
     ✓ All logs saved
```

## Component Interaction

```
┌──────────────────────────────────────────────────────────────────┐
│                     main_used_cars.py                            │
│                 (Orchestrator - Entry Point)                     │
│                                                                   │
│  async def run_scraper():                                        │
│    1. await initialize()                                         │
│    2. categories = await scraper.get_main_categories()           │
│    3. FOR each category:                                         │
│       a. category_data = await scrape_category(cat)    ┐         │
│       b. create_excel_file_with_styling(cat_data)     │         │
│       c. s3_helper.upload_file(excel_file)             │         │
│    4. await cleanup()                                  │         │
│                                                        │         │
│                                                        ▼         │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ async def scrape_category(main_category):              │  │
│    │   1. subcats = await scraper.get_subcategories(...)   │  │
│    │   2. FOR each subcategory:                            │  │
│    │      listings = await fetch_all_listings_for...()     │  │
│    │   3. Return {slug: [listings]}                        │  │
│    └─────────────────────────────────────────────────────────┘  │
│                                ▲                                 │
│                                │ Uses                            │
│                                │                                 │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ async def fetch_all_listings_for_subcategory():        │  │
│    │   1. page = 1                                          │  │
│    │   2. WHILE page <= total_pages:                        │  │
│    │      listings, total = await scraper.get_listings()   │  │
│    │      all_listings.extend(listings)                    │  │
│    │      page += 1                                         │  │
│    │   3. Return all_listings                              │  │
│    └─────────────────────────────────────────────────────────┘  │
│                                ▲                                 │
│                                │ Calls                          │
└────────────────────────────────┼──────────────────────────────────┘
                                 │
┌────────────────────────────────┴──────────────────────────────────┐
│                  json_scraper_used_cars.py                        │
│                   (Data Extraction)                              │
│                                                                   │
│  async def get_main_categories():                                │
│    → Fetch /ar/automotive/used-cars/1                           │
│    → Extract JSON from __NEXT_DATA__                            │
│    → Parse catChilds array                                       │
│    → Return [brands]                                            │
│                                                                   │
│  async def get_subcategories(brand_slug):                        │
│    → Fetch /ar/automotive/used-cars/{brand}/1                   │
│    → Extract catChilds (models)                                 │
│    → Return [models]                                            │
│                                                                   │
│  async def get_listings(brand, model, page):                     │
│    → Fetch /ar/automotive/used-cars/{brand}/{model}/{page}      │
│    → Extract listings array                                      │
│    → Return (listings, total_pages)                             │
│                                                                   │
│  async def get_listing_details(slug):                            │
│    → Fetch /ar/listing/{slug}                                   │
│    → Extract full details + images                               │
│    → Return detailed_listing                                     │
└─────────────────────────────────────────────────────────────────┘
                                 ▲
                                 │ HTTP Requests
                                 │
                    ┌────────────┴─────────────┐
                    │                          │
                    │   beautifulsoup4 + requests
                    │   (Extract JSON from HTML)
                    │
                    ▼
            Q84SALE WEBSITE
```

## Class Diagrams

### UsedCarsJsonScraper
```
UsedCarsJsonScraper
├── Attributes
│   ├── base_url: str = "https://www.q84sale.com/ar/automotive/used-cars"
│   └── session: requests.Session
│
└── Methods
    ├── get_page_json_data(url) → Dict
    ├── get_main_categories() → List[Dict]
    ├── get_subcategories(slug) → List[Dict]
    ├── get_listings(cat, subcat, page) → Tuple[List, int]
    ├── get_listing_details(slug) → Dict
    └── format_relative_date(date_str) → str
```

### UsedCarsScraperOrchestrator
```
UsedCarsScraperOrchestrator
├── Attributes
│   ├── scraper: UsedCarsJsonScraper
│   ├── s3_helper: S3Helper
│   ├── bucket_name: str
│   ├── temp_dir: Path
│   └── save_date: datetime
│
└── Methods
    ├── initialize() → None
    ├── cleanup() → None
    ├── run_scraper(max_categories) → None
    ├── scrape_category(category) → Dict
    ├── fetch_all_listings_for_subcategory(...) → List[Dict]
    ├── format_listings_for_excel(listings) → List[Dict]
    └── create_excel_file_with_styling(path, data) → None
```

### S3Helper
```
S3Helper
├── Attributes
│   ├── bucket_name: str
│   ├── region_name: str
│   └── s3_client: boto3.S3Client
│
└── Methods
    ├── get_partition_prefix(date) → str
    ├── upload_file(local, s3_name, date) → str
    ├── download_file(s3_name, local, date) → bool
    ├── file_exists(s3_name, date) → bool
    ├── get_file_size(s3_name, date) → int
    └── list_files(prefix) → List[str]
```

## Data Models

### Main Category
```python
{
    "id": 138,
    "slug": "toyota",
    "name_ar": "تويوتا",
    "name_en": "Toyota",
    "listings_count": 2334,
    "parent_slug": "used-cars",
    "slug_url": "automotive/used-cars/toyota/1"
}
```

### Subcategory (Model)
```python
{
    "id": 1983,
    "parent_id": 138,
    "slug": "land-cruiser",
    "name_ar": "لاند كروزر",
    "name_en": "Land Cruiser",
    "listings_count": 937,
    "slug_url": "automotive/used-cars/toyota/land-cruiser/1",
    "category_parent_slug": "toyota"
}
```

### Listing
```python
{
    "id": 20499635,
    "title": "صباح الناصر",
    "slug": "land-cruiser-20499635",
    "price": 1750,
    "phone": "96565555210",
    "user_name": "نايف العدواني",
    "date_published": "2025-12-24 09:55:42",
    "district_name": "الفروانية",
    "status": "pinned",
    "images_count": 9,
    "cat_name_en": "Land Cruiser",
    "cat_name_ar": "لاند كروزر",
    "desc_en": "For sale Land Cruiser...",
    "desc_ar": "للبيع لاندكروز..."
}
```

## Excel File Structure

```
Toyota.xlsx
├── Sheet: "Land Cruiser"
│   ├── Header Row: [Listing ID | Title | Price | ... ]
│   ├── Row 2: [20499635 | صباح الناصر | 1750 | ... ]
│   ├── Row 3: [20482559 | لاند كروز صبغ | 9000 | ... ]
│   └── ... (937 rows total)
│
├── Sheet: "Camry"
│   ├── Header Row: [Listing ID | Title | Price | ... ]
│   ├── Row 2-375: [listing data]
│   └── ...
│
├── Sheet: "Prado"
│   ├── ... (319 rows)
│
└── Sheet: "..." (30+ more models)
```

## Request Flow Sequence

```
1. Start
   ↓
2. Fetch /ar/automotive/used-cars/1
   ├─ Extract main_categories (67 brands)
   ├─ Parse each brand:
   │  - id, slug, name_en, name_ar, listings_count
   │
3. FOR each brand (e.g., toyota):
   ├─ Fetch /ar/automotive/used-cars/toyota/1
   ├─ Extract subcategories (35 models for Toyota)
   ├─ Parse each model:
   │  - id, parent_id, slug, name_en, name_ar, listings_count
   │
4. FOR each model (e.g., land-cruiser):
   ├─ page = 1
   ├─ WHILE more pages:
   │  ├─ Fetch /ar/automotive/used-cars/toyota/land-cruiser/{page}
   │  ├─ Extract listings array
   │  ├─ Parse each listing:
   │  │  - id, title, slug, price, phone, user_name, date, district
   │  ├─ page += 1
   │
5. Format all data for Excel
   ├─ Create DataFrame
   ├─ Apply styling
   ├─ Save Excel file
   │
6. Upload Excel to S3
   ├─ Partition: 4sale-data/used-cars/year=2024/month=12/day=30/
   ├─ File: Toyota.xlsx
   │
7. Repeat for all 67 brands

8. End
   ✓ All data collected
   ✓ All Excel files created
   ✓ All files uploaded
```

## Error Handling Flow

```
TRY scrape_category()
├─ TRY get_subcategories()
│  ├─ CATCH: Network error → Log warning, continue
│  └─ CATCH: Parse error → Log error, return []
│
├─ FOR each subcategory:
│  ├─ TRY fetch_all_listings_for_subcategory()
│  │  ├─ TRY get_listings(page)
│  │  │  ├─ CATCH: Network error → Retry with delay
│  │  │  └─ CATCH: No data → Break loop
│  │  │
│  │  └─ IF listings_count == 0: Skip
│  │
│  └─ TRY format_listings_for_excel()
│     └─ CATCH: Data error → Log, continue
│
├─ TRY create_excel_file_with_styling()
│  └─ CATCH: Disk error → Log error
│
├─ TRY s3_helper.upload_file()
│  ├─ Attempt 1: Try upload
│  ├─ Attempt 2: Retry with backoff
│  ├─ Attempt 3: Final retry
│  └─ CATCH: S3 error → Log, continue (fallback)
│
└─ FINALLY cleanup()
   └─ Delete temp files
```

## Performance Optimization

```
Request Rate Control:
├─ Between requests: 0.3-0.5 seconds
├─ Between brands: 0.5 seconds
└─ Between pages: 0.5 seconds

Memory Optimization:
├─ Stream data to Excel (no full load in memory)
├─ Process one brand at a time
├─ Delete temp files after upload
└─ Clear large lists after processing

Parallel Opportunities (future):
├─ Fetch multiple brands concurrently
├─ Upload files while scraping
└─ Process multiple pages in parallel
```

## Configuration Parameters

```
main_used_cars.py:
├── BUCKET_NAME = "4sale-data"
├── PROFILE_NAME = None
├── MAX_CATEGORIES = None
├── temp_dir = "temp_data"
└── scrape_date = yesterday

json_scraper_used_cars.py:
├── base_url = "https://www.q84sale.com/ar/automotive/used-cars"
├── timeout = 30 seconds
└── user_agent = Mozilla headers

s3_helper.py:
├── region_name = "us-east-1"
├── retries = 3
└── partition_format = "year/month/day"
```

---

This architecture provides:
- ✓ Clear separation of concerns
- ✓ Reusable components
- ✓ Flexible configuration
- ✓ Robust error handling
- ✓ Scalable design
- ✓ Easy maintenance
