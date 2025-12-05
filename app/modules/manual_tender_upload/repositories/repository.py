"""
Repository for manual tender upload operations.
"""
import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.modules.manual_tender_upload.db.schema import ManualTenderUpload


class ManualTenderUploadRepository:
    """Repository for manual tender upload database operations."""
    
    @staticmethod
    def create_upload(
        db: Session,
        user_id: uuid.UUID,
        tender_title: str,
        file_name: str,
        file_path: str,
        file_size: int,
        file_mime_type: str,
        upload_reference: str,
        tender_description: Optional[str] = None,
        employer_name: Optional[str] = None,
        estimated_cost: Optional[float] = None,
        submission_deadline = None,
        location: Optional[str] = None,
        category: Optional[str] = None,
        opportunity_name: Optional[str] = None,
        opportunity_description: Optional[str] = None,
    ) -> ManualTenderUpload:
        """Create a new manual tender upload record."""
        upload = ManualTenderUpload(
            user_id=user_id,
            tender_title=tender_title,
            tender_description=tender_description,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            file_mime_type=file_mime_type,
            upload_reference=upload_reference,
            employer_name=employer_name,
            estimated_cost=estimated_cost,
            submission_deadline=submission_deadline,
            location=location,
            category=category,
            opportunity_name=opportunity_name,
            opportunity_description=opportunity_description,
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)
        return upload
    
    @staticmethod
    def get_upload_by_id(db: Session, upload_id: uuid.UUID) -> Optional[ManualTenderUpload]:
        """Get upload by ID."""
        return db.query(ManualTenderUpload).filter(
            ManualTenderUpload.id == upload_id
        ).first()
    
    @staticmethod
    def get_upload_by_reference(db: Session, upload_reference: str) -> Optional[ManualTenderUpload]:
        """Get upload by reference."""
        return db.query(ManualTenderUpload).filter(
            ManualTenderUpload.upload_reference == upload_reference
        ).first()
    
    @staticmethod
    def get_user_uploads(
        db: Session,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        only_unanalyzed: bool = False
    ) -> List[ManualTenderUpload]:
        """Get all uploads for a user."""
        query = db.query(ManualTenderUpload).filter(
            ManualTenderUpload.user_id == user_id
        )
        
        if only_unanalyzed:
            query = query.filter(ManualTenderUpload.is_analyzed == False)
        
        return query.order_by(
            desc(ManualTenderUpload.created_at)
        ).limit(limit).offset(offset).all()
    
    @staticmethod
    def get_user_uploads_count(db: Session, user_id: uuid.UUID) -> int:
        """Get count of uploads for a user."""
        return db.query(ManualTenderUpload).filter(
            ManualTenderUpload.user_id == user_id
        ).count()
    
    @staticmethod
    def mark_analyzed(
        db: Session,
        upload_id: uuid.UUID,
        analysis_id: uuid.UUID
    ) -> ManualTenderUpload:
        """Mark upload as analyzed and link to analysis."""
        upload = ManualTenderUploadRepository.get_upload_by_id(db, upload_id)
        if upload:
            upload.is_analyzed = True
            upload.analysis_id = analysis_id
            db.commit()
            db.refresh(upload)
        return upload
    
    @staticmethod
    def update_upload(
        db: Session,
        upload_id: uuid.UUID,
        **kwargs
    ) -> Optional[ManualTenderUpload]:
        """Update upload metadata."""
        upload = ManualTenderUploadRepository.get_upload_by_id(db, upload_id)
        if upload:
            for key, value in kwargs.items():
                if hasattr(upload, key):
                    setattr(upload, key, value)
            db.commit()
            db.refresh(upload)
        return upload
    
    @staticmethod
    def delete_upload(db: Session, upload_id: uuid.UUID) -> bool:
        """Delete an upload record."""
        upload = ManualTenderUploadRepository.get_upload_by_id(db, upload_id)
        if upload:
            db.delete(upload)
            db.commit()
            return True
        return False
