"""
API Endpoints for Corrigendum Tracking

Provides endpoints to:
1. Detect changes in tenders (corrigendums)
2. Apply corrigendum updates
3. View change history
4. Get comparison views
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime, timezone

from app.db.database import get_db_session
from app.modules.auth.services.auth_service import get_current_active_user
from app.modules.auth.db.schema import User
from app.modules.tenderiq.services.corrigendum_service import CorrigendumTrackingService
from app.modules.tenderiq.models.pydantic_models import TenderHistoryItem
from app.modules.scraper.db.schema import ScrapedTender


router = APIRouter(prefix="/corrigendum", tags=["TenderIQ - Corrigendum Tracking"])


# ==================== Request/Response Models ====================

class ChangeRecord(BaseModel):
    """Represents a single field change"""
    field: str
    field_label: str
    old_value: Optional[str]
    new_value: Optional[str]
    change_type: str
    timestamp: str


class CorrigendumApplicationRequest(BaseModel):
    """Request to apply a corrigendum"""
    tender_id: str
    note: Optional[str] = None


class CorrigendumApplicationResponse(BaseModel):
    """Response after applying a corrigendum"""
    status: str
    message: str
    changes: List[ChangeRecord]
    action_log_id: Optional[str] = None


class ChangeHistoryRecord(BaseModel):
    """A historical change record"""
    id: str
    timestamp: str
    user_id: str
    changes: List[Dict[str, str]]
    note: str


class TenderChangeHistoryResponse(BaseModel):
    """Complete change history for a tender"""
    tender_id: str
    total_changes: int
    history: List[ChangeHistoryRecord]


# ==================== Endpoints ====================

@router.get("/{tender_id}/changes", response_model=List[ChangeRecord])
def get_tender_changes(
    tender_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get detected changes for a tender (compares with latest scraped data).
    
    This endpoint is useful for showing "A corrigendum was detected" notifications.
    """
    service = CorrigendumTrackingService(db)
    
    # Get latest scraped data for this tender
    latest_scraped = db.query(ScrapedTender).filter(
        ScrapedTender.tender_id_str == tender_id
    ).order_by(ScrapedTender.scraped_at.desc()).first()
    
    if not latest_scraped:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scraped data found for this tender"
        )
    
    changes = service.detect_changes(tender_id, latest_scraped)
    
    return [service._format_change(change) for change in changes]


@router.post("/{tender_id}/apply", response_model=CorrigendumApplicationResponse)
def apply_corrigendum(
    tender_id: str,
    request: CorrigendumApplicationRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Apply corrigendum changes to a tender.
    
    This updates the tender with new values and logs the changes.
    """
    service = CorrigendumTrackingService(db)
    
    # Get latest scraped data
    latest_scraped = db.query(ScrapedTender).filter(
        ScrapedTender.tender_id_str == tender_id
    ).order_by(ScrapedTender.scraped_at.desc()).first()
    
    if not latest_scraped:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scraped data found for this tender"
        )
    
    result = service.apply_corrigendum(
        tender_id=tender_id,
        new_scraped_data=latest_scraped,
        user_id=current_user.id,
        corrigendum_note=request.note
    )
    
    return result


@router.get("/{tender_id}/history", response_model=List[TenderHistoryItem])
def get_tender_change_history(
    tender_id: str,
    db: Session = Depends(get_db_session)
):
    """
    Get the complete change history for a tender in frontend-compatible format.
    
    Returns TenderHistoryItem[] that matches the frontend type definitions.
    Shows all corrigendums applied over time with what changed.
    """
    service = CorrigendumTrackingService(db)
    
    history = service.get_tender_change_history(tender_id)
    
    return history


@router.get("/{tender_id}/has-changes", response_model=Dict[str, Any])
def check_for_changes(
    tender_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Quick check if a tender has pending corrigendum changes.
    
    Returns a boolean flag and count of changes.
    Useful for showing badges/notifications in the UI.
    """
    service = CorrigendumTrackingService(db)
    
    # Get latest scraped data
    latest_scraped = db.query(ScrapedTender).filter(
        ScrapedTender.tender_id_str == tender_id
    ).order_by(ScrapedTender.scraped_at.desc()).first()
    
    if not latest_scraped:
        return {
            "has_changes": False,
            "change_count": 0,
            "message": "No scraped data available"
        }
    
    changes = service.detect_changes(tender_id, latest_scraped)
    
    return {
        "has_changes": len(changes) > 0,
        "change_count": len(changes),
        "message": f"{len(changes)} field(s) changed" if changes else "No changes detected"
    }


@router.get("/{tender_id}/comparison", response_model=Dict[str, Any])
def get_tender_comparison_view(
    tender_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a side-by-side comparison view of tender before and after changes.
    
    Returns current values and new values for all changed fields.
    Perfect for displaying "Before → After" views in the UI.
    """
    service = CorrigendumTrackingService(db)
    
    from app.modules.tenderiq.db.repository import TenderRepository
    repo = TenderRepository(db)
    
    # Get current tender
    tender = repo.get_by_tender_ref(tender_id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found"
        )
    
    # Get latest scraped data
    latest_scraped = db.query(ScrapedTender).filter(
        ScrapedTender.tender_id_str == tender_id
    ).order_by(ScrapedTender.scraped_at.desc()).first()
    
    if not latest_scraped:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scraped data found"
        )
    
    changes = service.detect_changes(tender_id, latest_scraped)
    
    comparison = {
        "tender_id": tender_id,
        "tender_title": tender.tender_title,
        "comparison_timestamp": datetime.now(timezone.utc).isoformat(),
        "changes": []
    }
    
    for change in changes:
        comparison["changes"].append({
            "field": change.field,
            "field_label": service.FIELD_LABELS.get(change.field, change.field),
            "current_value": str(change.old_value) if change.old_value else "Not set",
            "new_value": str(change.new_value) if change.new_value else "Removed",
            "change_type": change.change_type
        })
    
    return comparison
