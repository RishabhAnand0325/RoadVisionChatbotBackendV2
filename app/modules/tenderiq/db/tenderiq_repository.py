"""
TenderIQ Repository Layer

Encapsulates all data access logic for TenderIQ features.
Abstracts away the scraper database schema and provides TenderIQ-specific queries.

This separation ensures TenderIQ module doesn't directly depend on ScraperRepository,
making the modules properly decoupled and independently testable.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import Row, Tuple, and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.schema import Column

from app.modules.scraper.db.schema import (
    ScrapeRun,
    ScrapedTender,
    ScrapedTenderQuery,
)
from app.modules.tenderiq.db.schema import Tender


class TenderIQRepository:
    """Repository for TenderIQ-specific data access operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_wishlisted_tenders(self) -> List[Row[tuple[Tender, ScrapedTender]]]:
        """
        Get all tenders that have been marked as wishlisted.
        Joins by ID to ensure proper matching.
        """
        return self.db.query(Tender, ScrapedTender).join(
            ScrapedTender, Tender.id == ScrapedTender.id
        ).filter(Tender.is_wishlisted == True).all()

    def get_scraped_tenders_by_flag(self, flag_name: str, flag_value: bool = True) -> list[tuple[ScrapedTender, Optional[Tender]]]:
        """
        Get ScrapedTender objects filtered by a flag in the Tender table.
        
        This method properly joins scraped_tenders with tenders table,
        allowing filtering by flags (is_wishlisted, is_favorite, is_archived).
        
        Returns both ScrapedTender and Tender objects so the caller can
        access both scraped data and action flags.
        
        Args:
            flag_name: Name of the boolean flag (e.g., 'is_wishlisted', 'is_favorite', 'is_archived')
            flag_value: Value to filter by (default: True)
            
        Returns:
            List of tuples containing (ScrapedTender, Tender) objects
        """
        if not hasattr(Tender, flag_name):
            raise ValueError(f"'{flag_name}' is not a valid attribute of Tender model.")
        
        # Join ScrapedTender with Tender table and filter where the flag is True
        query = (
            self.db.query(ScrapedTender, Tender)
            .join(
                Tender,
                and_(
                    ScrapedTender.id == Tender.id,
                    getattr(Tender, flag_name) == flag_value
                ),
                isouter=False  # Inner join - only get tenders with the flag set
            )
            .options(
                joinedload(ScrapedTender.files),
                joinedload(ScrapedTender.query)
            )
        )
        
        return query.all()

    def enrich_scraped_tenders_with_flags(self, scraped_tenders: list[ScrapedTender]) -> list[ScrapedTender]:
        """
        Enrich ScrapedTender objects with action flags from the Tender table.
        
        For each ScrapedTender, looks up the corresponding Tender record and
        adds is_wishlisted, is_favorite, is_archived attributes.
        
        Args:
            scraped_tenders: List of ScrapedTender objects to enrich
            
        Returns:
            The same list with added flag attributes
        """
        if not scraped_tenders:
            return []
        
        # Get all tender IDs
        tender_ids = [t.id for t in scraped_tenders]
        
        # Fetch all corresponding Tender records in one query
        tender_records = (
            self.db.query(Tender)
            .filter(Tender.id.in_(tender_ids))
            .all()
        )
        
        # Create a lookup dictionary for quick access
        tender_flags_map = {
            t.id: {
                'is_wishlisted': t.is_wishlisted,
                'is_favorite': t.is_favorite,
                'is_archived': t.is_archived
            }
            for t in tender_records
        }
        
        # Add flags to each ScrapedTender object
        for scraped_tender in scraped_tenders:
            flags = tender_flags_map.get(scraped_tender.id, {
                'is_wishlisted': False,
                'is_favorite': False,
                'is_archived': False
            })
            
            # Set attributes on the SQLAlchemy object
            # These will be picked up by model_validate
            scraped_tender.is_wishlisted = flags['is_wishlisted']
            scraped_tender.is_favorite = flags['is_favorite']
            scraped_tender.is_archived = flags['is_archived']
        
        return scraped_tenders

    def get_tender_by_id(self, tender_id: UUID) -> Optional[ScrapedTender]:
        """
        Get a single tender by its UUID, with all relationships loaded.
        Also enriches with action flags from the Tender table.
        """
        tender = (
            self.db.query(ScrapedTender)
            .filter(ScrapedTender.id == tender_id)
            .options(
                joinedload(ScrapedTender.files),
                joinedload(ScrapedTender.query)
            )
            .first()
        )
        
        if tender:
            # Enrich with flags
            self.enrich_scraped_tenders_with_flags([tender])
        
        return tender

    def get_tenders_by_ids(self, tender_ids: list[Column[UUID]]) -> list[ScrapedTender]:
        """
        Get a list of tenders by their UUIDs, with all relationships loaded.
        Also enriches with action flags from the Tender table.
        """
        if not tender_ids:
            return []
        tenders = (
            self.db.query(ScrapedTender)
            .filter(ScrapedTender.id.in_(tender_ids))
            .options(
                joinedload(ScrapedTender.files),
                joinedload(ScrapedTender.query)
            )
            .all()
        )
        
        # Enrich with flags
        return self.enrich_scraped_tenders_with_flags(tenders)

    def get_tenders_by_ids_tenderiq(self, tender_ids: list[Column[UUID]]) -> list[Tender]:
        """
        Get a list of tenders from the tenders table by their UUIDs, with all relationships loaded.
        """
        if not tender_ids:
            return []
        return (
            self.db.query(Tender)
            .filter(Tender.id.in_(tender_ids))
            .all()
        )

    def get_available_scrape_runs(self) -> list[ScrapeRun]:
        """
        Get all distinct scrape runs ordered by most recent first.
        Eagerly loads all relationships for efficient access.

        Used by frontend to populate date selector dropdown.

        Ordered by tender_release_date (when tenders were released),
        not run_at (when we scraped them).

        Returns:
            List of ScrapeRun objects with all relationships loaded
        """
        return (
            self.db.query(ScrapeRun)
            .order_by(ScrapeRun.tender_release_date.desc())
            .options(
                joinedload(ScrapeRun.queries).joinedload(ScrapedTenderQuery.tenders)
            )
            .all()
        )

    def get_scrape_runs_by_date_range(
        self, days: Optional[int] = None
    ) -> list[ScrapeRun]:
        """
        Get scrape runs from a specific date range based on tender_release_date.

        Uses tender_release_date (when tenders were released from website header),
        not run_at (when we scraped them), for consistent grouping.

        Args:
            days: Number of days to look back. None means all historical data.

        Returns:
            List of ScrapeRun objects ordered by tender_release_date DESC (newest first)

        Example:
            get_scrape_runs_by_date_range(5)  # Last 5 days of releases
            get_scrape_runs_by_date_range()   # All historical data
        """
        query = self.db.query(ScrapeRun)

        if days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            # Filter by tender_release_date, not run_at
            query = query.filter(ScrapeRun.tender_release_date >= cutoff_date.date())

        return query.order_by(ScrapeRun.tender_release_date.desc()).options(
            joinedload(ScrapeRun.queries).joinedload(ScrapedTenderQuery.tenders)
        ).all()

    def get_scrape_runs_by_specific_date(
        self, date: str  # Format: "YYYY-MM-DD"
    ) -> list[ScrapeRun]:
        """
        Get scrape run(s) for a specific date based on tender_release_date.

        Uses tender_release_date (when tenders were released from website header),
        not run_at (when we scraped them).

        Args:
            date: Date string in format "YYYY-MM-DD"

        Returns:
            List of ScrapeRun objects with all relationships loaded

        Raises:
            ValueError: If date format is invalid

        Example:
            get_scrape_runs_by_specific_date("2024-11-03")
        """
        try:
            from datetime import date as date_type
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(
                f"Invalid date format. Expected YYYY-MM-DD, got '{date}'"
            ) from e

        return (
            self.db.query(ScrapeRun)
            .filter(ScrapeRun.tender_release_date == target_date)
            .order_by(ScrapeRun.tender_release_date.desc())
            .options(
                joinedload(ScrapeRun.queries).joinedload(ScrapedTenderQuery.tenders)
            )
            .all()
        )

    def get_tenders_by_scrape_run(
        self,
        scrape_run_id,
        category: Optional[str] = None,
        location: Optional[str] = None,
        state: Optional[str] = None,
        tender_type: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> list[ScrapedTender]:
        """
        Get all tenders from a specific scrape run with optional filters.

        Args:
            scrape_run_id: UUID of the ScrapeRun
            category: Filter by query_name (e.g., "Civil", "Electrical")
            location: Filter by city
            min_value: Filter by minimum tender value (in crore)
            max_value: Filter by maximum tender value (in crore)

        Returns:
            List of ScrapedTender objects matching filters

        Example:
            get_tenders_by_scrape_run(run_id, category="Civil", location="Mumbai")
        """
        query = (
            self.db.query(ScrapedTender)
            .join(ScrapedTenderQuery)
            .filter(ScrapedTenderQuery.scrape_run_id == scrape_run_id)
            .options(
                joinedload(ScrapedTender.files),
                joinedload(ScrapedTender.query)
            )
        )

        if category:
            query = query.filter(ScrapedTenderQuery.query_name == category)

        if location:
            query = query.filter(ScrapedTender.city == location)

        if state:
            query = query.filter(ScrapedTender.state == state)

        if tender_type:
            query = query.filter(ScrapedTender.tender_type == tender_type)

        # Note: min_value and max_value are stored as strings in DB
        # Would need parsing for true numeric comparison
        # For now, leaving as extension point

        return query.all()

    def get_tenders_by_specific_date(
        self,
        date: str,  # Format: "YYYY-MM-DD"
        category: Optional[str] = None,
        location: Optional[str] = None,
        state: Optional[str] = None,
        tender_type: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> list[ScrapedTender]:
        """
        Get all tenders released on a specific date (tender_release_date).

        Uses tender_release_date (when tenders were released from website header),
        not run_at (when we scraped them).

        Args:
            date: Date string in format "YYYY-MM-DD"
            category: Filter by query_name
            location: Filter by city
            min_value: Filter by minimum tender value
            max_value: Filter by maximum tender value

        Returns:
            List of ScrapedTender objects from that date

        Raises:
            ValueError: If date format is invalid

        Example:
            get_tenders_by_specific_date("2024-11-03", category="Civil")
        """
        try:
            from datetime import datetime as dt, date as date_type

            # Parse the date string to date object (not datetime)
            target_date = dt.strptime(date, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(
                f"Invalid date format. Expected YYYY-MM-DD, got '{date}'"
            ) from e

        # Query for tenders released on this specific date using tender_release_date
        query = (
            self.db.query(ScrapedTender)
            .join(ScrapedTenderQuery)
            .join(ScrapeRun)
            .filter(ScrapeRun.tender_release_date == target_date)
            .options(
                joinedload(ScrapedTender.files),
                joinedload(ScrapedTender.query)
            )
        )

        if category:
            query = query.filter(ScrapedTenderQuery.query_name == category)

        if location:
            query = query.filter(ScrapedTender.city == location)

        if state:
            query = query.filter(ScrapedTender.state == state)

        if tender_type:
            query = query.filter(ScrapedTender.tender_type == tender_type)

        return query.all()

    def get_all_tenders_with_filters(
        self,
        category: Optional[str] = None,
        location: Optional[str] = None,
        state: Optional[str] = None,
        tender_type: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> list[ScrapedTender]:
        """
        Get all tenders in the system with optional filters.

        Args:
            category: Filter by query_name
            location: Filter by city
            min_value: Filter by minimum tender value
            max_value: Filter by maximum tender value

        Returns:
            List of all ScrapedTender objects matching filters
        """
        query = self.db.query(ScrapedTender).options(
            joinedload(ScrapedTender.files),
            joinedload(ScrapedTender.query)
        )

        if category:
            query = query.join(ScrapedTenderQuery).filter(
                ScrapedTenderQuery.query_name == category
            )

        if location:
            query = query.filter(ScrapedTender.city == location)

        if state:
            query = query.filter(ScrapedTender.state == state)

        if tender_type:
            query = query.filter(ScrapedTender.tender_type == tender_type)

        return query.all()
