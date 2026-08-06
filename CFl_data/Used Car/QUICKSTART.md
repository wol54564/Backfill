# Used Cars Scraper - Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies
```bash
cd "Used Car"
pip install -r requirements.txt
```

### 2. Configure AWS Credentials
```bash
# Option A: Set environment variables
set AWS_ACCESS_KEY_ID=your-access-key
set AWS_SECRET_ACCESS_KEY=your-secret-key
set AWS_REGION=us-east-1

# Option B: Edit script directly (Not recommended for production)
# Edit main_used_cars.py and add your credentials
```

### 3. Run the Scraper
```bash
python main_used_cars.py
```

## What Happens

1. **Fetches Main Categories** (Toyota, Lexus, Chevrolet, etc.)
2. **Fetches Models** (Land Cruiser, Camry, Prado, etc.) for each brand
3. **Fetches All Listings** for each model across all pages
4. **Creates Excel Files** - One file per brand with sheets for each model
5. **Uploads to S3** - Automatically organizes by date

## Expected Output

### Console Output
```
INFO - Found 67 main categories
INFO - [1/67] Processing: Toyota
INFO - Found 35 subcategories for toyota
INFO - Creating sheet: Land Cruiser with 937 listings
INFO - Successfully created Excel file: temp_data/Toyota.xlsx
INFO - Uploading to S3: s3://4sale-data/4sale-data/used-cars/year=2024/month=12/day=30/Toyota.xlsx
```

### Generated Files

**Local (temp_data/)**:
- `Toyota.xlsx` - Contains all Toyota models as sheets
- `Lexus.xlsx` - Contains all Lexus models as sheets
- `Chevrolet.xlsx` - Contains all Chevrolet models as sheets
- ... (one file per brand)

**S3 (4sale-data/4sale-data/used-cars/year=2024/month=12/day=30/)**:
- Same files automatically uploaded

## Excel File Structure

Each file contains multiple sheets:

**Example: Toyota.xlsx**

| Sheet | Models | Listings |
|-------|--------|----------|
| Land Cruiser | 1 model | 937 listings |
| Camry | 1 model | 375 listings |
| Prado | 1 model | 319 listings |
| ... | ... | ... |

Each sheet has columns:
- Listing ID
- Title
- Price
- Phone
- Date Published
- District
- Description (EN/AR)
- Images Count
- ... and more

## Common Tasks

### Scrape Only First 5 Categories
Edit `main_used_cars.py`:
```python
MAX_CATEGORIES = 5  # Change from None to 5
```

### Change S3 Bucket
Edit `main_used_cars.py`:
```python
BUCKET_NAME = "your-bucket-name"  # Change from "4sale-data"
```

### View Logs While Running
The scraper outputs detailed logs:
- INFO: Successfully fetched data
- WARNING: Skipped empty categories
- ERROR: Failed operations with details

### Check S3 Upload
AWS CLI:
```bash
aws s3 ls s3://4sale-data/4sale-data/used-cars/
```

## Troubleshooting

### Error: "No AWS credentials found"
**Fix**: Set environment variables before running:
```bash
set AWS_ACCESS_KEY_ID=your-key
set AWS_SECRET_ACCESS_KEY=your-secret
python main_used_cars.py
```

### Error: "Failed to fetch main page JSON"
**Possible Causes**:
- Website is down
- Network issue
- IP is blocked

**Fix**: 
- Check if you can access https://www.q84sale.com/ar/automotive/used-cars/1
- Try running again after a few minutes
- Use VPN if IP is blocked

### Excel Files Created but Not Uploaded to S3
**Check**:
1. AWS credentials are valid
2. Bucket exists and you have write permissions
3. Network connectivity to AWS

### No Listings in Some Sheets
**Normal behavior**: Some models may have no listings. The scraper skips empty categories.

## Next Steps

1. **Schedule**: Set up a cron job to run daily
2. **Monitor**: Check S3 for new files
3. **Analyze**: Use Excel for data analysis
4. **Archive**: Move old files to archive folder on S3

## File Locations

- **Script**: `main_used_cars.py`
- **Scraper Logic**: `json_scraper_used_cars.py`
- **S3 Helper**: `s3_helper.py`
- **Dependencies**: `requirements.txt`
- **Documentation**: `README.md`

## Data Format Example

### Listing Entry (Excel Row)
```
ID: 20499635
Title: صباح الناصر
Price: 1750
Phone: 96565555210
Date: 2025-12-24 09:55:42
District: الفروانية
Status: pinned
Images: 9
Description EN: For sale Land Cruiser automatic model 97...
Description AR: للبيع لاندكروز تماتيك موديل 97...
```

## Performance Stats

- **Typical Runtime**: 30-60 minutes (all ~67 brands)
- **Data Volume**: ~200,000+ listings
- **File Size**: 5-50 MB per category file
- **S3 Upload**: Usually <5 minutes

## Tips

✓ Run during off-hours to minimize server load
✓ First run takes longer (fetches all pages)
✓ Network interruptions are handled gracefully
✓ Check logs for warnings about missing data
✓ Excel files are formatted for easy reading

## Support

If you encounter issues:
1. Check the detailed logs in console
2. Verify AWS credentials: `aws s3 ls`
3. Test website access: Visit the URL in browser
4. Review README.md for detailed documentation
