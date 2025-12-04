"""
TenderIQ Date Filtering Service

Phase TenderIQ: Service layer for filtering tenders by date and other criteria.

This service handles business logic for:
- Getting available scrape dates
- Filtering tenders by date range
- Filtering tenders by specific date
- Applying additional filters (category, location, value)
"""

import re
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

from app.modules.analyze.db.schema import AnalysisStatusEnum
from app.modules.tenderiq.db.repository import TenderRepository, TenderWishlistRepository
from app.modules.tenderiq.db.tenderiq_repository import TenderIQRepository
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.tenderiq.db.schema import TenderActionHistory, TenderActionEnum, Tender as TenderModel
from app.modules.tenderiq.models.pydantic_models import (
    AvailableDatesResponse,
    FilteredTendersResponse,
    HistoryAndWishlistResponse,
    HistoryData,
    HistoryDataResultsEnum,
    ScrapeDateInfo,
    ScrapedTenderRead,
    ScrapedTenderRead,
    Tender,
    DailyTendersResponse,
    ScrapedTenderQuery,
    TenderAnalysisRead,
)
from app.modules.tenderiq.repositories import analysis as analysis_repo
from app.modules.tenderiq.repositories import repository as tender_repo


def normalize_date_format(date_str: Optional[str]) -> str:
    """
    Converts various date formats to a standard ISO-like format (YYYY-MM-DD).
    Handles: DD-MM-YYYY, DD/MM/YYYY, DD-Mon-YYYY, ISO formats, and others.
    Returns empty string if date cannot be parsed.
    """
    if not date_str or not isinstance(date_str, str):
        return ""
    
    date_str = date_str.strip()
    if not date_str:
        return ""
    
    try:
        # First, try explicit DD-MM-YYYY format (most common in India)
        if len(date_str) == 10 and date_str.count('-') == 2:
            parts = date_str.split('-')
            if all(p.isdigit() for p in parts):
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                    from datetime import datetime as dt
                    parsed_date = dt(year, month, day)
                    return parsed_date.strftime("%Y-%m-%d")
        
        # Try dateutil parser for flexible parsing
        parsed_date = date_parser.parse(date_str, dayfirst=True)
        return parsed_date.strftime("%Y-%m-%d")
    except Exception:
        pass
    
    # If all parsing fails, return the original string (frontend will handle it)
    return date_str


class TenderFilterService:
    """Service for filtering and retrieving tenders by date and other criteria"""

    def __init__(self):
        """Initialize the service"""
        pass

    def get_wishlisted_tenders_with_history(self, db: Session, user_id: UUID) -> HistoryAndWishlistResponse:
        """
        Get wishlisted tenders with history for a specific user.
        Deduplicates entries to ensure each tender appears only once.
        """
        wishlist_repo = TenderWishlistRepository(db)
        user_wishlist = wishlist_repo.get_user_wishlist(user_id)
        history_data_list: List[HistoryData] = []
        
        # Additional deduplication by tender_ref_number to ensure uniqueness
        seen_tender_refs = set()
        repo = TenderIQRepository(db)

        for wishlist_entry in user_wishlist:
            tender_ref = wishlist_entry.tender_ref_number
            
            # Skip if we've already processed this tender_ref_number
            if tender_ref in seen_tender_refs:
                continue
            seen_tender_refs.add(tender_ref)
            
            # Get the tender and scraped tender data
            tender = db.query(TenderModel).filter(TenderModel.tender_ref_number == tender_ref).first()
            
            # Get the most recent ScrapedTender from the last 7 days
            # This ensures consistency with what the Live Tenders page shows
            from app.modules.scraper.db.schema import ScrapeRun, ScrapedTenderQuery
            from datetime import timezone
            
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            scraped_tender = db.query(ScrapedTender).join(
                ScrapedTenderQuery, ScrapedTender.query_id == ScrapedTenderQuery.id, isouter=True
            ).join(
                ScrapeRun, ScrapedTenderQuery.scrape_run_id == ScrapeRun.id, isouter=True
            ).filter(
                ScrapedTender.tender_id_str == tender_ref,
                ScrapeRun.run_at >= seven_days_ago
            ).order_by(
                desc(ScrapeRun.run_at)
            ).first()
            
            # If no recent scrape found, fall back to finding any scraped tender
            if not scraped_tender:
                scraped_tender = db.query(ScrapedTender).filter(
                    ScrapedTender.tender_id_str == tender_ref
                ).order_by(
                    desc(ScrapedTender.id)  # Order by ID as fallback
                ).first()
            
            if not tender:
                logger.warning(f"Tender not found for tender_ref: {tender_ref}, skipping...")
                continue
                
            analysis = analysis_repo.get_analysis_data(db, tender_ref)
            
            # Sync analysis progress to wishlist if analysis exists and is more up-to-date
            if analysis is not None:
                from app.modules.analyze.db.schema import AnalysisStatusEnum
                analysis_complete = analysis.status == AnalysisStatusEnum.completed
                analysis_progress = analysis.progress or 0
                
                # Update wishlist if analysis progress is more recent or analysis is complete
                if (analysis_progress > wishlist_entry.progress) or (analysis_complete and not wishlist_entry.analysis_state):
                    try:
                        wishlist_repo.update_wishlist_progress(
                            wishlist_entry.id,
                            progress=analysis_progress,
                            analysis_state=analysis_complete,
                            status_message=analysis.status_message or wishlist_entry.status_message
                        )
                        # Refresh wishlist entry to get updated values
                        db.refresh(wishlist_entry)
                    except Exception as e:
                        logger.warning(f"Failed to sync analysis progress to wishlist {wishlist_entry.id}: {e}")
            
            # Use wishlist entry data or fallback to tender data
            title = wishlist_entry.title or tender.tender_title or ''
            authority = wishlist_entry.authority or tender.employer_name or ''
            value = wishlist_entry.value or (float(tender.estimated_cost) if tender.estimated_cost else 0)
            emd = wishlist_entry.emd or (float(tender.bid_security) if tender.bid_security else 0)
            due_date = wishlist_entry.due_date or ''
            category = wishlist_entry.category or tender.category or ''
            
            if scraped_tender:
                value = self._convert_word_currency_to_number(str(scraped_tender.value)) if scraped_tender.value else value
                emd = self._convert_word_currency_to_number(str(scraped_tender.emd)) if scraped_tender.emd else emd
                due_date = str(scraped_tender.due_date) if scraped_tender.due_date else due_date
            
            # Determine analysis_state: use wishlist entry's analysis_state, or derive from analysis status
            from app.modules.analyze.db.schema import AnalysisStatusEnum
            if wishlist_entry.analysis_state:
                analysis_state = AnalysisStatusEnum.completed
            elif analysis:
                analysis_state = analysis.status
            else:
                analysis_state = AnalysisStatusEnum.pending
            
            # Use tender.id (from Tender table - stable across all scrape runs)
            # This avoids ID mismatches when user views old scrape runs but wishlist shows newer ones
            # The TenderDetails endpoint can handle both Tender IDs and ScrapedTender IDs via dual lookup
            tender_id = None
            if tender and tender.id:
                tender_id = str(tender.id)
            
            if not tender_id:
                logger.warning(f"Failed to get valid tender ID for tender_ref {tender_ref}, skipping...")
                continue
            
            history_data = HistoryData(
                id=tender_id,
                title=title,
                authority=authority,
                value=int(value),
                emd=int(emd),
                due_date=due_date,
                category=category,
                progress=wishlist_entry.progress if wishlist_entry.progress is not None else (analysis.progress if analysis else 0),
                analysis_state=analysis_state,
                synopsis_state=wishlist_entry.synopsis_state,
                evaluated_state=wishlist_entry.evaluated_state,
                results=HistoryDataResultsEnum(wishlist_entry.results) if wishlist_entry.results else HistoryDataResultsEnum.PENDING,
                analysis_details=TenderAnalysisRead.model_validate(analysis) if analysis else None,
                full_scraped_details=ScrapedTenderRead.model_validate(scraped_tender) if scraped_tender else None
            )
            history_data_list.append(history_data)

        return HistoryAndWishlistResponse(
            tenders=history_data_list,
            report_file_url="https://tenderiq.s3.amazonaws.com/2023/05/09/4b7b4c9b-9d3d-4e8a-9e3e-8b6e5f1a2b3c/wishlist_report.pdf",
        )

    def get_tender_details(self, db: Session, tender_id: UUID) -> Optional[Tender]:
        """
        Get full details for a single tender by its ID.
        Supports both Tender IDs and ScrapedTender IDs for lookup.
        
        First tries to find the ID in ScrapedTender table (preferred),
        then falls back to Tender table for stable IDs from wishlist.
        """
        repo = TenderIQRepository(db)
        
        # Try to get by ScrapedTender ID first (IDs from Live Tenders)
        tender = repo.get_tender_by_id(tender_id)
        if tender:
            # Normalize dates before returning
            tender_dict = Tender.model_validate(tender).model_dump()
            
            # Normalize all date fields
            date_fields = ["publish_date", "due_date", "last_date_of_bid_submission", "tender_opening_date"]
            for field in date_fields:
                if field in tender_dict and tender_dict[field]:
                    tender_dict[field] = normalize_date_format(tender_dict[field])
            
            return Tender.model_validate(tender_dict)
        
        # Fallback: try to find by Tender ID (stable IDs from wishlist)
        tender_obj = db.query(TenderModel).filter(TenderModel.id == tender_id).first()
        if not tender_obj:
            return None
        
        # If found by Tender ID, get the most recent ScrapedTender for display
        # This ensures we show current data, not stale Tender data
        scraped_tender = db.query(ScrapedTender).filter(
            ScrapedTender.tender_id_str == tender_obj.tender_ref_number
        ).order_by(
            desc(ScrapedTender.created_at) if hasattr(ScrapedTender, 'created_at') else desc(ScrapedTender.id)
        ).first()
        
        if scraped_tender:
            tender_dict = Tender.model_validate(scraped_tender).model_dump()
        else:
            tender_dict = Tender.model_validate(tender_obj).model_dump()
        
        # Normalize all date fields
        date_fields = ["publish_date", "due_date", "last_date_of_bid_submission", "tender_opening_date"]
        for field in date_fields:
            if field in tender_dict and tender_dict[field]:
                tender_dict[field] = normalize_date_format(tender_dict[field])
        
        return Tender.model_validate(tender_dict)

    def _get_tenders_by_user_action(self, db: Session, user_id: UUID, positive_action: TenderActionEnum, negative_action: TenderActionEnum) -> list[Tender]:
        """Helper to get all tenders where a user has performed a specific action (checking most recent action per tender)."""
        from sqlalchemy import and_, func
        
        # Get all action history entries for this user and these action types
        # We need to find the most recent action per tender for this user
        subquery = (
            db.query(
                TenderActionHistory.tender_id,
                func.max(TenderActionHistory.timestamp).label('max_timestamp')
            )
            .filter(
                and_(
                    TenderActionHistory.user_id == user_id,
                    TenderActionHistory.action.in_([positive_action, negative_action])
                )
            )
            .group_by(TenderActionHistory.tender_id)
            .subquery()
        )
        
        # Get the actual action history entries matching the most recent timestamps
        action_histories = (
            db.query(TenderActionHistory)
            .join(
                subquery,
                and_(
                    TenderActionHistory.tender_id == subquery.c.tender_id,
                    TenderActionHistory.timestamp == subquery.c.max_timestamp
                )
            )
            .filter(
                and_(
                    TenderActionHistory.user_id == user_id,
                    TenderActionHistory.action == positive_action  # Only get tenders where most recent action is positive
                )
            )
            .all()
        )
        
        if not action_histories:
            return []
        
        # Get unique tender IDs
        tender_ids = list(set([h.tender_id for h in action_histories]))
        
        # Get the tenders
        tenders = db.query(TenderModel).filter(TenderModel.id.in_(tender_ids)).all()
        tender_ref_numbers = [t.tender_ref_number for t in tenders if t.tender_ref_number]
        
        if not tender_ref_numbers:
            return []
        
        # Get scraped tenders
        scraped_tender_repo = TenderIQRepository(db)
        scraped_tenders = scraped_tender_repo.db.query(ScrapedTender).filter(
            ScrapedTender.tender_id_str.in_(tender_ref_numbers)
        ).all()
        
        return [Tender.model_validate(t) for t in scraped_tenders]

    def get_wishlisted_tenders(self, db: Session, user_id: UUID) -> list[Tender]:
        """Gets all tenders that are wishlisted by the specified user."""
        wishlist_repo = TenderWishlistRepository(db)
        user_wishlist = wishlist_repo.get_user_wishlist(user_id)
        
        if not user_wishlist:
            return []
        
        tender_ref_numbers = [entry.tender_ref_number for entry in user_wishlist]
        scraped_tender_repo = TenderIQRepository(db)
        scraped_tenders = scraped_tender_repo.db.query(ScrapedTender).filter(
            ScrapedTender.tender_id_str.in_(tender_ref_numbers)
        ).all()
        
        return [Tender.model_validate(t) for t in scraped_tenders]

    def get_archived_tenders(self, db: Session, user_id: UUID) -> list[Tender]:
        """Gets all tenders that are archived by the specified user."""
        return self._get_tenders_by_user_action(db, user_id, TenderActionEnum.archived, TenderActionEnum.unarchived)

    def get_favorited_tenders(self, db: Session, user_id: UUID) -> list[Tender]:
        """Gets all tenders that are marked as favorite by the specified user."""
        return self._get_tenders_by_user_action(db, user_id, TenderActionEnum.favorited, TenderActionEnum.unfavorited)

    def get_available_dates(self, db: Session) -> AvailableDatesResponse:
        """
        Get all available scrape dates with tender counts.

        Used by frontend to populate date selector dropdown.

        Tenders are grouped by tender_release_date (when they were released),
        not by run_at (when we scraped them).

        Args:
            db: SQLAlchemy database session

        Returns:
            AvailableDatesResponse with list of all available dates and tender counts
        """
        repo = TenderIQRepository(db)
        scrape_runs = repo.get_available_scrape_runs()

        dates_info = []
        is_first = True  # Mark the first (newest) as latest

        for scrape_run in scrape_runs:
            # Count total tenders across all queries in this scrape run
            tender_count = sum(len(query.tenders) for query in scrape_run.queries)

            # Use tender_release_date (when tenders were actually released from website header)
            # This is the canonical date for grouping - not when we scraped them
            date_str = scrape_run.date_str
            tender_release_date = scrape_run.tender_release_date

            # Format the tender_release_date to YYYY-MM-DD
            date_only = tender_release_date.strftime("%Y-%m-%d") if tender_release_date else ""

            date_obj = ScrapeDateInfo(
                date=date_only,
                date_str=date_str,
                run_at=scrape_run.run_at,
                tender_count=tender_count,
                is_latest=is_first,
            )
            dates_info.append(date_obj)
            is_first = False

        return AvailableDatesResponse(dates=dates_info)

    def get_latest_tenders(
        self,
        db: Session,
        category: Optional[str] = None,
        location: Optional[str] = None,
        state: Optional[str] = None,
        tender_type: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> DailyTendersResponse:
        """
        Get the latest (most recent) scrape run with optional filters.
        Returns in DailyTendersResponse format (hierarchical by scrape run and query).

        This is the default behavior when /tenders is called without parameters,
        matching the behavior of /dailytenders.

        Args:
            db: SQLAlchemy database session
            category: Filter by query_name (category)
            location: Filter by city
            min_value: Filter by minimum tender value
            max_value: Filter by maximum tender value

        Returns:
            DailyTendersResponse with tenders organized by scrape run and query

        Raises:
            ValueError: If no scrape runs found
        """
        repo = TenderIQRepository(db)

        # Get the latest scrape run
        scrape_runs = repo.get_scrape_runs_by_date_range(days=None)

        if scrape_runs:
            return self._scrape_run_to_daily_response(
                scrape_runs[0],
                category=category,
                location=location,
                state=state,
                tender_type=tender_type,
                min_value=min_value,
                max_value=max_value,
            )

        raise ValueError("No tenders found in the database")

    def get_tenders_by_date_range(
        self,
        db: Session,
        date_range: str,
        category: Optional[str] = None,
        location: Optional[str] = None,
        state: Optional[str] = None,
        tender_type: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> DailyTendersResponse:
        """
        Get tenders from a relative date range (e.g., "last 5 days").
        Returns in DailyTendersResponse format (hierarchical by scrape run and query).
        Aggregates tenders from ALL scrape runs in the date range.

        Args:
            db: SQLAlchemy database session
            date_range: One of "last_1_day", "last_5_days", "last_7_days", "last_30_days"
            category: Filter by query_name (category)
            location: Filter by city
            min_value: Filter by minimum tender value
            max_value: Filter by maximum tender value

        Returns:
            DailyTendersResponse with tenders organized by scrape run and query

        Raises:
            ValueError: If invalid date_range is provided
        """
        # Map date range strings to days
        range_to_days = {
            "last_1_day": 1,
            "last_2_days": 2,
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
        repo = TenderIQRepository(db)

        # Get ALL scrape runs in the date range
        scrape_runs = repo.get_scrape_runs_by_date_range(days=days)

        if not scrape_runs:
            raise ValueError(f"No tenders found for date range: {date_range}")

        # Aggregate queries and tenders from ALL scrape runs
        aggregated_queries = []
        seen_query_ids = set()
        
        for scrape_run in scrape_runs:
            for query in scrape_run.queries:
                # Avoid duplicate queries from different runs
                if query.id in seen_query_ids:
                    continue
                seen_query_ids.add(query.id)
                
                # Skip if category filter is specified and doesn't match
                if category and query.query_name.lower() != category.lower():
                    continue

                # Filter tenders in this query
                filtered_tenders = self._filter_tenders(
                    query.tenders,
                    location=location,
                    state=state,
                    tender_type=tender_type,
                    min_value=min_value,
                    max_value=max_value,
                )

                # Only include query if it has matching tenders
                if filtered_tenders:
                    aggregated_queries.append({
                        "id": query.id,
                        "query_name": query.query_name,
                        "number_of_tenders": str(len(filtered_tenders)),
                        "tenders": filtered_tenders,
                    })

        # Create DailyTendersResponse using the latest scrape run as metadata
        # but with aggregated tenders from all runs
        latest_run = scrape_runs[0]
        return DailyTendersResponse(
            id=latest_run.id,
            run_at=latest_run.run_at,
            date_str=f"{date_range} (aggregated)",
            name=latest_run.name,
            contact=latest_run.contact,
            no_of_new_tenders=str(
                sum(int(q["number_of_tenders"]) for q in aggregated_queries)
            ),
            company=latest_run.company,
            queries=aggregated_queries,
        )

    def get_tenders_by_specific_date(
        self,
        db: Session,
        date: str,  # Format: "YYYY-MM-DD"
        category: Optional[str] = None,
        location: Optional[str] = None,
        state: Optional[str] = None,
        tender_type: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> DailyTendersResponse:
        """
        Get tenders from a specific date.
        Returns in DailyTendersResponse format (hierarchical by scrape run and query).

        Args:
            db: SQLAlchemy database session
            date: Date string in format "YYYY-MM-DD"
            category: Filter by query_name
            location: Filter by city
            min_value: Filter by minimum tender value
            max_value: Filter by maximum tender value

        Returns:
            DailyTendersResponse with tenders from that date

        Raises:
            ValueError: If date format is invalid
        """
        repo = TenderIQRepository(db)

        # Get scrape run for the specific date
        scrape_runs = repo.get_scrape_runs_by_specific_date(date)

        if scrape_runs:
            return self._scrape_run_to_daily_response(
                scrape_runs[0],
                category=category,
                location=location,
                state=state,
                tender_type=tender_type,
                min_value=min_value,
                max_value=max_value,
            )

        raise ValueError(f"No tenders found for date: {date}")

    def get_all_tenders(
        self,
        db: Session,
        category: Optional[str] = None,
        location: Optional[str] = None,
        state: Optional[str] = None,
        tender_type: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> DailyTendersResponse:
        """
        Get all historical tenders with optional filters.
        Returns in DailyTendersResponse format (hierarchical by scrape run and query).

        Args:
            db: SQLAlchemy database session
            category: Filter by query_name
            location: Filter by city
            min_value: Filter by minimum tender value
            max_value: Filter by maximum tender value

        Returns:
            DailyTendersResponse with all tenders
        """
        repo = TenderIQRepository(db)

        # Get all scrape runs
        scrape_runs = repo.get_scrape_runs_by_date_range(days=None)

        # Return the latest scrape run with filters applied
        if scrape_runs:
            return self._scrape_run_to_daily_response(
                scrape_runs[0],
                category=category,
                location=location,
                state=state,
                tender_type=tender_type,
                min_value=min_value,
                max_value=max_value,
            )

        raise ValueError("No tenders found in the database")

    # ==================== Helper Methods ====================

    def _convert_word_currency_to_number(self, word: str) -> float:
        """
        Convert a word to a number in crore, lakh, thuosand (e.g., "6.6 crore" -> 66000000).

        Args:
            word: Word to convert

        Returns:
            Number in float
        """
        word = word.lower()
        if "crore" in word:
            number_str = re.sub("[^0-9.]", "", word)
            return float(number_str) * 10000000
        elif "lakh" in word:
            number_str = re.sub("[^0-9.]", "", word)
            return float(number_str) * 100000
        elif "thousand" in word:
            number_str = re.sub("[^0-9.]", "", word)
            return float(number_str) * 1000
        else:
            word = word.split(".")[0]
            regexed = re.sub("[^0-9.]", "", word)
            if regexed:
                return float(regexed)

            return 0.0


    def _get_available_dates_list(self, db: Session) -> list[str]:
        """
        Get list of all available dates as strings (YYYY-MM-DD format).

        Uses tender_release_date (when tenders were released), not run_at (when we scraped them).

        Args:
            db: SQLAlchemy database session

        Returns:
            List of date strings
        """
        repo = TenderIQRepository(db)
        scrape_runs = repo.get_available_scrape_runs()

        dates_list = []
        for run in scrape_runs:
            # Use tender_release_date for consistent grouping by tender release date
            tender_release_date = run.tender_release_date
            if tender_release_date:
                dates_list.append(tender_release_date.strftime("%Y-%m-%d"))

        return dates_list


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

    def _scrape_run_to_daily_response(
        self,
        scrape_run,
        category: Optional[str] = None,
        location: Optional[str] = None,
        state: Optional[str] = None,
        tender_type: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> DailyTendersResponse:
        """
        Convert a scrape run ORM object to DailyTendersResponse format.
        Applies optional filters to the tenders within each query.

        Args:
            scrape_run: ScrapeRun ORM object with queries and tenders loaded
            category: Filter by query_name
            location: Filter by city
            state: Filter by state
            tender_type: Filter by tender type
            min_value: Filter by minimum tender value (crore)
            max_value: Filter by maximum tender value (crore)

        Returns:
            DailyTendersResponse with hierarchical structure
        """
        # Filter and convert queries
        filtered_queries = []

        for query in scrape_run.queries:
            # Skip if category filter is specified and doesn't match
            if category and query.query_name.lower() != category.lower():
                continue

            # Filter tenders in this query
            filtered_tenders = self._filter_tenders(
                query.tenders,
                location=location,
                state=state,
                tender_type=tender_type,
                min_value=min_value,
                max_value=max_value,
            )

            # Only include query if it has matching tenders
            if filtered_tenders:
                filtered_queries.append({
                    "id": query.id,
                    "query_name": query.query_name,
                    "number_of_tenders": str(len(filtered_tenders)),
                    "tenders": filtered_tenders,
                })

        # Create DailyTendersResponse from scrape run
        return DailyTendersResponse(
            id=scrape_run.id,
            run_at=scrape_run.run_at,
            date_str=scrape_run.date_str,
            name=scrape_run.name,
            contact=scrape_run.contact,
            no_of_new_tenders=str(
                sum(len(q["tenders"]) for q in filtered_queries)
            ),
            company=scrape_run.company,
            queries=[ScrapedTenderQuery(**q) for q in filtered_queries],
        )

    def _filter_tenders(
        self,
        tenders,
        location: Optional[str] = None,
        state: Optional[str] = None,
        tender_type: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> list:
        """
        Filter a list of tenders based on criteria.

        Args:
            tenders: List of ScrapedTender ORM objects
            location: Filter by city
            state: Filter by state
            tender_type: Filter by tender type
            min_value: Filter by minimum tender value (crore)
            max_value: Filter by maximum tender value (crore)

        Returns:
            Filtered list of ScrapedTender objects
        """
        # Hidden tender names that should not be displayed
        HIDDEN_TENDER_NAMES = ['Military Engineer Services']

        filtered = []

        for tender in tenders:
            # Skip hidden tenders
            if tender.tender_name in HIDDEN_TENDER_NAMES:
                continue
            # Location filter
            if location and tender.city.lower() != location.lower():
                continue

            # State filter
            if state and tender.state and tender.state.lower() != state.lower():
                continue

            # Tender type filter
            if tender_type and tender.tender_type and tender.tender_type.lower() != tender_type.lower():
                continue

            # Value range filters
            if min_value is not None or max_value is not None:
                # Parse tender value if available
                try:
                    tender_val = self._parse_tender_value(tender.value)
                    if min_value is not None and tender_val < min_value:
                        continue
                    if max_value is not None and tender_val > max_value:
                        continue
                except (ValueError, TypeError):
                    # If value can't be parsed, skip value filter
                    pass

            filtered.append(tender)

        return filtered

    def _parse_tender_value(self, value_str: str) -> float:
        """
        Parse tender value string to float (in crore).

        Handles formats like:
        - "250 Crore"
        - "100 Lakh"
        - "50000000"

        Args:
            value_str: Tender value string

        Returns:
            Value in crore as float

        Raises:
            ValueError: If value cannot be parsed
        """
        if not value_str:
            raise ValueError("Empty value string")

        value_str = value_str.strip().lower()

        # Handle crore
        if "crore" in value_str:
            num_str = value_str.replace("crore", "").strip()
            return float(num_str)

        # Handle lakh (convert to crore)
        if "lakh" in value_str:
            num_str = value_str.replace("lakh", "").strip()
            return float(num_str) / 100.0

        # Try parsing as raw number
        return float(value_str) / 10000000.0  # Convert to crore
