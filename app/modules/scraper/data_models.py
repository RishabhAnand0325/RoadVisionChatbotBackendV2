from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum

class TenderDetailPageFile(BaseModel):
    file_name: str
    file_url: str
    file_description: str
    file_size: str

class TenderDetailNotice(BaseModel):
    tdr: str
    tendering_authority: str
    tender_no: str
    tender_id: str
    tender_brief: str
    city: str
    state: str
    document_fees: str
    emd: str
    tender_value: float
    tender_type: str
    bidding_type: str
    competition_type: str

class TenderDetailDetails(BaseModel):
    tender_details: str

class TenderDetailKeyDates(BaseModel):
    publish_date: str
    last_date_of_bid_submission: str
    tender_opening_date: str

class TenderDetailContactInformation(BaseModel):
    company_name: str
    contact_person: str
    address: str

class TenderDetailOtherDetail(BaseModel):
    information_source: str
    files: List[TenderDetailPageFile]

class TenderHistoryItem(BaseModel):
    """Represents a single history item from the scraped page"""
    id: Optional[str] = None  # May have an ID from the page
    type: str  # corrigendum, amendment, extension, etc.
    note: str  # Description of the change
    update_date: str  # Date when the change was made
    files_changed: List[TenderDetailPageFile] = []  # Files that changed
    date_change_from: Optional[str] = None  # Old date if date changed
    date_change_to: Optional[str] = None  # New date if date changed

class TenderDocumentChanges(BaseModel):
    """Document Changes & Corrigendums section from the page"""
    items: List[TenderHistoryItem] = []

class TenderActionHistoryItem(BaseModel):
    """Represents a single action from the Actions History section"""
    action: str  # Action type (viewed, updated, etc.)
    timestamp: str  # When the action occurred
    user: Optional[str] = None  # User who performed the action (if available)
    notes: Optional[str] = None  # Additional notes

class TenderActionsHistory(BaseModel):
    """Actions History section from the page"""
    items: List[TenderActionHistoryItem] = []

class TenderDetailPage(BaseModel):
    notice: TenderDetailNotice
    details: TenderDetailDetails
    key_dates: TenderDetailKeyDates
    contact_information: TenderDetailContactInformation
    other_detail: TenderDetailOtherDetail
    document_changes: Optional[TenderDocumentChanges] = None  # Document Changes & Corrigendums
    actions_history: Optional[TenderActionsHistory] = None  # Actions History

class HomePageHeader(BaseModel):
    date: str
    name: str
    contact: str
    no_of_new_tenders: str
    company: str

class Tender(BaseModel):
    tender_id: str
    tender_name: str
    tender_url: str
    dms_folder_id: Optional[UUID] = None
    city: str
    summary: str
    value: str
    due_date: str
    # Details of the tender, could be undefined
    details: TenderDetailPage | None

class TenderQuery(BaseModel):
    query_name: str
    number_of_tenders: str
    tenders: List[Tender]

class HomePageData(BaseModel):
    header: HomePageHeader
    query_table: List[TenderQuery]

