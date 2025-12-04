from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
import uuid as uuid_lib

from app.modules.bidsynopsis.db.repository import BidSynopsisRepository
from app.modules.bidsynopsis.synopsis_service import generate_bid_synopsis
from app.modules.bidsynopsis.pydantic_models import (
    BidSynopsisResponse,
    SaveBidSynopsisRequest
)
from app.modules.bidsynopsis.db.schema import (
    BidSynopsisRequirement,
    BidSynopsisCeigallData,
    BidSynopsisExtractedValue
)
from app.modules.analyze.db.schema import TenderAnalysis


class BidSynopsisService:
    """
    Service layer for BidSynopsis operations.
    Follows the same architectural pattern as TenderFilterService and other services.
    """

    def __init__(self):
        """Initialize the service"""
        pass

    def get_bid_synopsis(self, db: Session, tender_id: UUID) -> Optional[BidSynopsisResponse]:
        """
        Get complete bid synopsis for a tender.

        Args:
            db: Database session
            tender_id: UUID of the tender

        Returns:
            BidSynopsisResponse or None if tender not found

        This method follows the same pattern as other services:
        1. Create repository instance
        2. Fetch data through repository
        3. Apply business logic with analysis data
        4. Load saved edited data from database
        5. Return structured response with edited data merged in
        """
        # Initialize repository - same pattern as TenderFilterService
        repo = BidSynopsisRepository(db)

        # Fetch tender and scraped data through repository
        tender_data = repo.get_tender_with_scraped_data(tender_id)

        if not tender_data:
            return None

        tender, scraped_tender = tender_data

        # Get tender_ref_number for loading edited data
        tender_ref_number = tender.tender_ref_number

        # Fetch analysis data if available (tender_id_str from scraped_tender)
        analysis = None
        if scraped_tender:
            analysis = db.query(TenderAnalysis).filter(
                TenderAnalysis.tender_id == scraped_tender.tender_id_str
            ).first()

        # Generate bid synopsis using business logic with analysis data
        bid_synopsis = generate_bid_synopsis(tender, scraped_tender, analysis)

        # Load saved edited requirements from database
        saved_requirements = db.query(BidSynopsisRequirement).filter(
            BidSynopsisRequirement.tender_id == tender_ref_number
        ).all()

        # Load saved ceigall data from database
        saved_ceigall = db.query(BidSynopsisCeigallData).filter(
            BidSynopsisCeigallData.tender_id == tender_ref_number
        ).all()

        # Load saved extracted values from database
        saved_extracted = db.query(BidSynopsisExtractedValue).filter(
            BidSynopsisExtractedValue.tender_id == tender_ref_number
        ).all()

        # Merge edited requirements into response
        for saved_req in saved_requirements:
            if saved_req.requirement_index < len(bid_synopsis.allRequirements):
                bid_synopsis.allRequirements[saved_req.requirement_index].requirement = saved_req.edited_requirement

        # Merge ceigall data into response
        for saved_data in saved_ceigall:
            if saved_data.data_index < len(bid_synopsis.allRequirements):
                bid_synopsis.allRequirements[saved_data.data_index].ceigallValue = saved_data.ceigall_value

        # Merge extracted values into response
        for saved_val in saved_extracted:
            if saved_val.value_index < len(bid_synopsis.allRequirements):
                bid_synopsis.allRequirements[saved_val.value_index].extractedValue = saved_val.extracted_value

        return bid_synopsis

    def get_bid_synopsis_by_ref_number(self, db: Session, tender_ref_number: str) -> Optional[BidSynopsisResponse]:
        """
        Get bid synopsis by tender reference number.
        Alternative access method following analyze_tender.py pattern.
        """
        repo = BidSynopsisRepository(db)
        
        # Get tender by reference number
        tender = repo.get_tender_by_ref_number(tender_ref_number)
        if not tender:
            return None
            
        # Get scraped tender data
        scraped_tender = repo.get_scraped_tender_by_id_str(tender_ref_number)
        
        # Get analysis data
        analysis = db.query(TenderAnalysis).filter(
            TenderAnalysis.tender_id == tender_ref_number
        ).first()
        
        # Generate bid synopsis with analysis data
        bid_synopsis = generate_bid_synopsis(tender, scraped_tender, analysis)

        return bid_synopsis

    def save_bid_synopsis(self, db: Session, request: SaveBidSynopsisRequest) -> bool:
        """
        Save edited bid synopsis data to database.

        Args:
            db: Database session
            request: SaveBidSynopsisRequest with edited data

        Returns:
            bool: True if save was successful

        This method saves:
        1. Edited requirement text for each requirement item
        2. CEIGALL company data for each requirement item
        """
        try:
            user_id_uuid = None
            if request.user_id:
                try:
                    user_id_uuid = uuid_lib.UUID(request.user_id)
                except ValueError:
                    pass  # If invalid UUID, keep as None

            # Save requirement data
            for index, edited_text in request.requirement_data.items():
                # Check if record exists
                existing = db.query(BidSynopsisRequirement).filter(
                    BidSynopsisRequirement.tender_id == request.tender_id,
                    BidSynopsisRequirement.requirement_index == index
                ).first()

                if existing:
                    # Update existing record
                    existing.edited_requirement = edited_text
                    existing.user_id = user_id_uuid
                else:
                    # Create new record
                    new_requirement = BidSynopsisRequirement(
                        tender_id=request.tender_id,
                        user_id=user_id_uuid,
                        requirement_index=index,
                        edited_requirement=edited_text
                    )
                    db.add(new_requirement)

            # Save ceigall data
            for index, value in request.ceigall_data.items():
                # Check if record exists
                existing = db.query(BidSynopsisCeigallData).filter(
                    BidSynopsisCeigallData.tender_id == request.tender_id,
                    BidSynopsisCeigallData.data_index == index
                ).first()

                if existing:
                    # Update existing record
                    existing.ceigall_value = value
                    existing.user_id = user_id_uuid
                else:
                    # Create new record
                    new_data = BidSynopsisCeigallData(
                        tender_id=request.tender_id,
                        user_id=user_id_uuid,
                        data_index=index,
                        ceigall_value=value
                    )
                    db.add(new_data)

            # Save extracted value data
            for index, value in request.extracted_value_data.items():
                # Check if record exists
                existing = db.query(BidSynopsisExtractedValue).filter(
                    BidSynopsisExtractedValue.tender_id == request.tender_id,
                    BidSynopsisExtractedValue.value_index == index
                ).first()

                if existing:
                    # Update existing record
                    existing.extracted_value = value
                    existing.user_id = user_id_uuid
                else:
                    # Create new record
                    new_extracted = BidSynopsisExtractedValue(
                        tender_id=request.tender_id,
                        user_id=user_id_uuid,
                        value_index=index,
                        extracted_value=value
                    )
                    db.add(new_extracted)

            # Commit all changes
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            print(f"❌ Error saving bid synopsis data: {str(e)}")
            raise