"""
Service for performing actions on tenders.
"""
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.modules.tenderiq.db.tenderiq_repository import TenderIQRepository
from app.modules.tenderiq.db.repository import TenderRepository
from app.modules.tenderiq.models.pydantic_models import TenderActionRequest, TenderActionType
from app.modules.tenderiq.db.schema import Tender, TenderActionEnum

class TenderActionService:
    def __init__(self, db: Session):
        self.db = db
        self.tender_repo = TenderRepository(db)
        self.scraped_tender_repo = TenderIQRepository(db)

    def perform_action(self, tender_id: uuid.UUID, user_id: uuid.UUID, request: TenderActionRequest) -> Tender:
        scraped_tender = self.scraped_tender_repo.get_tender_by_id(tender_id)
        if not scraped_tender:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

        tender = self.tender_repo.get_or_create_by_id(scraped_tender)

        updates = {}
        action_to_log: Optional[TenderActionEnum] = None
        notes = request.payload.notes if request.payload else None

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

        if updates:
            updated_tender = self.tender_repo.update(tender, updates)
        else:
            updated_tender = tender

        if action_to_log:
            self.tender_repo.log_action(updated_tender.id, user_id, action_to_log, notes)
        
        return updated_tender
