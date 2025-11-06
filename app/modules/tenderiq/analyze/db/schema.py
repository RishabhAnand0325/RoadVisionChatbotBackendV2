import uuid
import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (Column, String, DateTime, ForeignKey, Text, JSON,
                        Integer, Boolean, Enum as SQLAlchemyEnum)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.database import Base
from app.modules.auth.db.schema import User
from app.modules.askai.db.models import Chat
from ..models.pydantic_models import OnePagerSchema, ScopeOfWorkSchema, DataSheetSchema


class AnalysisStatusEnum(str, enum.Enum):
    """Defines the processing status of a tender analysis."""
    pending = "pending"
    parsing = "parsing"
    analyzing = "analyzing"
    completed = "completed"
    failed = "failed"


class TenderAnalysis(Base):
    """
    Central table to track the analysis of a single tender.
    Maintains a one-to-one relationship with a ScrapedTender.
    """
    __tablename__ = 'tender_analysis'
    id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # One-to-one relationship to the ScrapedTender being analyzed. This refers to scraped_tenders.tender_id_str.
    tender_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey(User.id), nullable=True, index=True)
    chat_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey(Chat.id))
    
    # Analysis metadata
    status: Mapped[AnalysisStatusEnum] = mapped_column(postgresql.ENUM(AnalysisStatusEnum, name='analysisstatusenum', create_type=False), default=AnalysisStatusEnum.pending, nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status_message: Mapped[Optional[str]] = mapped_column(String(255))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    analysis_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    analysis_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Type-hinted Analysis Results
    one_pager_json: Mapped[Optional[OnePagerSchema]] = mapped_column(JSON)
    scope_of_work_json: Mapped[Optional[ScopeOfWorkSchema]] = mapped_column(JSON)
    data_sheet_json: Mapped[Optional[DataSheetSchema]] = mapped_column(JSON)

    # Relationships
    user: Mapped["User"] = relationship()
    chat: Mapped[Optional["Chat"]] = relationship()
    rfp_sections: Mapped[List["AnalysisRFPSection"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    document_templates: Mapped[List["AnalysisDocumentTemplate"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")

    def to_dict(self):
        """Converts the SQLAlchemy model instance to a dictionary."""
        return {
            "id": str(self.id),
            "tender_id": self.tender_id,
            "user_id": str(self.user_id) if self.user_id else None,
            "chat_id": str(self.chat_id) if self.chat_id else None,
            "status": self.status.value if self.status else None,
            "progress": self.progress,
            "status_message": self.status_message,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "analysis_started_at": self.analysis_started_at.isoformat() if self.analysis_started_at else None,
            "analysis_completed_at": self.analysis_completed_at.isoformat() if self.analysis_completed_at else None,
            "one_pager_json": self.one_pager_json,
            "scope_of_work_json": self.scope_of_work_json,
            "data_sheet_json": self.data_sheet_json,
        }


class AnalysisRFPSection(Base):
    """
    Stores a detailed, section-wise analysis of the RFP.
    Each row represents one section of the tender document.
    """
    __tablename__ = 'analysis_rfp_sections'
    id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('tender_analysis.id'), index=True)
    
    section_number: Mapped[Optional[str]] = mapped_column(String(50))
    section_title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    key_requirements: Mapped[Optional[list]] = mapped_column(JSON)
    compliance_issues: Mapped[Optional[list]] = mapped_column(JSON)
    page_references: Mapped[Optional[list]] = mapped_column(JSON)

    # Relationships
    analysis: Mapped["TenderAnalysis"] = relationship(back_populates="rfp_sections")


class AnalysisDocumentTemplate(Base):
    """
    Stores document templates extracted from the RFP (e.g., forms, declarations).
    """
    __tablename__ = 'analysis_document_templates'
    id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('tender_analysis.id'), index=True)
    
    template_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    required_format: Mapped[Optional[str]] = mapped_column(String(50))
    content_preview: Mapped[Optional[str]] = mapped_column(Text)
    page_references: Mapped[Optional[list]] = mapped_column(JSON)

    # Relationships
    analysis: Mapped["TenderAnalysis"] = relationship(back_populates="document_templates")
