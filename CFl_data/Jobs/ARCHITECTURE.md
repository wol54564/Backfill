# Jobs Scraper - Technical Specification

## Overview

Complete web scraping system for Q84Sale Jobs category (https://www.q84sale.com/ar/jobs) with two-tier category hierarchy and AWS S3 integration.

## Architecture

### Three-Module Design

```
┌─────────────────────────────────┐
│     JobsScraperOrchestrator     │
│          (main.py)              │
│  - Coordinates scraping         │
│  - Creates Excel files          │
│  - Manages S3 uploads           │
└────┬──────────────┬─────────────┘
     │              │
     ▼              ▼
┌────────────────┐ ┌─────────────┐
│ JobsJsonScraper│ │ S3Helper    │
│  (json_scraper)│ │(s3_helper)  │
│ - Page fetching│ │- S3 ops     │
│ - JSON parsing │ │- File upload│
│ - Data extract │ │- Partitions │
└────────────────┘ └─────────────┘
```

## Data Flow

```
Jobs Main Page (https://q84sale.com/ar/jobs/1)
    │
    ▼ Extract verticalSubcats
┌─────────────────────────────┐
│ Job Openings  | Job Seeker  │
└────────┬──────────┬─────────┘
         │          │
    ┌────▼──┐   ┌───▼────┐
    │ For each main category:
    │   GET https://q84sale.com/ar/jobs/{slug}/1
    ▼ Extract catChilds
┌──────────────────────────────────────────┐
│ Part Time | Accounting | Technology |... │
└────┬──────────────┬──────────────────────┘
     │              │
     └──────┬───────┘
            │
    ┌───────▼────────┐
    │ For each child category:
    │   Loop all pages:
    │   GET https://q84sale.com/ar/jobs/{main}/{child}/{page}
    ▼ Extract listings
┌──────────────────────────────┐
│ 250+ Listings               │
│ (titles, descriptions,      │
│  contacts, locations, etc.) │
└──────────────┬──────────────┘
               │
     ┌─────────┴─────────┐
     ▼                   ▼
┌──────────────┐  ┌──────────────┐
│ Create Excel │  │ Download     │
│ Files:       │  │ Images:      │
│ - Info sheet │  │ - Process    │
│ - Child cat. │  │ - Upload S3  │
│   sheets     │  │              │
└──────┬───────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                ▼
        ┌──────────────────┐
        │   Upload to S3   │
        │ with Partitions  │
        └──────────────────┘
```

## Category Hierarchy

### Level 1: verticalSubcats
Main categories from jobs main page.

```json
{
  "verticalSubcats": [
    {
      "id": 2802,
      "slug": "job-openings",
      "name_ar": "وظائف شاغرة",
      "name_en": "Job Openings",
      "listings_count": 253
    },
    {
      "id": 2809,
      "slug": "job-seeker",
      "name_ar": "باحث عن عمل",
      "name_en": "Job Seeker",
      "listings_count": 337
    }
  ]
}
```

### Level 2: catChilds
Child categories under each main category.

```json
{
  "catChilds": [
    {
      "id": 2918,
      "parent_id": 2802,
      "slug": "part-time-job",
      "name_ar": "وظيفة بدوام جزئي",
      "name_en": "Part Time Job",
      "listings_count": 24,
      "slug_url": "jobs/job-openings/part-time-job/1"
    },
    {
      "id": 1587,
      "parent_id": 2802,
      "slug": "accounting",
      "name_ar": "محاسبة",
      "name_en": "Accounting",
      "listings_count": 17,
      "slug_url": "jobs/job-openings/accounting/1"
    }
    // ... more child categories
  ]
}
```

### Level 3: Listings
Individual job listings under each child category.

```json
{
  "listings": [
    {
      "id": 20485498,
      "title": "مطلوب موظفين مزاد سيارات",
      "slug": "part-time-job-20485498",
      "description": "...",
      "price": 2025,
      "cat_id": 2918,
      "cat_en_name": "Part Time Job",
      "cat_ar_name": "وظيفة بدوام جزئي",
      "phone": "96555051215",
      "user": {"user_id": 2390986, "name": "Q8"},
      "district_name": "الكويت",
      "date_published": "2025-12-19 01:18:22",
      "images": ["https://media.q84sale.com/images/..."]
    }
    // ... more listings
  ],
  "totalPages": 2
}
```

## URL Patterns

### Main Page
- **URL**: `https://www.q84sale.com/ar/jobs/1`
- **Content**: verticalSubcats (2 main categories)

### Child Categories Page
- **URL**: `https://www.q84sale.com/ar/jobs/{main_slug}/1`
- **Example**: `https://www.q84sale.com/ar/jobs/job-openings/1`
- **Content**: catChilds for the main category

### Listings Page (Paginated)
- **URL**: `https://www.q84sale.com/ar/jobs/{main_slug}/{child_slug}/{page}`
- **Example**: `https://www.q84sale.com/ar/jobs/job-openings/part-time-job/1`
- **Content**: listings array + totalPages

### Listing Details
- **URL**: `https://www.q84sale.com/ar/jobs/{child_slug}-{listing_id}`
- **Example**: `https://www.q84sale.com/ar/jobs/part-time-job-20485498`
- **Content**: Detailed listing info with all attributes

## JSON Extraction

### Method
1. Load page with requests library
2. Parse HTML with BeautifulSoup4
3. Find `<script id="__NEXT_DATA__">` tag
4. Extract and parse JSON string

### Code Example
```python
soup = BeautifulSoup(response.content, 'html.parser')
script = soup.find('script', {'id': '__NEXT_DATA__'})
json_data = json.loads(script.string)
data = json_data.get("props", {}).get("pageProps", {})
```

## Class: JobsJsonScraper

### Methods

#### `get_main_subcategories() -> List[Dict]`
**Purpose**: Fetch main categories (Job Openings, Job Seeker)

**Process**:
1. GET `https://www.q84sale.com/ar/jobs/1`
2. Extract `verticalSubcats` from JSON
3. Return list of main categories

**Returns**: `[{"id": 2802, "slug": "job-openings", ...}, ...]`

#### `get_category_children(subcategory_slug: str) -> List[Dict]`
**Purpose**: Fetch child categories for a main category

**Process**:
1. GET `https://www.q84sale.com/ar/jobs/{slug}/1`
2. Extract `catChilds` from JSON
3. Return list of child categories

**Parameters**:
- `subcategory_slug`: e.g., "job-openings"

**Returns**: `[{"id": 2918, "parent_id": 2802, "slug": "part-time-job", ...}, ...]`

#### `get_listings(category_slug: str, page_num: int) -> Tuple[List[Dict], int]`
**Purpose**: Fetch listings for a category

**Process**:
1. GET `https://www.q84sale.com/ar/jobs/{slug}/{page_num}`
2. Extract `listings` and `totalPages` from JSON
3. Format listing data
4. Return listings and total pages

**Parameters**:
- `category_slug`: e.g., "job-openings/part-time-job"
- `page_num`: 1, 2, 3, ... (default: 1)
- `filter_yesterday`: Filter by yesterday's date (optional)

**Returns**: `([listings], total_pages)`

#### `get_listing_details(listing_slug: str) -> Optional[Dict]`
**Purpose**: Fetch detailed info for a single listing

**Process**:
1. GET listing details page
2. Extract `listing` object from JSON
3. Parse attributes and relations
4. Return detailed listing

**Parameters**:
- `listing_slug`: e.g., "part-time-job-20485498"

**Returns**: `{id, title, description, images, ...}`

#### `download_image(image_url: str) -> Optional[bytes]`
**Purpose**: Download image data

**Parameters**:
- `image_url`: Full image URL

**Returns**: Image bytes or None

## Class: JobsScraperOrchestrator

### Methods

#### `scrape_all_subcategories() -> List[Dict]`
**Purpose**: Main orchestration method

**Process**:
1. Fetch all main categories
2. For each main category:
   - Fetch all child categories
   - For each child category:
     - Scrape all pages of listings
     - Fetch detailed info for each listing
     - Download images
3. Return all scraped data

**Returns**: List of results with structure:
```python
[
  {
    "main_subcategory": {...},
    "child_categories": [
      {
        "child_category": {...},
        "listings": [...]
      }
    ],
    "total_listings": 250
  }
]
```

#### `scrape_child_category(main_subcat, child_cat) -> Dict`
**Purpose**: Scrape a single child category

**Process**:
1. Build full slug path
2. Loop through all pages
3. Fetch listing details for each
4. Return all listings for category

**Returns**: `{"child_category": {...}, "listings": [...], "total_pages": N}`

#### `save_all_to_s3(results: List[Dict]) -> Dict`
**Purpose**: Create Excel files and upload to S3

**Process**:
1. For each main category:
   - Create new Excel workbook
   - Add Info sheet with metadata
   - Add sheet for each child category
   - Upload to S3
2. Upload summary JSON
3. Return upload summary

**Excel Structure**:
```
Workbook: job-openings.xlsx
├── Sheet: Info
│   ├── Project
│   ├── Main Category
│   ├── Total Child Categories
│   ├── Total Listings
│   ├── Data Scraped Date
│   └── Saved to S3 Date
├── Sheet: Part Time Job
│   ├── Column: id
│   ├── Column: title
│   ├── Column: description
│   ├── ... (all listing fields)
│   └── Row: [listing data]
├── Sheet: Accounting
│   └── ... (similar structure)
└── ... (more sheets)
```

#### `run() -> Dict`
**Purpose**: Execute complete scraping pipeline

**Process**:
1. Initialize scraper and S3 client
2. Scrape all categories
3. Save to S3
4. Cleanup temporary files
5. Return summary

**Error Handling**:
- Automatic retry on failures
- Skip individual listings if they fail
- Continue with next category
- Comprehensive logging

## Class: S3Helper

### Methods

#### `get_partition_prefix(target_date) -> str`
**Purpose**: Generate S3 partition path

**Format**: `4sale-data/jobs/year=YYYY/month=MM/day=DD/`

**Example**: `4sale-data/jobs/year=2025/month=12/day=25/`

#### `upload_file(local_path, s3_filename, target_date, retries) -> Optional[str]`
**Purpose**: Upload file to S3 with partitioning

**Parameters**:
- `local_path`: Local file path
- `s3_filename`: Relative S3 filename (without partition)
- `target_date`: Partition date (default: yesterday)
- `retries`: Number of retry attempts (default: 3)

**Returns**: Full S3 key or None

#### `upload_image(image_url, image_data, subcategory_slug, ...) -> Optional[str]`
**Purpose**: Upload image with ID-based naming

**Naming**: `{listing_id}_{image_index}.jpg`

**Organization**: `images/{subcategory_slug}/{filename}`

#### `generate_s3_url(s3_key) -> str`
**Purpose**: Generate public URL for S3 object

**Returns**: `https://{bucket}.s3.{region}.amazonaws.com/{key}`

## Output Files

### Excel Files

**job-openings.xlsx**
- Info sheet: Summary metadata
- Part Time Job sheet: 24 listings
- Accounting sheet: 17 listings
- Technology & Engineering sheet: 8 listings
- ... (11 total child category sheets)

**job-seeker.xlsx**
- Similar structure with Job Seeker listings

### S3 Structure

```
4sale-data/jobs/year=2025/month=12/day=25/
├── excel-files/
│   ├── job-openings.xlsx
│   └── job-seeker.xlsx
├── images/
│   ├── job-openings/
│   │   ├── 20485498_0.jpg
│   │   ├── 20485498_1.jpg
│   │   ├── 20501348_0.jpg
│   │   └── ... (more images)
│   └── job-seeker/
│       └── ... (similar structure)
└── upload-summary.json
```

## Performance Characteristics

### Metrics
- **Main categories**: 2 (fixed)
- **Child categories per main**: ~11-12 each
- **Avg listings per child**: ~20-30
- **Total listings**: ~250-350 per main category

### Time Estimates
- Fetch main categories: ~2 seconds
- Fetch child categories: ~5 seconds per main
- Fetch listings: ~2 minutes per child category
- Image download/upload: ~30 seconds per listing with images
- Excel creation: ~30 seconds per file
- S3 upload: ~1-2 minutes total

**Total Estimated Runtime**: 30-45 minutes

### Rate Limiting
- Inter-request delay: 0.5-1.0 seconds
- Inter-page delay: 1 second
- Inter-category delay: 1-2 seconds
- Total requests: ~250-350

## Error Handling

### Retry Strategy
- **S3 uploads**: 3 automatic retries with 1-second delay
- **Image downloads**: 3 attempts
- **Page fetches**: 1 attempt (fail-fast)

### Graceful Degradation
- Skip listings without required fields
- Continue if individual listing fails
- Continue if individual image fails
- Continue if S3 upload fails (logs warning)
- Create partial Excel files if some categories fail

### Logging
- All operations logged at INFO level
- Warnings for non-critical failures
- Errors for critical failures
- Time-stamped with millisecond precision

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| requests | 2.31.0 | HTTP requests |
| beautifulsoup4 | 4.12.2 | HTML/JSON parsing |
| pandas | 2.0.3 | Excel creation |
| openpyxl | 3.1.2 | Excel formatting |
| boto3 | 1.26.137 | AWS S3 API |
| aiohttp | 3.9.1 | Async HTTP (future) |
| python-dateutil | 2.8.2 | Date utilities |

## Configuration

### AWS Configuration
```python
# In s3_helper.py
AWS_PROFILE_NAME = "PowerUserAccess-235010163908"
AWS_REGION = "us-east-1"
```

### Scraper Configuration
```python
# In main.py
BUCKET_NAME = "data-ingestion-prod"
AWS_PROFILE = "PowerUserAccess-235010163908"
```

## Testing Checklist

- [ ] Fetch main categories (Job Openings, Job Seeker)
- [ ] Fetch child categories (11-12 per main)
- [ ] Fetch listings for each child (all pages)
- [ ] Fetch listing details
- [ ] Download images
- [ ] Create Excel files with proper structure
- [ ] Upload Excel files to S3
- [ ] Upload images to S3
- [ ] Upload summary JSON
- [ ] Verify partition path: `4sale-data/jobs/year=YYYY/month=MM/day=DD/`
- [ ] Verify Excel sheets (Info + child categories)
- [ ] Verify image organization
- [ ] Check error handling
- [ ] Monitor rate limiting
- [ ] Verify cleanup of temp files

## Deployment Checklist

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Configure AWS profile in `s3_helper.py`
- [ ] Configure bucket name in `main.py`
- [ ] Set up AWS credentials
- [ ] Verify S3 bucket exists and is accessible
- [ ] Set up logging to file (optional)
- [ ] Create cron job for daily execution (optional)
- [ ] Verify disk space for temp files
- [ ] Test first run manually
- [ ] Monitor first few automated runs

## Maintenance

### Monitoring
- Check S3 uploads daily
- Review upload-summary.json
- Monitor error logs

### Updates Required If
- Q84Sale changes page structure (unlikely)
- AWS API changes (unlikely)
- Category count changes (update documentation)
- Column names change (update pandas export)

---

**Document Version**: 1.0  
**Last Updated**: December 25, 2025  
**Status**: Ready for Production
