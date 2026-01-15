#!/usr/bin/env python3
"""Check total tenders in database and filtering logic"""

import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

# Add backend to path
sys.path.insert(0, '/home/ubuntu/ceigall/backup-28nove/backend')

from app.modules.scraper.db.schema import ScrapedTender, ScrapedTenderQuery, ScrapeRun
from app.config import Settings

# Create engine
settings = Settings()
engine = create_engine(settings.DATABASE_URL)
db = Session(engine)

try:
    # Total tenders
    total_tenders = db.query(func.count(ScrapedTender.id)).scalar()
    print(f"✓ Total tenders in database: {total_tenders:,}")
    
    # Total unique tender_no values
    unique_tenders = db.query(func.count(func.distinct(ScrapedTender.tender_no))).scalar()
    print(f"✓ Total unique tender numbers: {unique_tenders:,}")
    
    # Total scrape runs
    total_runs = db.query(func.count(ScrapeRun.id)).scalar()
    print(f"✓ Total scrape runs: {total_runs:,}")
    
    # Scrape runs by date range
    print("\n=== Scrape Runs by Date Range ===")
    for days in [2, 5, 7, 30]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = db.query(func.count(ScrapeRun.id)).filter(ScrapeRun.run_at >= cutoff).scalar()
        print(f"  Last {days} days (run_at): {count} runs")
        
    # Scrape runs by tender_release_date
    print("\n=== Scrape Runs by tender_release_date ===")
    for days in [2, 5, 7, 30]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = db.query(func.count(ScrapeRun.id)).filter(ScrapeRun.tender_release_date >= cutoff.date()).scalar()
        print(f"  Last {days} days (tender_release_date): {count} runs")
    
    # Tenders per date range
    print("\n=== Tenders by Date Range (using run_at) ===")
    for days in [2, 5, 7, 30]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        # Get runs in date range
        runs = db.query(ScrapeRun.id).filter(ScrapeRun.run_at >= cutoff).all()
        run_ids = [r[0] for r in runs]
        
        if run_ids:
            # Count tenders in those runs
            count = db.query(func.count(ScrapedTender.id)).join(ScrapedTenderQuery).filter(
                ScrapedTenderQuery.scrape_run_id.in_(run_ids)
            ).scalar()
            print(f"  Last {days} days: {count:,} tenders")
        else:
            print(f"  Last {days} days: 0 tenders (no runs)")
    
    # Tenders per date range using tender_release_date
    print("\n=== Tenders by Date Range (using tender_release_date) ===")
    for days in [2, 5, 7, 30]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        # Get runs with tender_release_date in range
        runs = db.query(ScrapeRun.id).filter(ScrapeRun.tender_release_date >= cutoff.date()).all()
        run_ids = [r[0] for r in runs]
        
        if run_ids:
            # Count tenders in those runs
            count = db.query(func.count(ScrapedTender.id)).join(ScrapedTenderQuery).filter(
                ScrapedTenderQuery.scrape_run_id.in_(run_ids)
            ).scalar()
            print(f"  Last {days} days: {count:,} tenders")
        else:
            print(f"  Last {days} days: 0 tenders (no runs)")
    
    # Show the first and last scrape run
    print("\n=== Latest Scrape Runs ===")
    latest_runs = db.query(ScrapeRun).order_by(ScrapeRun.run_at.desc()).limit(5).all()
    for i, run in enumerate(latest_runs, 1):
        tender_count = db.query(func.count(ScrapedTender.id)).join(ScrapedTenderQuery).filter(
            ScrapedTenderQuery.scrape_run_id == run.id
        ).scalar()
        print(f"  {i}. {run.date_str} | run_at: {run.run_at} | tender_release_date: {run.tender_release_date} | tenders: {tender_count}")

finally:
    db.close()
