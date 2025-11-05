"""
Repository layer for TenderIQ Analyze module.

Encapsulates all database operations for analysis, risks, and RFP sections.
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload

from app.modules.tenderiq.analyze.db.schema import (
    TenderAnalysis,
    AnalysisResults,
    AnalysisRisk,
    AnalysisRFPSection,
    AnalysisStatusEnum,
)


class AnalyzeRepository:
    """Repository for TenderIQ Analyze operations"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== TenderAnalysis Operations ====================

    def create_analysis(
        self,
        tender_id: UUID,
        user_id: UUID,
        analysis_type: str = "full",
        include_risk_assessment: bool = True,
        include_rfp_analysis: bool = True,
        include_scope_of_work: bool = True,
    ) -> TenderAnalysis:
        """
        Create a new analysis record.

        Args:
            tender_id: Tender to analyze
            user_id: User initiating analysis
            analysis_type: "full", "summary", or "risk-only"
            include_risk_assessment: Include risk analysis
            include_rfp_analysis: Include RFP analysis
            include_scope_of_work: Include scope analysis

        Returns:
            Created TenderAnalysis record
        """
        analysis = TenderAnalysis(
            tender_id=tender_id,
            user_id=user_id,
            analysis_type=analysis_type,
            include_risk_assessment=include_risk_assessment,
            include_rfp_analysis=include_rfp_analysis,
            include_scope_of_work=include_scope_of_work,
        )
        self.db.add(analysis)
        self.db.commit()
        return analysis

    def get_analysis_by_id(self, analysis_id: UUID) -> Optional[TenderAnalysis]:
        """Get analysis by ID with all relationships loaded"""
        return (
            self.db.query(TenderAnalysis)
            .filter(TenderAnalysis.id == analysis_id)
            .options(
                joinedload(TenderAnalysis.results),
                joinedload(TenderAnalysis.risks),
                joinedload(TenderAnalysis.rfp_sections),
            )
            .first()
        )

    def update_analysis_status(
        self,
        analysis_id: UUID,
        status: AnalysisStatusEnum,
        progress: int = None,
        current_step: str = None,
        error_message: str = None,
    ) -> TenderAnalysis:
        """Update analysis status and progress"""
        analysis = self.db.query(TenderAnalysis).filter(TenderAnalysis.id == analysis_id).first()
        if not analysis:
            return None

        if status == AnalysisStatusEnum.processing and analysis.started_at is None:
            analysis.started_at = datetime.utcnow()

        analysis.status = status
        if progress is not None:
            analysis.progress = progress
        if current_step is not None:
            analysis.current_step = current_step
        if error_message is not None:
            analysis.error_message = error_message

        if status == AnalysisStatusEnum.completed:
            analysis.completed_at = datetime.utcnow()
            if analysis.started_at:
                analysis.processing_time_ms = int(
                    (analysis.completed_at - analysis.started_at).total_seconds() * 1000
                )
        elif status == AnalysisStatusEnum.failed:
            analysis.completed_at = datetime.utcnow()
            if analysis.started_at:
                analysis.processing_time_ms = int(
                    (analysis.completed_at - analysis.started_at).total_seconds() * 1000
                )

        self.db.commit()
        return analysis

    def get_user_analyses(
        self,
        user_id: UUID,
        status: Optional[AnalysisStatusEnum] = None,
        tender_id: Optional[UUID] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[TenderAnalysis], int]:
        """
        Get analyses for a user with optional filtering.

        Returns:
            Tuple of (analyses list, total count)
        """
        query = self.db.query(TenderAnalysis).filter(TenderAnalysis.user_id == user_id)

        if status:
            query = query.filter(TenderAnalysis.status == status)
        if tender_id:
            query = query.filter(TenderAnalysis.tender_id == tender_id)

        total = query.count()

        analyses = (
            query.order_by(TenderAnalysis.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return analyses, total

    def delete_analysis(self, analysis_id: UUID, user_id: UUID) -> bool:
        """Delete analysis if owned by user"""
        analysis = (
            self.db.query(TenderAnalysis)
            .filter(
                TenderAnalysis.id == analysis_id,
                TenderAnalysis.user_id == user_id
            )
            .first()
        )
        if not analysis:
            return False

        self.db.delete(analysis)
        self.db.commit()
        return True

    # ==================== AnalysisResults Operations ====================

    def create_analysis_results(
        self,
        analysis_id: UUID,
        summary_json: dict = None,
        rfp_analysis_json: dict = None,
        scope_of_work_json: dict = None,
        one_pager_json: dict = None,
    ) -> AnalysisResults:
        """
        Create analysis results record.
        Results expire after 7 days.
        """
        results = AnalysisResults(
            analysis_id=analysis_id,
            summary_json=summary_json,
            rfp_analysis_json=rfp_analysis_json,
            scope_of_work_json=scope_of_work_json,
            one_pager_json=one_pager_json,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        self.db.add(results)
        self.db.commit()
        return results

    def get_analysis_results(self, analysis_id: UUID) -> Optional[AnalysisResults]:
        """
        Get analysis results if they exist and haven't expired.

        Returns:
            AnalysisResults or None if expired
        """
        results = (
            self.db.query(AnalysisResults)
            .filter(AnalysisResults.analysis_id == analysis_id)
            .first()
        )

        if results and results.expires_at < datetime.utcnow():
            # Results expired - soft delete by returning None
            return None

        return results

    def update_analysis_results(
        self,
        analysis_id: UUID,
        summary_json: dict = None,
        rfp_analysis_json: dict = None,
        scope_of_work_json: dict = None,
        one_pager_json: dict = None,
    ) -> Optional[AnalysisResults]:
        """Update existing analysis results"""
        results = self.db.query(AnalysisResults).filter(AnalysisResults.analysis_id == analysis_id).first()
        if not results:
            return None

        if summary_json is not None:
            results.summary_json = summary_json
        if rfp_analysis_json is not None:
            results.rfp_analysis_json = rfp_analysis_json
        if scope_of_work_json is not None:
            results.scope_of_work_json = scope_of_work_json
        if one_pager_json is not None:
            results.one_pager_json = one_pager_json

        self.db.commit()
        return results

    # ==================== AnalysisRisk Operations ====================

    def create_risk(
        self,
        analysis_id: UUID,
        level: str,
        category: str,
        title: str,
        description: str,
        impact: str,
        likelihood: str,
        mitigation_strategy: str = None,
        recommended_action: str = None,
        related_documents: list = None,
    ) -> AnalysisRisk:
        """Create a risk record"""
        risk = AnalysisRisk(
            analysis_id=analysis_id,
            level=level,
            category=category,
            title=title,
            description=description,
            impact=impact,
            likelihood=likelihood,
            mitigation_strategy=mitigation_strategy,
            recommended_action=recommended_action,
            related_documents=related_documents or [],
        )
        self.db.add(risk)
        self.db.commit()
        return risk

    def get_analysis_risks(self, analysis_id: UUID) -> List[AnalysisRisk]:
        """Get all risks for an analysis"""
        return (
            self.db.query(AnalysisRisk)
            .filter(AnalysisRisk.analysis_id == analysis_id)
            .order_by(AnalysisRisk.level)
            .all()
        )

    def delete_analysis_risks(self, analysis_id: UUID) -> int:
        """Delete all risks for an analysis"""
        count = self.db.query(AnalysisRisk).filter(AnalysisRisk.analysis_id == analysis_id).delete()
        self.db.commit()
        return count

    # ==================== AnalysisRFPSection Operations ====================

    def create_rfp_section(
        self,
        analysis_id: UUID,
        section_number: str,
        title: str,
        description: str,
        key_requirements: list = None,
        estimated_complexity: str = "medium",
        compliance_status: str = None,
        compliance_issues: list = None,
        related_sections: list = None,
        document_references: list = None,
    ) -> AnalysisRFPSection:
        """Create an RFP section record"""
        section = AnalysisRFPSection(
            analysis_id=analysis_id,
            section_number=section_number,
            title=title,
            description=description,
            key_requirements=key_requirements or [],
            estimated_complexity=estimated_complexity,
            compliance_status=compliance_status,
            compliance_issues=compliance_issues or [],
            related_sections=related_sections or [],
            document_references=document_references or [],
        )
        self.db.add(section)
        self.db.commit()
        return section

    def get_analysis_rfp_sections(self, analysis_id: UUID) -> List[AnalysisRFPSection]:
        """Get all RFP sections for an analysis"""
        return (
            self.db.query(AnalysisRFPSection)
            .filter(AnalysisRFPSection.analysis_id == analysis_id)
            .order_by(AnalysisRFPSection.section_number)
            .all()
        )

    def get_rfp_section_by_number(
        self,
        analysis_id: UUID,
        section_number: str
    ) -> Optional[AnalysisRFPSection]:
        """Get specific RFP section"""
        return (
            self.db.query(AnalysisRFPSection)
            .filter(
                AnalysisRFPSection.analysis_id == analysis_id,
                AnalysisRFPSection.section_number == section_number
            )
            .first()
        )

    def delete_analysis_rfp_sections(self, analysis_id: UUID) -> int:
        """Delete all RFP sections for an analysis"""
        count = self.db.query(AnalysisRFPSection).filter(AnalysisRFPSection.analysis_id == analysis_id).delete()
        self.db.commit()
        return count
