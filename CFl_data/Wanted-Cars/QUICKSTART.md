# Quick Start Guide - Wanted Cars Scraper

## 🚀 30-Second Setup

### 1. Install Dependencies
```bash
cd Wanted-Cars
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

The scraper automatically discovers and scrapes 3 subcategories:

| Subcategory | Arabic | Count* |
|-------------|--------|--------|
| Wanted American Cars | مطلوب ونشتري سيارات امريكية | ~111 |
| Wanted European Cars | مطلوب ونشتري سيارات اوروبية | ~76 |
| Wanted Asian Cars | مطلوب ونشتري سيارات اسيوية | ~197 |

*Approximate counts, updates daily

## 📁 Output Files

### Excel: `wanted-cars.xlsx`
- **Info** sheet - Summary statistics
- **Arabic sheet names** - One sheet per subcategory with all listings
- Located in S3: `4sale-data/wanted-cars/year=YYYY/month=MM/day=DD/excel-files/`

### JSON: `summary_YYYYMMDD.json`
- Metadata and statistics
- Located in S3: `4sale-data/wanted-cars/year=YYYY/month=MM/day=DD/json-files/`

### Images
- Downloaded and uploaded to S3
- Located in S3: `4sale-data/wanted-cars/year=YYYY/month=MM/day=DD/images/{subcategory}/`

## ⚙️ Customization

### Change Max Pages
```bash
MAX_PAGES=10 python main.py
```

### Change S3 Bucket
```bash
S3_BUCKET_NAME="my-bucket" python main.py
```

### Change AWS Profile
```bash
AWS_PROFILE="my-profile" python main.py
```

## 🔍 Monitoring

Watch the logs as it runs:

```
2024-12-21 14:30:45 - INFO - WANTED CARS SCRAPER - AWS S3 INTEGRATION (SSO)
2024-12-21 14:30:45 - INFO - Bucket: data-collection-dl
2024-12-21 14:30:45 - INFO - Starting scraping...
2024-12-21 14:30:47 - INFO - Fetching wanted-cars subcategories...
2024-12-21 14:30:48 - INFO - Found 3 subcategories
2024-12-21 14:30:48 - INFO - [1/3] Processing: مطلوب ونشتري سيارات امريكية (wanted-american-cars)
...
2024-12-21 14:35:22 - INFO - ✓ Uploaded: wanted-cars.xlsx (384 listings)
2024-12-21 14:35:23 - INFO - SCRAPING COMPLETED
```

## 📋 Data Structure (Sample)

Each listing contains:
```python
{
    "id": 20476856,
    "title": "الكويت العاصمه",
    "slug": "wanted-american-cars-20476856",
    "price": 1000,
    "phone": "96551594994",
    "description": "نشتري جمبع انواع سيارات...",
    "date_published": "2025-12-15 16:21:23",
    "user_name": "هلا مرحبا",
    "user_email": "a7maad1985mmak@hotmail.com",
    "user_type": "normal",
    "is_verified": False,
    "images": ["https://..."],
    "s3_images": ["https://bucket.s3.amazonaws.com/..."],
    "attributes": {
        "Year": "2021",
        "Color": "Gray",
        "Mileage": "100"
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
- Try manually visiting: https://www.q84sale.com/ar/automotive/wanted-cars/1

### ❌ "Upload failed after 3 attempts"
- Check S3 bucket permissions
- Check AWS credentials are valid
- Verify bucket exists

## 📈 Expected Results

### Typical Run
- **Duration**: 15-30 minutes (depending on internet speed)
- **Listings**: 300-500 across 3 subcategories
- **Images**: 300-500 images downloaded and uploaded
- **Excel File**: Single `wanted-cars.xlsx` with 4 sheets

### Output Summary
```
Excel files uploaded: 1
  - wanted-cars: 384 listings

JSON files uploaded: 1
  - summary_20241221.json

Images uploaded: 384 images
  - wanted-american-cars: 111 images
  - wanted-european-car: 76 images
  - wanted-asian-cars: 197 images

Total S3 upload size: ~50-100 MB (depending on images)
```

## 🔄 Scheduled Runs

To run daily at 8 AM (Windows Task Scheduler):

```batch
@echo off
cd C:\Users\KimoStore\Desktop\Automative-Cars-and-Trucks\Wanted-Cars
C:\Users\KimoStore\Desktop\Automative-Cars-and-Trucks\myenv\Scripts\python.exe main.py >> logs\daily_run.log 2>&1
```

Or on Linux/macOS (cron):
```bash
0 8 * * * cd /path/to/Wanted-Cars && python main.py >> logs/daily_run.log 2>&1
```

## 📚 More Documentation

- **README.md** - Detailed documentation
- **SETUP_SUMMARY.md** - Complete setup explanation

## 💡 Pro Tips

1. **First Run**: Start with `MAX_PAGES=1` to test
   ```bash
   MAX_PAGES=1 python main.py
   ```

2. **Check Progress**: Monitor S3 uploads in real-time
   ```bash
   aws s3 ls s3://data-collection-dl/4sale-data/wanted-cars/ --recursive
   ```

3. **View Latest Data**: Check today's partition
   ```bash
   aws s3 ls s3://data-collection-dl/4sale-data/wanted-cars/year=2024/month=12/day=21/
   ```

4. **Download Excel**: After scraping
   ```bash
   aws s3 cp s3://data-collection-dl/4sale-data/wanted-cars/year=2024/month=12/day=21/excel-files/wanted-cars.xlsx ./
   ```

## ✅ Checklist

- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] AWS SSO configured: `aws sso login --profile PowerUserAccess-235010163908`
- [ ] S3 bucket accessible: `aws s3 ls data-collection-dl/`
- [ ] First run successful: `python main.py`
- [ ] Excel file downloaded and verified
- [ ] All 3 subcategories present in Excel sheets

## 🎯 Next Steps

1. Download the `wanted-cars.xlsx` from S3
2. Open in Excel and explore the data
3. Set up scheduled runs if needed
4. Integrate with your analysis pipeline

---

**Questions?** Check the detailed documentation in README.md
