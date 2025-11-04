from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime

class TenderBase(BaseModel):
    tender_title: str
    description: Optional[str] = None
    status: str = 'New'

class TenderCreate(TenderBase):
    pass

class Tender(TenderBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TenderAnalysisBase(BaseModel):
    tender_id: UUID
    executive_summary: Optional[str] = None

class TenderAnalysisCreate(TenderAnalysisBase):
    pass

class TenderAnalysis(TenderAnalysisBase):
    id: UUID
    analyzed_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Scraper Daily Tenders Models ---

class ScrapedTenderFile(BaseModel):
    """
    File metadata with support for hybrid remote + local caching storage.

    Fields:
    - file_url: Original internet source (for reference/direct access)
    - dms_path: DMS reference path where file is/will be cached (the authoritative path)
    - is_cached: Whether file has been downloaded to local DMS
    - cache_status: Current state (pending, cached, failed)
    """
    id: UUID
    file_name: str
    file_url: str  # Original internet URL
    dms_path: str  # DMS reference path (/tenders/YYYY/MM/DD/tender_id/files/filename)
    file_description: Optional[str] = None
    file_size: Optional[str] = None
    is_cached: bool = False  # Whether file is cached locally in DMS
    cache_status: Optional[str] = "pending"  # "pending", "cached", or "failed"
    model_config = ConfigDict(from_attributes=True)


class ScrapedTender(BaseModel):
    id: UUID
    tender_id_str: str
    tender_name: str
    tender_url: str
    drive_url: Optional[str] = None
    city: str
    summary: str
    value: str
    due_date: str
    tdr: Optional[str] = None
    tendering_authority: Optional[str] = None
    tender_no: Optional[str] = None
    tender_id_detail: Optional[str] = None
    tender_brief: Optional[str] = None
    state: Optional[str] = None
    document_fees: Optional[str] = None
    emd: Optional[str] = None
    tender_value: Optional[str] = None
    tender_type: Optional[str] = None
    bidding_type: Optional[str] = None
    competition_type: Optional[str] = None
    tender_details: Optional[str] = None
    publish_date: Optional[str] = None
    last_date_of_bid_submission: Optional[str] = None
    tender_opening_date: Optional[str] = None
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    address: Optional[str] = None
    information_source: Optional[str] = None
    files: list[ScrapedTenderFile]
    model_config = ConfigDict(from_attributes=True)


class ScrapedTenderQuery(BaseModel):
    id: UUID
    query_name: str
    number_of_tenders: str
    tenders: list[ScrapedTender]
    model_config = ConfigDict(from_attributes=True)


class DailyTendersResponse(BaseModel):
    id: UUID
    run_at: datetime
    date_str: str
    name: str
    contact: str
    no_of_new_tenders: str
    company: str
    queries: list[ScrapedTenderQuery]
    model_config = ConfigDict(from_attributes=True)


# --- Date Filtering Response Models (Phase TenderIQ) ---


class ScrapeDateInfo(BaseModel):
    """Information about a specific scrape date with tender count"""
    date: str  # YYYY-MM-DD
    date_str: str  # "November 3, 2024"
    run_at: datetime  # ISO format timestamp
    tender_count: int  # Total tenders on this date
    is_latest: bool  # Whether this is the most recent scrape

    model_config = ConfigDict(from_attributes=True)


class AvailableDatesResponse(BaseModel):
    """Response for GET /api/v1/tenderiq/dates endpoint"""
    dates: list[ScrapeDateInfo]  # All available scrape dates


class TenderResponseForFiltering(BaseModel):
    """Single tender in filtered results (subset of full tender details)"""
    id: UUID
    tender_id_str: str
    tender_name: str
    tender_url: str
    dms_folder_id: Optional[UUID] = None
    city: str
    value: str
    due_date: str
    summary: str
    # Optional detail fields
    query_name: Optional[str] = None  # Category from query
    tender_type: Optional[str] = None
    tender_value: Optional[str] = None
    state: Optional[str] = None
    publish_date: Optional[str] = None
    last_date_of_bid_submission: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FilteredTendersResponse(BaseModel):
    """Response for GET /api/v1/tenderiq/tenders endpoint with filters"""
    tenders: list[TenderResponseForFiltering]  # Filtered tender results
    total_count: int  # Total number of tenders returned
    filtered_by: dict  # What filters were applied (e.g., {"date_range": "last_5_days"})
    available_dates: list[str]  # List of all available dates in YYYY-MM-DD format

    model_config = ConfigDict(from_attributes=True)


# --- Tender Detail Response Models ---

class TenderNoticeInfo(BaseModel):
    tdr: Optional[str] = None
    tendering_authority: Optional[str] = None
    tender_no: Optional[str] = None
    tender_id_detail: Optional[str] = None
    tender_brief: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    document_fees: Optional[str] = None
    emd: Optional[str] = None
    tender_value: Optional[str] = None
    tender_type: Optional[str] = None
    bidding_type: Optional[str] = None
    competition_type: Optional[str] = None

class TenderKeyDatesInfo(BaseModel):
    publish_date: Optional[str] = None
    last_date_of_bid_submission: Optional[str] = None
    tender_opening_date: Optional[str] = None

class TenderContactInfo(BaseModel):
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    address: Optional[str] = None

class TenderDetailResponse(BaseModel):
    """Detailed response for a single tender."""
    id: UUID
    tender_id_str: str
    tender_name: str
    tender_url: str
    dms_folder_id: Optional[UUID] = None
    summary: str
    value: str
    due_date: str

    notice: TenderNoticeInfo
    key_dates: TenderKeyDatesInfo
    contact_info: TenderContactInfo

    tender_details: Optional[str] = None
    information_source: Optional[str] = None

    files: list[ScrapedTenderFile]

    model_config = ConfigDict(from_attributes=True)
