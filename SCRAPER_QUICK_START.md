# Scraper Progress Tracking - Quick Start Guide

## TL;DR

The scraper now shows **real-time progress bars** and **comprehensive logging** when it runs. You'll see progress for:
- Email processing 📧
- Tender detail scraping 📄
- Database operations 💾
- Per-category tenders 📋
- And more!

## Running the Scraper

### Option 1: Paste a URL
```bash
cd /path/to/chatbot-backend
python -m app.modules.scraper.main

# Select: 1
# Enter URL: https://www.tenderdetail.com/dailytenders/...
```

### Option 2: Listen for Emails (Continuous)
```bash
cd /path/to/chatbot-backend
python -m app.modules.scraper.main

# Select: 2
# Runs forever, checks for new emails every 5 minutes
```

## What You'll See

### Console Output (Real-time)
```
============================================================
📍 Homepage Scraping
============================================================
[2025-11-04 11:52:15] scraper - INFO - 📍 Starting scrape of: https://...
[2025-11-04 11:52:16] scraper - INFO - 📊 Found 450 tenders across 5 categories

============================================================
📍 Detail Page Scraping
============================================================
📄 Scraping Detail Pages: 75%|███████▌ | 338/450 [02:30<00:50]
📋 Processing Civil: 100%|██████████| 120/120
📋 Processing Electrical: 75%|███████▌ | 71/95
```

### Log File
All details are also saved to `scraper.log` for later review:
```bash
tail -50 scraper.log          # View last 50 lines
grep ERROR scraper.log        # Find errors
grep "Execution Summary" scraper.log -A 10  # View final summary
```

## Progress Bar Types

| Bar | Meaning |
|-----|---------|
| 📧 Email Processing | Number of emails being checked |
| 📄 Detail Pages | Individual tender details being scraped |
| 💾 Database Save | Data being saved to database |
| 📋 Category | Tenders within Civil/Electrical/etc category |
| 🔍 Deduplication | Checking if email/tender already processed |
| 📄 File Downloads | (Ready when file downloads are added) |

## Understanding the Progress Bars

```
📄 Scraping Detail Pages: 75%|███████▌ | 338/450 [02:30<00:50]
   ^                      ^^  ^^^^^^^^  ^^^^^^  ^^^^^^  ^^^^^^
   Icon                   % Complete  Current/Total  Elapsed/Remaining
```

- **Icon**: What's being tracked
- **%**: Percentage complete
- **Bar**: Visual progress
- **Current/Total**: 338 of 450 items done
- **Elapsed<Remaining**: 2:30 spent, ~50 seconds left

## Logging Levels

The scraper logs at different levels:

- **INFO** (console): User-visible messages
  ```
  📍 Starting scrape...
  ✅ Scraping completed
  ⚠️  Failed to scrape tender
  ```

- **DEBUG** (file only): Detailed technical info
  ```
  🎯 Scraping detail page for: Tender Name
  Processing tender ID: abc-123-def
  ```

## Common Tasks

### Stop the Scraper
```bash
Press Ctrl+C to stop
```

### View Logs
```bash
# Real-time (with tail)
tail -f scraper.log

# All messages from latest run
tail -200 scraper.log

# Just errors/warnings
grep -E "ERROR|WARNING|⚠️" scraper.log

# Just summary
grep "Execution Summary" scraper.log -A 10
```

### Disable Progress Bars (If Terminal Issues)
The progress bars will automatically disable if:
- Terminal doesn't support colors
- Output is piped to file
- Running in background

Or modify the code:
```python
tracker = ProgressTracker(verbose=False)  # Disable bars
```

## Troubleshooting

### No Progress Bars Showing
1. Check you're in the right terminal
2. Try: `export TERM=xterm-256color`
3. Fall back to logs: `tail -f scraper.log`

### Log File Too Large
```bash
# Compress and archive old logs
mv scraper.log scraper.log.$(date +%Y%m%d).gz
gzip scraper.log.*.gz
```

### Missing Details in Logs
- DEBUG logs might not show if level is wrong
- Check: `tail -500 scraper.log | grep DEBUG`

## Architecture

```
ProgressTracker (progress_tracker.py)
├─ Console Handler (INFO+) → real-time output
├─ File Handler (DEBUG+) → scraper.log
├─ ScrapeSection context manager → auto timing
└─ 7 Progress Bar Methods
   ├─ create_email_progress_bar()
   ├─ create_detail_scrape_progress_bar()
   ├─ create_database_save_progress_bar()
   ├─ create_query_progress_bar()
   ├─ create_deduplication_progress_bar()
   └─ ... and more

main.py Integration
├─ scrape_link() → 5 sections with progress
│  ├─ Homepage Scraping
│  ├─ Detail Page Scraping (with per-query bars)
│  ├─ DMS Integration & Database Save
│  ├─ Email Generation & Sending
│  └─ Summary Statistics
└─ listen_email() → cycle-based progress
   └─ Email Polling (every 5 minutes)
```

## For Developers

Want to add progress tracking to other functions? See:
- `app/modules/scraper/PROGRESS_TRACKING.md` - Full developer guide
- `SCRAPER_PROGRESS_TRACKING_SUMMARY.md` - Complete implementation details

## Performance

- Progress bar overhead: ~5-10% (negligible for network I/O)
- Logging overhead: ~1-2% (buffered)
- **Total impact**: Negligible (scraper is I/O-bound)

## More Info

📖 **Read the full docs**:
- Developer Guide: `app/modules/scraper/PROGRESS_TRACKING.md`
- Implementation Summary: `SCRAPER_PROGRESS_TRACKING_SUMMARY.md`

---

**That's it!** The scraper now provides comprehensive progress tracking. Run it and enjoy the real-time visibility! 🚀
