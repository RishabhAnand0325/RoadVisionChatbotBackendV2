from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
from enum import Enum


# ==================== Basic Info Models ====================

class BasicInfoItem(BaseModel):
    """Single item in the basic information section."""
    sno: int
    item: str
    description: str


class BasicInfoResponse(BaseModel):
    """Response containing basic tender information."""
    basicInfo: List[BasicInfoItem]

    model_config = ConfigDict(from_attributes=True)


# ==================== Requirements Models ====================

class RequirementItem(BaseModel):
    """Single eligibility requirement item."""
    description: str
    requirement: str
    extractedValue: Optional[str] = ""  # Value extracted from tender documents
    ceigallValue: Optional[str] = ""       # Calculated CEIGALL value


class AllRequirementsResponse(BaseModel):
    """Response containing all eligibility requirements."""
    allRequirements: List[RequirementItem]

    model_config = ConfigDict(from_attributes=True)


# ==================== Bid Synopsis Response ====================

class BidSynopsisResponse(BaseModel):
    """Complete Bid Synopsis Response with both basic info and requirements."""
    basicInfo: List[BasicInfoItem]
    allRequirements: List[RequirementItem]

    model_config = ConfigDict(from_attributes=True)


# ==================== Save Bid Synopsis Request ====================

class SaveBidSynopsisRequest(BaseModel):
    """Request model for saving edited bid synopsis data."""
    tender_id: str
    user_id: Optional[str] = None
    ceigall_data: Dict[int, str] = {}  # Index -> value mapping
    requirement_data: Dict[int, str] = {}  # Index -> edited requirement mapping
    extracted_value_data: Dict[int, str] = {}  # Index -> edited extracted value mapping

    model_config = ConfigDict(from_attributes=True)


class SaveBidSynopsisResponse(BaseModel):
    """Response model for save bid synopsis operation."""
    success: bool
    message: str
    tender_id: str

    model_config = ConfigDict(from_attributes=True)


# ==================== Error Response ====================

class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    status_code: int