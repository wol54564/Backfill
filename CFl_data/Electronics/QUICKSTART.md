# Electronics Scraper - Quick Start Guide

## Overview

This scraper automatically collects electronics listings from Q84Sale and organizes them into Excel files. It handles three different category structures and uploads everything to AWS S3.

## Structure Detection

The scraper automatically detects and handles:

### 1. Categories with catChilds (Brand-based)
**Example**: Mobile Phones and Accessories
```
Mobile Phones and Accessories
├── iPhone (with 332 listings)
├── Samsung (with 20 listings)
├── Huawei (with 11 listings)
├── Other Phones (with 71 listings)
└── Accessories (with 20 listings)
```
- **URL Pattern**: `electronics/mobile-phones-and-accessories/{child-slug}/`
- **Excel Output**: One sheet per brand (iPhone, Samsung, Huawei, etc.)

### 2. Categories with Subcategories
**Example**: Cameras
```
Cameras
├── Monitoring Cameras (with 778 listings)
├── Digital Cameras (with 12 listings)
└── Professional Cameras (with 81 listings)
```
- **URL Pattern**: `electronics/cameras/{sub-slug}/`
- **Excel Output**: One sheet per camera type

### 3. Direct Listing Categories
**Example**: Smartwatches
```
Smartwatches (78 listings directly)
```
- **URL Pattern**: `electronics/smartwatches/`
- **Excel Output**: Single sheet with all smartwatch listings

## Excel File Output

Each main category gets its own Excel file:

### File: `mobile-phones-and-accessories.xlsx`
```
Sheet 1: Info
├── Category: موبايلات و إكسسوارات
├── Structure Type: catchilds
├── Total Children/Sheets: 5
└── Total Listings: 474

Sheet 2: ايفون (iPhone)
├── 332 listings

Sheet 3: سامسونغ (Samsung)
├── 20 listings

Sheet 4: هواوي (Huawei)
├── 11 listings

Sheet 5: موبايلات أخرى (Other Phones)
├── 71 listings

Sheet 6: اكسسوارات (Accessories)
└── 20 listings
```

### File: `cameras.xlsx`
```
Sheet 1: Info
├── Category: كاميرات
├── Structure Type: subcategories
├── Total Children/Sheets: 3
└── Total Listings: 871

Sheet 2: كاميرات مراقبة (Monitoring Cameras)
├── 778 listings

Sheet 3: كاميرات ديجيتال (Digital Cameras)
├── 12 listings

Sheet 4: كاميرات إحترافية (Professional Cameras)
└── 81 listings
```

### File: `smartwatches.xlsx`
```
Sheet 1: Info
├── Category: ساعات ذكية
├── Structure Type: direct
├── Total Children/Sheets: 1
└── Total Listings: 78

Sheet 2: ساعات ذكية (Smartwatches)
└── 78 listings
```

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure AWS
```bash
# Setup AWS SSO
aws configure sso

# Get your profile name
aws configure list
```

### 3. Update Configuration
Edit `s3_helper.py`:
```python
AWS_PROFILE_NAME = "Your-Profile-Name"  # Your SSO profile
AWS_REGION = "us-east-1"                # Your region
```

### 4. Set Environment Variables (Optional)
```bash
export S3_BUCKET_NAME="your-bucket-name"
export AWS_PROFILE="Your-Profile-Name"
```

## Running the Scraper

### Basic Usage
```bash
python main.py
```

### Expected Output
```
============================================================
ELECTRONICS SCRAPER - AWS S3 INTEGRATION (SSO)
============================================================
Bucket: data-collection-dl
Mode: Scrape ALL available pages per category

Starting scraping...

[1/17] Processing: موبايلات و إكسسوارات (mobile-phones-and-accessories)
  Fetching catChilds...
  [1/5] Processing child: ايفون
    Fetching listings for electronics/mobile-phones-and-accessories/iphone-2285 page 1...
    Found 20 listings on page 1 (Total Pages: 17)
    Fetching details for 20 listings...
    ✓ Retrieved details for iphone-14-20494872
    Successfully fetched 20/20 detailed listings
    Total listings for ايفون: 20 (across 1 pages)
    
  [2/5] Processing child: سامسونغ
  ...

[2/17] Processing: تابلت / ايباد (tablets)
...

============================================================
UPLOADING TO S3
============================================================

Creating Excel file for موبايلات و إكسسوارات...
  Created sheet: ايفون (20 listings)
  Created sheet: سامسونغ (20 listings)
  ...
✓ Uploaded: mobile-phones-and-accessories.xlsx (474 listings across 5 sheets)

Creating Excel file for تابلت / ايباد...
...

============================================================
SCRAPING COMPLETED
============================================================
Excel files uploaded: 17
Total listings: 12,847

  - mobile-phones-and-accessories: 474 listings (5 sheets)
  - tablets: 144 listings (1 sheets)
  - cameras: 871 listings (3 sheets)
  ...
```

## Listing Data Format

Each listing includes:

### Basic Information
- `id`: Listing ID
- `title`: Product title (Arabic/English)
- `slug`: URL slug
- `price`: Price in KD
- `date_published`: Publication date

### Images
- `images`: Array of image URLs
- `images_count`: Total number of images
- `s3_images`: URLs of uploaded images on S3

### User Information
- `user_name`: Seller/Business name
- `user_email`: Email address
- `user_phone`: Phone number
- `user_type`: Business or individual
- `is_verified`: Verification status
- `user_ads`: Total ads count

### Location Information
- `address`: District name
- `full_address`: Complete Arabic address
- `full_address_en`: Complete English address
- `longitude`: GPS longitude
- `latitude`: GPS latitude

### Product Attributes
- `specification_en`: JSON of English specs
- `specification_ar`: JSON of Arabic specs
- Individual attribute columns for each specification

## Data Location in S3

After running, you'll find:

```
s3://data-collection-dl/4sale-data/electronics/year=2024/month=12/day=22/

├── excel-files/
│   ├── mobile-phones-and-accessories.xlsx
│   ├── cameras.xlsx
│   ├── smartwatches.xlsx
│   └── ... (one file per main category)
│
├── json-files/
│   └── electronics_summary_20241222.json
│
└── images/
    ├── mobile-phones-and-accessories/
    │   ├── 20494872_0.jpg
    │   ├── 20494872_1.jpg
    │   └── ...
    ├── cameras/
    │   └── ...
    └── ... (organized by category)
```

## Category Coverage

The scraper currently handles these main electronics categories:

1. **موبايلات و إكسسوارات** (Mobile Phones & Accessories) - catChilds
2. **تابلت / ايباد** (Tablets) - direct
3. **كاميرات** (Cameras) - subcategories
4. **أجهزة منزلية/مكتبية** (Home/Office Appliances) - catChilds
5. **ألعاب الفيديو و ملحقاتها** (Video Games & Consoles) - subcategories
6. **أرقام موبايلات** (Mobile Numbers) - direct
7. **الصوت و السماعات** (Audio & Headphones) - direct
8. **لابتوب وكمبيوتر** (Laptop & Computer) - catChilds
9. **اجهزة و شبكات** (Devices & Networking) - subcategories
10. **ساعات ذكية** (Smartwatches) - direct
11. **تلفزيونات ذكية** (Smart TV) - direct
12. **ريسيفرات** (Satellite Receiver) - direct
13. **مطلوب و نشتري** (Wanted Devices) - direct
14. **خدمات إلكترونية** (Electronics Services) - direct
15. **أجهزة أخرى** (Other Electronics) - direct
16. **محلات الإلكترونيات** (Electronics Shops) - subcategories
17. **[Any new categories added to the website]** - auto-detected

## Tips & Best Practices

### 1. Rate Limiting
- The scraper automatically waits between requests
- Respects the website's resources
- Delays vary: 0.5-2 seconds depending on operation

### 2. Handling Large Categories
- Mobile Phones has 474 listings across 17 pages
- Cameras has 871 listings across 3 types
- Automatic pagination handles all pages

### 3. Image Management
- Large images are downloaded and uploaded to S3
- Naming: `{listing_id}_{image_index}.jpg`
- Reduces original website bandwidth usage
- Improves reliability and archival

### 4. Scheduling
For regular collection:
```bash
# Daily at 2 AM
0 2 * * * cd /path/to/Electronics && python main.py >> logs/scraper.log 2>&1
```

### 5. Error Recovery
- Failed images don't stop the scraper
- Partial uploads are retried
- Check logs for any issues

## Troubleshooting

### No listings found
```bash
# Check website is accessible
curl https://www.q84sale.com/ar/electronics

# Check if structure detection is working
# Look for "Found X catChilds/subcategories" in logs
```

### S3 upload fails
```bash
# Verify AWS credentials
aws s3 ls

# Check profile name
aws configure list

# Test S3 access
aws s3 ls s3://your-bucket-name/
```

### Missing children/sheets
```bash
# Check structure detection in logs
# If category shows "Direct listings (no children)"
# it will have only one sheet with all listings
```

## Performance Metrics

Typical run statistics:
- **Main Categories**: 17 total
- **Total Listings**: 12,000+ listings
- **Total Images**: 30,000+ images
- **Runtime**: 2-4 hours (depending on network)
- **Data Size**: 500MB+ (including images)

## JSON Summary Format

```json
{
  "scraped_at": "2024-12-22T14:30:45.123456",
  "saved_to_s3_date": "2024-12-22",
  "total_main_categories": 17,
  "total_listings": 12847,
  "main_categories": [
    {
      "name_ar": "موبايلات و إكسسوارات",
      "name_en": "Mobile Phones & Accessories",
      "slug": "mobile-phones-and-accessories",
      "structure_type": "catchilds",
      "children_count": 5,
      "total_listings": 474
    },
    ...
  ]
}
```

## Notes

- Each run is a complete snapshot of the electronics category
- Historical data is organized by date
- Easy to compare categories over time
- All data is UTF-8 encoded for Arabic support
- Images are validated before upload

---

Need help? Check README.md for detailed documentation or review the logs for specific errors.
