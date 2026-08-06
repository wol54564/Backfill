# Dalil Scraper - GitHub Actions Setup

## Workflow Schedule

The Dalil scraper runs **automatically on the 1st day of every month at 2:00 AM UTC**.

Workflow file: `.github/workflows/dalil.yml`

## Cron Schedule

```yaml
schedule:
  - cron: '0 2 1 * *'  # 1st day of every month at 2:00 AM UTC
```

## Required Secrets

Configure these in your GitHub repository settings (Settings → Secrets and variables → Actions):

1. `AWS_ACCESS_KEY_ID` - Your AWS access key
2. `AWS_SECRET_ACCESS_KEY` - Your AWS secret key
3. `S3_BUCKET_NAME` - Your S3 bucket name (e.g., `4sale-scraper-data`)

## Manual Triggering

You can manually trigger the workflow anytime:

1. Go to **Actions** tab in GitHub
2. Select **Dalil Directory Scraper** workflow
3. Click **Run workflow** button
4. Choose the branch and click **Run workflow**

## Workflow Steps

1. ✅ Checkout repository code
2. ✅ Set up Python 3.11
3. ✅ Install dependencies from `requirements.txt`
4. ✅ Run `Dalil/main.py` with AWS credentials from secrets

## Testing Locally

Before committing, test the scraper locally:

```bash
cd Dalil

# Set environment variables
export S3_BUCKET_NAME="your-bucket-name"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"

# Run the scraper
python main.py
```

## What Gets Uploaded to S3

On each run, the workflow uploads to:
```
s3://your-bucket/4sale-data/Dalil/year=2026/month=02/day=01/
├── dalil_directory_20260201.xlsx      # Excel with 16 category sheets
├── dalil_summary_20260201.json        # JSON summary statistics
└── images/                             # Business images organized by category
    ├── restaurants-cafes/
    ├── healthcare/
    ├── beauty-spa/
    └── ... (all 16 categories)
```

## Monitoring

### View Workflow Runs
- Go to **Actions** tab in GitHub
- Click on **Dalil Directory Scraper**
- View run history and logs

### Check Logs
- Click on any workflow run
- Click on the **scrape** job
- Expand **Run Dalil scraper** step to see detailed logs

## Next Run

The workflow will automatically run on:
- **March 1, 2026 at 2:00 AM UTC**
- **April 1, 2026 at 2:00 AM UTC**
- And every 1st day of the month thereafter

## Troubleshooting

### Workflow Fails
1. Check the **Actions** tab for error logs
2. Verify all secrets are correctly configured
3. Ensure S3 bucket exists and has proper permissions

### Missing Data
1. Check if websites are accessible
2. Review logs for scraping errors
3. Manually trigger workflow to retry

### AWS Permissions
The AWS credentials need these permissions:
- `s3:PutObject` - Upload files to S3
- `s3:GetObject` - Read files from S3
- `s3:ListBucket` - List bucket contents

## Changing Schedule

To modify when the scraper runs, edit `.github/workflows/dalil.yml`:

```yaml
# Examples:
- cron: '0 2 1 * *'      # 1st of every month at 2 AM UTC (current)
- cron: '0 2 1,15 * *'   # 1st and 15th of every month at 2 AM UTC
- cron: '0 2 * * 0'      # Every Sunday at 2 AM UTC
- cron: '0 2 * * *'      # Every day at 2 AM UTC
```

Cron syntax: `minute hour day month day-of-week`

## Notes

- **Timeout**: Workflow has a default timeout of 6 hours
- **Rate Limiting**: Built-in delays prevent server overload
- **Error Handling**: Continues even if individual businesses fail
- **Image Processing**: Downloads and uploads ~1000-2000 images per run
