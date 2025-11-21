"""
Analysis Queue Service - Manages sequential tender analysis processing.

Ensures only one analysis runs at a time, with queued requests processed in order.
"""
import logging
from typing import Optional, List, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.modules.analyze.db.schema import TenderAnalysis, AnalysisStatusEnum

logger = logging.getLogger(__name__)


class AnalysisQueueService:
    """
    Service to manage analysis queue and prevent concurrent analysis runs.
    """
    
    @staticmethod
    def cleanup_stuck_analyses(db: Session, timeout_minutes: int = 30) -> int:
        """
        Clean up analyses that have been stuck in parsing/analyzing state.
        
        Args:
            db: Database session
            timeout_minutes: Consider analysis stuck if running longer than this
            
        Returns:
            Number of analyses cleaned up
        """
        from datetime import timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        stuck = db.query(TenderAnalysis).filter(
            or_(
                TenderAnalysis.status == AnalysisStatusEnum.parsing,
                TenderAnalysis.status == AnalysisStatusEnum.analyzing
            ),
            or_(
                TenderAnalysis.analysis_started_at < cutoff_time,
                TenderAnalysis.analysis_started_at.is_(None)
            )
        ).all()
        
        count = len(stuck)
        for analysis in stuck:
            analysis.status = AnalysisStatusEnum.failed
            analysis.error_message = f"Analysis timed out after {timeout_minutes} minutes"
            logger.warning(f"Cleaned up stuck analysis for tender {analysis.tender_id}")
        
        if count > 0:
            db.commit()
            logger.info(f"Cleaned up {count} stuck analyses")
        
        return count
    
    @staticmethod
    def get_queue_status(db: Session) -> Dict:
        """
        Get current analysis queue status.
        
        Returns:
            Dict with current analysis, queued count, and queue items
        """
        # Find currently running analysis - only check parsing and analyzing
        # Note: 'processing' is not a valid enum value
        current = db.query(TenderAnalysis).filter(
            or_(
                TenderAnalysis.status == AnalysisStatusEnum.parsing,
                TenderAnalysis.status == AnalysisStatusEnum.analyzing
            )
        ).order_by(TenderAnalysis.analysis_started_at.asc()).first()
        
        # Find queued analyses (pending status)
        queued = db.query(TenderAnalysis).filter(
            TenderAnalysis.status == AnalysisStatusEnum.pending
        ).order_by(TenderAnalysis.created_at.asc()).all()
        
        # Calculate elapsed time and estimate remaining time
        elapsed_seconds = 0
        estimated_remaining_seconds = 300  # Default 5 minutes
        
        if current and current.analysis_started_at:
            elapsed_seconds = int((datetime.utcnow() - current.analysis_started_at).total_seconds())
            # Estimate based on progress: assume 5 min total (300 sec)
            # If progress is known, calculate remaining time proportionally
            if current.progress > 0:
                estimated_total = (elapsed_seconds / current.progress) * 100
                estimated_remaining_seconds = max(0, int(estimated_total - elapsed_seconds))
            else:
                # No progress yet, assume 5 minutes from start
                estimated_remaining_seconds = max(0, 300 - elapsed_seconds)
        
        return {
            "has_active": current is not None,
            "current_analysis": {
                "tender_id": current.tender_id,
                "status": current.status.value,
                "progress": current.progress,
                "started_at": current.analysis_started_at.isoformat() if current.analysis_started_at else None,
                "elapsed_seconds": elapsed_seconds,
                "estimated_remaining_seconds": estimated_remaining_seconds,
            } if current else None,
            "queue_length": len(queued),
            "queued_items": [
                {
                    "tender_id": item.tender_id,
                    "queued_at": item.created_at.isoformat(),
                    "position": idx + 1
                }
                for idx, item in enumerate(queued)
            ]
        }
    
    @staticmethod
    def is_analysis_running(db: Session) -> bool:
        """
        Check if any analysis is currently running.
        Automatically cleans up stuck analyses before checking.
        
        Returns:
            True if analysis is running, False otherwise
        """
        # Clean up any stuck analyses first
        AnalysisQueueService.cleanup_stuck_analyses(db)
        
        running = db.query(TenderAnalysis).filter(
            or_(
                TenderAnalysis.status == AnalysisStatusEnum.parsing,
                TenderAnalysis.status == AnalysisStatusEnum.analyzing
            )
        ).first()
        
        return running is not None
    
    @staticmethod
    def get_tender_queue_position(db: Session, tender_id: str) -> Optional[int]:
        """
        Get the queue position of a tender.
        
        Args:
            tender_id: Tender reference number
            
        Returns:
            Queue position (1-indexed) or None if not in queue
        """
        analysis = db.query(TenderAnalysis).filter(
            TenderAnalysis.tender_id == tender_id
        ).first()
        
        if not analysis:
            return None
        
        # If already running or completed, not in queue
        if analysis.status != AnalysisStatusEnum.pending:
            return None
        
        # Count how many pending analyses are before this one
        earlier_count = db.query(TenderAnalysis).filter(
            TenderAnalysis.status == AnalysisStatusEnum.pending,
            TenderAnalysis.created_at < analysis.created_at
        ).count()
        
        return earlier_count + 1
    
    @staticmethod
    def add_to_queue(db: Session, tender_id: str, user_id: Optional[str] = None) -> Dict:
        """
        Add a tender to the analysis queue or return existing analysis.
        
        Args:
            tender_id: Tender reference number
            user_id: Optional user ID who requested the analysis
            
        Returns:
            Dict with analysis status and queue information
        """
        # Check if analysis already exists
        existing = db.query(TenderAnalysis).filter(
            TenderAnalysis.tender_id == tender_id
        ).first()
        
        if existing:
            if existing.status == AnalysisStatusEnum.completed:
                return {
                    "status": "already_completed",
                    "message": "Analysis already completed",
                    "analysis_id": str(existing.id),
                }
            elif existing.status == AnalysisStatusEnum.failed:
                # Reset failed analysis to pending
                existing.status = AnalysisStatusEnum.pending
                existing.progress = 0
                existing.error_message = None
                db.commit()
                
                position = AnalysisQueueService.get_tender_queue_position(db, tender_id)
                return {
                    "status": "queued",
                    "message": f"Analysis re-queued at position {position}",
                    "queue_position": position,
                    "analysis_id": str(existing.id),
                }
            elif existing.status in [AnalysisStatusEnum.parsing, AnalysisStatusEnum.processing, AnalysisStatusEnum.analyzing]:
                return {
                    "status": "in_progress",
                    "message": "Analysis is currently running",
                    "progress": existing.progress,
                    "analysis_id": str(existing.id),
                }
            else:  # pending
                position = AnalysisQueueService.get_tender_queue_position(db, tender_id)
                return {
                    "status": "queued",
                    "message": f"Already in queue at position {position}",
                    "queue_position": position,
                    "analysis_id": str(existing.id),
                }
        
        # Create new analysis record in pending state
        from uuid import uuid4
        new_analysis = TenderAnalysis(
            id=uuid4(),
            tender_id=tender_id,
            user_id=user_id,
            status=AnalysisStatusEnum.pending,
            progress=0,
            created_at=datetime.utcnow(),
        )
        db.add(new_analysis)
        db.commit()
        db.refresh(new_analysis)
        
        position = AnalysisQueueService.get_tender_queue_position(db, tender_id)
        
        return {
            "status": "queued",
            "message": f"Added to queue at position {position}",
            "queue_position": position,
            "analysis_id": str(new_analysis.id),
        }
    
    @staticmethod
    def get_next_in_queue(db: Session) -> Optional[str]:
        """
        Get the next tender ID that should be analyzed.
        
        Returns:
            Tender ID or None if queue is empty
        """
        # Only return next if nothing is currently running
        if AnalysisQueueService.is_analysis_running(db):
            return None
        
        next_analysis = db.query(TenderAnalysis).filter(
            TenderAnalysis.status == AnalysisStatusEnum.pending
        ).order_by(TenderAnalysis.created_at.asc()).first()
        
        return next_analysis.tender_id if next_analysis else None
