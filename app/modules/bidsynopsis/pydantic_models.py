from pydantic import BaseModel, ConfigDict
from typing import Optional, List
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
    ceigallValue: Optional[str] = ""


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


# ==================== Error Response ====================

class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    status_code: int