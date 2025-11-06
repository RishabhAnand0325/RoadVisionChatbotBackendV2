"""
Pydantic schemas for the structured JSON data stored in TenderAnalysis.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class OnePagerSchema(BaseModel):
    """Defines the structure for the one_pager_json field."""
    project_overview: str
    eligibility_highlights: List[str] = []
    important_dates: List[str] = []
    financial_requirements: List[str] = []
    risk_analysis: Dict[str, Any] = {}


class ScopeOfWorkProjectOverviewSchema(BaseModel):
    """Defines the nested project_overview object within the scope of work."""
    name: str
    location: Optional[str] = None
    total_length: Optional[str] = None
    duration: Optional[str] = None
    value: Optional[str] = None


class ScopeOfWorkSchema(BaseModel):
    """Defines the structure for the scope_of_work_json field."""
    project_overview: ScopeOfWorkProjectOverviewSchema
    major_work_components: List[str] = []
    technical_standards_and_specifications: List[str] = []


class DataSheetSchema(BaseModel):
    """Defines the structure for the data_sheet_json field."""
    key_tender_details: Dict[str, Any] = {}
    financial_summary: Dict[str, Any] = {}
    timeline: Dict[str, Any] = {}


class SSEEvent(BaseModel):
    """Defines the structure of a Server-Sent Event."""
    event: str  # e.g., 'update', 'status_change', 'error', 'complete'
    field: str  # e.g., 'one_pager', 'status', 'scope_of_work.project_overview'
    data: Any
