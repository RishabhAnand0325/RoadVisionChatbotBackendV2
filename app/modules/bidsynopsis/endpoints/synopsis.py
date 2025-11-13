from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from app.db.database import get_db_session
from app.modules.tenderiq.db.schema import Tender, ScrapedTender
from .pydantic_models import BidSynopsisResponse, ErrorResponse
from .synopsis_service import generate_bid_synopsis

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

    This endpoint retrieves structured bid synopsis data including:
    - **basicInfo**: 10 key fields (Employer, Name of Work, Tender Value, etc.)
    - **allRequirements**: Eligibility criteria with calculated values

    Data is dynamically fetched from:
    - `tenders` table: Core tender information (estimated_cost, dates, etc.)
    - `scraped_tenders` table: Detailed scraper data (document_fees, tender_details, etc.)

    The response is designed to be displayed in a two-pane layout:
    - Left pane: Editable draft sections
    - Right pane: PDF-style preview

    **Path Parameters:**
    - `tender_id` (UUID): The unique identifier of the tender

    **Example Request:**
    ```
    GET /api/v1/bidsynopsis/synopsis/550e8400-e29b-41d4-a716-446655440000
    ```

    **Example Response:**
    ```json
    {
      "basicInfo": [
        {
          "sno": 1,
          "item": "Employer",
          "description": "National Highways Authority of India (NHAI)"
        },
        {
          "sno": 2,
          "item": "Name of Work",
          "description": "Construction of 4-Lane Highway"
        }
      ],
      "allRequirements": [
        {
          "description": "Site Visit",
          "requirement": "Bidders shall submit their respective Bids after visiting the Project site...",
          "ceigallValue": ""
        }
      ]
    }
    ```

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
        # Query tender with eager loading for better performance
        tender = db.query(Tender).filter(Tender.id == tender_id).first()

        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender with ID {tender_id} not found."
            )

        # Try to find associated scraped tender by tender_ref_number or title
        scraped_tender = None
        if tender.tender_ref_number:
            scraped_tender = db.query(ScrapedTender).filter(
                ScrapedTender.tender_id_str == tender.tender_ref_number
            ).first()

        # If not found by ref_number, try by title (fuzzy match)
        if not scraped_tender and tender.tender_title:
            scraped_tender = db.query(ScrapedTender).filter(
                ScrapedTender.tender_name.ilike(f"%{tender.tender_title[:50]}%")
            ).first()

        # Generate and return the bid synopsis with both tender and scraped_tender data
        bid_synopsis = generate_bid_synopsis(tender, scraped_tender)
        return bid_synopsis

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        # Log and return generic 500 error
        print(f"❌ Error generating bid synopsis for tender {tender_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate bid synopsis: {str(e)}"
        )