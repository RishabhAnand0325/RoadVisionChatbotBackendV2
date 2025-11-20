from click import Option
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.db.database import get_db_session
from app.modules.auth.services.auth_service import get_current_active_user
from app.modules.auth.db.schema import User
from app.modules.tenderiq.models.pydantic_models import (
    DailyTendersResponse,
    AvailableDatesResponse,
    FullTenderDetails,
    HistoryAndWishlistResponse,
    ScrapedDatesResponse,
    Tender,
    FilteredTendersResponse,
    TenderActionRequest,
)
from app.modules.tenderiq.services import tender_service
from app.modules.tenderiq.services.tender_filter_service import TenderFilterService
from app.modules.tenderiq.services.tender_action_service import TenderActionService
from sse_starlette.sse import EventSourceResponse
from app.modules.tenderiq.services import tender_service_sse

router = APIRouter()


@router.get(
    "/dailytenders",
    response_model=DailyTendersResponse,
    tags=["TenderIQ"],
    summary="[DEPRECATED] Get the latest daily tenders - use /tenders instead",
    deprecated=True,
)
def get_daily_tenders(db: Session = Depends(get_db_session)):
    """
    **DEPRECATED**: Use `GET /tenders` without parameters instead.

    This endpoint has been merged into `/tenders`. Both endpoints now return
    the same hierarchical format. When calling `/tenders` without any parameters,
    it returns the latest scrape run (same as this endpoint).

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

@router.get(
    "/tenders-sse",
    response_model=DailyTendersResponse,
    tags=["TenderIQ"],
    summary="SSE version of the /tenders endpoint"
)
def get_daily_tenders_sse(
    start: Optional[int] = 0,
    end: Optional[int] = 1000,
    scrape_run_id: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    return EventSourceResponse(tender_service_sse.get_daily_tenders_sse(db, start, end, scrape_run_id))

@router.get(
    "/tenders/{tender_id}",
    response_model=Tender,
    tags=["TenderIQ"],
    summary="Get detailed information for a single tender",
)
def get_tender_details(
    tender_id: UUID,
    db: Session = Depends(get_db_session)
):
    """
    Retrieves comprehensive details for a specific tender by its UUID,
    including notice information, key dates, contact details, and associated files.
    """
    service = TenderFilterService()
    tender_details = service.get_tender_details(db, tender_id)
    if not tender_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found.",
        )
    return tender_details

## TODO: Implement this endpoint. It will replace /tenders/{tender_id} later
## Done :)
@router.get(
    "/tenders/{tender_id}/full",
    tags=["TenderIQ"],
    summary="Get detailed information for a single tender",
)
def get_full_tender_details(
    tender_id: UUID,
    db: Session = Depends(get_db_session)
):
    """
    Get complete tender details with all related data.
    """
    try:
        tender_details = tender_service.get_full_tender_details(db, tender_id)
        
        if not tender_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tender not found."
            )
        
        return tender_details
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve full tender details: {str(e)}"
        )


@router.get(
    "/wishlist",
    response_model=list[Tender],
    tags=["TenderIQ"],
    summary="Get all wishlisted tenders"
)
def get_wishlisted_tenders(db: Session = Depends(get_db_session)):
    """Retrieves all tenders that have been marked as wishlisted."""
    service = TenderFilterService()
    return service.get_wishlisted_tenders(db)

@router.get(
    "/history-wishlist",
    response_model=HistoryAndWishlistResponse,
    tags=["TenderIQ"],
    summary="Get all wishlisted tenders along with actions history"
)
def get_wishlisted_tenders_with_history(db: Session = Depends(get_db_session)):
    """Retrieves all tenders that have been marked as wishlisted."""
    service = TenderFilterService()
    return service.get_wishlisted_tenders_with_history(db)

@router.get(
    "/favourite",
    response_model=list[Tender],
    tags=["TenderIQ"],
    summary="Get all favorite tenders"
)
def get_favorite_tenders(db: Session = Depends(get_db_session)):
    """Retrieves all tenders that have been marked as favorites."""
    service = TenderFilterService()
    return service.get_favorited_tenders(db)

@router.get(
    "/archived",
    response_model=list[Tender],
    tags=["TenderIQ"],
    summary="Get all archived tenders"
)
def get_archived_tenders(db: Session = Depends(get_db_session)):
    """Retrieves all tenders that have been archived."""
    service = TenderFilterService()
    return service.get_archived_tenders(db)

@router.post(
    "/tenders/{tender_id}/actions",
    tags=["TenderIQ"],
    summary="Perform an action on a tender",
    status_code=status.HTTP_200_OK,
)
def perform_tender_action(
    tender_id: UUID,
    request: TenderActionRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Perform an action on a tender, such as wishlisting, archiving, or updating its status.

    **Available Actions:**
    - `toggle_wishlist`: Adds or removes the tender from the user's wishlist.
    - `toggle_favorite`: Marks or unmarks the tender as a favorite.
    - `toggle_archive`: Archives or unarchives the tender.
    - `update_status`: Changes the tender's main status (e.g., 'Won', 'Lost'). Requires a `status` in the payload.
    - `update_review_status`: Changes the tender's review status (e.g., 'Reviewed'). Requires a `review_status` in the payload.
    """
    try:
        service = TenderActionService(db)
        service.perform_action(tender_id, current_user.id, request)
        return {"message": "Action performed successfully", "tender_id": str(tender_id)}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )


@router.get(
    "/dates",
    response_model=ScrapedDatesResponse,
    tags=["TenderIQ"],
    summary="Get available scrape dates",
    description="Returns all available scrape dates with tender counts. "
    "Used by frontend to populate date selector dropdown.",
)
def get_available_dates(db: Session = Depends(get_db_session)):
    return tender_service_sse.get_scraped_dates(db)

