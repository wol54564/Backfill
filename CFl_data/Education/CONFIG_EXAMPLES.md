# Education Scraper - Configuration & Customization Guide

## Configuration Files

### 1. S3 Configuration (s3_helper.py)

Default AWS settings at the top of the file:

```python
AWS_PROFILE_NAME = "PowerUserAccess-235010163908"  # Your AWS SSO profile
AWS_REGION = "us-east-1"
```

**To customize:**
```python
# Option 1: Modify directly in s3_helper.py
AWS_PROFILE_NAME = "your-profile-name"
AWS_REGION = "eu-west-1"

# Option 2: Use environment variables (overrides defaults)
export AWS_PROFILE=your-profile-name
```

### 2. Base URL Configuration (json_scraper.py)

```python
self.base_url = "https://www.q84sale.com/ar/education"
```

**If the domain changes:**
```python
self.base_url = "https://new-domain.com/ar/education"
```

### 3. Rate Limiting (json_scraper.py & main.py)

Current settings (in seconds):
```python
# Between listing details
await asyncio.sleep(0.5)

# Between pages
await asyncio.sleep(1)

# Between child categories
await asyncio.sleep(1)

# Between subcategories
await asyncio.sleep(2)
```

**To adjust (e.g., slower for stability):**
```python
await asyncio.sleep(1.0)  # 1 second instead of 0.5
await asyncio.sleep(2)    # 2 seconds instead of 1
await asyncio.sleep(3)    # 3 seconds instead of 2
```

### 4. Temporary Directory

```python
temp_dir = "temp_data"  # Default
```

**To change:**
```python
temp_dir = "/path/to/your/temp"
```

## Environment Variables

### Required
None - all defaults are provided

### Optional

```bash
# AWS Configuration
export S3_BUCKET_NAME=your-bucket-name
export AWS_PROFILE=your-profile-name

# Logging (if adding logging level control)
export LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

## Logging Configuration

### Current Level
```python
logging.basicConfig(level=logging.INFO)
```

### To change to DEBUG (more verbose):
```python
logging.basicConfig(level=logging.DEBUG)
```

### To add file logging:
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("education_scraper.log"),
        logging.StreamHandler()
    ]
)
```

## Customizing Scraper Behavior

### 1. Filter by Specific Category

Modify `main.py` to only scrape certain categories:

```python
# In scrape_all_subcategories()
if not subcategories:
    logger.error("No subcategories found!")
    return []

# ADD THIS: Filter to specific categories
ALLOWED_CATEGORIES = ["languages", "school-supplies"]  # Only scrape these
subcategories = [s for s in subcategories if s['slug'] in ALLOWED_CATEGORIES]

logger.info(f"Found {len(subcategories)} vertical subcategories (filtered)")
```

### 2. Limit Pages per Category

Modify pagination in `main.py`:

```python
# In scrape_child_category() or scrape_subcategory()
MAX_PAGES = 2  # Only scrape first 2 pages

while True:
    listings, total_pages = await self.scraper.get_listings(...)
    
    if not listings:
        break
    
    # ... existing code ...
    
    page_num += 1
    
    # ADD THIS: Stop after MAX_PAGES
    if page_num > MAX_PAGES:
        logger.info(f"Reached max pages limit ({MAX_PAGES})")
        break
    
    if page_num > total_pages:
        logger.info(f"Reached total pages ({total_pages})")
        break
```

### 3. Skip Image Download

If you don't need images (faster scraping):

```python
# In scrape_child_category() or scrape_subcategory()
# Comment out image processing:

# if images:
#     logger.info(f"Processing {len(images)} images...")
#     # ... image processing code ...
#     details["s3_images"] = s3_image_urls

# Just skip images:
details["s3_images"] = []
```

### 4. Custom Data Fields

To add/remove fields from listings, modify in `json_scraper.py`:

```python
# In get_listings()
formatted_listings.append({
    "id": listing.get("id"),
    "title": listing.get("title"),
    # ... existing fields ...
    "custom_field": listing.get("custom_field_name"),  # ADD NEW
    # REMOVE unwanted fields by deleting their lines
})
```

### 5. Exclude Ad Boxes

Currently skipped automatically:
```python
# Skip ad boxes
if listing.get("adBoxId"):
    continue
```

To also skip other content, add similar checks:
```python
if listing.get("adBoxId"):
    continue
if listing.get("status") == "expired":  # Example: skip expired
    continue
```

## Excel Customization

### 1. Change Sheet Name Format

In `main.py`, in `save_all_to_s3()`:

```python
# Current: Uses Arabic name
sheet_name = child_cat["name_ar"][:31]

# Alternative: Use English name
sheet_name = child_cat["name_en"][:31]

# Alternative: Use slug
sheet_name = child_cat["slug"][:31]
```

### 2. Add/Remove Info Columns

```python
# In save_all_to_s3(), modify info_data:

info_data = [{
    "Project": "Education",
    "Subcategory": subcategory['name_ar'],
    # "Custom Column": "Custom Value",  # ADD
    # Remove unwanted columns by deleting
}]
```

### 3. Change DataFrame Formatting

```python
# Before writing to Excel, customize columns:

df = pd.DataFrame(child_result["listings"])

# Reorder columns
column_order = ["id", "title", "price", "phone", ...]
df = df[[col for col in column_order if col in df.columns]]

# Format specific columns
df["price"] = df["price"].fillna(0).astype(int)
df["date_published"] = pd.to_datetime(df["date_published"])

df.to_excel(writer, sheet_name=sheet_name, index=False)
```

## S3 Path Customization

### Change Partition Structure

In `s3_helper.py`, modify `get_partition_prefix()`:

```python
# Current: year=YYYY/month=MM/day=DD
return f"4sale-data/education/year={year}/month={month}/day={day}"

# Alternative: Simple date folder
return f"4sale-data/education/{year}/{month}/{day}"

# Alternative: Flatten to single folder
return f"4sale-data/education"
```

### Change Excel File Location

In `main.py`, in `save_all_to_s3()`:

```python
# Current
s3_excel_path = await asyncio.to_thread(
    self.s3_helper.upload_file,
    str(temp_excel),
    f"excel-files/{excel_filename}",  # CHANGE THIS
    self.save_date,
    retries=3
)

# Alternative: Category-based organization
s3_excel_path = await asyncio.to_thread(
    self.s3_helper.upload_file,
    str(temp_excel),
    f"education/excel/{safe_filename}.xlsx",
    self.save_date,
    retries=3
)
```

## Advanced Customizations

### 1. Add Proxy Support

In `json_scraper.py`:

```python
def __init__(self):
    self.base_url = "https://www.q84sale.com/ar/education"
    self.session = requests.Session()
    
    # ADD THIS: Set proxy
    proxies = {
        'http': 'http://proxy.example.com:8080',
        'https': 'http://proxy.example.com:8080',
    }
    self.session.proxies.update(proxies)
    
    self.session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
```

### 2. Add Retry Logic for Listings

```python
# In get_listings()
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        json_data = await self.get_page_json_data(url)
        if json_data:
            break
    except Exception as e:
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(2 ** attempt)
```

### 3. Add Database Storage

Instead of just S3, also store in database:

```python
# Add to main.py imports
import sqlite3

# Store listings before uploading to S3
for result in results:
    for listing in result["listings"]:
        conn = sqlite3.connect("education.db")
        conn.execute("INSERT INTO listings VALUES (...)")
        conn.commit()
```

### 4. Add Email Notifications

```python
# In main.py
import smtplib
from email.mime.text import MIMEText

def send_notification(upload_summary):
    msg = MIMEText(f"Scraped {upload_summary['total_listings']} listings")
    msg['Subject'] = "Education Scraper Completed"
    
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login("your-email@gmail.com", "your-password")
        server.send_message(msg)
```

## Testing Custom Changes

Before deploying changes:

```bash
# Test on a single category
# Modify scrape_all_subcategories() to return first category only

# Or test with minimal data
export LOG_LEVEL=DEBUG
python main.py

# Check temp_data/ for generated Excel files
ls temp_data/
```

## Performance Tuning

### For Faster Scraping
```python
# Reduce rate limiting
await asyncio.sleep(0.2)  # Instead of 0.5

# Limit pages
MAX_PAGES = 1

# Skip images
skip_images = True
```

### For More Reliable Scraping
```python
# Increase rate limiting
await asyncio.sleep(2.0)  # Instead of 0.5

# More retries
retries=5  # Instead of 3

# Better error handling
continue_on_error=True
```

## Monitoring & Debugging

### 1. Log specific category
```python
if subcategory['slug'] == 'languages':
    logger.debug(f"Detailed logs for languages: {json_data}")
```

### 2. Save intermediate results
```python
# Save listings before uploading
with open(f"debug_{slug}.json", 'w') as f:
    json.dump(result["listings"], f, indent=2)
```

### 3. Check S3 uploads
```bash
# List uploaded files
aws s3 ls s3://data-collection-dl/4sale-data/education/ --recursive

# Check specific date
aws s3 ls s3://data-collection-dl/4sale-data/education/year=2025/month=12/day=24/ --recursive
```

## Rollback Changes

To revert to original configuration:

```bash
# Reset from git (if in version control)
git checkout s3_helper.py json_scraper.py main.py

# Or restore from backup
cp backup/main.py main.py
```

## Common Customization Templates

### Template 1: Single Category Scraper
```python
# Only scrape 'languages' category
ALLOWED_CATEGORIES = ["languages"]
subcategories = [s for s in subcategories if s['slug'] in ALLOWED_CATEGORIES]
```

### Template 2: No Image Download
```python
# Skip image processing entirely
if images:
    details["s3_images"] = []  # Don't process images
else:
    details["s3_images"] = []
```

### Template 3: Local-Only (No S3)
```python
# Skip S3 upload, keep Excel files locally
# Comment out: await orchestrator.save_all_to_s3(results)
# Just keep Excel files in temp_data/
```

## Questions?

Refer to:
- `README.md` - Full feature documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical architecture
- `QUICKSTART.md` - Usage examples
- Source code comments for implementation details
