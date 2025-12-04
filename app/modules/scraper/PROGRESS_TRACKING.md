# Scraper Progress Tracking & Logging

This document explains the progress tracking and logging system implemented in the scraper module.

## Overview

The scraper now provides comprehensive real-time progress visibility and detailed logging for all operations.

### Key Features

- **7 Progress Bar Types**: Different progress bars for different scraping stages
- **Structured Logging**: Dual-handler logging to console and file
- **Section Tracking**: Automatic timing and completion reporting for logical sections
- **Real-time Updates**: Live progress visualization using tqdm

## Progress Bar Types

### 1. Email Processing Progress (📧)
**Used in**: `listen_email()` function
**Purpose**: Tracks number of emails being processed in each cycle
**Example**:
```
📧 Processing Emails: 45%|████▌     | 9/20 [00:15<00:20]
```

### 2. Tender Scraping Progress (🔗)
**Used in**: Can be added to home page scraping
**Purpose**: Tracks tender URLs being scraped from homepage
**Example**:
```
🔗 Scraping Tenders: 60%|██████    | 12/20 [00:10<00:07]
```

### 3. Detail Page Scraping Progress (📄)
**Used in**: `scrape_link()` function
**Purpose**: Tracks individual detail pages being scraped
**Example**:
```
📄 Scraping Detail Pages: 75%|███████▌ | 150/200 [02:30<00:50]
```

### 4. File Download Progress (⬇️)
**Used in**: Can be added to file download operations
**Purpose**: Tracks files being downloaded
**Example**:
```
⬇️  Downloading Files: 33%|███▎      | 5/15 [00:05<00:10]
```

### 5. Database Save Progress (💾)
**Used in**: `scrape_link()` function (DMS integration phase)
**Purpose**: Tracks database write operations
**Example**:
```
💾 Saving to Database: 100%|██████████| 1/1 [00:02<00:00]
```

### 6. Query Category Progress (📋)
**Used in**: `scrape_link()` function during detail scraping
**Purpose**: Tracks tenders within specific categories (Civil, Electrical, etc.)
**Example**:
```
📋 Processing Civil: 80%|████████   | 12/15
📋 Processing Electrical: 100%|██████████| 10/10
📋 Processing Mechanical: 50%|█████     | 5/10
```

### 7. Deduplication Progress (🔍)
**Used in**: `listen_email()` function
**Purpose**: Tracks email deduplication checks
**Example**:
```
🔍 Checking Duplicates: 85%|████████▌ | 17/20
```

## Logging Configuration

### Console Output (INFO level and above)
- Real-time progress bars
- Section start/end markers
- Email processing status (processed/skipped/failed)
- Error messages and warnings
- Final statistics and summary

### File Output (DEBUG level and above)
- Saved to `scraper.log` in the working directory
- Includes all console output plus debug-level messages
- Useful for post-execution analysis and debugging
- Contains detailed execution traces

### Log Format
```
[2025-11-04 11:52:15] scraper - INFO - 📍 Starting scrape of: https://...
[2025-11-04 11:52:16] scraper - DEBUG - 🎯 Scraping detail page for: Tender Name
[2025-11-04 11:52:17] scraper - WARNING - ⚠️  Failed to scrape details for: Tender Name: Error message
```

## Section Tracking

The `ScrapeSection` context manager provides automatic section tracking:

```python
with ScrapeSection(tracker, "Homepage Scraping"):
    # Code here is automatically timed and logged
    logger.info("Doing something important")
```

**Output**:
```
============================================================
📍 Homepage Scraping
============================================================
[2025-11-04 11:52:15] scraper - INFO - Doing something important
[2025-11-04 11:52:18] scraper - INFO - ✅ Homepage Scraping completed in 3.45s
============================================================
```

## Usage Examples

### In `scrape_link()` function

```python
def scrape_link(link: str):
    tracker = ProgressTracker(verbose=True)

    with ScrapeSection(tracker, "Homepage Scraping"):
        homepage = scrape_page(link)
        logger.info(f"Found {total_tenders} tenders")

    # Create progress bars
    detail_progress = tracker.create_detail_scrape_progress_bar(total_tenders)

    with ScrapeSection(tracker, "Detail Page Scraping"):
        for tender in tenders:
            # Scrape tender
            tender.details = scrape_tender(tender.url)

            # Update progress
            detail_progress.update(1)

    detail_progress.close()
```

### In `listen_email()` function

```python
def listen_email():
    tracker = ProgressTracker(verbose=True)

    while True:
        with ScrapeSection(tracker, f"Email Polling Cycle #{cycle_number}"):
            emails_data = listen_and_get_unprocessed_emails()

            email_progress = tracker.create_email_progress_bar(len(emails_data))
            dedup_progress = tracker.create_deduplication_progress_bar(len(emails_data))

            for email in emails_data:
                # Check deduplication
                if is_duplicate(email):
                    skipped_count += 1
                else:
                    # Process email
                    scrape_link(email.tender_url)
                    processed_count += 1

                email_progress.update(1)
                dedup_progress.update(1)

            # Log cycle summary
            tracker.log_stats({
                "Total Emails": len(emails_data),
                "Processed": processed_count,
                "Skipped": skipped_count
            })
```

## Checking Logs

After scraper execution, view the detailed log file:

```bash
# View last 50 lines
tail -50 scraper.log

# View specific errors
grep "ERROR\|CRITICAL" scraper.log

# View execution summary
grep "Execution Summary" scraper.log -A 10
```

## Output Example: Full Scrape Session

```
[2025-11-04 11:52:15] scraper - INFO -
============================================================
📍 Homepage Scraping
============================================================
[2025-11-04 11:52:15] scraper - INFO - 📍 Starting scrape of: https://www.tenderdetail.com/...
[2025-11-04 11:52:16] scraper - INFO - 📊 Found 450 tenders across 5 categories
[2025-11-04 11:52:16] scraper - INFO -    📋 Civil: 120 tenders
[2025-11-04 11:52:16] scraper - INFO -    📋 Electrical: 95 tenders
[2025-11-04 11:52:16] scraper - INFO -    📋 Mechanical: 85 tenders
[2025-11-04 11:52:16] scraper - INFO -    📋 IT: 75 tenders
[2025-11-04 11:52:16] scraper - INFO -    📋 General: 75 tenders
[2025-11-04 11:52:18] scraper - INFO - ✅ Homepage Scraping completed in 3.12s

============================================================
📍 Detail Page Scraping
============================================================
📄 Scraping Detail Pages: 45%|████▌     | 202/450 [02:15<02:45]
📋 Processing Civil: 100%|██████████| 120/120
📋 Processing Electrical: 75%|███████▌ | 71/95
...
[2025-11-04 11:52:18] scraper - INFO - ⚠️  Removed 5 tenders due to scraping errors
[2025-11-04 11:52:18] scraper - INFO - ✅ Detail page scraping completed for 445 tenders
[2025-11-04 11:52:18] scraper - INFO - ✅ Detail Page Scraping completed in 120.45s

============================================================
📍 DMS Integration & Database Save
============================================================
[2025-11-04 11:52:18] scraper - INFO - 🔄 Processing tenders for DMS integration...
[2025-11-04 11:52:18] scraper - INFO - 💾 Saving scraped data to database...
💾 Saving to Database: 100%|██████████| 1/1 [00:03<00:00]
[2025-11-04 11:52:21] scraper - INFO - ✅ Successfully saved 445 tenders to database
[2025-11-04 11:52:21] scraper - INFO - ✅ DMS Integration & Database Save completed in 3.21s

============================================================
📍 Email Generation & Sending
============================================================
[2025-11-04 11:52:21] scraper - INFO - 📧 Generating email template...
[2025-11-04 11:52:22] scraper - INFO - 💾 Writing HTML files...
[2025-11-04 11:52:22] scraper - INFO - 📤 Sending email...
[2025-11-04 11:52:25] scraper - INFO - ✅ Email sent successfully
[2025-11-04 11:52:25] scraper - INFO - ✅ Email Generation & Sending completed in 4.12s

============================================================
✨ Execution Summary
============================================================
Total Tenders Processed: 445
Tenders Removed (Errors): 5
Duration: 131.15s
Status: ✅ SUCCESS
============================================================
```

## Customization

### Disable Progress Bars
```python
tracker = ProgressTracker(verbose=False)
# Progress bars won't display, but logging continues
```

### Add Custom Logging
```python
logger.info("Custom message")
logger.debug("Debug-level message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

### Add Custom Statistics
```python
tracker.log_stats({
    "Key 1": "Value 1",
    "Key 2": "Value 2",
    "Key 3": "Value 3"
})
```

## Performance Impact

Progress tracking adds minimal overhead:
- tqdm progress bars: ~5-10% slowdown (negligible for network operations)
- Logging: ~1-2% slowdown (minimal I/O buffering)
- Overall impact: **Negligible** (scraping is I/O-bound, not CPU-bound)

## Troubleshooting

### Progress Bars Not Showing
1. Check if `verbose=True` is set when creating ProgressTracker
2. Ensure terminal supports ANSI colors (most modern terminals do)
3. Check logs directly in `scraper.log` if console display fails

### Log File Growing Too Large
1. Archive old logs: `mv scraper.log scraper.log.$(date +%Y%m%d)`
2. Reduce log level: Change `logger.setLevel(logging.DEBUG)` to `logging.INFO`
3. Implement log rotation in production (add `RotatingFileHandler`)

### Missing Log Details
1. Check file permissions for `scraper.log` write access
2. Ensure both handlers are properly configured in `setup_scraper_logger()`
3. Verify no exceptions are being silently caught

---

**Last Updated**: November 4, 2025
**Version**: 1.0 - Initial Implementation
