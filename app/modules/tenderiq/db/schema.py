import uuid
from datetime import datetime, timezone
from sqlalchemy import (Column, String, DateTime, ForeignKey, Text, JSON,
                        Integer, Boolean, Enum, Numeric, Float)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base

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

import enum

class TenderActivityLog(Base):
    __tablename__ = 'tender_activity_log'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey('tenders.id'))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    action_type = Column(String)
    action_details = Column(JSON)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
