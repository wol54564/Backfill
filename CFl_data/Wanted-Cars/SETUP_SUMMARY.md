# Wanted-Cars Scraper Project - Setup Complete ✓

## Summary

I've successfully created a complete web scraper for the wanted-cars section of Q84Sale.com, mirroring the architecture of your existing Automative-Cars-and-Trucks project.

## Files Created

### 1. **json_scraper.py** - WantedCarsJsonScraper
   - Dynamically discovers subcategories from the main wanted-cars page
   - Automatically detects:
     - Wanted American Cars (ID: 581)
     - Wanted European Car (ID: 582)  
     - Wanted Asian Cars (ID: 583)
   - Fetches listings across multiple pages per subcategory
   - Retrieves detailed listing information from individual listing pages
   - Downloads all images associated with listings
   - Extracts vehicle attributes (year, color, mileage, etc.)

### 2. **s3_helper.py** - S3Helper  
   - AWS S3 client with SSO profile support
   - **Partition Structure**: `4sale-data/wanted-cars/year=YYYY/month=MM/day=DD/`
   - Methods for:
     - File uploads with retry logic
     - Image uploads with automatic naming (listing_id_index.jpg)
     - JSON data uploads
     - File listing and deletion
     - S3 URL generation

### 3. **main.py** - WantedCarsScraperOrchestrator
   - Main orchestrator for the entire scraping workflow
   - Automatically discovers all subcategories
   - Scrapes each subcategory with configurable pagination
   - **Excel Output**: Single file named `wanted-cars.xlsx` with:
     - Info sheet (summary statistics)
     - One sheet per subcategory (named in Arabic)
   - **JSON Output**: Summary metadata file
   - **Image Organization**: Organized by subcategory slug in S3
   - Handles cleanup and error recovery

### 4. **README.md**
   - Comprehensive documentation
   - Installation and usage instructions
   - Data structure and field descriptions
   - AWS configuration guide
   - Troubleshooting section
   - API response structure examples

### 5. **requirements.txt**
   - All necessary dependencies
   - Compatible with your existing environment

## Key Differences from Automative-Cars-and-Trucks

| Aspect | Automative-Cars | Wanted-Cars |
|--------|-----------------|-------------|
| **Base URL** | `/ar/automotive/` | `/ar/automotive/wanted-cars/` |
| **Categories** | Hardcoded (classic-cars, junk-cars, food-trucks) | Dynamic discovery from catChilds |
| **Subcategories** | Support for child categories | Direct subcategories (American, European, Asian) |
| **Excel Structure** | Multiple files per category | Single wanted-cars.xlsx with multiple sheets |
| **S3 Folder** | `automative-cars-and-trucks/` | `wanted-cars/` |
| **Image Naming** | listing_id_index.jpg | listing_id_index.jpg (same) |

## How It Works

### 1. **Subcategory Discovery**
```
GET https://www.q84sale.com/ar/automotive/wanted-cars/1
↓
Extract catChilds from __NEXT_DATA__
↓
Returns: [wanted-american-cars, wanted-european-car, wanted-asian-cars]
```

### 2. **Listing Scraping**
```
For each subcategory:
  → GET https://www.q84sale.com/ar/automotive/wanted-cars/{slug}/{page}
  → Extract listings (title, price, phone, images, etc.)
  → For each listing:
    → GET https://www.q84sale.com/ar/listing/{slug}
    → Extract details and attributes
    → Download and upload images to S3
```

### 3. **Data Organization**
```
wanted-cars.xlsx
├── Sheet: Info (project summary)
├── Sheet: مطلوب ونشتري سيارات امريكية (111 listings)
├── Sheet: مطلوب ونشتري سيارات اوروبية (76 listings)
└── Sheet: مطلوب ونشتري سيارات اسيوية (197 listings)
```

## S3 Partition Structure

```
4sale-data/wanted-cars/year=2024/month=12/day=21/
├── excel-files/
│   └── wanted-cars.xlsx
├── json-files/
│   └── summary_20241221.json
└── images/
    ├── wanted-american-cars/
    │   ├── 20476856_0.jpg
    │   ├── 20449517_0.jpg
    │   └── ...
    ├── wanted-european-car/
    │   └── ...
    └── wanted-asian-cars/
        └── ...
```

## Usage

### Basic Command
```bash
cd Wanted-Cars
python main.py
```

### With Custom Settings
```bash
S3_BUCKET_NAME="my-bucket" MAX_PAGES="10" python main.py
```

### Environment Variables
- `S3_BUCKET_NAME` - Default: `data-collection-dl`
- `AWS_PROFILE` - Default: `PowerUserAccess-235010163908`
- `MAX_PAGES` - Default: `5` (pages per subcategory)

## Comparison with Original Project

Your original `Automative-Cars-and-Trucks` scraper has:
- Hardcoded target categories
- Support for child subcategories with district filtering
- Multiple Excel files per category

The new `Wanted-Cars` scraper has:
- **Automatic subcategory discovery** (no hardcoding needed)
- **Single unified Excel file** with all subcategories as sheets
- **Same S3 structure** but in `wanted-cars` folder
- **Same image handling** with listing ID-based naming
- **Compatible architecture** for easy maintenance

## Data Captured

Each listing includes:
- ✓ ID, slug, title, description
- ✓ Price, contact details (phone, email)
- ✓ User information (name, email, phone, type, verification)
- ✓ Address and coordinates
- ✓ Publication date and view count
- ✓ Images (automatically uploaded to S3)
- ✓ Car attributes (year, color, mileage)
- ✓ Listing status (normal, pinned)

## Notes

1. **Rate Limiting**: Built-in delays between requests to be respectful to the server
2. **Error Recovery**: Failed image uploads don't stop the scraping
3. **Async Operations**: Uses async/await for efficient concurrent operations
4. **Image Handling**: Images are downloaded from Q84Sale and uploaded to S3 with source URL tracking
5. **Excel Format**: Uses openpyxl for proper formatting and multilingual support (Arabic/English)
6. **JSON Metadata**: Structured summaries for further processing and analysis

## Next Steps

1. Ensure AWS SSO is configured: `aws configure sso`
2. Run the scraper: `python main.py`
3. Check S3 bucket for outputs
4. Download Excel file with all subcategories

---

**Created**: December 21, 2024
**Status**: Ready for use ✓
