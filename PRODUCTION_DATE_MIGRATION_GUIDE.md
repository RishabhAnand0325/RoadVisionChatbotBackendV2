# Production Database Migration: Add tender_release_date Column

**Date**: November 4, 2025
**Impact**: Data grouping will change - tenders grouped by release date instead of scrape date
**Downtime**: None (zero-downtime migration)
**Rollback**: Supported

---

## Overview

This migration adds a `tender_release_date` column to the `scrape_runs` table to group tenders by when they were released (website header date) instead of when we scraped them (run_at timestamp).

### What Changes

**Before**:
- Tenders grouped by `run_at` (when we ran the scraper)
- Date selector showed dates when scraper executed
- Example: Scraped Nov 3 → Grouped as "Nov 3" even if tenders released Nov 2

**After**:
- Tenders grouped by `tender_release_date` (when tenders released from website)
- Date selector shows dates when tenders were released
- Example: Released Nov 2 → Grouped as "Nov 2" regardless of when we scraped

### Timeline

| Phase | Action | Time |
|-------|--------|------|
| **Phase 1** | Deploy code changes | ~5 min |
| **Phase 2** | Run database migration | ~2-5 min (depends on data size) |
| **Phase 3** | Verify migration | ~5 min |
| **Phase 4** | Monitor (optional) | 30 min |

---

## Pre-Migration Checklist

```bash
# 1. Backup database
pg_dump -h <host> -U <user> -d <dbname> > scrape_runs_backup_$(date +%Y%m%d).sql

# 2. Verify current state
SELECT COUNT(*) as total_records,
       MIN(run_at) as earliest_run,
       MAX(run_at) as latest_run
FROM scrape_runs;

# 3. Check free disk space
SELECT pg_size_pretty(pg_database_size('ceigall'));

# 4. Take snapshot of current DB size
```

---

## Phase 1: Deploy Code Changes

### 1.1 Update Application Code

```bash
# Pull latest code with changes
git pull origin develop/tenderiq  # Or your branch

# Check what changed
git log --oneline HEAD~1..HEAD
# Should show: "feat: Add tender_release_date to group tenders..."
```

### 1.2 Verify Code Changes

```bash
# Syntax check
python -m py_compile app/modules/scraper/db/schema.py
python -m py_compile app/modules/tenderiq/db/tenderiq_repository.py
python -m py_compile app/modules/scraper/services/dms_integration_service.py

# Check migration file exists
ls -la alembic/versions/642bfe5074f2e_*.py
```

### 1.3 Restart Application (if running)

```bash
# If using systemd
sudo systemctl restart <your-app-service>

# If using docker
docker-compose restart <app-container>

# If using gunicorn/manual
# Kill existing process and restart
```

---

## Phase 2: Run Database Migration

### Option A: Using Alembic (Recommended - Production Ready)

```bash
# Connect to production database
cd /path/to/chatbot-backend

# 2.1 List pending migrations
python -m alembic current

# 2.2 Show what the migration does
python -m alembic show 642bfe5074f2e

# 2.3 Run migration
python -m alembic upgrade head

# 2.4 Verify migration ran
python -m alembic current
# Should show: 642bfe5074f2e_add_tender_release_date_column_to_scrape_runs
```

### Option B: Manual SQL (If Alembic fails)

If Alembic fails for any reason, run this SQL directly:

```sql
-- Step 1: Add the column
ALTER TABLE scrape_runs
ADD COLUMN tender_release_date DATE;

-- Step 2: Create index
CREATE INDEX idx_scrape_runs_release_date ON scrape_runs(tender_release_date);

-- Step 3: Populate from date_str (if available)
UPDATE scrape_runs
SET tender_release_date = TO_DATE(
    SUBSTRING(date_str FROM ',\s*(.+)$'),
    'Mon DD, YYYY'
)
WHERE date_str IS NOT NULL
AND date_str ~ '^\\w+,\\s+\\w+\\s+\\d{1,2},\\s+\\d{4}$';

-- Step 4: Handle any records that couldn't be parsed
UPDATE scrape_runs
SET tender_release_date = (run_at AT TIME ZONE 'UTC')::date
WHERE tender_release_date IS NULL;

-- Step 5: Make column NOT NULL
ALTER TABLE scrape_runs
ALTER COLUMN tender_release_date SET NOT NULL;

-- Verify
SELECT COUNT(*) as total,
       COUNT(tender_release_date) as populated,
       COUNT(CASE WHEN tender_release_date IS NULL THEN 1 END) as null_count
FROM scrape_runs;
```

---

## Phase 3: Verification

### 3.1 Check Migration Success

```sql
-- Verify column exists and is indexed
\d scrape_runs

-- Should show:
-- tender_release_date | date | not null
-- Indexes: idx_scrape_runs_release_date
```

### 3.2 Verify Data Integrity

```sql
-- Check that all records are populated
SELECT COUNT(*) as total,
       COUNT(tender_release_date) as populated,
       COUNT(CASE WHEN tender_release_date IS NULL THEN 1 END) as null_count
FROM scrape_runs;

-- Expected: total = populated, null_count = 0

-- Check data consistency
SELECT id, date_str, tender_release_date, run_at
FROM scrape_runs
ORDER BY run_at DESC
LIMIT 10;
```

### 3.3 Test Queries

```sql
-- Test query by date (used by API)
SELECT COUNT(*) as tender_count
FROM scrape_runs
WHERE tender_release_date = '2025-11-03';

-- Test date range query
SELECT COUNT(*) as tender_count
FROM scrape_runs
WHERE tender_release_date >= '2025-10-30'
  AND tender_release_date <= '2025-11-04';

-- Check index usage
EXPLAIN ANALYZE
SELECT * FROM scrape_runs
WHERE tender_release_date = '2025-11-03';
```

### 3.4 API Testing

```bash
# Test the date selector endpoint
curl -X GET "https://your-api.com/api/v1/tenderiq/dates" \
  -H "Authorization: Bearer <token>"

# Should return dates grouped by tender_release_date
# Check response:
# {
#   "dates": [
#     {
#       "date": "2025-11-03",      # This is tender_release_date
#       "date_str": "Sunday, Nov 03, 2025",
#       "run_at": "2025-11-04T10:30:00",
#       "tender_count": 1234,
#       "is_latest": true
#     }
#   ]
# }

# Test specific date query
curl -X GET "https://your-api.com/api/v1/tenderiq/tenders?date=2025-11-03" \
  -H "Authorization: Bearer <token>"

# Test last N days
curl -X GET "https://your-api.com/api/v1/tenderiq/tenders?date_range=last_7_days" \
  -H "Authorization: Bearer <token>"
```

---

## Rollback Plan

If something goes wrong:

### Option A: Alembic Rollback

```bash
# Show migration history
python -m alembic history

# Rollback to previous version
python -m alembic downgrade 9d6fa90879e4

# Verify
python -m alembic current
```

### Option B: Manual SQL Rollback

```sql
-- Only if manual migration was used

-- Drop the index
DROP INDEX IF EXISTS idx_scrape_runs_release_date;

-- Drop the column
ALTER TABLE scrape_runs DROP COLUMN tender_release_date;

-- Verify
\d scrape_runs
```

### Option C: Restore from Backup

```bash
# If something critically wrong
psql -h <host> -U <user> -d <dbname> < scrape_runs_backup_YYYYMMDD.sql
```

---

## Post-Migration Monitoring

### Monitor for 30 minutes after migration

```bash
# Check application logs for errors
tail -f /var/log/your-app.log | grep -i error

# Check database for slow queries
# (depends on your monitoring setup)

# Test endpoints periodically
for i in {1..10}; do
  curl -X GET "https://your-api.com/api/v1/tenderiq/dates" \
    -H "Authorization: Bearer <token>" > /dev/null
  sleep 5
done
```

### Verify Frontend Still Works

1. **Date Selector**:
   - Loads dates correctly
   - Dates match tender release dates, not scrape dates

2. **Tender Listing**:
   - Can filter by date
   - Results grouped correctly

3. **Performance**:
   - No slow queries
   - Response times < 1 second

---

## Production Checklist

- [ ] Backed up database
- [ ] Reviewed code changes
- [ ] Ran Alembic migration (or manual SQL)
- [ ] Verified column exists and is populated
- [ ] Tested queries work
- [ ] Tested API endpoints
- [ ] Verified frontend still works
- [ ] Monitored logs for 30 minutes
- [ ] Verified performance is acceptable

---

## What Gets Updated Going Forward

After this migration, all NEW scrape runs will have:

```python
ScrapeRun {
    id: UUID,
    run_at: DateTime,                    # When we ran the scraper
    tender_release_date: Date,           # When tenders were released (from website header)
    date_str: String,                    # Website header date string
    # ... other fields ...
}
```

The DMS folder structure stays the same (uses parsed YYYY-MM-DD format).

---

## FAQ

### Q: Will this affect my existing data?

**A**: No breaking changes. Existing data is migrated automatically. The only change is how tenders are grouped - by release date instead of scrape date.

### Q: Do I need to restart the application?

**A**: Yes. After running the migration:
1. Restart the application
2. Verify it loads the new schema
3. Check database connections work

### Q: What if the migration fails?

**A**:
1. Check the error message
2. Try manual SQL (Option B)
3. If still failing, rollback and contact support

### Q: How long does the migration take?

**A**:
- Small DB (< 100MB): < 1 minute
- Medium DB (100MB - 1GB): 2-5 minutes
- Large DB (> 1GB): Could be longer

### Q: Can I test this first?

**A**: Yes! Clone your production database to staging and test there first:

```bash
# On staging server
pg_dump -h prod-host -U prod-user -d ceigall | psql -h staging-host -U staging-user -d ceigall-staging

# Then run migration on staging first
python -m alembic upgrade head
```

### Q: What about data consistency?

**A**: The migration handles:
- ✅ Parsing date_str into tender_release_date
- ✅ Records where date_str is malformed (uses run_at.date() as fallback)
- ✅ Indexing for query performance
- ✅ NOT NULL constraint after data population

---

## Support

If you encounter issues:

1. **Check logs**: `tail -100 /var/log/your-app.log`
2. **Check database**: Run verification SQL queries
3. **Rollback if needed**: Use rollback plan above
4. **Contact support**: Include:
   - Error message
   - Migration output
   - Current database state (from verification queries)

---

## References

- Migration File: `alembic/versions/642bfe5074f2e_add_tender_release_date_column_to_scrape_runs.py`
- Schema Changes: `app/modules/scraper/db/schema.py`
- Code Changes Commit: `a000560`

---

*Last Updated: November 4, 2025*
*Status: Ready for Production*
