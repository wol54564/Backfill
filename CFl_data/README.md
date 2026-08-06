# CFl_data — Q84Sale Scraping Suite

A collection of category-specific web scrapers that collect listings from [Q84Sale](https://www.q84sale.com) and [Q84Sale Directory](https://directory.q84sale.com), then upload structured Excel and JSON output to **Cloudflare R2** with date-based partitioning.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Repository Structure](#repository-structure)
- [Category Scrapers](#category-scrapers)
- [Shared Utilities](#shared-utilities)
- [Environment Variables](#environment-variables)
- [Installation](#installation)
- [Running a Scraper](#running-a-scraper)
- [Backfill Runner](#backfill-runner)
- [R2 Output Layout](#r2-output-layout)
- [Testing R2 Connectivity](#testing-r2-connectivity)

---

## Architecture Overview

Every category scraper follows the same pattern:

```
json_scraper.py   ←  fetches & parses raw listing pages (BeautifulSoup + __NEXT_DATA__ JSON)
main.py           ←  orchestrates subcategory iteration, Excel generation, R2 upload
s3_helper.py      ←  thin boto3 wrapper for Cloudflare R2
```

### SmartSession (scraper_utils.py)

All HTTP requests go through `SmartSession`, a drop-in replacement for `requests.Session` that:

- Routes traffic through **DataImpulse residential proxies** (geo-targeted via env vars)
- Uses **curl_cffi TLS impersonation** (`chrome124`, `chrome120`, `chrome131`, `safari18_0`, `chrome116`) to bypass bot-detection
- **Auto-retries** with a different impersonation profile on HTTP 403 or connection errors
- **Caches** responses in-memory so duplicate fetches cost zero extra requests
- Applies **randomised delays** between requests (1.5–3.5 s between pages, 3–7 s between subcategories)

### Data flow

```
Q84Sale → SmartSession (proxy + TLS) → BeautifulSoup / JSON → pandas DataFrame
                                                                    ↓
                                             Excel file (.xlsx) + JSON summary
                                                                    ↓
                                                    Cloudflare R2  (date partition)
```

---

## Repository Structure

```
CFl_data/
├── scraper_utils.py            # Shared SmartSession, proxy config, random delays
├── test_r2_connection.py       # Diagnostic script — validates R2 credentials & access
├── requirements.txt            # Shared Python dependencies
│
├── Animals/
├── Automotive-Cars-and-Trucks/
├── bikes/
├── Camping/
├── Commercials/
├── Contracting/
├── Dalil/
├── Education/
├── Electronics/
├── Fashion-and-Family/
├── Furniture/
├── gifts/
├── Jobs/
├── New Car/
├── Others/
├── Property/
├── Rest-Automotive-Part1/
├── Rest-Automotive-Part2/
├── Rest-Automotive-Part3/
├── Services/
├── Sport/
├── Used Car/
├── Wanted-Cars/
│
└── backfill-c2/                # Backfill runners for historical date re-scraping
    ├── Automotive-Cars-and-Trucks/main.py
    ├── Commercials/main.py
    ├── Electronics/main.py
    ├── Furniture/main.py
    ├── Rest-Automotive-Part3/main.py
    └── Wanted-Cars/main.py
```

---

## Category Scrapers

| Folder | Source URL | Subcategories / Notes |
|---|---|---|
| `Animals` | `/ar/animals` | All animal subcategories (pets, livestock, etc.) |
| `Automotive-Cars-and-Trucks` | `/ar/automotive` | Cars, trucks, and full automotive hierarchy |
| `bikes` | `/ar/automotive/bikes` | Motorcycles and bicycles |
| `Camping` | `/ar/camping` | Camping & outdoor equipment |
| `Commercials` | `/ar/commercials` | Commercial & industrial listings |
| `Contracting` | `/ar/contracting` | Contracting services and materials |
| `Dalil` | `directory.q84sale.com/ar` | Business directory listings |
| `Education` | `/ar/education` | Books, courses, tutoring |
| `Electronics` | `/ar/electronics` | All electronics subcategories |
| `Fashion-and-Family` | `/ar/fashion-and-family` | Clothing, accessories, baby items |
| `Furniture` | `/ar/furniture` | Home & office furniture |
| `gifts` | `/ar/gifts` | Gifts and special occasion items |
| `Jobs` | `/ar/jobs` | Job listings by sector |
| `New Car` | `/ar/automotive` | New car listings with detailed specs (`car_scraper.py` + `details_scraping.py`) |
| `Others` | `/ar/others` | Currencies/stamps, books, wholesale, stickers, lost-and-found, miscellaneous |
| `Property` | `/ar/property` | Real estate — residential, commercial, land |
| `Rest-Automotive-Part1` | `/ar/automotive` | Remaining automotive subcategories — Part 1 |
| `Rest-Automotive-Part2` | `/ar/automotive` + `/ar` automotive-services | Remaining automotive subcategories — Part 2 |
| `Rest-Automotive-Part3` | `/ar` (businesses) | Business automotive categories |
| `Services` | `/ar/services` | All service listings |
| `Sport` | `/ar/sport` | Sports equipment and activities |
| `Used Car` | `/ar/automotive/used-cars` | Used cars, organised by make → model (one Excel per make) |
| `Wanted-Cars` | `/ar/automotive/wanted-cars` | Wanted car ads |

### Files in each category folder

| File | Purpose |
|---|---|
| `json_scraper.py` | Fetches listing pages and parses `__NEXT_DATA__` JSON or HTML; returns structured dicts |
| `main.py` | Orchestrator — iterates subcategories, builds DataFrames, creates Excel files, uploads to R2 |
| `s3_helper.py` / `s3_uploader.py` | Cloudflare R2 upload wrapper (boto3 with R2 endpoint) |
| `requirements.txt` | Per-category dependencies (most mirror the root `requirements.txt`) |
| `README.md` | Category-specific documentation |

> **New Car** and **Property** differ slightly: they use a `details_scraping.py` module that follows each listing URL to scrape full detail pages before upload.

---

## Shared Utilities

### `scraper_utils.py`

Provides everything HTTP-related that all scrapers share:

| Symbol | Description |
|---|---|
| `SmartSession` | Main HTTP client — proxy + TLS impersonation + retry + cache |
| `create_session()` | Factory that returns a configured `SmartSession` |
| `get_random_headers()` | Randomised browser-like request headers |
| `random_delay(min, max)` | Synchronous anti-detection sleep (default 1.5–3.5 s) |
| `async_random_delay(min, max)` | Async version of the delay |
| `configure_session_proxy(session)` | Applies DataImpulse proxy to a plain `requests.Session` |
| `PROXIES` | Module-level proxy dict built from env vars at import time |

### `test_r2_connection.py`

Validates the full R2 setup before running any scraper:

```bash
CF_R2_ACCESS_KEY_ID=... CF_R2_SECRET_ACCESS_KEY=... \
CF_R2_ENDPOINT_URL=... CF_R2_BUCKET_NAME=... \
python CFl_data/test_r2_connection.py
```

Runs seven checks: env vars, client init, HeadBucket, PutObject, GetObject, ListObjectsV2, DeleteObject. Exits `0` on full success.

---

## Environment Variables

### Cloudflare R2 (required by all scrapers)

| Variable | Description |
|---|---|
| `CF_R2_ACCESS_KEY_ID` | R2 API token — Access Key ID |
| `CF_R2_SECRET_ACCESS_KEY` | R2 API token — Secret Access Key |
| `CF_R2_ENDPOINT_URL` | R2 endpoint, e.g. `https://<account-id>.r2.cloudflarestorage.com` |
| `CF_R2_BUCKET_NAME` | Target bucket name (default: `data-collection-dl`) |

### DataImpulse Proxy (optional — scrapers work without it but use your real IP)

| Variable | Description |
|---|---|
| `DATAIMPULSE_USER` | Full username **including** geo suffix, e.g. `user123__cr.kw` |
| `DATAIMPULSE_PASS` | Proxy password |
| `DATAIMPULSE_HOST` | Proxy host (default: `gw.dataimpulse.com`) |
| `DATAIMPULSE_PORT` | Proxy port (default: `823`) |

Supported geo suffixes: `__cr.kw` (Kuwait), `__cr.sa` (Saudi Arabia), `__cr.eg` (Egypt).

---

## Installation

```bash
# From the repo root
pip install -r CFl_data/requirements.txt
```

Or install inside a specific category folder if it has its own `requirements.txt`:

```bash
pip install -r CFl_data/Electronics/requirements.txt
```

**Python 3.9+** is required.

---

## Running a Scraper

Each `main.py` is self-contained. Run from its own folder so relative imports resolve correctly:

```bash
cd CFl_data/Electronics

CF_R2_ACCESS_KEY_ID=<key> \
CF_R2_SECRET_ACCESS_KEY=<secret> \
CF_R2_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com \
CF_R2_BUCKET_NAME=data-collection-dl \
DATAIMPULSE_USER=user123__cr.kw \
DATAIMPULSE_PASS=<pass> \
python main.py
```

By default every scraper:
1. Targets **yesterday's** listings (filters by date)
2. Stores output under today's date partition in R2
3. Scrapes **all available pages** per subcategory (no page limit)

Some scrapers accept an optional `MAX_PAGES` env var:

```bash
MAX_PAGES=3 python main.py   # limit pages per subcategory (useful for testing)
```

---

## Backfill Runner

The `backfill-c2/` folder contains thin wrapper scripts that re-run a category scraper as if it were a specific historical date. Use this to fill in missed or failed daily runs.

```bash
cd CFl_data/backfill-c2/Electronics

TARGET_DATE=2026-05-20 \
CF_R2_ACCESS_KEY_ID=<key> \
CF_R2_SECRET_ACCESS_KEY=<secret> \
CF_R2_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com \
CF_R2_BUCKET_NAME=data-collection-dl \
python main.py
```

- `TARGET_DATE` is the **save date** (the R2 partition date).
- The scraper will fetch listings from `TARGET_DATE - 1 day` (i.e. the actual day the listings appeared).

Available backfill categories: `Automotive-Cars-and-Trucks`, `Commercials`, `Electronics`, `Furniture`, `Rest-Automotive-Part3`, `Wanted-Cars`.

---

## R2 Output Layout

All scrapers follow a consistent date-partitioned layout:

```
R2://<bucket>/
└── 4sale-data/
    └── <category-slug>/
        └── year=YYYY/
            └── month=MM/
                └── day=DD/
                    ├── excel-files/
                    │   ├── <subcategory-1>.xlsx
                    │   ├── <subcategory-2>.xlsx
                    │   └── ...
                    ├── json-files/
                    │   └── summary_YYYYMMDD.json
                    └── images/
                        ├── <subcategory-1>/
                        │   ├── <listing_id>_0.jpg
                        │   └── ...
                        └── ...
```

Each Excel file contains:
- **Info sheet** — run metadata (date, subcategory, listing count, scrape duration)
- **Data sheets** — one sheet per sub-subcategory (or `Main` when there are none), with all listing fields as columns

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `curl_cffi` | ≥ 0.7.0 | TLS impersonation for bot-bypass |
| `boto3` | 1.34.2 | Cloudflare R2 (S3-compatible) uploads |
| `beautifulsoup4` | 4.12.2 | HTML parsing |
| `pandas` | 2.1.3 | DataFrame construction and Excel export |
| `openpyxl` | 3.1.5 | Excel file writing |
| `requests` | 2.31.0 | Fallback HTTP sessions |
| `aiohttp` | 3.9.1 | Async HTTP where used |
| `lxml` | 4.9.3 | Fast HTML/XML parser backend |
| `numpy` | 1.26.4 | Numerical support for pandas |
| `python-dateutil` | 2.8.2 | Date parsing helpers |
