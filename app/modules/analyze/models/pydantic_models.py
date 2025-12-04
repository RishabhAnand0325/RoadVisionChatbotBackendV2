"""
Pydantic schemas for the structured JSON data stored in TenderAnalysis.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


# ============================================================================
# ONE-PAGER SCHEMAS
# ============================================================================

class RiskAnalysisSchema(BaseModel):
    """Risk analysis within the one-pager."""
    summary: Optional[str] = None
    high_risk_factors: Optional[List[str]] = []
    low_risk_areas: Optional[List[str]] = []
    compliance_concerns: Optional[List[str]] = []


class OnePagerSchema(BaseModel):
    """Defines the structure for the one_pager_json field."""
    project_overview: str
    eligibility_highlights: List[str] = Field(default_factory=list)
    important_dates: List[str] = Field(default_factory=list)
    financial_requirements: List[str] = Field(default_factory=list)
    risk_analysis: Optional[RiskAnalysisSchema] = None


# ============================================================================
# SCOPE OF WORK SCHEMAS
# ============================================================================

class WorkComponentSchema(BaseModel):
    """Individual component within a work package."""
    item: str
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    specifications: Optional[str] = None


class WorkPackageSchema(BaseModel):
    """Work package containing multiple components."""
    id: str
    name: str
    description: Optional[str] = None
    components: Optional[List[WorkComponentSchema]] = Field(default_factory=list)
    estimated_duration: Optional[str] = None
    dependencies: Optional[List[str]] = Field(default_factory=list)


class MaterialSpecificationSchema(BaseModel):
    """Material specification details."""
    material: str
    specification: str
    source: Optional[str] = None
    testing_standard: Optional[str] = None


class TechnicalSpecificationsSchema(BaseModel):
    """Technical specifications for the project."""
    standards: Optional[List[str]] = Field(default_factory=list)
    quality_requirements: Optional[List[str]] = Field(default_factory=list)
    materials_specification: Optional[List[MaterialSpecificationSchema]] = Field(default_factory=list)
    testing_requirements: Optional[List[str]] = Field(default_factory=list)


class DeliverableSchema(BaseModel):
    """Project deliverable."""
    item: str
    description: Optional[str] = None
    timeline: Optional[str] = None


class ScopeOfWorkProjectDetailsSchema(BaseModel):
    """Project details within scope of work."""
    project_name: Optional[str] = None
    location: Optional[str] = None
    total_length: Optional[str] = None
    total_area: Optional[str] = None
    duration: Optional[str] = None
    contract_value: Optional[str] = None


class ScopeOfWorkSchema(BaseModel):
    """Defines the structure for the scope_of_work_json field."""
    project_details: Optional[ScopeOfWorkProjectDetailsSchema] = None
    work_packages: Optional[List[WorkPackageSchema]] = Field(default_factory=list)
    technical_specifications: Optional[TechnicalSpecificationsSchema] = None
    deliverables: Optional[List[DeliverableSchema]] = Field(default_factory=list)
    exclusions: Optional[List[str]] = Field(default_factory=list)


# ============================================================================
# DATA SHEET SCHEMAS
# ============================================================================

class DataSheetItemSchema(BaseModel):
    """Individual item in a datasheet section."""
    label: str
    value: str
    type: Optional[str] = None  # e.g., 'money', 'date'
    highlight: Optional[bool] = False


class DataSheetSchema(BaseModel):
    """Defines the structure for the data_sheet_json field."""
    project_information: Optional[List[DataSheetItemSchema]] = Field(default_factory=list)
    contract_details: Optional[List[DataSheetItemSchema]] = Field(default_factory=list)
    financial_details: Optional[List[DataSheetItemSchema]] = Field(default_factory=list)
    technical_summary: Optional[List[DataSheetItemSchema]] = Field(default_factory=list)
    important_dates: Optional[List[DataSheetItemSchema]] = Field(default_factory=list)


# ============================================================================
# RFP SECTION SCHEMAS
# ============================================================================

class RFPSectionSchema(BaseModel):
    section_name: str;
    section_title: str;
    summary: str;
    key_requirements: List[str];
    compliance_issues: List[str];
    page_references: List[int];


class RFPSummarySchema(BaseModel):
    total_sections: int
    total_requirements: int


class RFPSectionsResponseSchema(BaseModel):
    """Complete RFP sections analysis."""
    rfp_summary: Optional[RFPSummarySchema] = None
    sections: Optional[List[RFPSectionSchema]] = Field(default_factory=list)


# ============================================================================
# DOCUMENT TEMPLATE SCHEMAS
# ============================================================================

class DocumentTemplateSchema(BaseModel):
    """Single document template."""
    id: str
    name: str
    description: Optional[str] = None
    format: str
    downloadUrl: Optional[str] = None
    mandatory: bool = True
    annex: Optional[str] = None


class TemplatesResponseSchema(BaseModel):
    """All document templates grouped by category."""
    bid_submission_forms: Optional[List[DocumentTemplateSchema]] = Field(default_factory=list)
    financial_formats: Optional[List[DocumentTemplateSchema]] = Field(default_factory=list)
    technical_documents: Optional[List[DocumentTemplateSchema]] = Field(default_factory=list)
    compliance_formats: Optional[List[DocumentTemplateSchema]] = Field(default_factory=list)


# ============================================================================
# MAIN RESPONSE SCHEMAS
# ============================================================================

class TenderAnalysisResponse(BaseModel):
    """Complete tender analysis response matching frontend mock structure."""
    id: str
    tender_id: str
    status: str
    progress: Optional[int] = Field(None, ge=0, le=100, description="Analysis progress percentage (0-100)")
    analyzed_at: Optional[datetime] = None

    one_pager: Optional[OnePagerSchema] = None
    scope_of_work: Optional[ScopeOfWorkSchema] = None
    rfp_sections: Optional[RFPSectionsResponseSchema] = None
    data_sheet: Optional[DataSheetSchema] = None
    templates: Optional[TemplatesResponseSchema] = None

    class Config:
        from_attributes = True


# ============================================================================
# LEGACY SCHEMAS (KEPT FOR BACKWARD COMPATIBILITY)
# ============================================================================

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
