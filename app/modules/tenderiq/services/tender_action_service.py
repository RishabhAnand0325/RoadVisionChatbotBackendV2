"""
Service for performing actions on tenders.
"""
import uuid
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
import threading

from app.modules.tenderiq.db.tenderiq_repository import TenderIQRepository
from app.modules.tenderiq.db.repository import TenderRepository, TenderWishlistRepository
from app.modules.tenderiq.models.pydantic_models import TenderActionRequest, TenderActionType, Tender
from app.modules.tenderiq.db.schema import Tender as TenderModel, TenderActionEnum, TenderWishlist
from app.modules.analyze.scripts.analyze_tender import analyze_tender
from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender
from app.core.helpers import get_number_from_currency_string
import uuid as uuid_module

logger = logging.getLogger(__name__)

class TenderActionService:
    def __init__(self, db: Session):
        self.db = db
        self.tender_repo = TenderRepository(db)
        self.scraped_tender_repo = TenderIQRepository(db)

    def perform_action(self, tender_id: uuid.UUID, user_id: uuid.UUID, request: TenderActionRequest) -> Tender:
        logger.info(f"Performing action on tender: {tender_id}, action: {request.action}")
        
        # Step 1: Try to get by ScrapedTender ID first (most common case)
        scraped_tender = self.scraped_tender_repo.get_tender_by_id(tender_id)
        logger.debug(f"Step 1 - ScrapedTender lookup for {tender_id}: {'Found' if scraped_tender else 'Not found'}")
        
        # If not found, try to get by Tender ID (secondary fallback)
        if not scraped_tender:
            logger.debug(f"Step 2 - Tender lookup for {tender_id}")
            tender_obj = self.db.query(TenderModel).filter(TenderModel.id == tender_id).first()
            logger.debug(f"Step 2 - Tender lookup result: {'Found' if tender_obj else 'Not found'}")
            
            if not tender_obj:
                logger.error(f"Tender not found in database: {tender_id}")
                # Check if tender exists with different conditions
                all_tenders_count = self.db.query(TenderModel).count()
                all_scraped_tenders_count = self.db.query(ScrapedTender).count()
                logger.error(f"Total Tenders in DB: {all_tenders_count}, Total ScrapedTenders: {all_scraped_tenders_count}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tender {tender_id} not found")
            
            # Get the most recent ScrapedTender for this Tender
            scraped_tender = self.db.query(ScrapedTender).filter(
                ScrapedTender.tender_id_str == tender_obj.tender_ref_number
            ).order_by(
                desc(ScrapedTender.id)  # Order by ID descending to get most recent
            ).first()
            if not scraped_tender:
                # If no ScrapedTender exists, we'll work with just the Tender model
                logger.warning(f"No ScrapedTender found for Tender {tender_id}, using Tender model directly")
                tender = tender_obj
            else:
                tender = self.tender_repo.get_or_create_by_id(scraped_tender)
        else:
            tender = self.tender_repo.get_or_create_by_id(scraped_tender)

        updates = {}
        action_to_log: Optional[TenderActionEnum] = None
        notes = request.payload.notes if request.payload else None

        if request.action == TenderActionType.TOGGLE_WISHLIST:
            updates['is_wishlisted'] = not tender.is_wishlisted
            action_to_log = TenderActionEnum.wishlisted if updates['is_wishlisted'] else TenderActionEnum.unwishlisted

            # Handle wishlist using TenderWishlist table for user-specific tracking
            wishlist_repo = TenderWishlistRepository(self.db)
            # Get tender_ref from scraped_tender if available, otherwise from tender model
            tender_ref = scraped_tender.tender_id_str if scraped_tender else tender.tender_ref_number
            
            if updates['is_wishlisted']:
                wishlist_id = None
                # Check if already in wishlist for this user
                existing = wishlist_repo.get_wishlist_by_tender_ref(tender_ref, user_id)
                if existing:
                    # Already wishlisted by this user, use existing entry
                    wishlist_id = existing.id
                    logger.info(f"Tender {tender_ref} already in wishlist (id: {wishlist_id})")
                else:
                    # Not in wishlist for this user, create new entry
                    # Parse currency values (handle formats like "166.70 Crore")
                    def safe_convert_to_float(value):
                        """Safely convert value to float, handling currency strings and numeric types"""
                        if value is None:
                            return 0.0
                        if isinstance(value, (int, float)):
                            return float(value)
                        if isinstance(value, str):
                            return get_number_from_currency_string(value)
                        return 0.0
                    
                    if scraped_tender:
                        value_float = safe_convert_to_float(scraped_tender.value or tender.estimated_cost)
                        emd_float = safe_convert_to_float(scraped_tender.emd or tender.bid_security)
                        title = scraped_tender.tender_name or tender.tender_title or ''
                        authority = scraped_tender.company_name or tender.employer_name or ''
                        category = tender.category or (scraped_tender.query.query_name if scraped_tender.query else '')
                        due_date = scraped_tender.due_date or ''
                    else:
                        value_float = safe_convert_to_float(tender.estimated_cost)
                        emd_float = safe_convert_to_float(tender.bid_security)
                        title = tender.tender_title or ''
                        authority = tender.employer_name or ''
                        category = tender.category or ''
                        due_date = ''
                    
                    wishlist_data = {
                        'id': str(uuid_module.uuid4()),
                        'tender_ref_number': tender_ref,
                        'user_id': user_id,
                        'title': title,
                        'authority': authority,
                        'value': value_float,
                        'emd': emd_float,
                        'due_date': due_date,
                        'category': category,
                    }
                    wishlist_entry = wishlist_repo.add_to_wishlist(wishlist_data)
                    wishlist_id = wishlist_entry.id
                
                # Trigger analysis in background (only if not already analyzed)
                from app.modules.analyze.db.schema import TenderAnalysis, AnalysisStatusEnum
                from app.modules.auth.db.schema import User
                
                existing_analysis = self.db.query(TenderAnalysis).filter(
                    TenderAnalysis.tender_id == tender_ref
                ).first()
                
                # Check user preference for auto-analysis
                user = self.db.query(User).filter(User.id == user_id).first()
                should_trigger = user.auto_analyze_on_wishlist if user else True
                
                if should_trigger:
                    logger.info(f"Triggering analysis for wishlisted tender: {tender_ref} (wishlist_id: {wishlist_id})")

                    # Update status immediately so frontend shows loading screen
                    if existing_analysis:
                        existing_analysis.status = AnalysisStatusEnum.pending
                        existing_analysis.progress = 0
                        existing_analysis.status_message = "Starting analysis..."
                        self.db.commit()

                    # Run analysis in background thread to avoid blocking the request
                    def run_analysis():
                        analysis_db = SessionLocal()
                        try:
                            analyze_tender(analysis_db, tender_ref, wishlist_id=wishlist_id)
                            logger.info(f"Analysis completed for tender: {tender_ref}")
                        except Exception as e:
                            logger.error(f"Background analysis failed for {tender_ref}: {e}")
                            # Update wishlist with error
                            if wishlist_id:
                                try:
                                    wishlist_repo_error = TenderWishlistRepository(analysis_db)
                                    wishlist_repo_error.update_wishlist_progress(
                                        wishlist_id,
                                        error_message=f"Analysis failed: {str(e)[:500]}",
                                        status_message="Analysis failed"
                                    )
                                except Exception as update_error:
                                    logger.error(f"Failed to update wishlist error status: {update_error}")
                        finally:
                            analysis_db.close()

                    thread = threading.Thread(target=run_analysis, daemon=True)
                    thread.start()
                    logger.info(f"Analysis triggered in background for tender: {tender_ref}")
            else:
                # Remove from wishlist for this user
                existing = wishlist_repo.get_wishlist_by_tender_ref(tender_ref, user_id)
                if existing:
                    wishlist_repo.remove_from_wishlist(existing.id)

        elif request.action == TenderActionType.TOGGLE_FAVORITE:
            updates['is_favorite'] = not tender.is_favorite
            action_to_log = TenderActionEnum.favorited if updates['is_favorite'] else TenderActionEnum.unfavorited

        elif request.action == TenderActionType.TOGGLE_ARCHIVE:
            updates['is_archived'] = not tender.is_archived
            action_to_log = TenderActionEnum.archived if updates['is_archived'] else TenderActionEnum.unarchived

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

        if updates:
            updated_tender = self.tender_repo.update(tender, updates)
        else:
            updated_tender = tender

        if action_to_log:
            try:
                self.tender_repo.log_action(updated_tender.id, user_id, action_to_log, notes)
            except Exception as e:
                # Log the error but don't fail the action
                # This handles cases where user_id doesn't exist or other logging issues
                logger.warning(
                    f"Failed to log action {action_to_log} for tender {updated_tender.id} "
                    f"by user {user_id}: {str(e)}"
                )

        return updated_tender
