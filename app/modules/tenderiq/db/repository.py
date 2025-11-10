
from typing import Optional
from uuid import UUID
from datetime import datetime
from dateutil import parser
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.modules.tenderiq.db.schema import Tender, TenderActionHistory, TenderActionEnum, TenderWishlist
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
    
    def get_tenders_by_flag(self, flag_name: str, flag_value: bool = True) -> list[Tender]:
        """
        Gets all Tenders where a specific boolean flag is set to the given value.
        """
        if not hasattr(Tender, flag_name):
            raise ValueError(f"'{flag_name}' is not a valid attribute of Tender model.")

        return self.db.query(Tender).filter(getattr(Tender, flag_name) == flag_value).all()

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
            
    # New method added
    def get_full_tender_details(self, tender_id: UUID):
        """
        Fetch full tender details with all related data.
        
        Includes:
        - Tender basic info
        - ScrapedTender data (files, dates, etc.)
        - Tender action history
        - Flags (favorite, archived, wishlisted)
        
        Args:
            tender_id: UUID of the tender
            
        Returns:
            Tender object with all relationships loaded
        """
        tender = self.db.query(Tender).filter(Tender.id == tender_id).first()
        return tender

# ==================== NEW: WISHLIST REPOSITORY METHODS ====================

class TenderWishlistRepository:
    """Repository for TenderWishlist data access operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_all_wishlist_tenders(self) -> list[TenderWishlist]:
        """
        Fetch all tenders in wishlist/history, ordered by latest added first.
        
        Returns:
            List of TenderWishlist objects sorted by added_to_wishlist_at DESC
        """
        return self.db.query(TenderWishlist).order_by(
            desc(TenderWishlist.added_to_wishlist_at)
        ).all()

    def get_wishlist_tender_by_id(self, wishlist_id: str) -> Optional[TenderWishlist]:
        """
        Fetch single wishlist tender by ID.
        
        Args:
            wishlist_id: Primary key of wishlist entry
            
        Returns:
            TenderWishlist object or None if not found
        """
        return self.db.query(TenderWishlist).filter(
            TenderWishlist.id == wishlist_id
        ).first()

    def get_wishlist_by_tender_ref(self, tender_ref_number: str) -> Optional[TenderWishlist]:
        """
        Fetch wishlist entry by tender reference number.
        
        Args:
            tender_ref_number: Reference number from tenders table
            
        Returns:
            TenderWishlist object or None if not found
        """
        return self.db.query(TenderWishlist).filter(
            TenderWishlist.tender_ref_number == tender_ref_number
        ).first()

    def get_user_wishlist(self, user_id: UUID) -> list[TenderWishlist]:
        """
        Fetch all wishlist entries for a specific user.
        
        Args:
            user_id: User UUID
            
        Returns:
            List of TenderWishlist objects for the user
        """
        return self.db.query(TenderWishlist).filter(
            TenderWishlist.user_id == user_id
        ).order_by(desc(TenderWishlist.added_to_wishlist_at)).all()

    def add_to_wishlist(self, tender_data: dict) -> TenderWishlist:
        """
        Add new tender to wishlist.
        
        Args:
            tender_data: Dictionary with all TenderWishlist fields
            
        Returns:
            Created TenderWishlist object
        """
        wishlist_entry = TenderWishlist(**tender_data)
        self.db.add(wishlist_entry)
        self.db.commit()
        self.db.refresh(wishlist_entry)
        return wishlist_entry

    def remove_from_wishlist(self, wishlist_id: str) -> bool:
        """
        Remove tender from wishlist.
        
        Args:
            wishlist_id: Primary key of wishlist entry
            
        Returns:
            True if successfully deleted, False if not found
        """
        result = self.db.query(TenderWishlist).filter(
            TenderWishlist.id == wishlist_id
        ).delete()
        self.db.commit()
        return result > 0

    def remove_from_wishlist_by_tender_ref(self, tender_ref_number: str) -> bool:
        """
        Remove tender from wishlist by tender reference number.
        
        Args:
            tender_ref_number: Reference number from tenders table
            
        Returns:
            True if successfully deleted
        """
        result = self.db.query(TenderWishlist).filter(
            TenderWishlist.tender_ref_number == tender_ref_number
        ).delete()
        self.db.commit()
        return result > 0

    def update_wishlist_progress(self, wishlist_id: str, **kwargs) -> Optional[TenderWishlist]:
        """
        Update progress/status fields for a wishlist tender.
        
        Args:
            wishlist_id: Primary key of wishlist entry
            **kwargs: Fields to update (progress, analysis_state, synopsis_state, 
                     evaluated_state, results, status_message, error_message)
        
        Returns:
            Updated TenderWishlist object or None if not found
        """
        wishlist = self.db.query(TenderWishlist).filter(
            TenderWishlist.id == wishlist_id
        ).first()
        
        if not wishlist:
            return None
        
        for key, value in kwargs.items():
            if hasattr(wishlist, key):
                setattr(wishlist, key, value)
        
        self.db.commit()
        self.db.refresh(wishlist)
        return wishlist

    def update_analysis_state(self, wishlist_id: str, analysis_done: bool, progress: int) -> Optional[TenderWishlist]:
        """
        Update analysis completion state and progress.
        
        Args:
            wishlist_id: Primary key of wishlist entry
            analysis_done: Whether analysis phase is complete
            progress: Current progress percentage (0-100)
        
        Returns:
            Updated TenderWishlist object
        """
        return self.update_wishlist_progress(
            wishlist_id,
            analysis_state=analysis_done,
            progress=progress
        )

    def update_synopsis_state(self, wishlist_id: str, synopsis_done: bool, progress: int) -> Optional[TenderWishlist]:
        """
        Update synopsis completion state and progress.
        
        Args:
            wishlist_id: Primary key of wishlist entry
            synopsis_done: Whether synopsis phase is complete
            progress: Current progress percentage (0-100)
        
        Returns:
            Updated TenderWishlist object
        """
        return self.update_wishlist_progress(
            wishlist_id,
            synopsis_state=synopsis_done,
            progress=progress
        )

    def update_evaluated_state(self, wishlist_id: str, evaluated_done: bool, results: str, progress: int = 100) -> Optional[TenderWishlist]:
        """
        Update evaluation completion state and final results.
        
        Args:
            wishlist_id: Primary key of wishlist entry
            evaluated_done: Whether evaluation is complete
            results: Final result status (won/rejected/incomplete/pending)
            progress: Current progress percentage (default 100)
        
        Returns:
            Updated TenderWishlist object
        """
        return self.update_wishlist_progress(
            wishlist_id,
            evaluated_state=evaluated_done,
            results=results,
            progress=progress
        )

    def get_wishlist_by_status(self, status: str) -> list[TenderWishlist]:
        """
        Get all wishlist entries with a specific status.
        
        Args:
            status: Status value (won/rejected/incomplete/pending)
        
        Returns:
            List of TenderWishlist objects with the specified status
        """
        return self.db.query(TenderWishlist).filter(
            TenderWishlist.results == status
        ).order_by(desc(TenderWishlist.updated_at)).all()

    def get_wishlist_count(self, user_id: UUID = None) -> int:
        """
        Get total count of wishlist entries.
        
        Args:
            user_id: Optional filter by user
        
        Returns:
            Count of wishlist entries
        """
        query = self.db.query(TenderWishlist)
        if user_id:
            query = query.filter(TenderWishlist.user_id == user_id)
        return query.count()
