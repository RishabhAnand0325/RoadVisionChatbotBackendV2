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
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.modules.analyze.db.schema import AnalysisStatusEnum
from app.modules.tenderiq.db.repository import TenderRepository
from app.modules.tenderiq.db.tenderiq_repository import TenderIQRepository
from app.modules.tenderiq.models.pydantic_models import (
    AvailableDatesResponse,
    FilteredTendersResponse,
    HistoryAndWishlistResponse,
    HistoryData,
    HistoryDataResultsEnum,
    ScrapeDateInfo,
    ScrapedTenderRead,
    Tender,
    DailyTendersResponse,
    ScrapedTenderQuery,
    TenderAnalysisRead,
)
from app.modules.tenderiq.repositories import analysis as analysis_repo
from app.modules.tenderiq.repositories import repository as tender_repo


class TenderFilterService:
    """Service for filtering and retrieving tenders by date and other criteria"""

    def __init__(self):
        """Initialize the service"""
        pass

    def get_wishlisted_tenders_with_history(self, db: Session) -> HistoryAndWishlistResponse:
        """
        Get wishlisted tenders with history.
        """
        repo = TenderIQRepository(db)
        wishlist = repo.get_wishlisted_tenders()
        history_data_list: List[HistoryData] = []

        for tender in wishlist:
            tenders_table = tender.tuple()[0]
            scraped_tender_table = tender.tuple()[1]
            analysis = analysis_repo.get_analysis_data(db, str(tenders_table.tender_ref_number))
            
            # Build full_scraped_details by merging scraped_tender_table and Tender table extras
            full_scraped = None
            if scraped_tender_table:
                # start with scraped model dict
                try:
                    scraped_dict = ScrapedTenderRead.model_validate(scraped_tender_table).model_dump()
                except Exception:
                    # fallback: shallow attribute extraction
                    scraped_dict = {k: getattr(scraped_tender_table, k, None) for k in dir(scraped_tender_table) if not k.startswith('_')}

                # Extract engineering metrics from analysis or tender table
                length_km = None
                road_work_amount = None
                structure_work_amount = None
                span_length = None
                
                # FIRST PRIORITY: Try to extract from analysis scope_of_work_json project_details
                if analysis and analysis.scope_of_work_json:
                    try:
                        scope = analysis.scope_of_work_json
                        if isinstance(scope, dict) and 'project_details' in scope:
                            details = scope['project_details']
                            if isinstance(details, dict):
                                # Get numeric fields directly (new AI-extracted values)
                                length_km = details.get('road_length_km') or details.get('total_length_km')
                                span_length = details.get('span_length_m')
                                road_work_amount = details.get('road_work_value_cr')
                                structure_work_amount = details.get('structure_work_value_cr')
                                
                                # If not found in numeric fields, try parsing from text fields
                                if not length_km:
                                    total_length_str = details.get('total_length', '')
                                    if total_length_str and 'km' in str(total_length_str).lower():
                                        import re
                                        match = re.search(r'([\d.,]+)\s*km', str(total_length_str), re.IGNORECASE)
                                        if match:
                                            length_km = float(match.group(1).replace(',', ''))
                    except Exception as e:
                        print(f"Error extracting from scope_of_work: {e}")

                # Fallback to Tender table if analysis didn't have these values
                if length_km is None:
                    length_km = float(tenders_table.length_km) if getattr(tenders_table, 'length_km', None) is not None else None
                if span_length is None:
                    span_length = float(tenders_table.span_length) if getattr(tenders_table, 'span_length', None) is not None else None
                if road_work_amount is None:
                    road_work_amount = float(tenders_table.road_work_amount) if getattr(tenders_table, 'road_work_amount', None) is not None else None
                if structure_work_amount is None:
                    structure_work_amount = float(tenders_table.structure_work_amount) if getattr(tenders_table, 'structure_work_amount', None) is not None else None
                
                # Calculate per_km_cost if we have length and value
                per_km_cost = None
                if length_km and length_km > 0:
                    try:
                        value_float = self._convert_word_currency_to_number(str(scraped_tender_table.value))
                        if value_float > 0:
                            per_km_cost = value_float / length_km
                    except Exception:
                        pass

                # add Tender table extra fields
                remarks_text = None
                if getattr(tenders_table, 'description', None):
                    remarks_text = str(tenders_table.description).strip()
                elif scraped_tender_table and hasattr(scraped_tender_table, 'tender_brief'):
                    remarks_text = str(scraped_tender_table.tender_brief).strip()
                
                # Clean up remarks - remove TDR prefix and clean text
                if remarks_text:
                    import re
                    # Remove "TDR:12345 tender for" pattern at the start
                    remarks_text = re.sub(r'^TDR:\d+\s+(?:tender for\s+)?', '', remarks_text, flags=re.IGNORECASE)
                    # Remove extra whitespace
                    remarks_text = ' '.join(remarks_text.split())
                    # Capitalize first letter
                    if remarks_text:
                        remarks_text = remarks_text[0].upper() + remarks_text[1:] if len(remarks_text) > 1 else remarks_text.upper()
                
                # Format status nicely
                status_val = getattr(tenders_table, 'review_status', None) or getattr(tenders_table, 'status', None)
                current_status = str(status_val).replace('_', ' ').title() if status_val else "Not Reviewed"
                
                scraped_dict.update({
                    "length_km": length_km,
                    "per_km_cost": per_km_cost,
                    "span_length": span_length,
                    "road_work_amount": road_work_amount,
                    "structure_work_amount": structure_work_amount,
                    "remarks": remarks_text,
                    "current_status": current_status
                })

                try:
                    full_scraped = ScrapedTenderRead.model_validate(scraped_dict)
                except Exception:
                    full_scraped = None

            # Create history data for all wishlisted tenders (with or without analysis)
            if analysis is not None:
                print(analysis.progress, analysis.tender_id)
                
            history_data = HistoryData(
                id=str(scraped_tender_table.id),  # Use ScrapedTender ID (matches Tender ID after fix)
                title=str(tenders_table.tender_title),
                authority=str(tenders_table.employer_name),
                value=int(self._convert_word_currency_to_number(str(scraped_tender_table.value))),
                emd=int(self._convert_word_currency_to_number(str(scraped_tender_table.emd))),
                due_date=str(scraped_tender_table.due_date),
                category=str(tenders_table.category).strip().replace('\r\n', ' ').replace('\n', ' '),
                progress=analysis.progress if analysis else 0,
                analysis_state=analysis.status if analysis else AnalysisStatusEnum.failed,
                synopsis_state=False,
                evaluated_state=False,
                results=HistoryDataResultsEnum.PENDING,
                analysis_details=TenderAnalysisRead.model_validate(analysis) if analysis else None,
                full_scraped_details=full_scraped
            )
            history_data_list.append(history_data)

        return HistoryAndWishlistResponse(
            tenders=history_data_list,
            report_file_url="https://tenderiq.s3.amazonaws.com/2023/05/09/4b7b4c9b-9d3d-4e8a-9e3e-8b6e5f1a2b3c/wishlist_report.pdf",
        )

    def get_tender_details(self, db: Session, tender_id: UUID) -> Optional[Tender]:
        """
        Get full details for a single tender by its ID.
        """
        repo = TenderIQRepository(db)
        tender = repo.get_tender_by_id(tender_id)
        if not tender:
            return None
        return tender

    def _get_tenders_by_flag(self, db: Session, flag_name: str) -> list[Tender]:
        """Helper to get all tenders where a specific boolean flag is set."""
        scraped_tender_repo = TenderIQRepository(db)
        
        # Use the new repository method that properly joins tables
        # Returns list of tuples: (ScrapedTender, Tender)
        tender_pairs = scraped_tender_repo.get_scraped_tenders_by_flag(flag_name, flag_value=True)
        
        result = []
        for scraped_tender, tender_record in tender_pairs:
            # Convert ScrapedTender to dict
            tender_dict = Tender.model_validate(scraped_tender).model_dump()
            
            # Add the flags from the Tender table
            if tender_record:
                tender_dict['is_favorite'] = tender_record.is_favorite
                tender_dict['is_wishlisted'] = tender_record.is_wishlisted
                tender_dict['is_archived'] = tender_record.is_archived
            else:
                # Default to False if no tender record exists (shouldn't happen with inner join)
                tender_dict['is_favorite'] = False
                tender_dict['is_wishlisted'] = False
                tender_dict['is_archived'] = False
            
            # Re-validate with the updated dict
            result.append(Tender.model_validate(tender_dict))
        
        return result

    def get_wishlisted_tenders(self, db: Session) -> list[Tender]:
        """Gets all tenders that are wishlisted."""
        return self._get_tenders_by_flag(db, 'is_wishlisted')

    def get_archived_tenders(self, db: Session) -> list[Tender]:
        """Gets all tenders that are archived."""
        return self._get_tenders_by_flag(db, 'is_archived')

    def get_favorited_tenders(self, db: Session) -> list[Tender]:
        """Gets all tenders that are marked as favorite."""
        return self._get_tenders_by_flag(db, 'is_favorite')

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

        # Get scrape runs and organize by hierarchical structure
        scrape_runs = repo.get_scrape_runs_by_date_range(days=days)

        # Return the latest scrape run in the range (or combine if needed)
        # For now, return the first (latest) one with all filters applied
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

        # Return empty response if no scrape runs found
        raise ValueError(f"No tenders found for date range: {date_range}")

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
        filtered = []

        for tender in tenders:
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
