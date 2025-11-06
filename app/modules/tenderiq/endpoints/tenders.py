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
    Tender,
    FilteredTendersResponse,
    TenderActionRequest,
)
from app.modules.tenderiq.services import tender_service
from app.modules.tenderiq.services.tender_filter_service import TenderFilterService
from app.modules.tenderiq.services.tender_action_service import TenderActionService

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
    "/archived",
    response_model=list[Tender],
    tags=["TenderIQ"],
    summary="Get all archived tenders"
)
def get_archived_tenders(db: Session = Depends(get_db_session)):
    """Retrieves all tenders that have been marked as archived."""
    service = TenderFilterService()
    return service.get_archived_tenders(db)


@router.get(
    "/favourite",
    response_model=list[Tender],
    tags=["TenderIQ"],
    summary="Get all favorite tenders"
)
def get_favorite_tenders(db: Session = Depends(get_db_session)):
    """Retrieves all tenders that have been marked as a favorite."""
    service = TenderFilterService()
    return service.get_favorited_tenders(db)


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


# ==================== Date Filtering Endpoints ====================


@router.get(
    "/dates",
    response_model=AvailableDatesResponse,
    tags=["TenderIQ"],
    summary="Get available scrape dates",
    description="Returns all available scrape dates with tender counts. "
    "Used by frontend to populate date selector dropdown.",
)
def get_available_dates(db: Session = Depends(get_db_session)):
    """
    Get all available scrape dates with tender counts.

    Returns a list of all dates when tenders were scraped, sorted by newest first.
    Each date includes:
    - date: YYYY-MM-DD format
    - date_str: Human-readable format (e.g., "November 3, 2024")
    - run_at: ISO format timestamp
    - tender_count: Number of tenders scraped on that date
    - is_latest: Whether this is the most recent scrape

    Frontend uses this to populate the date selector dropdown.

    **Example Response:**
    ```json
    {
      "dates": [
        {
          "date": "2024-11-03",
          "date_str": "November 3, 2024",
          "run_at": "2024-11-03T10:30:00Z",
          "tender_count": 45,
          "is_latest": true
        },
        {
          "date": "2024-11-02",
          "date_str": "November 2, 2024",
          "run_at": "2024-11-02T09:15:00Z",
          "tender_count": 38,
          "is_latest": false
        }
      ]
    }
    ```
    """
    try:
        service = TenderFilterService()
        return service.get_available_dates(db)
    except Exception as e:
        print(f"❌ Error fetching available dates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch available dates",
        )


@router.get(
    "/tenders",
    response_model=DailyTendersResponse,
    tags=["TenderIQ"],
    summary="Get tenders with date and other filters",
    description="Retrieves tenders filtered by specific date(s) or date ranges, "
    "with optional additional filters like category, location, and value range. "
    "Returns data in the same hierarchical format as /dailytenders endpoint.",
)
def get_filtered_tenders(
    db: Session = Depends(get_db_session),
    date: Optional[str] = Query(
        None,
        description="Specific date to retrieve tenders for (format: YYYY-MM-DD). "
        "Returns all tenders scraped on this date.",
        example="2024-11-03",
    ),
    date_range: Optional[str] = Query(
        None,
        description="Predefined date range filter. "
        "Options: 'last_1_day', 'last_5_days', 'last_7_days', 'last_30_days'",
        example="last_5_days",
    ),
    include_all_dates: bool = Query(
        False,
        description="If true, returns all historical tenders regardless of date. "
        "Takes precedence over 'date' and 'date_range' parameters.",
    ),
    category: Optional[str] = Query(
        None,
        description="Filter by query category/name (e.g., 'Civil', 'Electrical')",
        example="Civil",
    ),
    location: Optional[str] = Query(
        None,
        description="Filter by location/city",
        example="Mumbai",
    ),
    state: Optional[str] = Query(
        None,
        description="Filter by state",
        example="Maharashtra",
    ),
    tender_type: Optional[str] = Query(
        None,
        description="Filter by tender type (e.g., 'Open', 'Limited')",
        example="Open",
    ),
    min_value: Optional[float] = Query(
        None,
        description="Minimum tender value in crore",
        example=300,
    ),
    max_value: Optional[float] = Query(
        None,
        description="Maximum tender value in crore",
    ),
):
    """
    Get tenders with optional filtering by date and other criteria.

    Returns tenders in a hierarchical format organized by scrape run and query category.

    **Default behavior (no parameters)**: Returns the latest scrape run with all tenders
    (equivalent to the deprecated `/dailytenders` endpoint).

    The endpoint supports three ways to filter by date (in priority order):
    1. **include_all_dates=true**: Returns all historical tenders
    2. **date=YYYY-MM-DD**: Returns tenders from a specific date
    3. **date_range=last_N_days**: Returns tenders from last N days

    If no date filter is specified, the latest scrape run is returned.

    Additional filters (category, location, value) can be applied in combination
    with any date filter.

    **Example Requests:**
    ```
    GET /tenders                                          # Latest scrape run
    GET /tenders?date_range=last_5_days                   # Latest from last 5 days
    GET /tenders?date=2024-11-03&category=Civil           # Specific date + category
    GET /tenders?include_all_dates=true&location=Mumbai   # All tenders from Mumbai
    ```

    **Example Response:**
    ```json
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "run_at": "2024-11-03T10:30:00Z",
      "date_str": "November 3, 2024",
      "name": "Daily Tender Scrape",
      "contact": "contact@example.com",
      "no_of_new_tenders": "12",
      "company": "Company Name",
      "queries": [
        {
          "id": "550e8400-e29b-41d4-a716-446655440001",
          "query_name": "Civil",
          "number_of_tenders": "12",
          "tenders": [
            {
              "id": "550e8400-e29b-41d4-a716-446655440002",
              "tender_id_str": "TEN-2024-001",
              "tender_name": "Construction of Multi-Story Building",
              "tender_url": "https://...",
              "city": "Mumbai",
              "value": "250 Crore",
              "due_date": "2024-11-15",
              "summary": "...",
              "files": [...]
            }
          ]
        }
      ]
    }
    ```
    """
    try:
        service = TenderFilterService()

        # Determine which filter to use (include_all_dates takes precedence)
        if include_all_dates:
            print(f"📅 Fetching all tenders with filters: category={category}, location={location}")
            return service.get_all_tenders(
                db,
                category=category,
                location=location,
                state=state,
                tender_type=tender_type,
                min_value=min_value,
                max_value=max_value,
            )
        elif date:
            # Validate date format
            if not service.validate_date_format(date):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Use YYYY-MM-DD",
                )
            print(f"📅 Fetching tenders for date: {date}")
            return service.get_tenders_by_specific_date(
                db,
                date=date,
                category=category,
                location=location,
                state=state,
                tender_type=tender_type,
                min_value=min_value,
                max_value=max_value,
            )
        elif date_range:
            print(f"📅 Fetching tenders for date range: {date_range}")
            return service.get_tenders_by_date_range(
                db,
                date_range=date_range,
                category=category,
                location=location,
                state=state,
                tender_type=tender_type,
                min_value=min_value,
                max_value=max_value,
            )
        else:
            # Default: return latest scrape (same as /dailytenders)
            print("📅 No date filter specified, returning latest scrape")
            return service.get_latest_tenders(
                db,
                category=category,
                location=location,
                state=state,
                tender_type=tender_type,
                min_value=min_value,
                max_value=max_value,
            )

    except ValueError as e:
        print(f"⚠️  Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        print(f"❌ Error fetching filtered tenders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch tenders with filters",
        )
