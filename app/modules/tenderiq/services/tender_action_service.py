"""
Service for performing actions on tenders.
"""
import uuid
import logging
import threading
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.modules.tenderiq.db.tenderiq_repository import TenderIQRepository
from app.modules.tenderiq.db.repository import TenderRepository
from app.modules.tenderiq.models.pydantic_models import TenderActionRequest, TenderActionType
from app.modules.tenderiq.db.schema import Tender, TenderActionEnum
from app.modules.analyze.scripts.analyze_tender import analyze_tender
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)


class TenderActionService:
    def __init__(self, db: Session):
        self.db = db
        self.tender_repo = TenderRepository(db)
        self.scraped_tender_repo = TenderIQRepository(db)

    def perform_action(self, tender_id: uuid.UUID, user_id: uuid.UUID, request: TenderActionRequest) -> Tuple[Tender, Optional[str]]:
        scraped_tender = self.scraped_tender_repo.get_tender_by_id(tender_id)
        if not scraped_tender:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

        tender = self.tender_repo.get_or_create_by_id(scraped_tender)

        # Get tender reference for queue operations
        tender_ref = getattr(scraped_tender, 'tdr', None) or getattr(scraped_tender, 'tender_id_str', None)

        updates = {}
        action_to_log: Optional[TenderActionEnum] = None
        notes = request.payload.notes if request.payload else None

        # Capture old state BEFORE updates for analysis trigger logic
        was_wishlisted = tender.is_wishlisted

        if request.action == TenderActionType.TOGGLE_WISHLIST:
            updates['is_wishlisted'] = not tender.is_wishlisted
            action_to_log = TenderActionEnum.wishlisted if updates['is_wishlisted'] else TenderActionEnum.unwishlisted

        elif request.action == TenderActionType.TOGGLE_FAVORITE:
            updates['is_favorite'] = not tender.is_favorite

        elif request.action == TenderActionType.TOGGLE_ARCHIVE:
            updates['is_archived'] = not tender.is_archived

        elif request.action == TenderActionType.UPDATE_STATUS:
            if not request.payload or not request.payload.status:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status payload is required for this action")
            updates['status'] = request.payload.status.value
            if request.payload.status.value == "Shortlisted":
                action_to_log = TenderActionEnum.shortlisted

        elif request.action == TenderActionType.UPDATE_REVIEW_STATUS:
            if not request.payload or not request.payload.review_status:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Review status payload is required for this action")
            updates['review_status'] = request.payload.review_status.value
            if request.payload.review_status.value == "Shortlisted" and tender.status != "Shortlisted":
                action_to_log = TenderActionEnum.shortlisted

        # Apply updates and commit FIRST before triggering analysis
        updated_tender = self.tender_repo.update(tender, updates) if updates else tender

        # Best-effort action logging (don’t fail user action if logging breaks)
        if action_to_log:
            try:
                self.tender_repo.log_action(updated_tender.id, user_id, action_to_log, notes)
            except Exception as e:
                logger.warning(
                    "Failed to log action %s for tender %s by user %s: %s",
                    action_to_log, updated_tender.id, user_id, str(e)
                )

        # Auto-trigger analysis AFTER wishlist is committed to DB
        if request.action == TenderActionType.TOGGLE_WISHLIST:
            # Only when transitioning from not wishlisted -> wishlisted
            if not was_wishlisted and updates.get('is_wishlisted'):
                logger.info("Wishlisted tender %s; considering analysis trigger (ref=%s)", updated_tender.id, tender_ref)
                try:
                    from app.modules.analyze.services.analysis_queue_service import AnalysisQueueService
                    from app.modules.analyze.db.schema import TenderAnalysis, AnalysisStatusEnum

                    if tender_ref:
                        # If analysis already completed, skip
                        existing_analysis = self.db.query(TenderAnalysis).filter(
                            TenderAnalysis.tender_id == tender_ref
                        ).first()

                        if existing_analysis and existing_analysis.status == AnalysisStatusEnum.completed:
                            logger.info("Analysis already completed for %s, skipping trigger", tender_ref)
                        else:
                            is_running = AnalysisQueueService.is_analysis_running(self.db)
                            logger.info("Is analysis currently running? %s", is_running)

                            if not is_running:
                                # Run immediately in background thread
                                def run_analysis_in_background():
                                    """Run analysis in a separate thread with its own DB session"""
                                    bg_db = SessionLocal()
                                    try:
                                        logger.info("Background thread starting analysis for %s", tender_ref)
                                        analyze_tender(bg_db, tender_ref)
                                        logger.info("Background analysis completed for %s", tender_ref)
                                    except Exception as e:
                                        logger.error("Background analysis failed for %s: %s", tender_ref, e, exc_info=True)
                                    finally:
                                        bg_db.close()

                                logger.info("Triggering background analysis for %s", tender_ref)
                                thread = threading.Thread(target=run_analysis_in_background, daemon=True)
                                thread.start()
                                logger.info("Background thread started successfully")
                            else:
                                # Queue if something is running
                                logger.info("Analysis running; queuing tender %s", tender_ref)
                                AnalysisQueueService.add_to_queue(self.db, tender_ref, str(user_id))
                    else:
                        logger.warning("No tender_ref found for scraped tender %s; cannot trigger analysis", scraped_tender.id)
                except Exception as e:
                    # Don’t fail wishlist toggle if trigger/queue fails
                    safe_ref = tender_ref or getattr(scraped_tender, 'id', 'unknown')
                    logger.error("Failed to trigger/queue analysis for %s: %s", safe_ref, e, exc_info=True)

        # Maintain main’s return signature
        return updated_tender, tender_ref
