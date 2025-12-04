# Assignment: Fix and Configure Tender Scraping Service

## Overview

The tender scraping service is currently non-functional because the source website (tenderdetails.com) has changed its structure. Your task is to analyze the website changes and reconfigure the scraper to work with the new layout.

## Background

The application scrapes tender data from tenderdetails.com to populate the TenderIQ module. The scraper was working previously but has stopped functioning due to website structure changes.

## Current Scraper Location

The scraping logic is located in:
```
/home/ubuntu/ceigall/backup-22nov/backend/app/modules/scraper/
```

Key files to examine:
- `main.py` - Main scraper orchestration
- `process_tender.py` - Individual tender processing logic
- `www.tenderdetails.com/main.py` - Site-specific scraping logic
- `tenderdetails_v2/main.py` - Alternative scraper version

## Task Requirements

### 1. Website Analysis

**Objective**: Understand the current structure of tenderdetails.com

**Steps**:
1. Visit https://www.tenderdetails.com
2. Inspect the HTML structure using browser DevTools
3. Identify:
   - Tender listing page structure
   - Individual tender detail page structure
   - Pagination mechanism
   - Search/filter parameters
   - Any authentication or rate limiting

**Deliverable**: Document the current website structure including:
- URL patterns
- HTML selectors for tender data
- CSS classes/IDs used
- JavaScript-rendered content (if any)
- API endpoints (if exposed)

### 2. Compare with Existing Scraper

**Objective**: Identify what has changed

**Steps**:
1. Read the existing scraper code
2. Identify the selectors and patterns it's using
3. Compare with current website structure
4. Document specific breaking changes

**Deliverable**: A comparison document showing:
- Old selectors vs new selectors
- Removed fields
- New fields available
- Changed URL patterns

### 3. Update Scraper Configuration

**Objective**: Modify the scraper to work with new structure

**Required Changes**:
1. Update CSS/XPath selectors
2. Modify URL construction logic
3. Update field mapping
4. Handle any new pagination
5. Add error handling for missing fields

**Files to Modify**:
```python
# Main scraping logic
app/modules/scraper/www.tenderdetails.com/main.py
app/modules/scraper/tenderdetails_v2/main.py

# Data models (if field changes needed)
app/modules/scraper/db/schema.py

# Processing logic
app/modules/scraper/process_tender.py
```

### 4. Test the Scraper

**Objective**: Verify the scraper works correctly

**Testing Steps**:

1. **Test Individual Tender Scraping**:
```bash
cd /home/ubuntu/ceigall/backup-22nov/backend
source venv/bin/activate
python -c "
from app.modules.scraper.www.tenderdetails.com.main import scrape_tender
result = scrape_tender('TEST_TENDER_ID')
print(result)
"
```

2. **Test Full Scraping Run**:
```bash
python app/modules/scraper/main.py
```

3. **Verify Data in Database**:
```bash
./venv/bin/python -c "
from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender

db = SessionLocal()
count = db.query(ScrapedTender).count()
print(f'Total scraped tenders: {count}')

latest = db.query(ScrapedTender).order_by(ScrapedTender.created_at.desc()).first()
if latest:
    print(f'Latest tender: {latest.tender_name}')
db.close()
"
```

### 5. Update Documentation

**Objective**: Document changes for future maintenance

**Required Documentation**:
1. Updated scraper configuration guide
2. New selector mappings
3. Known limitations
4. Troubleshooting guide

## Technical Specifications

### Expected Data Fields

The scraper should extract the following fields for each tender:

**Basic Information**:
- `tender_id_str` - Unique tender reference number
- `tender_name` - Tender title/description
- `tendering_authority` - Issuing organization
- `state` - State/location
- `tender_type` - Type of tender (e.g., ICB, NCB)
- `bidding_type` - Single/Two-bid system

**Financial Details**:
- `tender_value` - Contract value
- `emd` - Earnest Money Deposit
- `document_fee` - Cost to purchase tender documents

**Dates**:
- `publish_date` - When tender was published
- `due_date` - Submission deadline
- `tender_opening_date` - Bid opening date

**Documents**:
- `file_url` - URLs to tender documents (PDFs)
- `file_name` - Document filenames
- `file_size` - Document sizes

### Scraper Architecture

```
┌─────────────────────────────────────────┐
│         Main Scraper                    │
│  (app/modules/scraper/main.py)          │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│   Site-Specific Scraper                 │
│  (www.tenderdetails.com/main.py)        │
│  - Fetch tender listings                │
│  - Extract tender details               │
│  - Download documents                   │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│    Process Tender                       │
│  (process_tender.py)                    │
│  - Parse documents                      │
│  - Extract text                         │
│  - Store in database                    │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│         Database                        │
│  - scraped_tenders table                │
│  - scraped_tender_files table           │
└─────────────────────────────────────────┘
```

## Common Issues and Solutions

### Issue 1: Website Requires JavaScript

**Problem**: Content is dynamically loaded via JavaScript

**Solution Options**:
1. Use Selenium or Playwright for browser automation
2. Reverse-engineer the API calls and use them directly
3. Use a headless browser service

### Issue 2: Rate Limiting

**Problem**: Too many requests trigger blocking

**Solution**:
```python
import time
import random

# Add delays between requests
time.sleep(random.uniform(2, 5))

# Use rotating user agents
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...'
}
```

### Issue 3: Changed Authentication

**Problem**: Website now requires login

**Solution**:
1. Add authentication flow to scraper
2. Store and reuse session cookies
3. Implement token refresh logic

### Issue 4: Captcha Protection

**Problem**: Website added captcha verification

**Solution**:
1. Use captcha-solving services (2captcha, Anti-Captcha)
2. Implement manual intervention mode
3. Request API access from website owner

## Implementation Guidelines

### Best Practices

1. **Use Proper Selectors**:
```python
# Good - Specific and stable
soup.select('div.tender-item[data-tender-id]')

# Bad - Too generic, likely to break
soup.select('div > div > div')
```

2. **Error Handling**:
```python
try:
    tender_name = soup.select_one('.tender-title').text.strip()
except AttributeError:
    tender_name = "Unknown"
    logger.warning(f"Could not extract tender name for {tender_id}")
```

3. **Logging**:
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Scraping tender {tender_id}")
logger.error(f"Failed to scrape tender {tender_id}: {error}")
```

4. **Rate Limiting**:
```python
from time import sleep
from datetime import datetime

last_request_time = None

def rate_limited_request(url):
    global last_request_time
    if last_request_time:
        elapsed = (datetime.now() - last_request_time).total_seconds()
        if elapsed < 2:  # Minimum 2 seconds between requests
            sleep(2 - elapsed)

    response = requests.get(url)
    last_request_time = datetime.now()
    return response
```

## Deliverables

### 1. Updated Scraper Code
- Modified Python files with new selectors
- Updated configuration if needed
- New helper functions (if required)

### 2. Documentation
- **SCRAPER_CHANGES.md** - Document all changes made
- **SELECTORS.md** - List of all CSS/XPath selectors used
- **TESTING_GUIDE.md** - How to test the scraper

### 3. Test Results
- Screenshots of successful scraping
- Database dump showing scraped data
- Log files from test runs

### 4. Maintenance Guide
- How to update selectors when website changes again
- Monitoring and alerting setup
- Backup/fallback strategies

## Timeline

- **Day 1-2**: Website analysis and comparison
- **Day 3-4**: Scraper modification
- **Day 5**: Testing and debugging
- **Day 6**: Documentation
- **Day 7**: Final review and deployment

## Success Criteria

The assignment is complete when:

1. ✅ Scraper successfully extracts tender data from current website
2. ✅ All required fields are captured correctly
3. ✅ Documents are downloaded successfully
4. ✅ Data is stored in database without errors
5. ✅ Scraper handles errors gracefully
6. ✅ Rate limiting prevents IP blocking
7. ✅ Code is well-documented
8. ✅ Tests pass successfully

## Resources

### Useful Tools

1. **Browser DevTools** - Inspect website structure
2. **Postman** - Test API endpoints (if any)
3. **Beautiful Soup Docs** - https://www.crummy.com/software/BeautifulSoup/bs4/doc/
4. **Selenium Docs** - https://selenium-python.readthedocs.io/ (if needed)
5. **requests Library** - https://docs.python-requests.org/

### Testing URLs

Test the scraper with these approaches:
- Start with a single known tender ID
- Test pagination with page=1, page=2, etc.
- Test date range filtering
- Test category filtering

### Database Connection

```python
# Connect to database
from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender

db = SessionLocal()

# Query scraped tenders
tenders = db.query(ScrapedTender).limit(10).all()
for tender in tenders:
    print(f"{tender.tender_id_str}: {tender.tender_name}")

db.close()
```

## Support

If you encounter issues:

1. **Check Logs**:
```bash
tail -f /home/ubuntu/ceigall/backup-22nov/backend/scraper.log
```

2. **Enable Debug Mode**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

3. **Test Individual Components**:
```python
# Test HTML parsing
from bs4 import BeautifulSoup
html = """..."""
soup = BeautifulSoup(html, 'html.parser')
print(soup.select('.tender-item'))
```

## Submission

When complete, provide:

1. **Code Changes** - Git diff or modified files
2. **Documentation** - All markdown files
3. **Test Results** - Screenshots and logs
4. **Demo** - Working scraper demonstration

## Questions?

Document any questions or blockers in:
```
ASSIGNMENT_QUESTIONS.md
```

Good luck! 🚀
