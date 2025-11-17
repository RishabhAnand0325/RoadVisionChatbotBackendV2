from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.modules.bidsynopsis.db.repository import BidSynopsisRepository
from app.modules.bidsynopsis.synopsis_service import generate_bid_synopsis
from app.modules.bidsynopsis.pydantic_models import BidSynopsisResponse
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
        4. Return structured response
        """
        # Initialize repository - same pattern as TenderFilterService
        repo = BidSynopsisRepository(db)
        
        # Fetch tender and scraped data through repository
        tender_data = repo.get_tender_with_scraped_data(tender_id)
        
        if not tender_data:
            return None
            
        tender, scraped_tender = tender_data
        
        # Fetch analysis data if available (tender_id_str from scraped_tender)
        analysis = None
        if scraped_tender:
            analysis = db.query(TenderAnalysis).filter(
                TenderAnalysis.tender_id == scraped_tender.tender_id_str
            ).first()
        
        # Generate bid synopsis using business logic with analysis data
        bid_synopsis = generate_bid_synopsis(tender, scraped_tender, analysis)
        
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