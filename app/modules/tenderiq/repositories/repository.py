from typing import List
from uuid import UUID
from sqlalchemy import Float, cast, desc, func
from sqlalchemy.orm import Session, joinedload, noload, selectinload
from sqlalchemy.sql import over

from app.modules.scraper.db.schema import ScrapeRun, ScrapedTender, ScrapedTenderQuery

def get_tenders_from_category(db: Session, query: ScrapedTenderQuery, offset: int, limit: int, min_publish_date: str = None, unique_only: bool = True) -> List[ScrapedTender]:
    base_query = (
        db.query(ScrapedTender)
        .filter(ScrapedTender.query_id == query.id)
    )

    # Remove the 100 crore tender value filter to allow all tenders to be displayed
    # base_query = base_query.filter(cast(ScrapedTender.tender_value, Float) >= 100000000)

    if min_publish_date:
        # Assuming publish_date is stored as 'DD-MM-YYYY' string
        base_query = base_query.filter(func.to_date(ScrapedTender.publish_date, 'DD-MM-YYYY') >= func.to_date(min_publish_date, 'YYYY-MM-DD'))

    if unique_only:
        # Get only unique tenders by tender_no (keep first/oldest occurrence of each duplicate)
        # Use ROW_NUMBER to assign row numbers within each tender_no group
        # Then filter to only keep row number 1
        subquery = db.query(
            ScrapedTender.id,
            func.row_number().over(
                partition_by=ScrapedTender.tender_no,
                order_by=ScrapedTender.tender_no.asc()
            ).label('rn')
        ).filter(ScrapedTender.query_id == query.id)
        
        if min_publish_date:
            subquery = subquery.filter(func.to_date(ScrapedTender.publish_date, 'DD-MM-YYYY') >= func.to_date(min_publish_date, 'YYYY-MM-DD'))
        
        subquery = subquery.subquery()
        
        base_query = (
            db.query(ScrapedTender)
            .join(subquery, ScrapedTender.id == subquery.c.id)
            .filter(subquery.c.rn == 1)
        )

    return (
        base_query
        .order_by(desc(func.to_date(ScrapedTender.publish_date, 'DD-MM-YYYY')))
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

