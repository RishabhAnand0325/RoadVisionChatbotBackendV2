from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Hearing(BaseModel):
    """Hearing information"""
    date: str
    judge: str
    purpose: str
    outcome: str
    document: str


class CaseDocument(BaseModel):
    """Document metadata"""
    name: str
    uploadDate: str
    type: str


class AIInsights(BaseModel):
    """AI-generated insights about the case"""
    summary: str
    winProbability: str
    estimatedDuration: str
    recommendedAction: str


class CaseBase(BaseModel):
    """Base case information"""
    caseTitle: str
    caseId: str
    courtName: str
    caseType: str
    litigationStatus: str
    filingDate: str
    filingNumber: Optional[str] = "N/A"
    registrationNumber: Optional[str] = "N/A"
    registrationDate: Optional[str] = "N/A"
    cnrNumber: Optional[str] = "N/A"
    jurisdiction: Optional[str] = "N/A"
    courtNumber: Optional[str] = "N/A"
    judgeName: Optional[str] = "N/A"
    caseStage: Optional[str] = "N/A"
    underActs: Optional[str] = "N/A"
    sections: Optional[str] = "N/A"
    policeStation: Optional[str] = "N/A"
    firNumber: Optional[str] = "N/A"
    petitioner: Optional[str] = "N/A"
    petitionerAdvocate: Optional[str] = "N/A"
    respondent: Optional[str] = "N/A"
    respondentAdvocate: Optional[str] = "N/A"


class CaseResponse(CaseBase):
    """Complete case response with all details"""
    id: int
    hearings: List[Hearing] = []
    documents: List[CaseDocument] = []
    aiInsights: AIInsights


class CaseCreateRequest(BaseModel):
    """Optional metadata when creating a case"""
    caseTitle: Optional[str] = None
    caseId: Optional[str] = None
    courtName: Optional[str] = None
    caseType: Optional[str] = "Arbitration"
    litigationStatus: Optional[str] = "Pending"


class CaseUpdateRequest(CaseBase):
    """Request to update case information"""
    hearings: Optional[List[Hearing]] = None
    documents: Optional[List[CaseDocument]] = None


class UploadResponse(BaseModel):
    """Response after uploading a document"""
    message: str
    case: CaseResponse


class CasesListResponse(BaseModel):
    """Response with list of all cases"""
    cases: List[CaseResponse]
    totalActiveCases: int
    upcomingHearings: int
    avgCaseDuration: float


class SaveResearchCaseRequest(BaseModel):
    """Request to save a legal research case to case tracker"""
    title: str = Field(..., description="Case title from Indian Kanoon")
    tid: str = Field(..., description="Indian Kanoon document ID")
    docsource: str = Field(..., description="Source court/tribunal")
    date: Optional[str] = Field(None, description="Date the case was decided")
