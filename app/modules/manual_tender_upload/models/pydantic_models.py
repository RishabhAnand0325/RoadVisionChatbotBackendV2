"""
Pydantic models for manual tender upload endpoints.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ManualTenderUploadRequest(BaseModel):
    """Request model for manual tender upload."""
    tender_title: str = Field(..., min_length=1, max_length=500, description="Title of the tender")
    tender_description: Optional[str] = Field(None, max_length=5000, description="Description of the tender")
    employer_name: Optional[str] = Field(None, max_length=255)
    estimated_cost: Optional[float] = Field(None, ge=0, description="Estimated cost in crore")
    submission_deadline: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=255)
    opportunity_name: Optional[str] = Field(None, max_length=500, description="Name of opportunity this relates to")
    opportunity_description: Optional[str] = Field(None, max_length=5000)


class ManualTenderUploadResponse(BaseModel):
    """Response model for manual tender upload."""
    id: str
    upload_reference: str
    tender_title: str
    file_name: str
    file_size: int
    created_at: datetime
    is_analyzed: bool
    analysis_id: Optional[str] = None
    opportunity_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class ManualTenderDetailsResponse(BaseModel):
    """Detailed response for a single manual tender upload."""
    id: str
    user_id: str
    upload_reference: str
    tender_title: str
    tender_description: Optional[str]
    file_name: str
    file_size: int
    employer_name: Optional[str]
    estimated_cost: Optional[float]
    submission_deadline: Optional[datetime]
    location: Optional[str]
    category: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_analyzed: bool
    analysis_id: Optional[str]
    opportunity_name: Optional[str]
    opportunity_description: Optional[str]
    
    class Config:
        from_attributes = True


class ManualTenderListResponse(BaseModel):
    """Response model for listing manual tender uploads."""
    id: str
    upload_reference: str
    tender_title: str
    employer_name: Optional[str]
    category: Optional[str]
    location: Optional[str]
    file_name: str
    created_at: datetime
    is_analyzed: bool
    opportunity_name: Optional[str]
    
    class Config:
        from_attributes = True
