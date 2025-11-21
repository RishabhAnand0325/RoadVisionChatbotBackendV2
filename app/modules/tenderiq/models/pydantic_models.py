from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum

from app.modules.analyze.db.schema import AnalysisStatusEnum, TenderAnalysis
from app.modules.analyze.models.pydantic_models import DataSheetSchema, OnePagerSchema, ScopeOfWorkSchema
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.tenderiq.db.schema import TenderActionEnum


# ==================== Tender Models ====================

class TenderFile(BaseModel):
    id: UUID
    file_name: str
    file_url: str
    dms_path: str
    file_description: Optional[str] = None
    file_size: Optional[str] = None
    is_cached: bool = False
    cache_status: Optional[str] = "pending"
    model_config = ConfigDict(from_attributes=True)
    file_type: Optional[str] = "Unknown"

class Tender(BaseModel):
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
    files: list[TenderFile]
    dms_folder_id: Optional[UUID] = None
    
    # Action flags - These are from the tenders table, not scraped_tenders
    is_favorite: Optional[bool] = False
    is_wishlisted: Optional[bool] = False
    is_archived: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)

class TenderCreate(BaseModel):
    tender_title: str
    description: Optional[str] = None
    status: str = 'New'


# ==================== Request Models ====================

class TenderActionType(str, Enum):
    """Defines the types of actions that can be performed on a tender."""
    TOGGLE_WISHLIST = "toggle_wishlist"
    TOGGLE_FAVORITE = "toggle_favorite"
    TOGGLE_ARCHIVE = "toggle_archive"
    UPDATE_STATUS = "update_status"
    UPDATE_REVIEW_STATUS = "update_review_status"

class TenderStatusEnum(str, Enum):
    """Matches the 'tender_status_enum' in the database."""
    NEW = 'New'
    REVIEWED = 'Reviewed'
    SHORTLISTED = 'Shortlisted'
    BID_PREPARATION = 'Bid_Preparation'
    SUBMITTED = 'Submitted'
    WON = 'Won'
    LOST = 'Lost'
    NOT_INTERESTED = 'Not_Interested'
    PENDING_RESULTS = 'Pending_Results'

class ReviewStatusEnum(str, Enum):
    """Matches the 'review_status_enum' in the database."""
    NOT_REVIEWED = 'Not_Reviewed'
    REVIEWED = 'Reviewed'
    SHORTLISTED = 'Shortlisted'

class TenderActionPayload(BaseModel):
    """Optional payload for actions like updating status."""
    status: Optional[TenderStatusEnum] = None
    review_status: Optional[ReviewStatusEnum] = None
    notes: Optional[str] = None

class TenderActionRequest(BaseModel):
    """Request model for the new tender action endpoint."""
    action: TenderActionType
    payload: Optional[TenderActionPayload] = None

# ==================== Response Models - History And Wishlist ====================
class ScrapedTenderRead(BaseModel):
    id: UUID

    # From Tender model
    tender_id_str: str
    tender_name: str
    tender_url: str
    dms_folder_id: Optional[UUID] = None
    city: str
    summary: str
    value: str
    due_date: str

    analysis_status: Optional[str] = None
    error_message: Optional[str] = None

    query_id: UUID

    # From TenderDetailPage models
    # TenderDetailNotice
    tdr: str
    tendering_authority: str
    tender_no: str
    tender_id_detail: str
    tender_brief: str
    # city is already there from Tender model
    state: str
    document_fees: str
    emd: str
    tender_value: str
    tender_type: str
    bidding_type: str
    competition_type: str

    # TenderDetailDetails
    tender_details: str

    # TenderDetailKeyDates
    publish_date: str
    last_date_of_bid_submission: str
    tender_opening_date: str

    # TenderDetailContactInformation
    company_name: str
    contact_person: str
    address: str

    # TenderDetailOtherDetail
    information_source: str
    # Extra fields merged from Tender table for wishlist/export
    length_km: Optional[float] = None
    per_km_cost: Optional[float] = None
    span_length: Optional[float] = None
    road_work_amount: Optional[float] = None
    structure_work_amount: Optional[float] = None
    remarks: Optional[str] = None
    current_status: Optional[str] = None
    class Config:
        from_attributes = True

class TenderAnalysisRead(BaseModel):
    """
    Central table to track the analysis of a single tender.
    Maintains a one-to-one relationship with a ScrapedTender.
    """
    id: UUID
    
    # One-to-one relationship to the ScrapedTender being analyzed. This refers to scraped_tenders.tender_id_str.
    tender_id: str
    user_id: Optional[UUID] = None
    chat_id: Optional[UUID] = None
    
    # Analysis metadata
    status: AnalysisStatusEnum
    progress: int
    status_message: Optional[str] = None
    error_message: Optional[str] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    analysis_started_at: datetime
    analysis_completed_at: Optional[datetime] = None
    
    # Analysis Results - JSON columns (untyped to avoid circular imports)
    one_pager_json: Optional[OnePagerSchema] = None
    scope_of_work_json: Optional[ScopeOfWorkSchema] = None
    data_sheet_json: Optional[DataSheetSchema] = None

    class Config:
        from_attributes = True

class HistoryDataResultsEnum(str, Enum):
    WON = "won"
    REJECTED = "rejected"
    INCOMPLETE = "incomplete"
    PENDING = "pending"

class HistoryData(BaseModel):
    id: str
    title: str;
    authority: str;
    value: int;
    emd: int;
    due_date: str;
    category: str;
    progress: int;
    analysis_state: AnalysisStatusEnum;
    synopsis_state: bool;
    evaluated_state: bool;
    # results: "won" | "rejected" | "incomplete" | "pending";
    results: HistoryDataResultsEnum;
    full_scraped_details: Optional[ScrapedTenderRead] = None
    analysis_details: Optional[TenderAnalysisRead] = None


class HistoryAndWishlistResponse(BaseModel):
    report_file_url: str
    tenders: List[HistoryData]

# ==================== Response Models - Full Tender Details ====================

class StatusEnum(str, Enum):
    NEW = "new"
    REVIEWED = "reviewed"
    SHORTLISTED = "shortlisted"
    BID_PREPARATION = "bid_preparation"
    SUBMITTED = "submitted"
    WON = "won"
    LOST = "lost"
    NOT_INTERESTED = "not_interested"
    PENDING_RESULTS = "pending_results"

class ActionHistoryItem(BaseModel):
    """Logs specific user-driven actions on a tender for history tracking."""
    id: str
    tender_id: str
    user_id: str
    action: TenderActionEnum
    notes: str
    timestamp: datetime

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class TenderHistoryType(str, Enum):
    DUE_DATE_EXTENSION = "due_date_extension"
    BID_DEADLINE_EXTENSION = "bid_deadline_extension"
    CORRIGENDUM = "corrigendum"
    AMENDMENT = "amendment"
    OTHER = "other"

class TenderHistoryDateChange(BaseModel):
    from_date: str
    to_date: str

class TenderHistoryItem(BaseModel):
    id: str
    tender_id: str
    user_id: Optional[str] = None  # Added to track which user performed the action
    tdr: str
    type: TenderHistoryType
    note: str
    update_date: str
    files_changed: Optional[List[TenderFile]] = []
    date_change: Optional[TenderHistoryDateChange] = None


class FullTenderDetails(BaseModel):
    risk_level: RiskLevel
    ## From ScrapedTender
    id: str

    # From Tender model
    tender_id_str: str
    tender_name: str
    tender_url: str
    # dms_folder_id = Column(UUID(as_uuid=True), nullable=True)
    city: str
    summary: str
    value: str
    due_date: str

    analysis_status: str  # Use string instead of enum to avoid import issues
    error_message: str

    query_id: str
    query: str

    # From TenderDetailPage models
    # TenderDetailNotice
    tdr: str
    tendering_authority: str
    tender_no: str
    tender_id_detail: str
    tender_brief: str
    # city is already there from Tender model
    state: str
    document_fees: str
    emd: int
    tender_value: int
    tender_type: str
    bidding_type: str
    competition_type: str

    # TenderDetailDetails
    tender_details: str

    # TenderDetailKeyDates
    publish_date: str
    last_date_of_bid_submission: str
    tender_opening_date: str

    # TenderDetailContactInformation
    company_name: str
    contact_person: str
    address: str

    # TenderDetailOtherDetail
    information_source: str

    files: List[TenderFile]

    ## From Tender
    id: str
    tender_ref_number: str
    tender_title: str
    description: str
    employer_name: str
    employer_address: str
    issuing_authority: str
    state: str
    location: str
    category: str
    mode: str
    estimated_cost: int
    bid_security: int
    length_km: int
    per_km_cost: int
    span_length: int
    road_work_amount: int
    structure_work_amount: int
    e_published_date: datetime
    identification_date: datetime
    submission_deadline: datetime
    prebid_meeting_date: datetime
    site_visit_deadline: datetime
    portal_source: str
    portal_url: str
    document_url: str
    status: StatusEnum
    review_status: ReviewStatusEnum
    reviewed_by_id: str
    reviewed_at: datetime
    created_at: datetime
    updated_at: datetime
    is_favorite: bool
    is_archived: bool
    is_wishlisted: bool
    history: List[ActionHistoryItem]
    tender_history: List[TenderHistoryItem]
    model_config = ConfigDict(from_attributes=True)

# ==================== Response Models - Analysis Metadata ====================

class ScrapedDate(BaseModel):
    id: str
    date: str
    run_at: str
    tender_count: int
    is_latest: bool
    model_config = ConfigDict(from_attributes=True)

class ScrapedDatesResponse(BaseModel):
    dates: list[ScrapedDate]
    model_config = ConfigDict(from_attributes=True)

# ==================== Response Models - Analysis Metadata ====================


# ==================== Response Models - Risk Assessment ====================


# ==================== Response Models - RFP Analysis ====================


# ==================== Response Models - Scope of Work ====================


# ==================== Response Models - Summary ====================


# ==================== Response Models - One-Pager ====================


# ==================== Response Models - Data Sheet ====================


# ==================== Response Models - Full Analysis Results ====================


# ==================== Response Models - Analysis List ====================


# ==================== Response Models - Delete ====================


# ==================== Response Models - Error ====================

# ==================== Scraper Models ====================

class ScrapedTenderQuery(BaseModel):
    id: UUID
    query_name: str
    number_of_tenders: str
    tenders: list[Tender]
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


# ==================== Date Filtering Models ====================

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


class FilteredTendersResponse(BaseModel):
    """Response for GET /api/v1/tenderiq/tenders endpoint with filters"""
    tenders: list[Tender]  # Filtered tender results
    total_count: int  # Total number of tenders returned
    filtered_by: dict  # What filters were applied (e.g., {"date_range": "last_5_days"})
    available_dates: list[str]  # List of all available dates in YYYY-MM-DD format

    model_config = ConfigDict(from_attributes=True)
