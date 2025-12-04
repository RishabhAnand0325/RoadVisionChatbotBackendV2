import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (Column, String, DateTime, ForeignKey, Text, JSON,
Integer, Boolean, Enum, Numeric, Float)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.modules.auth.db.schema import User
from app.modules.askai.db.models import Chat

class Tender(Base):
    __tablename__ = 'tenders'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_ref_number = Column(String, unique=True)
    tender_title = Column(Text)
    description = Column(Text)
    employer_name = Column(String)
    employer_address = Column(Text)
    issuing_authority = Column(String)
    state = Column(String)
    location = Column(String)
    category = Column(String)
    mode = Column(String)
    estimated_cost = Column(Numeric)
    bid_security = Column(Numeric)
    length_km = Column(Numeric, nullable=True)
    per_km_cost = Column(Numeric, nullable=True)
    span_length = Column(Numeric, nullable=True)
    road_work_amount = Column(Numeric, nullable=True)
    structure_work_amount = Column(Numeric, nullable=True)
    e_published_date = Column(DateTime)
    identification_date = Column(DateTime)
    submission_deadline = Column(DateTime)
    prebid_meeting_date = Column(DateTime, nullable=True)
    site_visit_deadline = Column(DateTime, nullable=True)
    portal_source = Column(String)
    portal_url = Column(String)
    document_url = Column(String)
    status = Column(Enum('New', 'Reviewed', 'Shortlisted', 'Bid_Preparation', 'Submitted', 'Won', 'Lost', 'Not_Interested', 'Pending_Results', name='tender_status_enum'), default='New')
    review_status = Column(Enum('Not_Reviewed', 'Reviewed', 'Shortlisted', name='review_status_enum'), default='Not_Reviewed')
    reviewed_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_favorite = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    is_wishlisted = Column(Boolean, default=False, index=True)
    history = relationship("TenderActionHistory", back_populates="tender", cascade="all, delete-orphan")


class TenderDocument(Base):
    __tablename__ = 'tender_documents'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey('tenders.id'))
    document_name = Column(String)
    document_type = Column(Enum('Original_RFP', 'Amendment', 'Bid_Document', 'Supporting', 'Comparison_Report', name='tender_doc_type_enum'))
    file_path = Column(String)
    file_size = Column(Integer)
    uploaded_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TenderComparison(Base):
    __tablename__ = 'tender_comparisons'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_1_id = Column(UUID(as_uuid=True), ForeignKey('tenders.id'))
    tender_2_id = Column(UUID(as_uuid=True), ForeignKey('tenders.id'))
    comparison_report = Column(JSON)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TenderTeam(Base):
    __tablename__ = 'tender_team'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey('tenders.id'))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    role = Column(String)
    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    assigned_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))


class TenderNote(Base):
    __tablename__ = 'tender_notes'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey('tenders.id'))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    note_content = Column(Text)
    parent_note_id = Column(UUID(as_uuid=True), ForeignKey('tender_notes.id'), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_important = Column(Boolean, default=False)


class TenderActionEnum(str, enum.Enum):
    """Enumeration for user actions on a tender."""
    viewed = "viewed"
    wishlisted = "wishlisted"
    unwishlisted = "unwishlisted"
    favorited = "favorited"
    unfavorited = "unfavorited"
    archived = "archived"
    unarchived = "unarchived"
    analysis_started = "analysis_started"
    analysis_completed = "analysis_completed"
    shortlisted = "shortlisted"
    accepted = "accepted"
    rejected = "rejected"
    corrigendum_updated = "corrigendum_updated"


class TenderActionHistory(Base):
    """Logs specific user-driven actions on a tender for history tracking."""
    __tablename__ = 'tender_action_history'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey('tenders.id'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    action = Column(Enum(TenderActionEnum), nullable=False)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    tender = relationship("Tender", back_populates="history")


class TenderActivityLog(Base):
    __tablename__ = 'tender_activity_log'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey('tenders.id'))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    action_type = Column(String)
    action_details = Column(JSON)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ==================== NEW: TENDER WISHLIST MODEL ====================
class WishlistStatusEnum(str, enum.Enum):
    """Defines the status of a tender in wishlist/history."""
    won = "won"
    rejected = "rejected"
    incomplete = "incomplete"
    pending = "pending"


class TenderWishlist(Base):
    """
    Stores saved tenders in user's wishlist/history.
    Tracks tender progress through analysis workflow stages (STAGE 3 UI).
    
    Linked to:
    - Tender: Original tender information via tender_ref_number
    - User: User who saved the tender
    - TenderAnalysis: Detailed analysis results (from analyze module)
    """
    __tablename__ = 'tender_wishlist'
    
    # Primary Keys
    id = Column(String, primary_key=True, index=True)
    tender_ref_number = Column(String, ForeignKey('tenders.tender_ref_number'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    
    # Tender Information (denormalized for quick access)
    title = Column(String(255), nullable=False)
    authority = Column(String(255), nullable=False)
    value = Column(Float, nullable=False)
    emd = Column(Float, nullable=False)
    due_date = Column(String(50), nullable=False)  # Format: "15 Dec"
    category = Column(String(100), nullable=False)
    
    # Analysis Progress Tracking (Matches STAGE 3 - Wishlist workflow)
    progress = Column(Integer, default=0, nullable=False)  # 0-100% completion
    analysis_state = Column(Boolean, default=False)  # Analysis phase done
    synopsis_state = Column(Boolean, default=False)  # Synopsis phase done
    evaluated_state = Column(Boolean, default=False)  # Evaluation phase done
    results = Column(String(50), default=WishlistStatusEnum.pending.value)  # won/rejected/incomplete/pending
    
    # Status Messages
    status_message = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    added_to_wishlist_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert SQLAlchemy model to dictionary for API responses."""
        return {
            'id': self.id,
            'tender_ref_number': self.tender_ref_number,
            'user_id': str(self.user_id) if self.user_id else None,
            'title': self.title,
            'authority': self.authority,
            'value': float(self.value),
            'emd': float(self.emd),
            'due_date': self.due_date,
            'category': self.category,
            'progress': self.progress,
            'analysis_state': self.analysis_state,
            'synopsis_state': self.synopsis_state,
            'evaluated_state': self.evaluated_state,
            'results': self.results,
            'status_message': self.status_message,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'added_to_wishlist_at': self.added_to_wishlist_at.isoformat() if self.added_to_wishlist_at else None,
        }
