from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from typing import Optional
from uuid import UUID

from app.modules.tenderiq.db.schema import Tender
from app.modules.scraper.db.schema import ScrapedTender


class BidSynopsisRepository:
    """Repository for BidSynopsis-specific data access operations following project patterns"""

    def __init__(self, db: Session):
        self.db = db

    def get_tender_with_scraped_data(self, tender_id: UUID) -> Optional[tuple[Tender, Optional[ScrapedTender]]]:
        """
        Get tender and associated scraped tender data by tender UUID.
        Follows the same pattern as other repositories in the project.
        
        Returns:
            tuple[Tender, Optional[ScrapedTender]]: Tender and scraped data if found
        """
        # First get the tender
        tender = self.db.query(Tender).filter(Tender.id == tender_id).first()
        
        if not tender:
            return None
            
        # Try to find associated scraped tender by tender_ref_number
        scraped_tender = None
        if tender.tender_ref_number:
            scraped_tender = (
                self.db.query(ScrapedTender)
                .options(
                    joinedload(ScrapedTender.files),
                    joinedload(ScrapedTender.query)
                )
                .filter(ScrapedTender.tender_id_str == tender.tender_ref_number)
                .first()
            )
        
        # If not found by ref_number, try by title (fuzzy match) - following existing patterns
        if not scraped_tender and tender.tender_title:
            scraped_tender = (
                self.db.query(ScrapedTender)
                .options(
                    joinedload(ScrapedTender.files),
                    joinedload(ScrapedTender.query)
                )
                .filter(ScrapedTender.tender_name.ilike(f"%{tender.tender_title[:50]}%"))
                .first()
            )
        
        return (tender, scraped_tender)

    def get_tender_by_ref_number(self, tender_ref_number: str) -> Optional[Tender]:
        """
        Get tender by reference number.
        Consistent with patterns used in analyze_tender.py
        """
        return (
            self.db.query(Tender)
            .filter(Tender.tender_ref_number == tender_ref_number)
            .first()
        )

    def get_scraped_tender_by_id_str(self, tender_id_str: str) -> Optional[ScrapedTender]:
        """
        Get scraped tender by tender_id_str with relationships loaded.
        Consistent with patterns used in tenderiq_repository.py
        """
        return (
            self.db.query(ScrapedTender)
            .options(
                joinedload(ScrapedTender.files),
                joinedload(ScrapedTender.query)
            )
            .filter(ScrapedTender.tender_id_str == tender_id_str)
            .first()
        )