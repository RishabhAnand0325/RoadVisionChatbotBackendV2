"""
Schema for manually uploaded tenders.
Tracks manually uploaded RFP PDFs and their metadata.
"""
import uuid
import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, 
    Enum as SQLAlchemyEnum, Integer, Float
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.database import Base


class UploadSourceEnum(str, enum.Enum):
    """Defines the source of a tender."""
    manually_uploaded = "manually_uploaded"
    scraped = "scraped"


class ManualTenderUpload(Base):
    """
    Tracks manually uploaded RFP documents by users.
    
    This table allows users to upload PDF files that are not scraped from
    tender portals but need the same analysis workflow as scraped tenders.
    
    The uploaded tender can have its own opportunity context and can be 
    analyzed through the same AI modules as scraped tenders.
    """
    __tablename__ = 'manual_tender_uploads'
    
    # Primary key and identification
    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # User metadata
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('users.id'), 
        nullable=False, 
        index=True
    )
    
    # Tender metadata
    tender_title: Mapped[str] = mapped_column(String(500), nullable=False)
    tender_description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Unique reference for this upload
    upload_reference: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        index=True,
        nullable=False
    )
    
    # File metadata
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # in bytes
    file_mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Tender details from upload
    employer_name: Mapped[Optional[str]] = mapped_column(String(255))
    estimated_cost: Mapped[Optional[float]] = mapped_column(Float)  # in crore
    submission_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime)
    location: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Status tracking
    is_analyzed: Mapped[bool] = mapped_column(default=False, index=True)
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('tender_analysis.id'), 
        nullable=True,
        index=True
    )
    
    # Opportunity context (optional)
    opportunity_name: Mapped[Optional[str]] = mapped_column(String(500))
    opportunity_description: Mapped[Optional[str]] = mapped_column(Text)
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "tender_title": self.tender_title,
            "tender_description": self.tender_description,
            "upload_reference": self.upload_reference,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "employer_name": self.employer_name,
            "estimated_cost": self.estimated_cost,
            "submission_deadline": self.submission_deadline.isoformat() if self.submission_deadline else None,
            "location": self.location,
            "category": self.category,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_analyzed": self.is_analyzed,
            "analysis_id": str(self.analysis_id) if self.analysis_id else None,
            "opportunity_name": self.opportunity_name,
            "opportunity_description": self.opportunity_description,
        }
