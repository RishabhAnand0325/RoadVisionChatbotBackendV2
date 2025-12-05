from click import Option
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, Literal
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
    HistoryData,
)
from app.modules.tenderiq.services import tender_service
from app.modules.tenderiq.services.tender_filter_service import TenderFilterService
from app.modules.tenderiq.services.tender_action_service import TenderActionService
from app.modules.tenderiq.db.repository import TenderWishlistRepository
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
    latest_tenders = tender_service.get_daily_tenders(db)
    if not latest_tenders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scraped tenders found in the database.",
        )
    return latest_tenders

@router.get(
    "/tenders",
    tags=["TenderIQ"],
    summary="Get tenders with optional filters (replaces /dailytenders)"
)
def get_tenders(
    date: Optional[str] = Query(None, description="Specific date in YYYY-MM-DD format"),
    date_range: Optional[str] = Query(None, description="Range like 'last_5_days'"),
    include_all_dates: bool = Query(False, description="Include all historical tenders"),
    category: Optional[str] = Query(None, description="Filter by category"),
    location: Optional[str] = Query(None, description="Filter by location"),
    min_value: Optional[float] = Query(None, description="Minimum tender value in crore"),
    max_value: Optional[float] = Query(None, description="Maximum tender value in crore"),
    db: Session = Depends(get_db_session)
):
    """
    Get tenders with optional filters.
    If no filters are provided, returns the latest daily tenders.
    """
    service = TenderFilterService()
    
    if date:
        return service.get_tenders_by_specific_date(
            db, date, category, location, None, None, min_value, max_value
        )
    elif date_range:
        return service.get_tenders_by_date_range(
            db, date_range, category, location, None, None, min_value, max_value
        )
    elif include_all_dates:
        return service.get_all_tenders(db, category, location, None, None, min_value, max_value)
    else:
        return tender_service.get_daily_tenders(db)

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
    date_range: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    # If date_range is provided, use it as scrape_run_id
    run_id = date_range if date_range else scrape_run_id
    return EventSourceResponse(tender_service_sse.get_daily_tenders_sse(db, start, end, run_id))

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
    summary="Get all wishlisted tenders for the current user"
)
def get_wishlisted_tenders(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieves all tenders that have been marked as wishlisted by the current user."""
    service = TenderFilterService()
    return service.get_wishlisted_tenders(db, current_user.id)

@router.patch(
    "/wishlist/{wishlist_id}/results/{results}",
    tags=["TenderIQ"],
    summary="Update the results status of a wishlisted tender",
    status_code=status.HTTP_200_OK,
)
def update_wishlist_tender_results(
    wishlist_id: str,
    results: Literal["won", "rejected", "incomplete", "pending"],
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update the results status of a wishlisted tender.
    
    **Available Results:**
    - `won`: Tender was successfully won
    - `rejected`: Tender was rejected
    - `incomplete`: Tender submission was incomplete
    - `pending`: Tender results are still pending
    """
    try:
        wishlist_repo = TenderWishlistRepository(db)
        updated_wishlist = wishlist_repo.update_wishlist_progress(wishlist_id, results=results)
        
        if not updated_wishlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wishlist item not found"
            )
        
        return {"message": "Wishlist tender results updated successfully", "wishlist_id": wishlist_id, "results": results}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update wishlist tender results: {str(e)}"
        )

@router.get(
    "/history-wishlist",
    response_model=HistoryAndWishlistResponse,
    tags=["TenderIQ"],
    summary="Get all wishlisted tenders along with actions history for the current user"
)
def get_wishlisted_tenders_with_history(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieves all tenders that have been marked as wishlisted by the current user."""
    service = TenderFilterService()
    return service.get_wishlisted_tenders_with_history(db, current_user.id)

@router.get(
    "/favourite",
    response_model=list[Tender],
    tags=["TenderIQ"],
    summary="Get all favorite tenders for the current user"
)
def get_favorite_tenders(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieves all tenders that have been marked as favorites by the current user."""
    service = TenderFilterService()
    return service.get_favorited_tenders(db, current_user.id)

@router.get(
    "/archived",
    response_model=list[Tender],
    tags=["TenderIQ"],
    summary="Get all archived tenders for the current user"
)
def get_archived_tenders(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieves all tenders that have been archived by the current user."""
    service = TenderFilterService()
    return service.get_archived_tenders(db, current_user.id)

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

