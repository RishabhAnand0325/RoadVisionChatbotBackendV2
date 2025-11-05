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

class TenderAnalysis(Base):
    __tablename__ = 'tender_analysis'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey('tenders.id'))
    executive_summary = Column(Text)
    eligibility_criteria = Column(JSON)
    scope_of_work = Column(Text)
    financial_analysis = Column(JSON)
    timeline_analysis = Column(JSON)
    risk_assessment = Column(JSON)
    compliance_checklist = Column(JSON)
    key_clauses = Column(JSON)
    evaluation_criteria = Column(Text)
    recommendations = Column(Text)
    win_probability = Column(Float)
    analyzed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    analyzed_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))

    # Fields from analyze/db/schema.py
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # User who initiated analysis
    status = Column(Enum('pending', 'processing', 'completed', 'failed', name='analysis_status_enum'), default='pending', index=True)
    progress = Column(Integer, default=0)  # 0-100 percentage
    current_step = Column(String(50), default="initializing")  # Current processing step
    analysis_type = Column(String(50), default="full")  # "full", "summary", "risk-only"
    include_risk_assessment = Column(Boolean, default=True)
    include_rfp_analysis = Column(Boolean, default=True)
    include_scope_of_work = Column(Boolean, default=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)  # Time taken in milliseconds

    # Relationships from analyze/db/schema.py
    results = relationship("AnalysisResults", back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    risks = relationship("AnalysisRisk", back_populates="analysis", cascade="all, delete-orphan")
    rfp_sections = relationship("AnalysisRFPSection", back_populates="analysis", cascade="all, delete-orphan")
    extracted_content = relationship("TenderExtractedContent", back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    quality_metrics = relationship("ExtractionQualityMetrics", back_populates="analysis", uselist=False, cascade="all, delete-orphan")


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


class AnalysisStatusEnum(str, enum.Enum):
    """Analysis processing status"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class RiskLevelEnum(str, enum.Enum):
    """Risk severity levels"""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskCategoryEnum(str, enum.Enum):
    """Risk categories"""
    regulatory = "regulatory"
    financial = "financial"
    operational = "operational"
    contractual = "contractual"
    market = "market"


class AnalysisResults(Base):
    """
    Cached analysis results for a tender analysis.

    Stores complete analysis output including:
    - Summary (title, overview, key points)
    - RFP analysis sections
    - Scope of work
    - One-pager content
    """
    __tablename__ = "analysis_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analysis.id"), nullable=False, unique=True)

    summary_json = Column(JSON, nullable=True)  # {title, overview, keyPoints}
    rfp_analysis_json = Column(JSON, nullable=True)  # {sections, missingDocuments}
    scope_of_work_json = Column(JSON, nullable=True)  # {description, workItems, deliverables, effort}
    one_pager_json = Column(JSON, nullable=True)  # {content, generatedAt}

    # Cache metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)  # Results expire after 7 days

    # Relationships
    analysis = relationship("TenderAnalysis", back_populates="results")


class AnalysisRisk(Base):
    """
    Individual risk identified during analysis.

    Stores:
    - Risk classification (level, category)
    - Risk details (title, description)
    - Mitigation information
    - Related documents
    """
    __tablename__ = "analysis_risks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analysis.id"), nullable=False, index=True)

    level = Column(Enum(RiskLevelEnum), nullable=False)  # low, medium, high, critical
    category = Column(Enum(RiskCategoryEnum), nullable=False)  # regulatory, financial, etc

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    impact = Column(String(20), nullable=False)  # low, medium, high
    likelihood = Column(String(20), nullable=False)  # low, medium, high

    mitigation_strategy = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)

    related_documents = Column(JSON, default=[])  # List of document IDs

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    analysis = relationship("TenderAnalysis", back_populates="risks")


class AnalysisRFPSection(Base):
    """
    RFP section extracted from tender documents.

    Stores:
    - Section identification (number, title)
    - Section content (description, requirements)
    - Complexity assessment
    - Cross-references and compliance info
    """
    __tablename__ = "analysis_rfp_sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analysis.id"), nullable=False, index=True)

    section_number = Column(String(50), nullable=False)  # "1.1", "2.3", etc
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    key_requirements = Column(JSON, default=[])  # List of requirement strings
    estimated_complexity = Column(String(20), nullable=False)  # low, medium, high

    compliance_status = Column(String(20), nullable=True)  # compliant, non-compliant, requires-review
    compliance_issues = Column(JSON, default=[])  # List of issues

    related_sections = Column(JSON, default=[])  # List of section numbers
    document_references = Column(JSON, default=[])  # [{documentId, pageNumber}]

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    analysis = relationship("TenderAnalysis", back_populates="rfp_sections")


class TenderExtractedContent(Base):
    """
    Extracted and processed content from tender documents.

    Stores:
    - Raw extracted text from PDF
    - Identified document structure (sections, tables, figures)
    - Extraction quality metrics (OCR confidence, completeness)
    - Parsed content for each section
    """
    __tablename__ = "tender_extracted_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analysis.id"), nullable=False, unique=True)

    # Document metadata
    original_filename = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # In bytes
    file_type = Column(String(50), nullable=False)  # e.g., "application/pdf"
    page_count = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, nullable=False)

    # Extracted content
    raw_text = Column(Text, nullable=False)  # Full extracted text
    sections = Column(JSON, default={})  # {section_number: text, ...}
    tables = Column(JSON, default=[])  # [{table_data, location, page}]
    figures = Column(JSON, default=[])  # [{figure_type, description, page}]

    # Extraction metadata
    extraction_quality = Column(Float, default=0.0)  # 0-100 confidence
    ocr_required = Column(Boolean, default=False)  # Was OCR used?
    ocr_confidence = Column(Float, nullable=True)  # 0-100 if OCR was used
    extractable_sections = Column(Integer, default=0)  # Number of sections found

    # Processing status
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    extraction_started_at = Column(DateTime, nullable=True)
    extraction_completed_at = Column(DateTime, nullable=True)

    # Relationships
    analysis = relationship("TenderAnalysis", back_populates="extracted_content")


class ExtractionQualityMetrics(Base):
    """
    Quality assessment metrics for document extraction.

    Stores:
    - Data completeness score
    - Confidence levels per major field
    - Warnings about data quality
    - Recommendations for improving extraction
    """
    __tablename__ = "extraction_quality_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analysis.id"), nullable=False, unique=True)

    # Quality scores
    data_completeness = Column(Float, default=0.0)  # 0-100: how much data was extracted
    overall_confidence = Column(Float, default=0.0)  # 0-100: confidence in extraction quality

    # Section-wise confidence
    tender_info_confidence = Column(Float, default=0.0)
    financial_confidence = Column(Float, default=0.0)
    scope_confidence = Column(Float, default=0.0)
    rfp_sections_confidence = Column(Float, default=0.0)
    eligibility_confidence = Column(Float, default=0.0)

    # Quality warnings and recommendations
    warnings = Column(JSON, default=[])  # List of warning strings
    recommendations = Column(JSON, default=[])  # List of recommendation strings

    # Extraction summary
    sections_extracted = Column(Integer, default=0)
    tables_extracted = Column(Integer, default=0)
    figures_extracted = Column(Integer, default=0)
    annexures_identified = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    analysis = relationship("TenderAnalysis", back_populates="quality_metrics")
