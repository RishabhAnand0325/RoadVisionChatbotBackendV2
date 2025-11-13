from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.database import get_db_session
from app.modules.bidsynopsis.pydantic_models import BidSynopsisResponse, ErrorResponse
from app.modules.bidsynopsis.services.bid_synopsis_service import BidSynopsisService

router = APIRouter()


@router.get(
    "/synopsis/{tender_id}",
    response_model=BidSynopsisResponse,
    tags=["BidSynopsis"],
    summary="Get bid synopsis for a tender",
    description="Retrieves structured bid synopsis containing basic information and eligibility requirements for a specific tender. Dynamically fetches data from both tender and scraped_tender tables.",
    responses={
        200: {
            "description": "Bid synopsis retrieved successfully",
            "model": BidSynopsisResponse
        },
        404: {
            "description": "Tender not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
def get_bid_synopsis(
    tender_id: UUID,
    db: Session = Depends(get_db_session)
) -> BidSynopsisResponse:
    """
    Get the complete bid synopsis for a tender with dynamic data fetching.
    
    **Architecture Pattern:**
    This endpoint follows the same layered architecture as other modules:
    - Service Layer: BidSynopsisService (business logic)
    - Repository Layer: BidSynopsisRepository (data access)
    - Endpoint Layer: This function (API interface)

    This endpoint retrieves structured bid synopsis data including:
    - **basicInfo**: 10 key fields (Employer, Name of Work, Tender Value, etc.)
    - **allRequirements**: Eligibility criteria with calculated values

    Data is dynamically fetched from:
    - `tenders` table: Core tender information (estimated_cost, dates, etc.)
    - `scraped_tenders` table: Detailed scraper data (document_fees, tender_details, etc.)

    **Path Parameters:**
    - `tender_id` (UUID): The unique identifier of the tender

    **Error Responses:**
    - `404`: Tender not found in database
    - `500`: Server error during synopsis generation

    **Data Sources:**
    The endpoint intelligently combines data from multiple database tables:
    
    From `tenders` table:
    - employer_name, tender_title, estimated_cost, bid_security, length_km
    - submission_deadline, prebid_meeting_date, site_visit_deadline
    - issuing_authority, state, location, category
    
    From `scraped_tenders` table (if available):
    - document_fees, tender_details, tender_brief
    - tendering_authority, tender_name, due_date
    - Additional scraped metadata
    
    Fields marked as "N/A" indicate missing data in both tables.
    """
    try:
        # Use service layer - same pattern as other endpoints
        service = BidSynopsisService()
        bid_synopsis = service.get_bid_synopsis(db, tender_id)

        if not bid_synopsis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender with ID {tender_id} not found."
            )

        return bid_synopsis

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        # Log and return generic 500 error - same pattern as other endpoints
        print(f"❌ Error generating bid synopsis for tender {tender_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate bid synopsis: {str(e)}"
        )