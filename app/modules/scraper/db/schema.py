import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class ScrapedEmailLog(Base):
    """
    Tracks emails from tenders@tenderdetail.com to prevent duplicate processing.
    Uses composite key of email_uid + tender_url for deduplication.
    """
    __tablename__ = 'scraped_email_logs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Email metadata
    email_uid = Column(String, nullable=False, index=True)  # IMAP unique identifier
    email_sender = Column(String, nullable=False)  # e.g., "tenders@tenderdetail.com"
    email_received_at = Column(DateTime, nullable=False, index=True)  # When email was received

    # Tender metadata
    tender_url = Column(String, nullable=False, index=True)  # The scrape link extracted from email
    tender_id = Column(String, nullable=True)  # Optional: tender ID if parsed

    # Processing status
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When we processed it
    processing_status = Column(String, default="success", nullable=False)  # "success", "failed", "skipped"
    error_message = Column(Text, nullable=True)  # If processing failed, store error

    # Foreign key to scrape run (if successfully processed)
    scrape_run_id = Column(UUID(as_uuid=True), ForeignKey('scrape_runs.id'), nullable=True)
    scrape_run = relationship("ScrapeRun", foreign_keys=[scrape_run_id])

    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_email_uid_tender_url', 'email_uid', 'tender_url', unique=True),  # Composite unique constraint
        Index('idx_email_received_at', 'email_received_at'),  # For 24-hour window queries
        Index('idx_tender_url', 'tender_url'),  # For URL deduplication
    )


class ScrapeRun(Base):
    __tablename__ = 'scrape_runs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_at = Column(DateTime, default=datetime.utcnow, index=True)

    # from HomePageHeader
    date_str = Column(String)  # 'date' from header
    name = Column(String)
    contact = Column(String)
    no_of_new_tenders = Column(String)
    company = Column(String)

    queries = relationship("ScrapedTenderQuery", back_populates="scrape_run", cascade="all, delete-orphan")


class ScrapedTenderQuery(Base):
    __tablename__ = 'scraped_tender_queries'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_name = Column(String, index=True)
    number_of_tenders = Column(String)

    scrape_run_id = Column(UUID(as_uuid=True), ForeignKey('scrape_runs.id'))
    scrape_run = relationship("ScrapeRun", back_populates="queries")

    tenders = relationship("ScrapedTender", back_populates="query", cascade="all, delete-orphan")


class ScrapedTender(Base):
    __tablename__ = 'scraped_tenders'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # From Tender model
    tender_id_str = Column(String, index=True)  # tender_id from pydantic model
    tender_name = Column(String)
    tender_url = Column(String)
    dms_folder_id = Column(UUID(as_uuid=True), nullable=True)
    city = Column(String)
    summary = Column(Text)
    value = Column(String)
    due_date = Column(String)

    query_id = Column(UUID(as_uuid=True), ForeignKey('scraped_tender_queries.id'))
    query = relationship("ScrapedTenderQuery", back_populates="tenders")

    # From TenderDetailPage models
    # TenderDetailNotice
    tdr = Column(String, nullable=True)
    tendering_authority = Column(String, nullable=True)
    tender_no = Column(String, nullable=True)
    tender_id_detail = Column(String, nullable=True)  # tender_id from notice
    tender_brief = Column(Text, nullable=True)
    # city is already there from Tender model
    state = Column(String, nullable=True)
    document_fees = Column(String, nullable=True)
    emd = Column(String, nullable=True)
    tender_value = Column(String, nullable=True)  # tender_value from notice
    tender_type = Column(String, nullable=True)
    bidding_type = Column(String, nullable=True)
    competition_type = Column(String, nullable=True)

    # TenderDetailDetails
    tender_details = Column(Text, nullable=True)

    # TenderDetailKeyDates
    publish_date = Column(String, nullable=True)
    last_date_of_bid_submission = Column(String, nullable=True)
    tender_opening_date = Column(String, nullable=True)

    # TenderDetailContactInformation
    company_name = Column(String, nullable=True)
    contact_person = Column(String, nullable=True)
    address = Column(Text, nullable=True)

    # TenderDetailOtherDetail
    information_source = Column(String, nullable=True)

    files = relationship("ScrapedTenderFile", back_populates="tender", cascade="all, delete-orphan")


class ScrapedTenderFile(Base):
    __tablename__ = 'scraped_tender_files'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String)
    file_url = Column(String)
    file_description = Column(String, nullable=True)
    file_size = Column(String, nullable=True)

    tender_id = Column(UUID(as_uuid=True), ForeignKey('scraped_tenders.id'))
    tender = relationship("ScrapedTender", back_populates="files")
