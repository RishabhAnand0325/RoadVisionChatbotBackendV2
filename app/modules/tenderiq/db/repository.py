"""
TenderIQ Main Repository

Encapsulates all data access logic for the main TenderIQ features,
interacting with the `tenders` table and related entities.
"""

from typing import Optional
from uuid import UUID
from datetime import datetime
from dateutil import parser
from sqlalchemy.orm import Session

from app.modules.tenderiq.db.schema import Tender, TenderActionHistory, TenderActionEnum
from app.modules.scraper.db.schema import ScrapedTender


class TenderRepository:
    """Repository for main Tender data access operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_by_id(self, scraped_tender: ScrapedTender) -> Tender:
        """
        Gets a Tender by its UUID. If it doesn't exist, it creates one
        based on the corresponding ScrapedTender data.
        """
        tender = self.db.query(Tender).filter(Tender.tender_ref_number == scraped_tender.tender_id_str).first()
        if not tender:
            # Map fields from ScrapedTender to Tender
            tender = Tender(
                id=scraped_tender.id,
                tender_ref_number=scraped_tender.tender_id_str,
                tender_title=scraped_tender.tender_name,
                description=scraped_tender.summary,
                employer_name=scraped_tender.company_name,
                issuing_authority=scraped_tender.tendering_authority,
                state=scraped_tender.state,
                location=scraped_tender.city,
                category=scraped_tender.query.query_name if scraped_tender.query else None,
                estimated_cost=self._parse_cost(scraped_tender.value),
                submission_deadline=self._parse_date(scraped_tender.last_date_of_bid_submission),
                portal_url=scraped_tender.tender_url,
            )
            self.db.add(tender)
            self.db.commit()
            self.db.refresh(tender)
        return tender

    def update(self, tender: Tender, updates: dict) -> Tender:
        """Updates a Tender instance with new values."""
        for key, value in updates.items():
            setattr(tender, key, value)
        self.db.commit()
        self.db.refresh(tender)
        return tender

    def log_action(self, tender_id: UUID, user_id: UUID, action: TenderActionEnum, notes: Optional[str] = None) -> TenderActionHistory:
        """Logs a user action on a tender."""
        history_log = TenderActionHistory(
            tender_id=tender_id,
            user_id=user_id,
            action=action,
            notes=notes,
        )
        self.db.add(history_log)
        self.db.commit()
        self.db.refresh(history_log)
        return history_log
    
    def _parse_cost(self, cost_str: Optional[str]) -> Optional[float]:
        if not cost_str:
            return None
        try:
            # Basic parsing, can be expanded
            return float(cost_str.lower().replace("crore", "").replace("lakh", "").strip())
        except ValueError:
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            # Assumes "DD-Mon-YYYY" format from ScrapedTender e.g. "08-Nov-2025"
            return datetime.strptime(date_str, "%d-%b-%Y")
        except (ValueError, TypeError):
            # Fallback for other potential formats if needed in the future
            try:
                return parser.parse(date_str)
            except (parser.ParserError, TypeError):
                return None

    def get_tenders_by_flag(self, flag_name: str, flag_value: bool = True) -> list[Tender]:
        """
        Gets all Tenders where a specific boolean flag is set to the given value.
        """
        if not hasattr(Tender, flag_name):
            raise ValueError(f"'{flag_name}' is not a valid attribute of Tender model.")
        
        return self.db.query(Tender).filter(getattr(Tender, flag_name) == flag_value).all()
