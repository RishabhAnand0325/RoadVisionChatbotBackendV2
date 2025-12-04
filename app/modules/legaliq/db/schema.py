import uuid
from datetime import datetime, timezone
from sqlalchemy import (Column, String, DateTime, ForeignKey, Text, JSON,
                        Table, Integer, Boolean, Enum, Float, Numeric)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base

# Note: Foreign Keys to 'users.id' assume the Users table is defined in the 'auth' module.

class Case(Base):
    __tablename__ = 'cases'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_number = Column(String, unique=True)
    case_title = Column(Text)
    description = Column(Text)
    case_type = Column(String)
    jurisdiction = Column(String)
    court_name = Column(String)
    presiding_judge = Column(String, nullable=True)
    filing_date = Column(DateTime)
    registration_date = Column(DateTime, nullable=True)
    status = Column(Enum('Pending', 'Under_Review', 'Closed', 'Archived', name='case_status_enum'), default='Pending')
    client_name = Column(String)
    opposing_party = Column(String, nullable=True)
    advocate_petitioner = Column(String, nullable=True)
    advocate_respondent = Column(String, nullable=True)
    department = Column(String)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    updated_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_favorite = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)

class LegalIQDocument(Base):
    __tablename__ = 'legaliq_documents'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.id'))
    document_name = Column(String)
    document_type = Column(Enum('Petition', 'Affidavit', 'Legal_Notice', 'Rejoinder', 'MoU', 'Order', 'Judgment', 'Supporting_Document', name='legaliq_doc_type_enum'))
    file_path = Column(String)
    file_size = Column(Integer)
    version = Column(String, nullable=True)
    uploaded_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_anonymized = Column(Boolean, default=False)
    linked_analysis_id = Column(UUID(as_uuid=True), ForeignKey('document_analysis.id'), nullable=True)
    description = Column(Text, nullable=True)

class DocumentAnalysis(Base):
    __tablename__ = 'document_analysis'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('legaliq_documents.id'))
    executive_summary = Column(Text)
    extracted_facts = Column(JSON)
    key_clauses = Column(JSON)
    risk_assessment = Column(JSON)
    compliance_findings = Column(JSON)
    suggested_next_steps = Column(JSON)
    ai_model_version = Column(String)
    win_probability = Column(Float, nullable=True)
    analyzed_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    analyzed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class LegalResearch(Base):
    __tablename__ = 'legal_research'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_text = Column(Text)
    search_category = Column(Enum('Judgment', 'Act', 'Statute', 'Legal_Issue', name='research_category_enum'))
    results_json = Column(JSON)
    total_results = Column(Integer)
    average_relevance_score = Column(Float)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    saved_to_case = Column(Boolean, default=False)
    linked_case_id = Column(UUID(as_uuid=True), ForeignKey('cases.id'), nullable=True)

class DraftingTemplate(Base):
    __tablename__ = 'drafting_templates'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_name = Column(String)
    template_type = Column(Enum('Statement_of_Facts', 'Legal_Notice', 'Rejoinder', 'MoU', 'Affidavit', name='template_type_enum'))
    template_version = Column(String)
    template_description = Column(Text)
    last_modified_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    last_modified_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

class AnonymizationJob(Base):
    __tablename__ = 'anonymization_jobs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('legaliq_documents.id'))
    fields_anonymized = Column(JSON)
    total_fields_redacted = Column(Integer)
    status = Column(Enum('Pending', 'In_Progress', 'Completed', 'Failed', name='job_status_enum'))
    output_file_path = Column(String, nullable=True)
    processed_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    processed_at = Column(DateTime)

class CaseHearing(Base):
    __tablename__ = 'case_hearings'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.id'))
    hearing_date = Column(DateTime)
    hearing_purpose = Column(Text)
    judge_name = Column(String, nullable=True)
    outcome = Column(Text, nullable=True)
    order_document_id = Column(UUID(as_uuid=True), ForeignKey('legaliq_documents.id'), nullable=True)
    next_hearing_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class CaseAnalytics(Base):
    __tablename__ = 'case_analytics'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.id'))
    total_documents = Column(Integer)
    total_hearings = Column(Integer)
    average_case_duration = Column(Numeric)
    success_rate = Column(Float)
    risk_index = Column(Float)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class CaseNote(Base):
    __tablename__ = 'case_notes'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.id'))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    note_content = Column(Text)
    parent_note_id = Column(UUID(as_uuid=True), ForeignKey('case_notes.id'), nullable=True)
    is_important = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ActivityLog(Base):
    __tablename__ = 'activity_log'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.id'), nullable=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey('legaliq_documents.id'), nullable=True)
    action_type = Column(String)
    action_details = Column(JSON)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AccessControl(Base):
    __tablename__ = 'access_control'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.id'), nullable=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey('legaliq_documents.id'), nullable=True)
    permission_level = Column(Enum('View', 'Edit', 'Delete', 'Share', 'Admin', name='permission_level_enum'))
    granted_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    granted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    notification_type = Column(Enum('Reminder', 'Update', 'Alert', 'System', name='notification_type_enum'))
    notification_title = Column(String)
    notification_body = Column(Text)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
