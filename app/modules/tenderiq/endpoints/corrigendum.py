"""
API Endpoints for Corrigendum Tracking

Provides endpoints to:
1. Detect changes in tenders (corrigendums)
2. Apply corrigendum updates
3. View change history
4. Get comparison views
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime, timezone
import logging

from app.db.database import get_db_session
from app.modules.auth.services.auth_service import get_current_active_user
from app.modules.auth.db.schema import User
from app.modules.tenderiq.services.corrigendum_service import CorrigendumTrackingService
from app.modules.tenderiq.models.pydantic_models import TenderHistoryItem
from app.modules.scraper.db.schema import ScrapedTender

logger = logging.getLogger(__name__)

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
    
    Includes:
    - Corrigendum history from TenderActionHistory
    - Document changes scraped from the tender detail page (document_changes_json)
    - Actions history scraped from the tender detail page (actions_history_json)
    """
    from app.modules.tenderiq.db.schema import Tender
    from app.modules.scraper.db.schema import ScrapedTender
    from sqlalchemy.orm import joinedload
    
    service = CorrigendumTrackingService(db)
    
    logger.info(f"Fetching tender history for: {tender_id}")
    
    # Get history from TenderActionHistory (existing corrigendum tracking)
    # First try to find Tender by ID (if UUID) or TDR to get corrigendum history
    tender = None
    try:
        # Try to parse as UUID first
        from uuid import UUID
        try:
            tender_uuid = UUID(tender_id)
            tender = db.query(Tender).filter(Tender.id == tender_uuid).first()
            if tender:
                logger.info(f"Found tender by UUID: {tender.id}, TDR: {tender.tender_ref_number}")
        except (ValueError, AttributeError):
            # Not a UUID, try as TDR
            tender = db.query(Tender).filter(Tender.tender_ref_number == tender_id).first()
            if tender:
                logger.info(f"Found tender by TDR: {tender.tender_ref_number}, ID: {tender.id}")
    except Exception as e:
        # If UUID parsing fails, try as TDR
        logger.warning(f"Error parsing tender_id {tender_id}: {str(e)}")
        tender = db.query(Tender).filter(Tender.tender_ref_number == tender_id).first()
        if tender:
            logger.info(f"Found tender by TDR (fallback): {tender.tender_ref_number}")
    
    history = []
    if tender:
        # Get corrigendum history from TenderActionHistory
        history = service.get_tender_change_history(str(tender.id))
        logger.info(f"Found {len(history)} corrigendum history items from TenderActionHistory")
    else:
        # If no Tender found, try ScrapedTender directly
        scraped_tender = None
        try:
            # Try as UUID first
            from uuid import UUID
            try:
                scraped_uuid = UUID(tender_id)
                scraped_tender = db.query(ScrapedTender).filter(ScrapedTender.id == scraped_uuid).first()
            except (ValueError, AttributeError):
                # Not a UUID, try as TDR
                scraped_tender = db.query(ScrapedTender).filter(ScrapedTender.tdr == tender_id).first()
        except Exception:
            # If UUID parsing fails, try as TDR
            scraped_tender = db.query(ScrapedTender).filter(ScrapedTender.tdr == tender_id).first()
        
        if scraped_tender and scraped_tender.tdr:
            # Try to find Tender by TDR for corrigendum history
            tender_by_tdr = db.query(Tender).filter(
                Tender.tender_ref_number == scraped_tender.tdr
            ).first()
            if tender_by_tdr:
                history = service.get_tender_change_history(str(tender_by_tdr.id))
    
    # Also get scraped document changes and actions history from ScrapedTender
    # Also convert detected changes to history items if they exist
    try:
        # Re-find tender and scraped_tender (we may have found them above)
        if not tender:
            try:
                from uuid import UUID
                try:
                    tender_uuid = UUID(tender_id)
                    tender = db.query(Tender).filter(Tender.id == tender_uuid).first()
                except (ValueError, AttributeError):
                    tender = db.query(Tender).filter(Tender.tender_ref_number == tender_id).first()
            except Exception:
                tender = db.query(Tender).filter(Tender.tender_ref_number == tender_id).first()
        
        scraped_tender = None
        tender_tdr = None
        
        if tender:
            # Get the most recent ScrapedTender for this tender.
            # Try both tender_id_str and tdr to improve hit-rate.
            scraped_tender = (
                db.query(ScrapedTender)
                .filter(
                    or_(
                        ScrapedTender.tender_id_str == tender.tender_ref_number,
                        ScrapedTender.tdr == tender.tender_ref_number,
                    )
                )
                .order_by(
                    ScrapedTender.scraped_at.desc()
                    if hasattr(ScrapedTender, "scraped_at")
                    else ScrapedTender.id.desc()
                )
                .first()
            )

            # If latest scrape has no changes/actions, try to find any previous scrape with data
            if not scraped_tender or (
                not scraped_tender.document_changes_json
                and not scraped_tender.actions_history_json
            ):
                fallback_scraped = (
                    db.query(ScrapedTender)
                    .filter(
                        or_(
                            ScrapedTender.tender_id_str == tender.tender_ref_number,
                            ScrapedTender.tdr == tender.tender_ref_number,
                        ),
                        or_(
                            ScrapedTender.document_changes_json.isnot(None),
                            ScrapedTender.actions_history_json.isnot(None),
                        ),
                    )
                    .order_by(
                        ScrapedTender.scraped_at.desc()
                        if hasattr(ScrapedTender, "scraped_at")
                        else ScrapedTender.id.desc()
                    )
                    .first()
                )
                if fallback_scraped:
                    scraped_tender = fallback_scraped
            tender_tdr = tender.tender_ref_number
        else:
            # If no Tender found, try to find ScrapedTender directly by ID or TDR
            try:
                from uuid import UUID
                try:
                    scraped_uuid = UUID(tender_id)
                    scraped_tender = db.query(ScrapedTender).filter(ScrapedTender.id == scraped_uuid).order_by(ScrapedTender.scraped_at.desc() if hasattr(ScrapedTender, 'scraped_at') else ScrapedTender.id.desc()).first()
                except (ValueError, AttributeError):
                    scraped_tender = db.query(ScrapedTender).filter(ScrapedTender.tdr == tender_id).order_by(ScrapedTender.scraped_at.desc() if hasattr(ScrapedTender, 'scraped_at') else ScrapedTender.id.desc()).first()
            except Exception:
                scraped_tender = db.query(ScrapedTender).filter(ScrapedTender.tdr == tender_id).order_by(ScrapedTender.scraped_at.desc() if hasattr(ScrapedTender, 'scraped_at') else ScrapedTender.id.desc()).first()
            
            if scraped_tender:
                tender_tdr = scraped_tender.tdr
                
                # If we have ScrapedTender but no Tender, check for detected changes
                # by comparing with previous scrapes
                if scraped_tender.tdr:
                    from sqlalchemy import and_
                    previous_scrape = db.query(ScrapedTender).filter(
                        and_(
                            ScrapedTender.tdr == scraped_tender.tdr,
                            ScrapedTender.id != scraped_tender.id
                        )
                    ).order_by(ScrapedTender.scraped_at.desc() if hasattr(ScrapedTender, 'scraped_at') else ScrapedTender.id.desc()).first()
                    
                    if previous_scrape:
                        # Detect changes between previous and current scrape
                        try:
                            detected_changes = service.detect_changes(scraped_tender.tdr, scraped_tender)
                            if detected_changes:
                                # Convert detected changes to history items
                                # Convert TenderChange objects to dict format for _determine_history_type_and_dates
                                changes_dict = []
                                for change in detected_changes:
                                    field_label = service.FIELD_LABELS.get(change.field, change.field)
                                    changes_dict.append({
                                        "field": field_label,
                                        "old_value": str(change.old_value) if change.old_value else "",
                                        "new_value": str(change.new_value) if change.new_value else ""
                                    })
                                
                                # Determine history type and date changes from all changes
                                history_type, date_change = service._determine_history_type_and_dates(changes_dict)
                                if date_change is None:
                                    date_change = {"from_date": None, "to_date": None}
                                
                                # Create a single history item for all detected changes
                                history_item = {
                                    "id": f"detected_{len(history)}",
                                    "tender_id": str(scraped_tender.id),
                                    "user_id": None,
                                    "tdr": scraped_tender.tdr or "",
                                    "type": history_type,
                                    "note": service._format_changes_note(detected_changes),
                                    "update_date": scraped_tender.scraped_at.isoformat() if hasattr(scraped_tender, 'scraped_at') and scraped_tender.scraped_at else datetime.now(timezone.utc).isoformat(),
                                    "files_changed": [],
                                    "date_change": date_change
                                }
                                history.append(history_item)
                        except Exception as e:
                            # If detect_changes fails (e.g., no Tender record), skip it
                            pass
            
        if scraped_tender:
            logger.info(f"Found ScrapedTender: {scraped_tender.id}, TDR: {scraped_tender.tdr}")
            
            # ALWAYS check for detected changes if there are multiple scrapes (even if Tender exists)
            # This ensures corrigendums detected during scraping are shown
            if scraped_tender.tdr:
                from sqlalchemy import and_
                previous_scrape = db.query(ScrapedTender).filter(
                    and_(
                        ScrapedTender.tdr == scraped_tender.tdr,
                        ScrapedTender.id != scraped_tender.id
                    )
                ).order_by(ScrapedTender.scraped_at.desc() if hasattr(ScrapedTender, 'scraped_at') else ScrapedTender.id.desc()).first()
                
                if previous_scrape:
                    # Detect changes between previous and current scrape
                    try:
                        detected_changes = service.detect_changes(scraped_tender.tdr, scraped_tender)
                        if detected_changes:
                            logger.info(f"Detected {len(detected_changes)} changes for tender {tender_id}")
                            # Convert detected changes to history items
                            changes_dict = []
                            for change in detected_changes:
                                field_label = service.FIELD_LABELS.get(change.field, change.field)
                                changes_dict.append({
                                    "field": field_label,
                                    "old_value": str(change.old_value) if change.old_value else "",
                                    "new_value": str(change.new_value) if change.new_value else ""
                                })
                            
                            # Determine history type and date changes from all changes
                            history_type, date_change = service._determine_history_type_and_dates(changes_dict)
                            if date_change is None:
                                date_change = {"from_date": None, "to_date": None}
                            
                            # Create a single history item for all detected changes
                            history_item = {
                                "id": f"detected_{len(history)}",
                                "tender_id": str(tender.id) if tender else str(scraped_tender.id),
                                "user_id": None,
                                "tdr": scraped_tender.tdr or "",
                                "type": history_type,
                                "note": service._format_changes_note(detected_changes),
                                "update_date": scraped_tender.scraped_at.isoformat() if hasattr(scraped_tender, 'scraped_at') and scraped_tender.scraped_at else datetime.now(timezone.utc).isoformat(),
                                "files_changed": [],
                                "date_change": date_change
                            }
                            history.append(history_item)
                            logger.info(f"Added detected corrigendum to history for tender {tender_id}")
                    except Exception as e:
                        logger.warning(f"Error detecting changes for tender {tender_id}: {str(e)}", exc_info=True)
            
            # Add scraped document changes
            if scraped_tender.document_changes_json:
                logger.info(f"Processing document_changes_json for tender {tender_id}")
                scraped_changes = scraped_tender.document_changes_json
                # If stored as JSON string, parse it
                if isinstance(scraped_changes, str):
                    try:
                        import json
                        scraped_changes = json.loads(scraped_changes)
                    except Exception:
                        scraped_changes = {}
                items_list = []
                
                # Handle different data formats
                if isinstance(scraped_changes, dict):
                    # Standard format: {'items': [...]}
                    if 'items' in scraped_changes:
                        items_list = scraped_changes.get('items', [])
                    # Alternative: direct dict with item data
                    elif 'type' in scraped_changes or 'note' in scraped_changes:
                        items_list = [scraped_changes]
                elif isinstance(scraped_changes, list):
                    # Direct list format
                    items_list = scraped_changes
                
                # Process each item
                for idx, item in enumerate(items_list):
                    if not isinstance(item, dict):
                        continue
                    
                    try:
                        # Convert scraped history item to TenderHistoryItem format
                        history_item = {
                            "id": item.get('id') or f"scraped_{len(history)}_{idx}",
                            "tender_id": str(tender.id) if tender else str(scraped_tender.id),
                            "user_id": None,
                            "tdr": tender_tdr or scraped_tender.tdr or "",
                            "type": item.get('type', 'corrigendum'),
                            "note": item.get('note', item.get('description', 'No description available')),
                            "update_date": item.get('update_date', item.get('date', scraped_tender.scraped_at.isoformat() if hasattr(scraped_tender, 'scraped_at') and scraped_tender.scraped_at else 'N/A')),
                            "files_changed": [
                                {
                                    "id": str(i),
                                    "file_name": f.get('file_name', f.get('name', '')),
                                    "file_url": f.get('file_url', f.get('url', '')),
                                    "dms_path": f.get('file_url', f.get('url', '')),
                                    "file_description": f.get('file_description', f.get('description', '')),
                                    "file_size": f.get('file_size', f.get('size', '')),
                                    "is_cached": False,
                                    "cache_status": "pending",
                                    "file_type": f.get('file_type', f.get('file_description', 'Unknown'))
                                }
                                for i, f in enumerate(item.get('files_changed', item.get('files', [])))
                            ],
                            "date_change": {
                                "from_date": item.get('date_change_from', item.get('from_date')),
                                "to_date": item.get('date_change_to', item.get('to_date'))
                            } if (item.get('date_change_from') or item.get('date_change_to') or item.get('from_date') or item.get('to_date')) else None
                        }
                        history.append(history_item)
                    except Exception as e:
                        logger.warning(f"Error processing document change item {idx}: {str(e)}")
                        continue
                
                # Add scraped actions history (convert to TenderHistoryItem format)
                if scraped_tender.actions_history_json:
                    scraped_actions = scraped_tender.actions_history_json
                    # If stored as JSON string, parse it
                    if isinstance(scraped_actions, str):
                        try:
                            import json
                            scraped_actions = json.loads(scraped_actions)
                        except Exception:
                            scraped_actions = {}
                    actions_list = []
                    
                    # Handle different data formats
                    if isinstance(scraped_actions, dict):
                        if 'items' in scraped_actions:
                            actions_list = scraped_actions.get('items', [])
                        elif 'action' in scraped_actions or 'timestamp' in scraped_actions:
                            actions_list = [scraped_actions]
                    elif isinstance(scraped_actions, list):
                        actions_list = scraped_actions
                    
                    for idx, item in enumerate(actions_list):
                        if not isinstance(item, dict):
                            continue
                        
                        try:
                            # Convert action history to history item format
                            history_item = {
                                "id": f"action_{len(history)}_{idx}",
                                "tender_id": str(tender.id) if tender else str(scraped_tender.id),
                                "user_id": item.get('user', item.get('user_id')),
                                "tdr": tender_tdr or scraped_tender.tdr or "",
                                "type": "other",  # Actions are typically "other" type
                                "note": f"{item.get('action', 'Action')}: {item.get('notes', item.get('note', ''))}".strip(),
                                "update_date": item.get('timestamp', item.get('date', scraped_tender.scraped_at.isoformat() if hasattr(scraped_tender, 'scraped_at') and scraped_tender.scraped_at else 'N/A')),
                                "files_changed": [],
                                "date_change": None
                            }
                            history.append(history_item)
                        except Exception as e:
                            logger.warning(f"Error processing action history item {idx}: {str(e)}")
                            continue
    except Exception as e:
        # Log error but don't fail the request
        logger.warning(f"Error fetching scraped history for tender {tender_id}: {str(e)}", exc_info=True)
    
    # Sort by update_date descending (most recent first)
    history = sorted(
        history,
        key=lambda x: x.get("update_date", ""),
        reverse=True
    )
    
    logger.info(f"Returning {len(history)} total history items for tender {tender_id}")
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
