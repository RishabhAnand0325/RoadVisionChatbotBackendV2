from typing import List
from sqlalchemy import Float, cast
from sqlalchemy.orm import Session, joinedload, noload, selectinload

from app.modules.scraper.db.schema import ScrapeRun, ScrapedTender, ScrapedTenderQuery

def get_tenders_from_category(db: Session, query: ScrapedTenderQuery, offset: int, limit: int) -> List[ScrapedTender]:
    base_query = (
        db.query(ScrapedTender)
        .filter(ScrapedTender.query_id == query.id)
    )

    base_query = base_query.filter(cast(ScrapedTender.tender_value, Float) >= 100000000)

    return (
        base_query
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
        .order_by(ScrapeRun.tender_release_date.desc())
        .options(noload(ScrapeRun.queries))
        .all()
    )

def get_scrape_run_by_id(db: Session, scrape_run_id: str) -> ScrapeRun:
    return (
        db.query(ScrapeRun)
        .filter(ScrapeRun.id == scrape_run_id)
        .first()
    )
