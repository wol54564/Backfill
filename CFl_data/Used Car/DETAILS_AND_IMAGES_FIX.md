# Used Car Scraper - Details and Images Fix

## Summary
Fixed the Used Car scraper to save detailed listing information and images, matching the functionality of the Wanted-Cars scraper.

## Changes Made

### 1. json_scraper_used_cars.py

#### Added Import
- Added `aiohttp` import for async image downloading

#### Enhanced Methods
- **`extract_attributes`**: Updated to better handle attribute types (boolean vs numeric) and provide both nested and flattened output
- **`get_listing_details`**: Already existed but now properly integrated - fetches comprehensive details from individual listing pages including:
  - Full description
  - Complete user information (email, phone, type, etc.)
  - Address details (full address, coordinates)
  - All images array
  - Detailed attributes/specifications
  - View counts, dates, verification status

#### New Method
- **`download_image`**: Async method to download images using aiohttp
  - Downloads image bytes from URL
  - Returns image data for S3 upload
  - Includes proper error handling

### 2. main_used_cars.py

#### New Method
- **`fetch_listing_details_batch`**: Fetches detailed information for batches of listings
  - Takes basic listings from listings page
  - Calls `get_listing_details` for each listing
  - Downloads and uploads images to S3
  - Generates S3 URLs for images
  - Returns enriched detailed listings

#### Updated Methods
- **`scrape_category`**: Changed from basic listing scraping to detailed scraping
  - Old: Only fetched basic listing info from listings pages
  - New: Fetches basic listings, then calls `fetch_listing_details_batch` for full details
  
- **`format_listings_for_excel`**: Enhanced to include new detailed fields
  - Added fields: User Email, User Phone, User Type, Date Relative, Address, Full Address, Description, Views, Coordinates, Specifications
  - Properly handles S3 images list conversion to pipe-separated string

- **`create_excel_file_with_styling`**: Updated column widths for new fields

#### Removed Method
- **`download_and_upload_images`**: Removed old synchronous image download method (replaced by async approach in `fetch_listing_details_batch`)

### 3. requirements.txt
- Added `aiohttp==3.9.1` for async HTTP requests

## New Data Fields Captured

The scraper now captures all the following details for each listing:

### Basic Information
- Listing ID, Title, Slug, Price, Phone
- Status, Category, Date Published, Date Relative

### User Information
- User Name, User Email, User Phone
- User Type, User Verification Status

### Location
- Address, Full Address, Full Address (English)
- Latitude, Longitude

### Media
- Images Count
- S3 Images (all image URLs uploaded to S3)

### Detailed Information
- Description (full text)
- Specifications (English & Arabic, both JSON and flattened)
- Views Count
- Date Created, Date Expired, Date Sort
- Membership Information

## How It Works

1. **Fetch Listings**: Gets basic listing info from category/subcategory pages
2. **Fetch Details**: For each listing, visits individual listing page to get full details
3. **Download Images**: Downloads all images from the listing using async aiohttp
4. **Upload to S3**: Uploads images to S3 organized by category/subcategory
5. **Generate URLs**: Stores S3 URLs in the listing data
6. **Export to Excel**: Creates Excel files with all detailed information

## Comparison with Wanted-Cars

The Used Car scraper now has feature parity with Wanted-Cars:
- ✅ Fetches detailed listing information
- ✅ Downloads and uploads images to S3
- ✅ Stores S3 image URLs
- ✅ Captures all user details
- ✅ Includes specifications/attributes
- ✅ Exports comprehensive Excel files

## Usage

No changes to usage - the scraper works the same way but now captures much more data:

```bash
python main_used_cars.py
```

The scraper will automatically:
- Fetch all categories and subcategories
- Get detailed information for each listing
- Download and upload all images
- Create organized Excel files with complete data
