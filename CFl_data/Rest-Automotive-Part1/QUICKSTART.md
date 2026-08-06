# Quick Start Guide - Rest-Automative-Part1 Scraper

## 🚀 30-Second Setup

### 1. Install Dependencies
```bash
cd Rest-Automative-Part1
pip install -r requirements.txt
```

### 2. Configure AWS (if not done)
```bash
aws configure sso
# Profile name: PowerUserAccess-235010163908
# Region: us-east-1
```

### 3. Run Scraper
```bash
python main.py
```

Done! ✓

## 📊 What Gets Scraped

The scraper automatically discovers and scrapes 5 categories with multiple subcategories each:

| Category | Arabic | Type |
|----------|--------|------|
| Watercraft | المركبات المائية | Boats, Jet Skis |
| Spare Parts | قطع الغيار | Auto Parts |
| Automotive Accessories | إكسسوارات سيارات | Car Accessories |
| CMVs | المركبات التجارية | Commercial Vehicles |
| Rentals | تأجير | Vehicle Rentals |

*Counts vary - updated daily*

## 📁 Output Files

### Excel Files (One per Category):
- **Watercraft.xlsx** - Watercraft subcategories and listings
- **Spare Parts.xlsx** - Spare parts subcategories and listings
- **Automotive Accessories.xlsx** - Automotive accessories subcategories and listings
- **CMVs.xlsx** - Commercial vehicles subcategories and listings
- **Rentals.xlsx** - Rentals subcategories and listings

Each Excel file contains:
- **Info** sheet - Category summary statistics
- **Category sheets** - One sheet per subcategory with all listings
- Located in S3: `4sale-data/rest-automative/year=YYYY/month=MM/day=DD/excel-files/`

### JSON: `summary_YYYYMMDD.json`
- Metadata and statistics grouped by category
- Located in S3: `4sale-data/rest-automative/year=YYYY/month=MM/day=DD/json-files/`

### Images
- Downloaded and uploaded to S3
- Located in S3: `4sale-data/rest-automative/year=YYYY/month=MM/day=DD/images/{category}/`

## ⚙️ Customization

### Change S3 Bucket
```bash
S3_BUCKET_NAME="my-bucket" python main.py
```

### Change AWS Profile
```bash
AWS_PROFILE="my-profile" python main.py
```

### Full Custom Setup
```bash
S3_BUCKET_NAME="my-bucket" AWS_PROFILE="my-profile" python main.py
```

## 🔍 Monitoring

Watch the logs as it runs:

```
2024-12-21 14:30:45 - INFO - REST-AUTOMATIVE SCRAPER STARTING
2024-12-21 14:30:45 - INFO - Bucket: data-collection-dl
2024-12-21 14:30:45 - INFO - Starting scraping...
2024-12-21 14:30:47 - INFO - Fetching Rest-Automative categories...
2024-12-21 14:30:48 - INFO - Found 5 categories
2024-12-21 14:30:48 - INFO - [1/5] Processing: المركبات المائية (watercraft)
...
2024-12-21 14:45:22 - INFO - ✓ Uploaded: rest-automative.xlsx (X listings)
2024-12-21 14:45:23 - INFO - SCRAPING COMPLETED
```

## 📋 Data Structure (Sample)

Each listing contains:
```python
{
    "id": 20476856,
    "title": "Listing Title",
    "slug": "category-slug-20476856",
    "price": 5000,
    "phone": "96551594994",
    "description": "Item description...",
    "date_published": "2025-12-15 16:21:23",
    "date_relative": "2 days ago",
    "user_name": "Seller Name",
    "user_email": "seller@example.com",
    "user_type": "normal",
    "is_verified": False,
    "images": ["https://..."],
    "s3_images": ["https://bucket.s3.amazonaws.com/..."],
    "attributes": {
        "Year": "2021",
        "Color": "Gray",
        "Condition": "Excellent"
    }
    # ... more fields
}
```

## 🆘 Troubleshooting

### ❌ "Failed to verify bucket"
```bash
# Login to AWS
aws sso login --profile PowerUserAccess-235010163908
python main.py
```

### ❌ "No __NEXT_DATA__ found"
- Check internet connection
- Q84Sale website might be temporarily down
- Try manually visiting: https://www.q84sale.com/ar/automotive/watercraft/1

### ❌ "Upload failed after 3 attempts"
- Check S3 bucket permissions
- Check AWS credentials are valid
- Verify bucket exists

## 📈 Expected Results

### Typical Run
- **Duration**: 20-40 minutes (depending on internet speed and number of listings)
- **Listings**: 200+ across all categories
- **Images**: Variable based on listings
- **Excel Files**: 5 separate files (one per category)

### Output Summary
```
Excel files uploaded: 5
  - Watercraft: X listings
  - Spare Parts: Y listings
  - Automotive Accessories: Z listings
  - CMVs: A listings
  - Rentals: B listings

JSON files uploaded: 1
  - summary_YYYYMMDD.json
```

## 💡 Pro Tips

1. **First Run**: Will take longer as images are downloaded for the first time
2. **Network**: Use a stable internet connection for best results
3. **S3 Access**: Ensure your AWS profile has S3 write permissions
4. **Monitoring**: Monitor the console output to track progress
5. **Errors**: Check logs if any errors occur - most are recoverable

## 🔗 More Information

- See [README.md](README.md) for complete documentation
- See [SETUP_SUMMARY.md](SETUP_SUMMARY.md) for detailed setup info
- See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details
