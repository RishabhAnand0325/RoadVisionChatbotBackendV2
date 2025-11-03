from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from app.modules.scraper.data_models import HomePageData
from app.modules.scraper.db.schema import (
    ScrapeRun,
    ScrapedTender,
    ScrapedTenderFile,
    ScrapedTenderQuery,
    ScrapedEmailLog,
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

    def create_scrape_run(self, homepage_data: HomePageData) -> ScrapeRun:
        """
        Creates a new scrape run and all its related entities in the database
        from the provided Pydantic model.
        """
        scrape_run = ScrapeRun(
            date_str=homepage_data.header.date,
            name=homepage_data.header.name,
            contact=homepage_data.header.contact,
            no_of_new_tenders=homepage_data.header.no_of_new_tenders,
            company=homepage_data.header.company,
        )

        for query_data in homepage_data.query_table:
            scraped_query = ScrapedTenderQuery(
                query_name=query_data.query_name,
                number_of_tenders=query_data.number_of_tenders,
            )
            scrape_run.queries.append(scraped_query)

            for tender_data in query_data.tenders:
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
                    # Notice
                    scraped_tender.tdr = details.notice.tdr
                    scraped_tender.tendering_authority = (
                        details.notice.tendering_authority
                    )
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
                    # Details
                    scraped_tender.tender_details = details.details.tender_details
                    # Key Dates
                    scraped_tender.publish_date = details.key_dates.publish_date
                    scraped_tender.last_date_of_bid_submission = (
                        details.key_dates.last_date_of_bid_submission
                    )
                    scraped_tender.tender_opening_date = (
                        details.key_dates.tender_opening_date
                    )
                    # Contact Information
                    scraped_tender.company_name = (
                        details.contact_information.company_name
                    )
                    scraped_tender.contact_person = (
                        details.contact_information.contact_person
                    )
                    scraped_tender.address = details.contact_information.address
                    # Other Detail
                    scraped_tender.information_source = (
                        details.other_detail.information_source
                    )

                    for file_data in details.other_detail.files:
                        scraped_file = ScrapedTenderFile(
                            file_name=file_data.file_name,
                            file_url=file_data.file_url,
                            file_description=file_data.file_description,
                            file_size=file_data.file_size,
                        )
                        scraped_tender.files.append(scraped_file)

                scraped_query.tenders.append(scraped_tender)

        self.db.add(scrape_run)
        self.db.commit()
        self.db.refresh(scrape_run)
        return scrape_run

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
    ) -> ScrapedEmailLog:
        """
        Log that an email has been processed.

        Args:
            email_uid: IMAP unique identifier for the email
            email_sender: Email sender address (e.g., "tenders@tenderdetail.com")
            email_received_at: When the email was received (from email header)
            tender_url: The tender link extracted from email
            tender_id: Optional tender ID if extracted
            processing_status: "success", "failed", or "skipped"
            error_message: Error details if processing failed
            scrape_run_id: ScrapeRun ID if successfully processed

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
