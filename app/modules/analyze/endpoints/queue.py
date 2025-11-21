"""
Analysis Queue API endpoints.
"""
import logging
import threading
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db_session, SessionLocal
from app.modules.auth.services.auth_service import get_current_active_user
from app.modules.analyze.services.analysis_queue_service import AnalysisQueueService
from app.modules.analyze.db.schema import TenderAnalysis, AnalysisStatusEnum

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/queue/status",
    summary="Get Analysis Queue Status",
    description="Get current analysis queue status including active analysis and queued items",
    tags=["Analyze"],
)
def get_queue_status(
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_active_user),
):
    """
    Get analysis queue status.
    
    Returns:
        - has_active: Whether an analysis is currently running
        - current_analysis: Details of the running analysis (if any)
        - queue_length: Number of analyses waiting in queue
        - queued_items: List of queued analyses with positions
    """
    try:
        status_data = AnalysisQueueService.get_queue_status(db)
        return status_data
    except Exception as e:
        logger.error(f"Error getting queue status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting queue status: {str(e)}"
        )


@router.get(
    "/queue/position/{tender_id}",
    summary="Get Tender Queue Position",
    description="Get the queue position of a specific tender",
    tags=["Analyze"],
)
def get_tender_position(
    tender_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_active_user),
):
    """
    Get queue position for a tender.
    
    Args:
        tender_id: Tender reference number
        
    Returns:
        Queue position or null if not in queue
    """
    try:
        position = AnalysisQueueService.get_tender_queue_position(db, tender_id)
        return {
            "tender_id": tender_id,
            "queue_position": position,
            "in_queue": position is not None
        }
    except Exception as e:
        logger.error(f"Error getting tender position: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting position: {str(e)}"
        )


@router.post(
    "/trigger/{tender_id}",
    summary="Trigger Tender Analysis",
    description="Manually trigger analysis for a tender. If analysis already exists, returns existing status.",
    tags=["Analyze"],
)
def trigger_analysis(
    tender_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_active_user),
):
    """
    Trigger analysis for a tender.
    
    Args:
        tender_id: Tender reference number
        
    Returns:
        Analysis status and queue information
    """
    try:
        # Check if analysis already exists
        existing_analysis = db.query(TenderAnalysis).filter(
            TenderAnalysis.tender_id == tender_id
        ).first()
        
        if existing_analysis:
            # Analysis exists - return its status
            queue_status = AnalysisQueueService.get_queue_status(db)
            position = AnalysisQueueService.get_tender_queue_position(db, tender_id)
            
            return {
                "message": "Analysis already exists for this tender",
                "analysis_exists": True,
                "status": existing_analysis.status.value,
                "progress": existing_analysis.progress,
                "queue_position": position,
                "has_active_analysis": queue_status.get("has_active", False),
                "tender_id": tender_id
            }
        
        # Create new analysis entry in pending state
        new_analysis = TenderAnalysis(
            tender_id=tender_id,
            user_id=None,  # Manual trigger, not tied to specific user
            chat_id=None,
            status=AnalysisStatusEnum.pending,
            progress=0,
            status_message="Analysis queued"
        )
        db.add(new_analysis)
        db.commit()
        db.refresh(new_analysis)
        
        logger.info(f"Created pending analysis for tender {tender_id}")
        
        # Start analysis in background thread
        def run_analysis_in_background(tender_id: str):
            """Run analysis in a separate thread with its own DB session"""
            thread_db = SessionLocal()
            try:
                from app.modules.analyze.scripts.analyze_tender import analyze_tender
                analyze_tender(tender_id, thread_db)
            except Exception as e:
                logger.error(f"Background analysis failed for {tender_id}: {e}", exc_info=True)
            finally:
                thread_db.close()
        
        # Start background thread
        analysis_thread = threading.Thread(
            target=run_analysis_in_background,
            args=(tender_id,),
            daemon=True
        )
        analysis_thread.start()
        logger.info(f"Started background analysis thread for tender {tender_id}")
        
        # Get queue status
        queue_status = AnalysisQueueService.get_queue_status(db)
        position = AnalysisQueueService.get_tender_queue_position(db, tender_id)
        
        return {
            "message": "Analysis started successfully",
            "analysis_exists": False,
            "status": "pending",
            "progress": 0,
            "queue_position": position,
            "has_active_analysis": queue_status.get("has_active", False),
            "tender_id": tender_id
        }
        
    except Exception as e:
        logger.error(f"Error triggering analysis for tender {tender_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error triggering analysis: {str(e)}"
        )
