"""
Pydantic models for TenderIQ Analyze module.

Request and response validation models for all analyze endpoints.
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ==================== Request Models ====================

class AnalyzeTenderRequest(BaseModel):
    """Request to initiate tender analysis"""
    document_ids: Optional[List[UUID]] = None  # Specific documents to analyze
    analysis_type: Optional[str] = "full"  # "full", "summary", "risk-only"
    include_risk_assessment: bool = True
    include_rfp_analysis: bool = True
    include_scope_of_work: bool = True


class GenerateOnePagerRequest(BaseModel):
    """Request to generate one-pager"""
    format: str = "markdown"  # "markdown", "html", "pdf"
    include_risk_assessment: bool = True
    include_scope_of_work: bool = True
    include_financials: bool = True
    max_length: int = 800  # words


# ==================== Response Models - Analysis Metadata ====================

class AnalysisStatusResponse(BaseModel):
    """Status of an ongoing analysis"""
    analysis_id: UUID
    tender_id: UUID
    status: str  # "pending", "processing", "completed", "failed"
    progress: int  # 0-100
    current_step: str  # "initializing", "parsing-documents", "analyzing-risk", etc
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AnalysisInitiatedResponse(BaseModel):
    """Response when analysis is initiated (202 Accepted)"""
    analysis_id: UUID
    tender_id: UUID
    status: str
    created_at: datetime
    estimated_completion_time: int  # milliseconds


# ==================== Response Models - Risk Assessment ====================

class RiskDetailResponse(BaseModel):
    """Single risk identified"""
    id: UUID
    level: str  # "low", "medium", "high", "critical"
    category: str  # "regulatory", "financial", "operational", "contractual", "market"
    title: str
    description: str
    impact: str  # "low", "medium", "high"
    likelihood: str  # "low", "medium", "high"
    mitigation_strategy: Optional[str] = None
    recommended_action: Optional[str] = None
    related_documents: List[UUID] = []

    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentResponse(BaseModel):
    """Risk assessment for a tender"""
    tender_id: UUID
    overall_risk_level: str  # "low", "medium", "high", "critical"
    risk_score: int  # 0-100
    executive_summary: Optional[str] = None
    risks: List[RiskDetailResponse]
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentInAnalysis(BaseModel):
    """Risk assessment component in full analysis results"""
    overall_risk_level: str
    risk_score: int
    risks: List[RiskDetailResponse]


# ==================== Response Models - RFP Analysis ====================

class RFPSectionComplianceResponse(BaseModel):
    """Compliance status for RFP section"""
    status: str  # "compliant", "non-compliant", "requires-review"
    issues: List[str] = []


class DocumentReferenceResponse(BaseModel):
    """Reference to document and location"""
    document_id: UUID
    page_number: Optional[int] = None


class RFPSectionResponse(BaseModel):
    """Single RFP section"""
    id: UUID
    number: str  # "1.1", "2.3", etc
    title: str
    description: str
    key_requirements: List[str]
    compliance: Optional[RFPSectionComplianceResponse] = None
    estimated_complexity: str  # "low", "medium", "high"
    related_sections: List[str] = []
    document_references: List[DocumentReferenceResponse] = []

    model_config = ConfigDict(from_attributes=True)


class RFPSectionSummaryResponse(BaseModel):
    """Summary of all RFP sections"""
    total_requirements: int
    criticality: dict  # {"high": 12, "medium": 23, "low": 10}


class RFPAnalysisResponse(BaseModel):
    """RFP section analysis for a tender"""
    tender_id: UUID
    total_sections: int
    sections: List[RFPSectionResponse]
    summary: RFPSectionSummaryResponse

    model_config = ConfigDict(from_attributes=True)


class RFPAnalysisInResults(BaseModel):
    """RFP analysis component in full analysis results"""
    sections: List[RFPSectionResponse]
    missing_documents: List[str] = []


# ==================== Response Models - Scope of Work ====================

class WorkItemResponse(BaseModel):
    """Single work item"""
    id: UUID
    description: str
    estimated_duration: str
    priority: str  # "high", "medium", "low"
    dependencies: List[UUID] = []


class DeliverableResponse(BaseModel):
    """Deliverable with acceptance criteria"""
    id: UUID
    description: str
    delivery_date: Optional[str] = None  # "YYYY-MM-DD"
    acceptance_criteria: List[str] = []


class KeyDatesResponse(BaseModel):
    """Key project dates"""
    start_date: Optional[str] = None  # "YYYY-MM-DD"
    end_date: Optional[str] = None


class ScopeOfWorkDetailResponse(BaseModel):
    """Detailed scope of work"""
    description: str
    work_items: List[WorkItemResponse] = []
    key_deliverables: List[DeliverableResponse] = []
    estimated_total_effort: int  # days
    estimated_total_duration: str
    key_dates: KeyDatesResponse


class ScopeOfWorkResponse(BaseModel):
    """Scope of work analysis for a tender"""
    tender_id: UUID
    scope_of_work: ScopeOfWorkDetailResponse
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScopeOfWorkInResults(BaseModel):
    """Scope of work component in full analysis results"""
    description: str
    estimated_duration: str
    key_deliverables: List[str]
    estimated_effort: int  # days


# ==================== Response Models - Summary ====================

class TenderSummaryResponse(BaseModel):
    """Summary of tender analysis"""
    title: str
    overview: str
    key_points: List[str]


# ==================== Response Models - One-Pager ====================

class OnePagerResponse(BaseModel):
    """Generated one-pager document"""
    tender_id: UUID
    one_pager: dict  # {content: str, format: str, generatedAt: datetime}

    model_config = ConfigDict(from_attributes=True)


# ==================== Response Models - Data Sheet ====================

class BasicInfoResponse(BaseModel):
    """Basic tender information"""
    tender_number: str
    tender_name: str
    tendering_authority: str
    tender_url: str


class FinancialInfoResponse(BaseModel):
    """Financial information"""
    estimated_value: Optional[float] = None
    currency: str = "INR"
    emd: Optional[float] = None
    bid_security_required: bool = False


class TemporalInfoResponse(BaseModel):
    """Timeline information"""
    release_date: Optional[str] = None
    due_date: Optional[str] = None
    opening_date: Optional[str] = None


class ScopeInfoResponse(BaseModel):
    """Scope information"""
    location: str
    category: str
    description: str


class AnalysisInfoResponse(BaseModel):
    """Analysis summary in datasheet"""
    risk_level: str
    estimated_effort: int
    complexity_level: str


class DataSheetContentResponse(BaseModel):
    """Data sheet content"""
    basic_info: BasicInfoResponse
    financial_info: FinancialInfoResponse
    temporal: TemporalInfoResponse
    scope: ScopeInfoResponse
    analysis: Optional[AnalysisInfoResponse] = None


class DataSheetResponse(BaseModel):
    """Generated data sheet"""
    tender_id: UUID
    data_sheet: DataSheetContentResponse
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== Response Models - Full Analysis Results ====================

class AnalysisResultsResponse(BaseModel):
    """Complete analysis results for a tender"""
    analysis_id: UUID
    tender_id: UUID
    status: str  # "completed" or "failed"
    results: dict  # {summary, riskAssessment, rfpAnalysis, scopeOfWork, onePager}
    completed_at: datetime
    processing_time_ms: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ==================== Response Models - Analysis List ====================

class AnalysisListItemResponse(BaseModel):
    """Item in analyses list"""
    analysis_id: UUID
    tender_id: UUID
    tender_name: Optional[str] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PaginationResponse(BaseModel):
    """Pagination metadata"""
    total: int
    limit: int
    offset: int


class AnalysesListResponse(BaseModel):
    """List of recent analyses"""
    analyses: List[AnalysisListItemResponse]
    pagination: PaginationResponse


# ==================== Response Models - Delete ====================

class DeleteAnalysisResponse(BaseModel):
    """Response to delete analysis"""
    success: bool
    message: str


# ==================== Response Models - Error ====================

class ErrorResponse(BaseModel):
    """Consistent error response format"""
    error: str
    code: str  # "INVALID_REQUEST", "UNAUTHORIZED", "NOT_FOUND", etc
    details: Optional[str] = None
    timestamp: datetime
