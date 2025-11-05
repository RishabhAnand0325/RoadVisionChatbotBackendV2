"""
TenderIQ Analyze Module - Database Schema

Defines SQLAlchemy ORM models for tender analysis functionality:
- TenderAnalysis: Analysis metadata and status
- AnalysisResults: Cached analysis results
- AnalysisRisk: Risk assessment details
- AnalysisRFPSection: RFP section analysis
"""

from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey, Text, JSON, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.database import Base


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


class TenderAnalysis(Base):
    """
    Tracks tender analyses with metadata and status.

    Stores:
    - Analysis metadata (id, tender_id, user_id)
    - Processing status (pending, processing, completed, failed)
    - Timestamps (created, completed)
    - Analysis configuration (what was analyzed)
    """
    __tablename__ = "tender_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Reference to ScrapedTender
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # User who initiated analysis

    status = Column(Enum(AnalysisStatusEnum), default=AnalysisStatusEnum.pending, index=True)
    progress = Column(Integer, default=0)  # 0-100 percentage
    current_step = Column(String(50), default="initializing")  # Current processing step

    analysis_type = Column(String(50), default="full")  # "full", "summary", "risk-only"
    include_risk_assessment = Column(Boolean, default=True)
    include_rfp_analysis = Column(Boolean, default=True)
    include_scope_of_work = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True, index=True)

    error_message = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)  # Time taken in milliseconds

    # Relationships
    results = relationship("AnalysisResults", back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    risks = relationship("AnalysisRisk", back_populates="analysis", cascade="all, delete-orphan")
    rfp_sections = relationship("AnalysisRFPSection", back_populates="analysis", cascade="all, delete-orphan")


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
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analyses.id"), nullable=False, unique=True, index=True)

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
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analyses.id"), nullable=False, index=True)

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
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analyses.id"), nullable=False, index=True)

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
