"""
Service for performing actions on tenders.
"""
import uuid
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import logging

from app.modules.tenderiq.db.tenderiq_repository import TenderIQRepository
from app.modules.tenderiq.db.repository import TenderRepository
from app.modules.tenderiq.models.pydantic_models import TenderActionRequest, TenderActionType
from app.modules.tenderiq.db.schema import Tender, TenderActionEnum

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
        if updates:
            updated_tender = self.tender_repo.update(tender, updates)
        else:
            updated_tender = tender

        if action_to_log:
            self.tender_repo.log_action(updated_tender.id, user_id, action_to_log, notes)
        
        # NOW trigger analysis AFTER wishlist is committed to DB
        if request.action == TenderActionType.TOGGLE_WISHLIST:
            # Auto-trigger analysis when wishlisting a tender (was_wishlisted captured before updates)
            if not was_wishlisted and updates.get('is_wishlisted'):
                print(f"[WISHLIST DEBUG] Wishlisting tender, was_wishlisted={was_wishlisted}, new_value={updates['is_wishlisted']}")
                try:
                    from app.modules.analyze.services.analysis_queue_service import AnalysisQueueService
                    from app.modules.analyze.db.schema import TenderAnalysis, AnalysisStatusEnum
                    
                    if tender_ref:
                        # First check if analysis already exists and is completed
                        existing_analysis = self.db.query(TenderAnalysis).filter(
                            TenderAnalysis.tender_id == tender_ref
                        ).first()
                        
                        if existing_analysis and existing_analysis.status == AnalysisStatusEnum.completed:
                            print(f"[ANALYSIS DEBUG] Analysis already completed for {tender_ref}, skipping")
                            logger.info(f"Analysis already completed for tender {tender_ref}, skipping trigger")
                        else:
                            # Check if analysis is currently running
                            is_running = AnalysisQueueService.is_analysis_running(self.db)
                            print(f"[QUEUE DEBUG] Is analysis running? {is_running}")
                            logger.info(f"Is analysis currently running? {is_running}")
                            
                            if not is_running:
                                # No analysis running - trigger in background thread
                                try:
                                    import threading
                                    from app.modules.analyze.scripts.analyze_tender import analyze_tender
                                    from app.db.database import SessionLocal
                                    
                                    def run_analysis_in_background():
                                        """Run analysis in a separate thread with its own DB session"""
                                        # Debug: Write to file to prove thread started
                                        import os
                                        debug_file = '/tmp/analysis_thread_debug.log'
                                        with open(debug_file, 'a') as f:
                                            f.write(f"Thread started for tender {tender_ref}\\n")
                                        
                                        bg_db = SessionLocal()
                                        try:
                                            print(f"[ANALYSIS DEBUG] Background thread starting analysis for {tender_ref}")
                                            logger.info(f"Background thread starting analysis for tender {tender_ref}")
                                            with open(debug_file, 'a') as f:
                                                f.write(f"About to call analyze_tender for {tender_ref}\\n")
                                            
                                            analyze_tender(bg_db, tender_ref)
                                            
                                            with open(debug_file, 'a') as f:
                                                f.write(f"analyze_tender completed for {tender_ref}\\n")
                                            print(f"[ANALYSIS DEBUG] Background analysis completed for {tender_ref}")
                                            logger.info(f"Background analysis completed for tender {tender_ref}")
                                        except Exception as e:
                                            with open(debug_file, 'a') as f:
                                                import traceback
                                                f.write(f"ERROR in thread for {tender_ref}: {e}\\n")
                                                f.write(traceback.format_exc())
                                            print(f"[ANALYSIS ERROR] Background analysis failed: {e}")
                                            logger.error(f"Background analysis failed: {e}", exc_info=True)
                                        finally:
                                            bg_db.close()
                                            with open(debug_file, 'a') as f:
                                                f.write(f"Thread cleanup complete for {tender_ref}\\n\\n")
                                    
                                    print(f"[ANALYSIS DEBUG] Triggering analysis in background thread for {tender_ref}")
                                    logger.info(f"Triggering analysis in background thread for tender {tender_ref}")
                                    thread = threading.Thread(target=run_analysis_in_background, daemon=True)
                                    thread.start()
                                    print(f"[ANALYSIS DEBUG] Background thread started")
                                    logger.info(f"Background thread started successfully")
                                except Exception as analyze_error:
                                    print(f"[ANALYSIS ERROR] Failed to start background thread: {analyze_error}")
                                    logger.error(f"Failed to start background thread: {analyze_error}", exc_info=True)
                            else:
                                # Analysis is running - add to queue
                                print(f"[QUEUE DEBUG] Analysis already running, adding {tender_ref} to queue")
                                logger.info(f"Analysis already running, adding tender {tender_ref} to queue")
                                queue_result = AnalysisQueueService.add_to_queue(self.db, tender_ref, str(user_id))
                                print(f"[QUEUE DEBUG] Queue result: {queue_result}")
                                logger.info(f"Queue result for tender {tender_ref}: {queue_result}")
                    else:
                        print(f"[QUEUE DEBUG] No tender_ref found for scraped tender {scraped_tender.id}")
                        logger.warning(f"Could not find tender reference for scraped tender {scraped_tender.id}")
                except Exception as e:
                    # Don't fail the wishlist action if queue add fails
                    tender_ref_log = tender_ref or getattr(scraped_tender, 'id', 'unknown')
                    print(f"[QUEUE ERROR] Failed to add to queue: {e}")
                    logger.error(f"Failed to add tender {tender_ref_log} to analysis queue: {e}", exc_info=True)
        
        return updated_tender, tender_ref
