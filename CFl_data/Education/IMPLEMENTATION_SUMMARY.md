# Education Scraper - Implementation Summary

## Key Differences from Wanted Cars

### 1. **Category Structure**
- **Wanted Cars**: Uses `catChilds` (3 fixed subcategories)
- **Education**: Uses `verticalSubcats` with dynamic handling of both:
  - **Case 1**: Direct listings categories (no children)
  - **Case 2**: Categories with `catChilds` that have their own listings

### 2. **Excel File Organization**
- **Wanted Cars**: Single Excel file with one sheet per subcategory
- **Education**: One Excel file per vertical subcategory with:
  - **Info sheet**: Summary for the category
  - **Listing sheets**: One sheet per child category (if children exist) OR one "Listings" sheet (if direct)

### 3. **URL Structure**
- **Wanted Cars**: `https://www.q84sale.com/ar/automotive/wanted-cars/{slug}/{page}`
- **Education**: 
  - Direct: `https://www.q84sale.com/ar/education/{slug}/{page}`
  - Children: `https://www.q84sale.com/ar/education/{parent_slug}/{child_slug}/{page}`

### 4. **Data Flow**

```
WANTED CARS FLOW:
  Main page → catChilds → Get listings per child → Save to Excel with multiple sheets

EDUCATION FLOW:
  Main page → verticalSubcats → For each:
    → Check for catChilds
    → If found (Case 2): Get listings per child → One Excel file with sheets per child
    → If not found (Case 1): Get direct listings → One Excel file with single sheet
```

### 5. **Excel File Examples**

#### Case 1 (Direct Listings): `school-supplies.xlsx`
```
Sheets:
  - Info: Project, Subcategory, Type=Direct Listings, Total Listings, Pages, Date
  - Listings: id, title, slug, price, ... (all listing fields)
```

#### Case 2 (With Children): `languages.xlsx`
```
Sheets:
  - Info: Project, Subcategory, Type=Has Child Categories, Child Count, Total Listings, Date
  - تدريس لغة عربية: arabic-teaching listings
  - تدريس لغة انجليزية: english-teaching listings
  - تدريس لغة فرنسية: french-teaching listings
  - (and any other child categories)
```

### 6. **S3 Partitioning**
Both use the same partitioning structure but different prefixes:
- **Wanted Cars**: `4sale-data/wanted-cars/year=YYYY/month=MM/day=DD/`
- **Education**: `4sale-data/education/year=YYYY/month=MM/day=DD/`

### 7. **JSON Summary**
- **Wanted Cars**: Lists subcategories with total listings count
- **Education**: Lists subcategories with:
  - `has_children` flag
  - Child category details (if any)
  - Listings count for each child

## Code Reuse

The following components are reused (with minimal adaptation):
- ✅ BeautifulSoup JSON extraction method: `get_page_json_data()`
- ✅ S3 operations: `upload_file()`, `upload_image()`, `generate_s3_url()`
- ✅ Image handling: `download_image()`, batch image processing
- ✅ Excel creation with openpyxl
- ✅ Rate limiting strategy
- ✅ Async/await pattern
- ✅ Logging structure

## Main Implementation Differences

### json_scraper.py
```
- get_vertical_subcategories() → NEW (extracts verticalSubcats instead of catChilds)
- get_child_categories() → NEW (checks for catChilds per category)
- get_listings() → ADAPTED (handles both direct and child category slugs)
```

### main.py
```
- scrape_child_category() → NEW (scrapes individual child category)
- scrape_subcategory() → ADAPTED (checks for children, routes to appropriate handler)
- save_all_to_s3() → ADAPTED (creates one file per subcategory instead of one file total)
  - Intelligently creates sheets based on case (direct vs children)
  - Generates case-specific summary info
```

### s3_helper.py
```
- Partition prefix changed: wanted-cars → education
- No other changes needed (fully compatible)
```

## Execution Flow

1. Discover 7 vertical subcategories from main page
2. For each subcategory:
   - Check if it has child categories
   - Route to appropriate scraper:
     - **Case 1**: Scrape direct listings → Create single-sheet Excel
     - **Case 2**: Scrape each child category → Create multi-sheet Excel
3. Upload Excel files to S3 with date-based partitioning
4. Create JSON summary with category metadata

## Testing Checklist

✅ JSON extraction from __NEXT_DATA__ script tag
✅ verticalSubcats parsing
✅ catChilds detection (Case 2)
✅ Direct listings scraping (Case 1)
✅ Child category listings scraping (Case 2)
✅ Image downloading and S3 upload
✅ Excel file generation with correct sheet structure
✅ Info sheet with appropriate summary for both cases
✅ JSON summary creation
✅ S3 upload with proper partitioning
✅ Rate limiting between requests
✅ Error handling and logging

## Notes

- The scraper handles Arabic text correctly in both sheet names and data
- Excel sheet names are automatically sanitized (max 31 characters)
- Case detection is automatic based on presence of catChilds
- Pagination is handled uniformly for both direct and child categories
- All timestamps are preserved for proper chronological ordering
