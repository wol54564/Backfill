# Jobs Scraper - Quick Start Guide

## Setup (5 minutes)

### 1. Install Dependencies
```bash
cd Jobs
pip install -r requirements.txt
```

### 2. Configure AWS
Edit `s3_helper.py` line 12:
```python
AWS_PROFILE_NAME = "your-aws-profile"  # Update with your AWS SSO profile
```

Edit `main.py` line 427-428:
```python
BUCKET_NAME = "your-bucket-name"  # Your S3 bucket
AWS_PROFILE = "your-aws-profile"  # Your AWS SSO profile
```

### 3. Verify AWS Configuration
```bash
aws sts get-caller-identity --profile your-aws-profile
```

## Run the Scraper

### Option 1: Direct Execution
```bash
python main.py
```

### Option 2: In Python
```python
import asyncio
from main import JobsScraperOrchestrator

async def main():
    orchestrator = JobsScraperOrchestrator(
        bucket_name="your-bucket",
        profile_name="your-profile"
    )
    result = await orchestrator.run()
    print(result)

asyncio.run(main())
```

## What Happens

1. **Fetches Main Categories** (2 categories)
   - Job Openings
   - Job Seeker

2. **Fetches Child Categories** (11-12 per main)
   - Part Time Job, Accounting, Technology, etc.

3. **Scrapes Listings** (all pages, 250-350 total)
   - Fetches listing details
   - Downloads images

4. **Creates Excel Files**
   - `job-openings.xlsx` - One sheet per child category
   - `job-seeker.xlsx` - One sheet per child category
   - Each file has Info sheet with metadata

5. **Uploads to S3**
   - Excel files in `excel-files/` folder
   - Images in `images/{category}/` folders
   - Summary in `upload-summary.json`

## Monitor Progress

The scraper logs all operations to console:
```
INFO - Fetching jobs main subcategories...
INFO - Found 2 main subcategories
INFO - Fetching child categories for Job Openings...
INFO - Found 11 child categories
INFO - Processing child category...
...
```

## Output Location (S3)

```
s3://your-bucket/4sale-data/jobs/year=2025/month=12/day=25/
├── excel-files/
│   ├── job-openings.xlsx
│   └── job-seeker.xlsx
├── images/
│   ├── job-openings/
│   └── job-seeker/
└── upload-summary.json
```

## Verify Results

Check S3 console:
```bash
aws s3 ls s3://your-bucket/4sale-data/jobs/ --profile your-profile
```

Or check specific date:
```bash
aws s3 ls s3://your-bucket/4sale-data/jobs/year=2025/month=12/day=25/ --profile your-profile
```

## Troubleshooting

### No S3 uploads
```
❌ AWS connection failed
✅ Check: aws sts get-caller-identity --profile your-profile
✅ Check: S3 bucket exists and is accessible
```

### Empty results
```
❌ No listings found
✅ Check: Internet connection
✅ Check: Website structure hasn't changed
✅ Check: No IP rate limiting (wait and retry)
```

### File not found error
```
❌ Temp directory issue
✅ Check: Disk space available
✅ Check: Permissions in working directory
```

## Expected Output Example

```json
{
  "excel_files": [
    {
      "name": "job-openings",
      "main_category": "وظائف شاغرة",
      "child_categories_count": 11,
      "total_listings": 250,
      "s3_path": "4sale-data/jobs/year=2025/month=12/day=25/excel-files/job-openings.xlsx",
      "s3_url": "https://bucket.s3.us-east-1.amazonaws.com/..."
    },
    {
      "name": "job-seeker",
      "main_category": "باحث عن عمل",
      "child_categories_count": 11,
      "total_listings": 280,
      "s3_path": "4sale-data/jobs/year=2025/month=12/day=25/excel-files/job-seeker.xlsx",
      "s3_url": "https://bucket.s3.us-east-1.amazonaws.com/..."
    }
  ],
  "total_listings": 530,
  "total_main_subcategories": 2,
  "upload_time": "2025-12-25T12:30:45.123456"
}
```

## Schedule Regular Runs

### Using Cron (Linux/Mac)
```bash
# Edit crontab
crontab -e

# Add this line to run daily at 2 AM
0 2 * * * cd /path/to/Jobs && python main.py >> jobs_scraper.log 2>&1
```

### Using Task Scheduler (Windows)
1. Open Task Scheduler
2. Create Basic Task
3. Set to run daily at 2 AM
4. Action: `python main.py`
5. Start in: `/path/to/Jobs`

## Next Steps

1. ✅ Install dependencies
2. ✅ Configure AWS credentials
3. ✅ Update S3 bucket name
4. ✅ Test first run: `python main.py`
5. ✅ Verify S3 uploads
6. ✅ Set up scheduling (optional)
7. ✅ Monitor logs daily

## Documentation

- **README.md** - Full documentation
- **IMPLEMENTATION_SUMMARY.md** - Implementation details
- **ARCHITECTURE.md** - Technical specification
- **QUICKSTART.md** - This file

## Support Files

- **json_scraper.py** - Web scraping logic
- **main.py** - Orchestration logic
- **s3_helper.py** - AWS S3 operations
- **requirements.txt** - Dependencies

---

**Status**: Ready to use  
**Last Updated**: December 25, 2025
