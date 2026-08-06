# Rest-Automative-Part1 Scraper

Scraper for Q84Sale Rest-Automative-Part1 categories with hierarchical structure (Category → Subcategories → Listings).

## Categories Covered

1. **Watercraft** (المركبات المائية) - boats, jet skis, yachts, sea trips, etc.
2. **Spare Parts** (قطع الغيار) - car parts and accessories
3. **Automotive Accessories** (إكسسوارات سيارات) - vehicle accessories
4. **CMVs** (المركبات التجارية) - commercial vehicles
5. **Rentals** (تأجير) - vehicle rentals

## Project Structure

```
Rest-Automatives-Part1/
├── json_scraper_rest.py      # Scraper for Rest-Automative categories
├── s3_helper.py              # AWS S3 integration with folder support
├── main_rest.py              # Orchestrator and main scraping logic
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## How It Works

1. **Fetches Categories**: Gets 5 main Rest-Automative categories
2. **Gets Subcategories**: For each category, fetches all subcategories (from `catChilds`)
3. **Paginates Listings**: For each subcategory, fetches multiple pages of listings
4. **Details Retrieval**: For each listing, fetches detailed information
5. **Excel Generation**: Creates separate Excel files per **subcategory** with:
   - **Info sheet**: Metadata (subcategory name, parent category, date, listings count)
   - **Listings sheet**: All listings for that subcategory
6. **S3 Upload**: Uploads to `4sale-data/Rest-Automative-Part1/` folder structure

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Automation

### GitHub Actions Workflow

This scraper runs automatically via GitHub Actions (`.github/workflows/rest-automative-part1.yml`):
- **Schedule**: Daily at 3:00 AM UTC
- **Manual trigger**: Via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

## Local Development

```bash
# Configure AWS credentials
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=data-collection-dl

# Run the scraper
python main.py
```

## Environment Variables

- `S3_BUCKET_NAME`: AWS S3 bucket name (default: "data-collection-dl")
- `MAX_PAGES`: Maximum pages to scrape per subcategory (default: 5)

## Output Structure

Excel files are saved with Arabic subcategory names:
- `CMVs.xlsx` 
- `Watercrafts.xlsx` 
- etc.

Each file contains:
- **Info**: Metadata about the subcategory
- **Listings**: All listing details with attributes

S3 Structure:
```
4sale-data/Rest-Automative-Part1/
  ├── year=2025/month=12/day=20/
  │   ├── excel-files/
  │   │   ├── Watercrafts.xlsx
  │   │   ├── CMVs.xlsx
  │   │   └── ...
  │   └── images/
  │       ├── Watercrafts/
  │       ├── CMVs/
  │       └── ...
  │   └── json-files/
  │       └── summary_20251220.json #timestamp in filename
```

## Notes

- The scraper filters out ad boxes automatically
- Rate limiting is implemented (0.5s between listing details, 1-2s between pages)
- Each subcategory generates its own Excel file with the subcategory name
- Data is partitioned by date in S3
- Supports both English and Arabic attribute names
