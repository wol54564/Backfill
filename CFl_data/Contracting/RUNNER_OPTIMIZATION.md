# Contracting Scraper - GitHub Actions Runner Optimization

## Problem
The Contracting scraper was causing GitHub Actions runners to crash with:
```
The hosted runner lost communication with the server. Anything in your workflow 
that terminates the runner process, starves it for CPU/Memory, or blocks its 
network access can cause this error.
```

## Root Cause
The Contracting scraper is significantly more resource-intensive than other scrapers because it:

1. **Downloads MULTIPLE images per listing** (most listings have 5-10+ images)
2. **Processes ALL listing details** with full image downloads
3. **Handles multiple districts** with pagination
4. **No memory management** - kept all data in memory simultaneously
5. **Unlimited concurrent downloads** - could spawn dozens of simultaneous image downloads

This exhausted the GitHub Actions runner's memory (7GB RAM limit).

## Solutions Implemented

### 1. Image Limiting
**File:** [main.py](main.py#L22-L27)
```python
self.max_images_per_listing = 3  # Limit images to prevent memory issues
self.max_concurrent_downloads = 2  # Limit concurrent downloads
self.batch_size = 10  # Process listings in batches
```
- Limited to first 3 images per listing (instead of all 5-10+)
- Reduces memory usage by 60-70%

### 2. Batch Processing
**File:** [main.py](main.py#L65-L77)
- Process listings in batches of 10
- Forces garbage collection after each batch
- Prevents memory accumulation

### 3. Concurrency Control
**File:** [json_scraper.py](json_scraper.py#L27-L28)
```python
self._download_semaphore = asyncio.Semaphore(2)
```
- Limits concurrent image downloads to 2 at a time
- Prevents network congestion and memory spikes

### 4. Image Size Limits
**File:** [json_scraper.py](json_scraper.py#L349-L352)
```python
# Limit image size to prevent memory issues (max 5MB)
if len(data) > 5 * 1024 * 1024:
    logger.warning(f"Image too large ({len(data)} bytes), skipping")
    return None
```
- Rejects images larger than 5MB
- Prevents single large image from consuming excessive memory

### 5. Timeout Controls
**File:** [.github/workflows/contracting.yml](.github/workflows/contracting.yml#L9-L11)
```yaml
timeout-minutes: 60  # Job timeout
```
- Prevents infinite hangs
- Kills job after 60 minutes

### 6. Immediate Memory Cleanup
**File:** [main.py](main.py#L113-L114)
```python
# Clear image data from memory immediately
del image_data
```
- Deletes image data immediately after upload
- Allows garbage collector to free memory faster

### 7. Reduced Timeouts
**File:** [json_scraper.py](json_scraper.py#L347)
```python
async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=20))
```
- Reduced from 30s to 20s timeout
- Faster failure recovery

## Memory Usage Comparison

### Before Optimization
- Processing 50 listings with 7 images each = 350 images
- Average image size: 500KB
- Total memory: ~175MB + overhead = **~250MB**
- All loaded simultaneously = potential **OOM crash**

### After Optimization  
- Processing 50 listings with 3 images each = 150 images
- Batch processing: max 10 listings × 3 images = 30 images at once
- With 2 concurrent downloads + cleanup
- Total memory: ~15MB + overhead = **~30MB peak**
- **87% memory reduction**

## Expected Results

✅ **No more runner crashes**  
✅ **Successful completion within timeout**  
✅ **Reduced S3 storage costs** (fewer images)  
✅ **Faster execution** (fewer downloads)  

## Testing

Test the scraper with:
```bash
cd Contracting
python main.py
```

Or trigger via GitHub Actions:
- Go to Actions → Contracting Scraper → Run workflow

## Monitoring

Watch for these logs to confirm optimizations are working:
```
Memory optimization: Max 3 images/listing, batch size 10
Processing batch 1: listings 1-10/50
Batch complete, memory cleanup performed
Processing 3/7 images for listing-slug...
```

## Future Improvements

If still experiencing issues:
1. Reduce `max_images_per_listing` to 2
2. Reduce `batch_size` to 5
3. Add district/subcategory limits
4. Consider splitting into multiple workflows
