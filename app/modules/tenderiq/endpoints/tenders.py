from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db_session
from app.modules.tenderiq.models.pydantic_models import DailyTendersResponse
from app.modules.tenderiq.services import tender_service

router = APIRouter()


@router.get(
    "/dailytenders",
    response_model=DailyTendersResponse,
    tags=["TenderIQ"],
    summary="Get the latest daily tenders from the scraper",
)
def get_daily_tenders(db: Session = Depends(get_db_session)):
    """
    Retrieves the most recent batch of tenders added by the scraper.
    This represents the latest daily scrape run.
    """
    latest_tenders = tender_service.get_latest_daily_tenders(db)
    if not latest_tenders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scraped tenders found in the database.",
        )
    return latest_tenders
