import uuid
from datetime import datetime, date

from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Text, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class ScrapedEmailLog(Base):
    """
    Tracks all tender processing (email and manual) to prevent duplicate processing.
    Supports unified deduplication across both email and manual link pasting modes.

    Fields:
    - email_uid: "manual" for manual link pasting, IMAP UID for email mode
    - email_sender: "manual_input" for manual, email address for email mode
    - priority: For conflict resolution when same tender from multiple sources
    """
    __tablename__ = 'scraped_email_logs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Email metadata (or manual source info)
    email_uid = Column(String, nullable=False, index=True)  # IMAP UID or "manual"
    email_sender = Column(String, nullable=False)  # Email address or "manual_input"
    email_received_at = Column(DateTime, nullable=False, index=True)  # When email received or manually pasted

    # Tender metadata
    tender_url = Column(String, nullable=False, index=True)  # The scrape link
    tender_id = Column(String, nullable=True)  # Optional: tender ID if parsed

    # Processing status
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When we processed it
    processing_status = Column(String, default="success", nullable=False)  # "success", "failed", "skipped", "superseded"
    error_message = Column(Text, nullable=True)  # If processing failed, store error

    # Priority for conflict resolution
    # Higher priority = preferred when same tender from multiple sources
    # Email priority defaults to 1, manual override can be 2, programmatic requests can be 3
    priority = Column(String, default="normal", nullable=False)  # "low", "normal", "high"

    # Foreign key to scrape run (if successfully processed)
    scrape_run_id = Column(UUID(as_uuid=True), ForeignKey('scrape_runs.id'), nullable=True)
    scrape_run = relationship("ScrapeRun", foreign_keys=[scrape_run_id])

    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_email_uid_tender_url', 'email_uid', 'tender_url', unique=True),  # Composite unique constraint
        Index('idx_email_received_at', 'email_received_at'),  # For 24-hour window queries
        Index('idx_tender_url', 'tender_url'),  # For URL deduplication
        Index('idx_tender_url_priority', 'tender_url', 'priority'),  # For priority-based conflict resolution
    )


class ScrapeRun(Base):
    __tablename__ = 'scrape_runs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Tender release date (from website header, parsed from date_str)
    # Used for grouping tenders by when they were released, not when we scraped them
    tender_release_date = Column(Date, nullable=False, index=True)

    # from HomePageHeader
    date_str = Column(String)  # 'date' from header (e.g., "Sunday, Nov 02, 2025")
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

    analysis_status = Column(String, default="pending", nullable=False)  # "pending", "failed", "skipped", "completed"
    error_message = Column(Text, nullable=True)

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
    """
    Stores tender file metadata with support for both remote and locally cached files.

    Strategy:
    - file_url: Original URL from internet (source of truth)
    - dms_path: Reference path in DMS where file is/will be cached (e.g., /dms/tenders/YYYY/MM/DD/tender_id/files/filename)
    - is_cached: Whether file has been downloaded to DMS
    - cache_status: Current state (pending, cached, failed)

    DMS Module handles the logic of fetching from remote vs local storage.
    """
    __tablename__ = 'scraped_tender_files'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # File metadata
    file_name = Column(String, nullable=False)
    file_url = Column(String, nullable=False)  # Original internet URL (source)
    file_description = Column(String, nullable=True)
    file_size = Column(String, nullable=True)

    # DMS storage metadata
    dms_path = Column(String, nullable=False)  # Reference path: /dms/tenders/YYYY/MM/DD/tender_id/files/filename
    is_cached = Column(Boolean, default=False, nullable=False)  # True = file exists locally in DMS
    cache_status = Column(String, default="pending", nullable=False)  # "pending", "cached", "failed"
    cache_error = Column(Text, nullable=True)  # Error message if caching failed

    # Relationship
    tender_id = Column(UUID(as_uuid=True), ForeignKey('scraped_tenders.id'))
    tender = relationship("ScrapedTender", back_populates="files")


class EmailTemplateHash(Base):
    """
    Stores the expected hash/fingerprint of incoming email templates for security validation.
    If an incoming email's template structure doesn't match the stored hash, processing is stopped.
    
    This prevents processing emails with changed templates that could indicate:
    - Email format changes from the sender
    - Potential phishing or malicious emails
    - Unexpected email structure that could break parsing
    """
    __tablename__ = 'email_template_hashes'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Template hash/fingerprint
    template_hash = Column(String, nullable=False, unique=True, index=True)  # SHA256 hash of template structure
    
    # Metadata
    email_sender = Column(String, nullable=False)  # Email sender this template is for (e.g., "tenders@tenderdetail.com")
    is_active = Column(Boolean, default=True, nullable=False)  # Whether this template is currently active
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_validated_at = Column(DateTime, nullable=True)  # Last time an email matched this template
    
    # Description for reference
    description = Column(Text, nullable=True)  # Optional description of the template
