import uuid
import enum
from datetime import datetime
from sqlalchemy import (Column, String, DateTime, ForeignKey, Text, JSON,
                        Integer, Boolean, Enum as SQLAlchemyEnum, Float)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

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
    __tablename__ = 'tender_analysis'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey('tenders.id'))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    
    status = Column(SQLAlchemyEnum(AnalysisStatusEnum), default=AnalysisStatusEnum.pending, index=True)
    progress = Column(Integer, default=0)
    current_step = Column(String(50), default="initializing")
    analysis_type = Column(String(50), default="full")
    include_risk_assessment = Column(Boolean, default=True)
    include_rfp_analysis = Column(Boolean, default=True)
    include_scope_of_work = Column(Boolean, default=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    results = relationship("AnalysisResults", back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    risks = relationship("AnalysisRisk", back_populates="analysis", cascade="all, delete-orphan")
    rfp_sections = relationship("AnalysisRFPSection", back_populates="analysis", cascade="all, delete-orphan")
    extracted_content = relationship("TenderExtractedContent", back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    quality_metrics = relationship("ExtractionQualityMetrics", back_populates="analysis", uselist=False, cascade="all, delete-orphan")


class AnalysisResults(Base):
    __tablename__ = "analysis_results"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analysis.id"), nullable=False, unique=True)
    summary_json = Column(JSON, nullable=True)
    rfp_analysis_json = Column(JSON, nullable=True)
    scope_of_work_json = Column(JSON, nullable=True)
    one_pager_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    analysis = relationship("TenderAnalysis", back_populates="results")


class AnalysisRisk(Base):
    __tablename__ = "analysis_risks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analysis.id"), nullable=False, index=True)
    level = Column(SQLAlchemyEnum(RiskLevelEnum), nullable=False)
    category = Column(SQLAlchemyEnum(RiskCategoryEnum), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    impact = Column(String(20), nullable=False)
    likelihood = Column(String(20), nullable=False)
    mitigation_strategy = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    related_documents = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    analysis = relationship("TenderAnalysis", back_populates="risks")


class AnalysisRFPSection(Base):
    __tablename__ = "analysis_rfp_sections"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analysis.id"), nullable=False, index=True)
    section_number = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    key_requirements = Column(JSON, default=[])
    estimated_complexity = Column(String(20), nullable=False)
    compliance_status = Column(String(20), nullable=True)
    compliance_issues = Column(JSON, default=[])
    related_sections = Column(JSON, default=[])
    document_references = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    analysis = relationship("TenderAnalysis", back_populates="rfp_sections")


class TenderExtractedContent(Base):
    __tablename__ = "tender_extracted_content"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analysis.id"), nullable=False, unique=True)
    original_filename = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(50), nullable=False)
    page_count = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, nullable=False)
    raw_text = Column(Text, nullable=False)
    sections = Column(JSON, default={})
    tables = Column(JSON, default=[])
    figures = Column(JSON, default=[])
    extraction_quality = Column(Float, default=0.0)
    ocr_required = Column(Boolean, default=False)
    ocr_confidence = Column(Float, nullable=True)
    extractable_sections = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    extraction_started_at = Column(DateTime, nullable=True)
    extraction_completed_at = Column(DateTime, nullable=True)
    analysis = relationship("TenderAnalysis", back_populates="extracted_content")


class ExtractionQualityMetrics(Base):
    __tablename__ = "extraction_quality_metrics"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("tender_analysis.id"), nullable=False, unique=True)
    data_completeness = Column(Float, default=0.0)
    overall_confidence = Column(Float, default=0.0)
    tender_info_confidence = Column(Float, default=0.0)
    financial_confidence = Column(Float, default=0.0)
    scope_confidence = Column(Float, default=0.0)
    rfp_sections_confidence = Column(Float, default=0.0)
    eligibility_confidence = Column(Float, default=0.0)
    warnings = Column(JSON, default=[])
    recommendations = Column(JSON, default=[])
    sections_extracted = Column(Integer, default=0)
    tables_extracted = Column(Integer, default=0)
    figures_extracted = Column(Integer, default=0)
    annexures_identified = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    analysis = relationship("TenderAnalysis", back_populates="quality_metrics")
