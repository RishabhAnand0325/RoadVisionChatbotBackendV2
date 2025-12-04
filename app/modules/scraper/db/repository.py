from typing import Optional
from datetime import datetime, timedelta, date as date_type

from sqlalchemy.orm import Session, joinedload

from typing import Tuple, Dict
from app.modules.scraper.data_models import HomePageData, Tender
from app.modules.scraper.db.schema import (
    ScrapeRun,
    ScrapedTender,
    ScrapedTenderFile,
    ScrapedTenderQuery,
    ScrapedEmailLog,
    EmailTemplateHash,
)


class ScraperRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_scrape_run(self) -> Optional[ScrapeRun]:
        """
        Retrieves the most recent scrape run from the database, eagerly loading
        all related queries, tenders, and files.
        """
        return (
            self.db.query(ScrapeRun)
            .order_by(ScrapeRun.run_at.desc())
            .options(
                joinedload(ScrapeRun.queries)
                .joinedload(ScrapedTenderQuery.tenders)
                .joinedload(ScrapedTender.files)
            )
            .first()
        )

    def create_scrape_run_shell(self, homepage_data: HomePageData, tender_release_date: Optional[date_type] = None) -> Tuple[ScrapeRun, Dict[str, ScrapedTenderQuery]]:
        """
        Creates the main ScrapeRun and its associated query categories in the database,
        but does NOT add the individual tenders. This sets up the parent records.
        """
        from app.modules.scraper.services.dms_integration_service import _parse_date_to_date_object

        if tender_release_date is None:
            tender_release_date = _parse_date_to_date_object(homepage_data.header.date)
        if tender_release_date is None:
            tender_release_date = datetime.utcnow().date()

        scrape_run = ScrapeRun(
            tender_release_date=tender_release_date,
            date_str=homepage_data.header.date,
            name=homepage_data.header.name,
            contact=homepage_data.header.contact,
            no_of_new_tenders=homepage_data.header.no_of_new_tenders,
            company=homepage_data.header.company,
        )
        self.db.add(scrape_run)

        query_map = {}
        for query_data in homepage_data.query_table:
            scraped_query = ScrapedTenderQuery(
                query_name=query_data.query_name,
                number_of_tenders=query_data.number_of_tenders,
            )
            scrape_run.queries.append(scraped_query)
            query_map[query_data.query_name] = scraped_query

        self.db.commit()
        self.db.refresh(scrape_run)
        for query in scrape_run.queries:
            self.db.refresh(query)

        return scrape_run, query_map

    def add_scraped_tender_details(
        self, query_orm: ScrapedTenderQuery, tender_data: Tender, tender_release_date: date_type
    ) -> ScrapedTender:
        """
        Creates a single ScrapedTender record with all its details and files,
        associating it with an existing ScrapedTenderQuery.
        Handles deduplication by checking if TDR already exists.
        """
        # DEDUPLICATION: Check if tender with same TDR already exists
        if tender_data.details and tender_data.details.notice.tdr:
            existing_tdr = self.db.query(ScrapedTender).filter(
                ScrapedTender.tdr == tender_data.details.notice.tdr
            ).first()
            
            if existing_tdr:
                # TDR already exists, return the existing record instead of creating duplicate
                print(f"⚠️  TDR {tender_data.details.notice.tdr} already exists (ID: {existing_tdr.id}), skipping duplicate")
                return existing_tdr
        
        scraped_tender = ScrapedTender(
            tender_id_str=tender_data.tender_id,
            tender_name=tender_data.tender_name,
            tender_url=tender_data.tender_url,
            dms_folder_id=tender_data.dms_folder_id,
            city=tender_data.city,
            summary=tender_data.summary,
            value=tender_data.value,
            due_date=tender_data.due_date,
        )

        if tender_data.details:
            details = tender_data.details
            scraped_tender.tdr = details.notice.tdr
            scraped_tender.tendering_authority = details.notice.tendering_authority
            scraped_tender.tender_no = details.notice.tender_no
            scraped_tender.tender_id_detail = details.notice.tender_id
            scraped_tender.tender_brief = details.notice.tender_brief
            scraped_tender.state = details.notice.state
            scraped_tender.document_fees = details.notice.document_fees
            scraped_tender.emd = details.notice.emd
            scraped_tender.tender_value = details.notice.tender_value
            scraped_tender.tender_type = details.notice.tender_type
            scraped_tender.bidding_type = details.notice.bidding_type
            scraped_tender.competition_type = details.notice.competition_type
            scraped_tender.tender_details = details.details.tender_details
            scraped_tender.publish_date = details.key_dates.publish_date
            scraped_tender.last_date_of_bid_submission = details.key_dates.last_date_of_bid_submission
            scraped_tender.tender_opening_date = details.key_dates.tender_opening_date
            scraped_tender.company_name = details.contact_information.company_name
            scraped_tender.contact_person = details.contact_information.contact_person
            scraped_tender.address = details.contact_information.address
            scraped_tender.information_source = details.other_detail.information_source

            for file_data in details.other_detail.files:
                date_str = tender_release_date.strftime("%Y-%m-%d")
                year, month, day = date_str.split('-')
                safe_filename = self._sanitize_filename(file_data.file_name)
                dms_path = f"/tenders/{year}/{month}/{day}/{tender_data.tender_id}/files/{safe_filename}"

                scraped_file = ScrapedTenderFile(
                    file_name=file_data.file_name,
                    file_url=file_data.file_url,
                    file_description=file_data.file_description,
                    file_size=file_data.file_size,
                    dms_path=dms_path,
                    is_cached=False,
                    cache_status="pending",
                )
                scraped_tender.files.append(scraped_file)

        query_orm.tenders.append(scraped_tender)
        self.db.add(scraped_tender)
        self.db.commit()
        self.db.refresh(scraped_tender)
        return scraped_tender

    def has_email_been_processed(self, email_uid: str, tender_url: str) -> bool:
        """
        Check if an email+tender combination has already been processed.
        Uses composite key: email_uid + tender_url
        """
        existing = self.db.query(ScrapedEmailLog).filter(
            ScrapedEmailLog.email_uid == email_uid,
            ScrapedEmailLog.tender_url == tender_url,
        ).first()
        return existing is not None

    def has_tender_url_been_processed(self, tender_url: str) -> bool:
        """
        Check if this tender URL has been processed from ANY email.
        Prevents duplicate scraping of same tender from different emails.
        """
        existing = self.db.query(ScrapedEmailLog).filter(
            ScrapedEmailLog.tender_url == tender_url,
            ScrapedEmailLog.processing_status == "success",
        ).first()
        return existing is not None

    # ==================== UNIFIED DEDUPLICATION (Email + Manual) ====================

    def check_tender_duplicate_with_priority(self, tender_url: str, source_priority: str = "normal") -> tuple[bool, Optional[ScrapedEmailLog]]:
        """
        Unified deduplication check for both email and manual link pasting.
        Handles priority-based conflict resolution when same tender from multiple sources.

        Returns:
            (is_duplicate, existing_log)
            - is_duplicate: True if tender already processed with same or higher priority
            - existing_log: The existing ScrapedEmailLog record if duplicate found

        Priority levels: "low" < "normal" < "high"
        - If incoming priority is HIGHER: can override (not a duplicate)
        - If incoming priority is SAME or LOWER: it's a duplicate
        """
        existing = self.db.query(ScrapedEmailLog).filter(
            ScrapedEmailLog.tender_url == tender_url,
            ScrapedEmailLog.processing_status.in_(["success", "superseded"]),
        ).order_by(ScrapedEmailLog.processed_at.desc()).first()

        if existing is None:
            return False, None

        # Priority comparison: high > normal > low
        priority_order = {"low": 0, "normal": 1, "high": 2}
        source_level = priority_order.get(source_priority, 1)
        existing_level = priority_order.get(existing.priority, 1)

        # If new priority is higher, it's not a duplicate (can override)
        if source_level > existing_level:
            return False, existing

        # Same or lower priority = duplicate
        return True, existing

    def mark_superseded(self, email_log_id: str, reason: str = "Overridden by higher priority source") -> ScrapedEmailLog:
        """
        Mark a previous processing as superseded by a newer, higher-priority one.
        Used when a tender is re-processed with higher priority.

        Args:
            email_log_id: UUID of the ScrapedEmailLog to supersede
            reason: Reason for superseding

        Returns:
            Updated ScrapedEmailLog record
        """
        email_log = self.db.query(ScrapedEmailLog).filter(
            ScrapedEmailLog.id == email_log_id
        ).first()

        if email_log:
            email_log.processing_status = "superseded"
            email_log.error_message = reason
            self.db.commit()
            self.db.refresh(email_log)

        return email_log

    def get_duplicate_sources_for_tender(self, tender_url: str) -> list[ScrapedEmailLog]:
        """
        Get all processing records for a specific tender URL.
        Useful for understanding which sources (emails, manual) processed this tender.

        Returns:
            List of ScrapedEmailLog records ordered by date (newest first)
        """
        return self.db.query(ScrapedEmailLog).filter(
            ScrapedEmailLog.tender_url == tender_url
        ).order_by(ScrapedEmailLog.processed_at.desc()).all()

    def log_email_processing(
        self,
        email_uid: str,
        email_sender: str,
        email_received_at: datetime,
        tender_url: str,
        tender_id: Optional[str] = None,
        processing_status: str = "success",
        error_message: Optional[str] = None,
        scrape_run_id: Optional[str] = None,
        priority: str = "normal",
    ) -> ScrapedEmailLog:
        """
        Log that an email or manual link has been processed.
        Supports unified logging for both email and manual link pasting modes.

        Args:
            email_uid: IMAP UID for email mode, or "manual" for manual link pasting
            email_sender: Email sender address, or "manual_input" for manual mode
            email_received_at: When email received or manually submitted
            tender_url: The tender link extracted or pasted
            tender_id: Optional tender ID if extracted
            processing_status: "success", "failed", "skipped", or "superseded"
            error_message: Error details if processing failed
            scrape_run_id: ScrapeRun ID if successfully processed
            priority: "low", "normal", or "high" - for conflict resolution

        Returns:
            ScrapedEmailLog record
        """
        email_log = ScrapedEmailLog(
            email_uid=email_uid,
            email_sender=email_sender,
            email_received_at=email_received_at,
            tender_url=tender_url,
            tender_id=tender_id,
            processing_status=processing_status,
            error_message=error_message,
            scrape_run_id=scrape_run_id,
            priority=priority,
        )
        self.db.add(email_log)
        self.db.commit()
        self.db.refresh(email_log)
        return email_log

    def get_emails_from_last_24_hours(self) -> list[ScrapedEmailLog]:
        """
        Get all email logs from the last 24 hours.
        Useful for checking what emails have been processed recently.
        """
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        return self.db.query(ScrapedEmailLog).filter(
            ScrapedEmailLog.email_received_at >= twenty_four_hours_ago
        ).order_by(ScrapedEmailLog.email_received_at.desc()).all()

    def cleanup_old_email_logs(self, days_to_keep: int = 30) -> int:
        """
        Delete email logs older than specified days (for cleanup).
        Returns number of deleted records.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        deleted_count = self.db.query(ScrapedEmailLog).filter(
            ScrapedEmailLog.processed_at < cutoff_date
        ).delete()
        self.db.commit()
        return deleted_count

    # ==================== DATE FILTERING METHODS (Phase TenderIQ) ====================

    def get_scrape_runs_by_date_range(
        self, days: Optional[int] = None
    ) -> list[ScrapeRun]:
        """
        Get scrape runs from the last N days.

        Args:
            days: Number of days to look back. None means all historical data.

        Returns:
            List of ScrapeRun objects ordered by run_at DESC (newest first)

        Example:
            get_scrape_runs_by_date_range(5)  # Last 5 days
            get_scrape_runs_by_date_range()   # All historical
        """
        query = self.db.query(ScrapeRun)

        if days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(ScrapeRun.run_at >= cutoff_date)

        return query.order_by(ScrapeRun.run_at.desc()).all()

    def get_available_scrape_runs(self) -> list[ScrapeRun]:
        """
        Get all distinct scrape runs ordered by date (newest first).
        Used to populate date selector dropdown in frontend.

        Returns:
            List of ScrapeRun objects with count of tenders eager-loaded

        Note:
            Each ScrapeRun has a relationship to queries which have tenders.
            Caller can count len(scrape_run.queries[*].tenders) for tender_count.
        """
        return (
            self.db.query(ScrapeRun)
            .order_by(ScrapeRun.run_at.desc())
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
            .options(joinedload(ScrapedTender.files))
        )

        if category:
            query = query.filter(ScrapedTenderQuery.query_name == category)

        if location:
            query = query.filter(ScrapedTender.city == location)

        # Note: min_value and max_value are stored as strings in DB
        # Would need parsing for true numeric comparison
        # For now, leaving as extension point

        return query.all()

    def get_tenders_by_specific_date(
        self,
        date: str,  # Format: "YYYY-MM-DD"
        category: Optional[str] = None,
        location: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> list[ScrapedTender]:
        """
        Get all tenders scraped on a specific date.

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
            from datetime import datetime as dt

            # Parse the date string
            target_date = dt.strptime(date, "%Y-%m-%d")
            next_day = target_date + timedelta(days=1)
        except ValueError as e:
            raise ValueError(f"Invalid date format. Expected YYYY-MM-DD, got '{date}'") from e

        # Query for scrape runs on this specific date
        query = (
            self.db.query(ScrapedTender)
            .join(ScrapedTenderQuery)
            .join(ScrapeRun)
            .filter(ScrapeRun.run_at >= target_date)
            .filter(ScrapeRun.run_at < next_day)
            .options(joinedload(ScrapedTender.files))
        )

        if category:
            query = query.filter(ScrapedTenderQuery.query_name == category)

        if location:
            query = query.filter(ScrapedTender.city == location)

        return query.all()

    def get_all_tenders_with_filters(
        self,
        category: Optional[str] = None,
        location: Optional[str] = None,
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
        query = self.db.query(ScrapedTender).options(joinedload(ScrapedTender.files))

        if category:
            query = query.join(ScrapedTenderQuery).filter(
                ScrapedTenderQuery.query_name == category
            )

        if location:
            query = query.filter(ScrapedTender.city == location)

        return query.all()

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Remove special characters from filename while preserving extension.
        Used when generating DMS paths.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for filesystem
        """
        import os
        import re
        name, ext = os.path.splitext(filename)
        # Keep only alphanumeric, hyphens, underscores
        name = re.sub(r'[^\w\-]', '', name)
        return f"{name}{ext}" if ext else name

    # ==================== EMAIL TEMPLATE HASH MANAGEMENT ====================

    def get_active_template_hash(self, email_sender: str) -> Optional[EmailTemplateHash]:
        """
        Get the active template hash for a sender.
        
        Args:
            email_sender: Email sender address
            
        Returns:
            EmailTemplateHash record if found, None otherwise
        """
        return self.db.query(EmailTemplateHash).filter(
            EmailTemplateHash.email_sender == email_sender,
            EmailTemplateHash.is_active == True
        ).first()

    def set_template_hash(self, template_hash: str, email_sender: str, description: Optional[str] = None) -> EmailTemplateHash:
        """
        Set or update the template hash for a sender.
        
        Args:
            template_hash: SHA256 hash of the template structure
            email_sender: Email sender address
            description: Optional description
            
        Returns:
            EmailTemplateHash record
        """
        # Deactivate old templates for this sender
        self.db.query(EmailTemplateHash).filter(
            EmailTemplateHash.email_sender == email_sender
        ).update({'is_active': False})
        
        # Check if this exact hash already exists
        existing = self.db.query(EmailTemplateHash).filter(
            EmailTemplateHash.template_hash == template_hash,
            EmailTemplateHash.email_sender == email_sender
        ).first()
        
        if existing:
            existing.is_active = True
            existing.last_validated_at = datetime.utcnow()
            if description:
                existing.description = description
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        # Create new template hash
        new_hash = EmailTemplateHash(
            template_hash=template_hash,
            email_sender=email_sender,
            is_active=True,
            description=description,
            last_validated_at=datetime.utcnow()
        )
        self.db.add(new_hash)
        self.db.commit()
        self.db.refresh(new_hash)
        return new_hash
