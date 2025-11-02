from typing import Optional

from sqlalchemy.orm import Session

from app.modules.scraper.db.repository import ScraperRepository
from app.modules.tenderiq.models.pydantic_models import DailyTendersResponse


def get_latest_daily_tenders(db: Session) -> Optional[DailyTendersResponse]:
    """
    Fetches the latest scrape run and formats it for the API response.
    """
    scraper_repo = ScraperRepository(db)
    latest_run = scraper_repo.get_latest_scrape_run()

    if not latest_run:
        return None

    return DailyTendersResponse.model_validate(latest_run)
