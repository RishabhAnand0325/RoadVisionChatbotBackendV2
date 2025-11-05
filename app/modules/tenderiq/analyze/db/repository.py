"""
TenderIQ Analyze Repository Layer

Encapsulates all data access logic for TenderIQ analysis features.
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.modules.tenderiq.analyze.db.schema import (
    TenderAnalysis,
    AnalysisResults,
    AnalysisRisk,
    AnalysisRFPSection,
    TenderExtractedContent,
    ExtractionQualityMetrics,
    AnalysisStatusEnum,
)


class AnalyzeRepository:
    """Repository for TenderIQ analysis data access operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_analysis(
        self, tender_id: UUID, user_id: UUID, analysis_type: str, **kwargs
    ) -> TenderAnalysis:
        """Create a new tender analysis record."""
        analysis = TenderAnalysis(
            tender_id=tender_id,
            user_id=user_id,
            analysis_type=analysis_type,
            **kwargs,
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def get_analysis_by_id(self, analysis_id: UUID) -> Optional[TenderAnalysis]:
        """Get an analysis by its ID."""
        return (
            self.db.query(TenderAnalysis)
            .filter(TenderAnalysis.id == analysis_id)
            .first()
        )

    def update_analysis_status(
        self,
        analysis_id: UUID,
        status: AnalysisStatusEnum,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Update the status and progress of an analysis."""
        analysis = self.get_analysis_by_id(analysis_id)
        if not analysis:
            return None

        analysis.status = status
        if progress is not None:
            analysis.progress = progress
        if current_step is not None:
            analysis.current_step = current_step
        if error_message is not None:
            analysis.error_message = error_message
        
        if status == AnalysisStatusEnum.processing and not analysis.started_at:
            analysis.started_at = datetime.utcnow()
        
        if status in [AnalysisStatusEnum.completed, AnalysisStatusEnum.failed]:
            analysis.completed_at = datetime.utcnow()
            if analysis.started_at:
                analysis.processing_time_ms = int((analysis.completed_at - analysis.started_at).total_seconds() * 1000)

        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def get_analysis_results(
        self, analysis_id: UUID
    ) -> Optional[AnalysisResults]:
        """Get analysis results by analysis ID."""
        return (
            self.db.query(AnalysisResults)
            .filter(AnalysisResults.analysis_id == analysis_id)
            .first()
        )

    def create_or_update_analysis_results(
        self,
        analysis_id: UUID,
        summary: dict,
        rfp: dict,
        scope: dict,
        one_pager: dict
    ) -> AnalysisResults:
        """Create or update analysis results."""
        results = self.get_analysis_results(analysis_id)
        if not results:
            results = AnalysisResults(
                analysis_id=analysis_id,
                expires_at=datetime.utcnow() + timedelta(days=7) # Add expiration
            )
            self.db.add(results)
        
        results.summary_json = summary
        results.rfp_analysis_json = rfp
        results.scope_of_work_json = scope
        results.one_pager_json = one_pager
        
        self.db.commit()
        self.db.refresh(results)
        return results

    def get_user_analyses(
        self, user_id: UUID, status: Optional[str], tender_id: Optional[UUID], limit: int, offset: int
    ) -> (List[TenderAnalysis], int):
        """Get all analyses for a user with optional filters."""
        query = self.db.query(TenderAnalysis).filter(TenderAnalysis.user_id == user_id)
        if status:
            query = query.filter(TenderAnalysis.status == status)
        if tender_id:
            query = query.filter(TenderAnalysis.tender_id == tender_id)
        
        total = query.count()
        analyses = query.limit(limit).offset(offset).all()
        return analyses, total

    def delete_analysis(self, analysis_id: UUID, user_id: UUID) -> bool:
        """Delete an analysis and its results. Must match user_id."""
        analysis = (
            self.db.query(TenderAnalysis)
            .filter(TenderAnalysis.id == analysis_id, TenderAnalysis.user_id == user_id)
            .first()
        )
        if analysis:
            self.db.delete(analysis)
            self.db.commit()
            return True
        return False
