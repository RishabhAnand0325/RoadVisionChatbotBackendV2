from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.database import get_db_session
from app.modules.tenderiq.db.schema import Tender
from app.modules.bidsynopsis.pydantic_models import BidSynopsisResponse, ErrorResponse
from app.modules.bidsynopsis.synopsis_service import generate_bid_synopsis

router = APIRouter()


@router.get(
    "/synopsis/{tender_id}",
    response_model=BidSynopsisResponse,
    tags=["BidSynopsis"],
    summary="Get bid synopsis for a tender",
    description="Retrieves structured bid synopsis containing basic information and eligibility requirements for a specific tender.",
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
    Get the complete bid synopsis for a tender.

    This endpoint retrieves structured bid synopsis data including:
    - **basicInfo**: 10 key fields (Employer, Name of Work, Tender Value, etc.)
    - **allRequirements**: Eligibility criteria with calculated values

    The response is designed to be displayed in a two-pane layout:
    - Left pane: Editable draft sections
    - Right pane: PDF-style preview

    **Path Parameters:**
    - `tender_id` (UUID): The unique identifier of the tender

    **Example Request:**
    ```
    GET /api/v1/synopsis/550e8400-e29b-41d4-a716-446655440000
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
    """
    try:
        # Query for the tender by ID
        tender = db.query(Tender).filter(Tender.id == tender_id).first()

        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender with ID {tender_id} not found."
            )

        # Generate and return the bid synopsis
        bid_synopsis = generate_bid_synopsis(tender)
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