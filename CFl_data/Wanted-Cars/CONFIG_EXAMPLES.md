# Configuration Examples - Wanted Cars Scraper

## Environment Variables

### Basic Configuration
```bash
# Default settings (most common use case)
python main.py
```

### Custom S3 Bucket
```bash
export S3_BUCKET_NAME="my-custom-bucket"
python main.py
```

### Custom AWS Profile
```bash
export AWS_PROFILE="MyCustomProfile"
python main.py
```

### Custom Max Pages
```bash
export MAX_PAGES="10"
python main.py
```

### All Custom Settings
```bash
export S3_BUCKET_NAME="my-bucket"
export AWS_PROFILE="MyProfile"
export MAX_PAGES="15"
python main.py
```

## Common Scenarios

### Scenario 1: Quick Test
**Goal**: Test scraper with minimal data

```bash
# Only scrape first page of each subcategory
MAX_PAGES=1 python main.py
```

**Expected Result**: 
- ~10-50 listings total
- ~10-50 images
- Run time: 2-5 minutes

---

### Scenario 2: Full Daily Scrape
**Goal**: Complete daily data collection

```bash
# Default settings - full 5 pages per subcategory
python main.py
```

**Expected Result**:
- ~300-500 listings total
- ~300-500 images
- Run time: 15-30 minutes

---

### Scenario 3: Comprehensive Weekly Scrape
**Goal**: Detailed collection for analysis

```bash
# Scrape all pages available
MAX_PAGES=50 python main.py
```

**Expected Result**:
- ~500-1000+ listings (all available)
- ~500-1000+ images
- Run time: 30-60 minutes

---

### Scenario 4: Specific Bucket Upload
**Goal**: Upload to company data lake

```bash
S3_BUCKET_NAME="company-data-lake" python main.py
```

**S3 Structure**:
```
company-data-lake/4sale-data/wanted-cars/year=2024/month=12/day=21/
├── excel-files/wanted-cars.xlsx
├── json-files/summary_20241221.json
└── images/...
```

---

### Scenario 5: Development Environment
**Goal**: Test with different AWS account

```bash
AWS_PROFILE="dev-account" \
S3_BUCKET_NAME="dev-bucket" \
MAX_PAGES="1" \
python main.py
```

---

## Configuration Files (Optional)

### .env File (using python-dotenv)
Create `.env` file in Wanted-Cars folder:

```bash
S3_BUCKET_NAME=data-collection-dl
AWS_PROFILE=PowerUserAccess-235010163908
MAX_PAGES=5
```

Then modify `main.py` to load it:
```python
from dotenv import load_dotenv
import os

load_dotenv()

bucket_name = os.environ.get("S3_BUCKET_NAME", "data-collection-dl")
profile_name = os.environ.get("AWS_PROFILE", None)
max_pages = int(os.environ.get("MAX_PAGES", "5"))
```

### config.py File
Create `config.py`:

```python
# config.py
import os

class Config:
    """Base configuration"""
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "data-collection-dl")
    AWS_PROFILE = os.environ.get("AWS_PROFILE", "PowerUserAccess-235010163908")
    AWS_REGION = "us-east-1"
    MAX_PAGES = int(os.environ.get("MAX_PAGES", "5"))
    TEMP_DIR = "temp_data"

class DevelopmentConfig(Config):
    """Development configuration"""
    S3_BUCKET_NAME = "dev-bucket"
    MAX_PAGES = 1
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    S3_BUCKET_NAME = "prod-bucket"
    MAX_PAGES = 10
    DEBUG = False

# Usage in main.py
if __name__ == "__main__":
    env = os.environ.get("ENV", "production")
    config = ProductionConfig if env == "production" else DevelopmentConfig
    
    orchestrator = WantedCarsScraperOrchestrator(
        bucket_name=config.S3_BUCKET_NAME,
        profile_name=config.AWS_PROFILE
    )
```

---

## Batch/Script Examples

### Windows Batch Script
Create `run_wanted_cars.bat`:

```batch
@echo off
setlocal enabledelayedexpansion

REM Set configuration
set S3_BUCKET_NAME=data-collection-dl
set AWS_PROFILE=PowerUserAccess-235010163908
set MAX_PAGES=5

REM Change to script directory
cd /d %~dp0

REM Create logs directory if not exists
if not exist logs mkdir logs

REM Run scraper with logging
echo Starting Wanted Cars Scraper...
echo Time: %date% %time%

python main.py >> logs\wanted_cars_%date:~10,4%%date:~4,2%%date:~7,2%.log 2>&1

if %errorlevel% equ 0 (
    echo Scraping completed successfully
) else (
    echo Scraping failed with error code %errorlevel%
)

pause
```

### Linux/macOS Shell Script
Create `run_wanted_cars.sh`:

```bash
#!/bin/bash

# Set configuration
export S3_BUCKET_NAME="data-collection-dl"
export AWS_PROFILE="PowerUserAccess-235010163908"
export MAX_PAGES="5"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create logs directory if not exists
mkdir -p logs

# Get current date and time
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Run scraper with logging
echo "Starting Wanted Cars Scraper..."
echo "Time: $(date)"

python main.py >> logs/wanted_cars_$TIMESTAMP.log 2>&1

if [ $? -eq 0 ]; then
    echo "Scraping completed successfully"
else
    echo "Scraping failed with error code $?"
fi
```

Make it executable:
```bash
chmod +x run_wanted_cars.sh
./run_wanted_cars.sh
```

---

## Task Scheduler Setup (Windows)

### Create Scheduled Task via Command Line
```batch
REM Run daily at 8:00 AM
schtasks /create /tn "WantedCarsScraper" /tr "C:\Users\KimoStore\Desktop\Automative-Cars-and-Trucks\Wanted-Cars\run_wanted_cars.bat" /sc daily /st 08:00

REM Verify task was created
schtasks /query /tn "WantedCarsScraper" /v

REM To delete the task
schtasks /delete /tn "WantedCarsScraper" /f
```

### Create via GUI
1. Open **Task Scheduler**
2. Click **Create Task**
3. **General** tab:
   - Name: `WantedCarsScraper`
   - Run whether user is logged in or not
   - Run with highest privileges

4. **Triggers** tab:
   - New Trigger
   - Daily at 08:00

5. **Actions** tab:
   - Action: Start a program
   - Program: `C:\Users\KimoStore\Desktop\Automative-Cars-and-Trucks\myenv\Scripts\python.exe`
   - Arguments: `main.py`
   - Start in: `C:\Users\KimoStore\Desktop\Automative-Cars-and-Trucks\Wanted-Cars`

6. **Conditions** tab:
   - Only run if user is logged in
   - Power settings: Don't start if on batteries

---

## Cron Job Setup (Linux/macOS)

### Edit Crontab
```bash
crontab -e
```

### Add Daily Run
```bash
# Run at 8:00 AM every day
0 8 * * * cd /path/to/Wanted-Cars && /usr/bin/python3 main.py >> logs/daily.log 2>&1

# Run every 6 hours
0 */6 * * * cd /path/to/Wanted-Cars && /usr/bin/python3 main.py >> logs/six_hourly.log 2>&1

# Run every Monday at 9:00 AM (weekly)
0 9 * * 1 cd /path/to/Wanted-Cars && /usr/bin/python3 main.py >> logs/weekly.log 2>&1
```

### View Cron Logs
```bash
# macOS
log stream --predicate 'process == "cron"'

# Linux
grep CRON /var/log/syslog
```

---

## Docker Container Setup (Optional)

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY json_scraper.py .
COPY s3_helper.py .
COPY main.py .

# Set environment variables
ENV S3_BUCKET_NAME=data-collection-dl
ENV AWS_PROFILE=PowerUserAccess-235010163908
ENV MAX_PAGES=5

# Run scraper
CMD ["python", "main.py"]
```

### Build and Run
```bash
# Build image
docker build -t wanted-cars-scraper:latest .

# Run container with AWS credentials
docker run --rm \
  -e S3_BUCKET_NAME=data-collection-dl \
  -e AWS_PROFILE=PowerUserAccess-235010163908 \
  -e MAX_PAGES=5 \
  -v ~/.aws:/root/.aws:ro \
  wanted-cars-scraper:latest
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  wanted-cars-scraper:
    build: .
    image: wanted-cars-scraper:latest
    environment:
      S3_BUCKET_NAME: data-collection-dl
      AWS_PROFILE: PowerUserAccess-235010163908
      MAX_PAGES: 5
    volumes:
      - ~/.aws:/root/.aws:ro
      - ./logs:/app/logs
    restart: on-failure:3
    container_name: wanted-cars-scraper
```

Run with docker-compose:
```bash
docker-compose up
```

---

## Monitoring & Alerts

### Email Notifications (optional enhancement)
```python
import smtplib
from email.mime.text import MIMEText

def send_email_notification(subject, body, success=True):
    # Add to main.py after scraping completes
    msg = MIMEText(body)
    msg['Subject'] = f"[{'✓' if success else '✗'}] {subject}"
    msg['From'] = "scraper@example.com"
    msg['To'] = "admin@example.com"
    
    # Send email
    # Implementation varies by email provider
```

### Log Monitoring
```bash
# Watch logs in real-time
tail -f logs/daily.log

# Count listings in today's log
grep "Total listings for" logs/daily.log | tail -1

# Check for errors
grep "ERROR" logs/daily.log
```

---

## Performance Tuning

### For Large Datasets
```bash
# Increase max pages
MAX_PAGES=50 python main.py

# Increase rate limiting in code:
# Change: await asyncio.sleep(1)
# To: await asyncio.sleep(0.5)
```

### For Minimal Data
```bash
# Single page per subcategory
MAX_PAGES=1 python main.py
```

### For Best Performance
- Run during off-peak hours
- Use SSD for temp files
- Ensure stable internet connection
- Monitor S3 upload bandwidth

---

## Troubleshooting Configurations

### Debug Mode (verbose logging)
Modify main.py:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    format="%(asctime)s - %(levelname)s - %(message)s"
)
```

### Test AWS Connection
```bash
# Test S3 access
aws s3 ls s3://data-collection-dl/ --profile PowerUserAccess-235010163908

# Test SSO login
aws sso login --profile PowerUserAccess-235010163908

# Get account ID
aws sts get-caller-identity --profile PowerUserAccess-235010163908
```

### Test URL Access
```bash
# Test main URL
curl -s "https://www.q84sale.com/ar/automotive/wanted-cars/1" | head -100

# Test API endpoint
curl -I "https://www.q84sale.com/ar/automotive/wanted-cars/1"
```

---

Created: December 21, 2024
