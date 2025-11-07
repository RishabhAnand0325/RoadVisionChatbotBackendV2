"""
Pydantic schemas for the structured JSON data stored in TenderAnalysis.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

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


# ==================== NEW: TENDER WISHLIST SCHEMAS ====================

class TenderWishlistItemSchema(BaseModel):
    """
    Schema for a single tender in the wishlist/history.
    Used in the history-wishlist endpoint response.
    """
    id: str
    tender_ref_number: str
    user_id: Optional[str] = None
    title: str
    authority: str
    value: float
    emd: float
    due_date: str
    category: str
    progress: int = Field(ge=0, le=100, description="Progress percentage 0-100")
    analysis_state: bool = Field(description="Whether analysis phase is completed")
    synopsis_state: bool = Field(description="Whether synopsis phase is completed")
    evaluated_state: bool = Field(description="Whether evaluation is completed")
    results: Literal["won", "rejected", "incomplete", "pending"] = Field(description="Final tender result status")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "wish_123",
                "tender_ref_number": "TEND_2025_001",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Road Construction Project",
                "authority": "PWD Ministry",
                "value": 5000000.0,
                "emd": 250000.0,
                "due_date": "15 Dec",
                "category": "Civil Works",
                "progress": 80,
                "analysis_state": True,
                "synopsis_state": True,
                "evaluated_state": False,
                "results": "pending"
            }
        }


class HistoryWishlistResponseSchema(BaseModel):
    """
    Schema for the GET /tenderiq/history-wishlist endpoint response.
    Contains report URL and list of saved tenders.
    """
    report_file_url: str = Field(description="URL to download comprehensive Excel report")
    tenders: List[TenderWishlistItemSchema] = Field(description="List of all saved tenders")

    class Config:
        json_schema_extra = {
            "example": {
                "report_file_url": "https://api.example.com/api/tenderiq/download/comprehensive-report",
                "tenders": [
                    {
                        "id": "wish_123",
                        "tender_ref_number": "TEND_2025_001",
                        "user_id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "Road Construction Project",
                        "authority": "PWD Ministry",
                        "value": 5000000.0,
                        "emd": 250000.0,
                        "due_date": "15 Dec",
                        "category": "Civil Works",
                        "progress": 80,
                        "analysis_state": True,
                        "synopsis_state": True,
                        "evaluated_state": False,
                        "results": "pending"
                    },
                    {
                        "id": "wish_124",
                        "tender_ref_number": "TEND_2025_002",
                        "user_id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "Bridge Construction",
                        "authority": "Ministry of Road Transport",
                        "value": 7500000.0,
                        "emd": 375000.0,
                        "due_date": "20 Dec",
                        "category": "Structural Work",
                        "progress": 45,
                        "analysis_state": True,
                        "synopsis_state": False,
                        "evaluated_state": False,
                        "results": "pending"
                    }
                ]
            }
        }


class AddToWishlistRequestSchema(BaseModel):
    """Schema for adding a tender to wishlist."""
    tender_ref_number: str
    title: str
    authority: str
    value: float
    emd: float
    due_date: str
    category: str

    class Config:
        json_schema_extra = {
            "example": {
                "tender_ref_number": "TEND_2025_001",
                "title": "Road Construction Project",
                "authority": "PWD Ministry",
                "value": 5000000.0,
                "emd": 250000.0,
                "due_date": "15 Dec",
                "category": "Civil Works"
            }
        }


class UpdateWishlistProgressRequestSchema(BaseModel):
    """Schema for updating wishlist tender progress."""
    progress: Optional[int] = Field(None, ge=0, le=100)
    analysis_state: Optional[bool] = None
    synopsis_state: Optional[bool] = None
    evaluated_state: Optional[bool] = None
    results: Optional[Literal["won", "rejected", "incomplete", "pending"]] = None
    status_message: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "progress": 80,
                "analysis_state": True,
                "synopsis_state": True,
                "status_message": "Analysis completed successfully"
            }
        }
