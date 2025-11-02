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
    id: UUID
    file_name: str
    file_url: str
    file_description: Optional[str] = None
    file_size: Optional[str] = None
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
