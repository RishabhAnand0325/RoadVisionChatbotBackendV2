from typing import List
from uuid import UUID
from sqlalchemy import Float, cast, desc, func, case, text
from sqlalchemy.orm import Session, joinedload, noload, selectinload
from sqlalchemy.sql import over

from app.modules.scraper.db.schema import ScrapeRun, ScrapedTender, ScrapedTenderQuery

def get_tenders_from_category(db: Session, query: ScrapedTenderQuery, offset: int, limit: int, min_publish_date: str = None, unique_only: bool = True) -> List[ScrapedTender]:
    """
    Get tenders from a category with optional date filtering and deduplication.
    Optimized for performance with proper indexing.
    """
    base_query = (
        db.query(ScrapedTender)
        .filter(ScrapedTender.query_id == query.id)
    )

    if min_publish_date:
        # Use simple string comparison with the indexed publish_date column
        # Convert DD-MM-YYYY format to YYYY-MM-DD for comparison
        # Use regexp_replace for conversion - database handles this efficiently with index
        iso_date_str = func.regexp_replace(ScrapedTender.publish_date, r'^(\d{2})-(\d{2})-(\d{4})$', r'\3-\2-\1')
        
        # Filter by converted date
        safe_iso_date = case(
            (text("scraped_tenders.publish_date ~ '^\\d{2}-\\d{2}-\\d{4}$'"), iso_date_str),
            else_='0000-00-00'
        )
        base_query = base_query.filter(safe_iso_date >= min_publish_date)

    if unique_only:
        # OPTIMIZED: Use DISTINCT ON instead of ROW_NUMBER() for much better performance
        # DISTINCT ON is PostgreSQL-specific and much faster than window functions
        # It keeps the first row for each tender_no based on the ORDER BY
        base_query = base_query.distinct(ScrapedTender.tender_no)

    # Sort by publish_date (converted to ISO format for proper sorting)
    iso_date_str_sort = func.regexp_replace(ScrapedTender.publish_date, r'^(\d{2})-(\d{2})-(\d{4})$', r'\3-\2-\1')
    safe_date_sort = case(
        (text("scraped_tenders.publish_date ~ '^\\d{2}-\\d{2}-\\d{4}$'"), iso_date_str_sort),
        else_='0000-00-00'
    )

    # IMPORTANT: When using DISTINCT ON, the ORDER BY must start with the DISTINCT ON columns
    # Then add our desired sort order
    return (
        base_query
        .order_by(ScrapedTender.tender_no, desc(safe_date_sort))
        .options(joinedload(ScrapedTender.files))
        .offset(offset)
        .limit(limit)
        .all()
    )

def get_all_tenders_from_category(db: Session, query: ScrapedTenderQuery) -> List[ScrapedTender]:
    return (
        db.query(ScrapedTender)
        .filter(ScrapedTender.query_id == query.id)
        .options(joinedload(ScrapedTender.files))
        .all()
    )

def get_all_categories(db: Session, scrape_run: ScrapeRun) -> List[ScrapedTenderQuery]:
    return (
        db.query(ScrapedTenderQuery)
        .filter(ScrapedTenderQuery.scrape_run_id == scrape_run.id)
        .options(noload(ScrapedTenderQuery.tenders))
        .all()
    )

def get_scrape_runs(db: Session) -> List[ScrapeRun]:
    return (
        db.query(ScrapeRun)
        .order_by(ScrapeRun.run_at.desc())
        .options(noload(ScrapeRun.queries))
        .all()
    )

def get_scrape_run_by_id(db: Session, scrape_run_id: str) -> ScrapeRun:
    return (
        db.query(ScrapeRun)
        .filter(ScrapeRun.id == scrape_run_id)
        .first()
    )

def get_scraped_tender(db: Session, tender_id: UUID) -> ScrapedTender:
    return db.query(ScrapedTender).filter(ScrapedTender.id == tender_id).first()

def get_scrape_runs_by_date_range(db: Session, days: int) -> List[ScrapeRun]:
    from datetime import datetime, timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(ScrapeRun)
        .filter(ScrapeRun.run_at >= cutoff_date)
        .order_by(ScrapeRun.run_at.desc())
        .options(noload(ScrapeRun.queries))
        .all()
    )

