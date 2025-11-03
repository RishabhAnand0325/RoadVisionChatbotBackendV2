"""
TenderIQ Date Filtering Service

Phase TenderIQ: Service layer for filtering tenders by date and other criteria.

This service handles business logic for:
- Getting available scrape dates
- Filtering tenders by date range
- Filtering tenders by specific date
- Applying additional filters (category, location, value)
"""

from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.modules.scraper.db.repository import ScraperRepository
from app.modules.tenderiq.models.pydantic_models import (
    AvailableDatesResponse,
    FilteredTendersResponse,
    ScrapeDateInfo,
    TenderResponseForFiltering,
)


class TenderFilterService:
    """Service for filtering and retrieving tenders by date and other criteria"""

    def __init__(self):
        """Initialize the service"""
        pass

    def get_available_dates(self, db: Session) -> AvailableDatesResponse:
        """
        Get all available scrape dates with tender counts.

        Used by frontend to populate date selector dropdown.

        Args:
            db: SQLAlchemy database session

        Returns:
            AvailableDatesResponse with list of all available dates and tender counts
        """
        repo = ScraperRepository(db)
        scrape_runs = repo.get_available_scrape_runs()

        dates_info = []
        is_first = True  # Mark the first (newest) as latest

        for scrape_run in scrape_runs:
            # Count total tenders across all queries in this scrape run
            tender_count = sum(len(query.tenders) for query in scrape_run.queries)

            # Use run_at timestamp for consistent date derivation
            # This ensures date (YYYY-MM-DD) and date_str are derived from the same source
            date_only = scrape_run.run_at.strftime("%Y-%m-%d")
            date_str_formatted = scrape_run.run_at.strftime("%A, %B %d, %Y")

            date_obj = ScrapeDateInfo(
                date=date_only,
                date_str=date_str_formatted,
                run_at=scrape_run.run_at,
                tender_count=tender_count,
                is_latest=is_first,
            )
            dates_info.append(date_obj)
            is_first = False

        return AvailableDatesResponse(dates=dates_info)

    def get_tenders_by_date_range(
        self,
        db: Session,
        date_range: str,
        category: Optional[str] = None,
        location: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> FilteredTendersResponse:
        """
        Get tenders from a relative date range (e.g., "last 5 days").

        Args:
            db: SQLAlchemy database session
            date_range: One of "last_1_day", "last_5_days", "last_7_days", "last_30_days"
            category: Filter by query_name (category)
            location: Filter by city
            min_value: Filter by minimum tender value
            max_value: Filter by maximum tender value

        Returns:
            FilteredTendersResponse with tenders and metadata

        Raises:
            ValueError: If invalid date_range is provided
        """
        # Map date range strings to days
        range_to_days = {
            "last_1_day": 1,
            "last_5_days": 5,
            "last_7_days": 7,
            "last_30_days": 30,
        }

        if date_range not in range_to_days:
            raise ValueError(
                f"Invalid date_range: {date_range}. "
                f"Must be one of: {', '.join(range_to_days.keys())}"
            )

        days = range_to_days[date_range]
        repo = ScraperRepository(db)

        # Get all tenders from scrape runs in the date range
        all_tenders = []
        scrape_runs = repo.get_scrape_runs_by_date_range(days=days)

        for scrape_run in scrape_runs:
            tenders = repo.get_tenders_by_scrape_run(
                scrape_run.id,
                category=category,
                location=location,
                min_value=min_value,
                max_value=max_value,
            )
            all_tenders.extend(tenders)

        # Build response
        available_dates = self._get_available_dates_list(db)
        filtered_by = {
            "date_range": date_range,
        }
        if category:
            filtered_by["category"] = category
        if location:
            filtered_by["location"] = location

        return FilteredTendersResponse(
            tenders=[self._tender_to_response(t) for t in all_tenders],
            total_count=len(all_tenders),
            filtered_by=filtered_by,
            available_dates=available_dates,
        )

    def get_tenders_by_specific_date(
        self,
        db: Session,
        date: str,  # Format: "YYYY-MM-DD"
        category: Optional[str] = None,
        location: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> FilteredTendersResponse:
        """
        Get tenders from a specific date.

        Args:
            db: SQLAlchemy database session
            date: Date string in format "YYYY-MM-DD"
            category: Filter by query_name
            location: Filter by city
            min_value: Filter by minimum tender value
            max_value: Filter by maximum tender value

        Returns:
            FilteredTendersResponse with tenders from that date

        Raises:
            ValueError: If date format is invalid
        """
        repo = ScraperRepository(db)

        try:
            tenders = repo.get_tenders_by_specific_date(
                date=date,
                category=category,
                location=location,
                min_value=min_value,
                max_value=max_value,
            )
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")

        # Build response
        available_dates = self._get_available_dates_list(db)
        filtered_by = {
            "date": date,
        }
        if category:
            filtered_by["category"] = category
        if location:
            filtered_by["location"] = location

        return FilteredTendersResponse(
            tenders=[self._tender_to_response(t) for t in tenders],
            total_count=len(tenders),
            filtered_by=filtered_by,
            available_dates=available_dates,
        )

    def get_all_tenders(
        self,
        db: Session,
        category: Optional[str] = None,
        location: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> FilteredTendersResponse:
        """
        Get all historical tenders with optional filters.

        Args:
            db: SQLAlchemy database session
            category: Filter by query_name
            location: Filter by city
            min_value: Filter by minimum tender value
            max_value: Filter by maximum tender value

        Returns:
            FilteredTendersResponse with all tenders
        """
        repo = ScraperRepository(db)

        tenders = repo.get_all_tenders_with_filters(
            category=category,
            location=location,
            min_value=min_value,
            max_value=max_value,
        )

        # Build response
        available_dates = self._get_available_dates_list(db)
        filtered_by = {
            "include_all_dates": True,
        }
        if category:
            filtered_by["category"] = category
        if location:
            filtered_by["location"] = location

        return FilteredTendersResponse(
            tenders=[self._tender_to_response(t) for t in tenders],
            total_count=len(tenders),
            filtered_by=filtered_by,
            available_dates=available_dates,
        )

    # ==================== Helper Methods ====================

    def _get_available_dates_list(self, db: Session) -> list[str]:
        """
        Get list of all available dates as strings (YYYY-MM-DD format).

        Args:
            db: SQLAlchemy database session

        Returns:
            List of date strings
        """
        repo = ScraperRepository(db)
        scrape_runs = repo.get_available_scrape_runs()
        return [run.run_at.strftime("%Y-%m-%d") for run in scrape_runs]

    def _tender_to_response(self, tender) -> TenderResponseForFiltering:
        """
        Convert a ScrapedTender ORM object to a response model.

        Args:
            tender: ScrapedTender ORM object

        Returns:
            TenderResponseForFiltering response model
        """
        return TenderResponseForFiltering(
            id=tender.id,
            tender_id_str=tender.tender_id_str,
            tender_name=tender.tender_name,
            tender_url=tender.tender_url,
            city=tender.city,
            value=tender.value,
            due_date=tender.due_date,
            summary=tender.summary,
            query_name=None,  # Would need to load from relationship
            tender_type=tender.tender_type,
            tender_value=tender.tender_value,
            state=tender.state,
            publish_date=tender.publish_date,
            last_date_of_bid_submission=tender.last_date_of_bid_submission,
        )

    def validate_date_format(self, date_str: str) -> bool:
        """
        Validate that a date string is in YYYY-MM-DD format.

        Args:
            date_str: Date string to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
