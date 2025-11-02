from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.modules.scraper.db.schema import ScrapeRun, ScrapedTender, ScrapedTenderQuery


class ScraperRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_scrape_run(self) -> Optional[ScrapeRun]:
        """
        Retrieves the most recent scrape run from the database, eagerly loading
        all related queries, tenders, and files.
        """
        return (
            self.db.query(ScrapeRun)
            .order_by(ScrapeRun.run_at.desc())
            .options(
                joinedload(ScrapeRun.queries)
                .joinedload(ScrapedTenderQuery.tenders)
                .joinedload(ScrapedTender.files)
            )
            .first()
        )
