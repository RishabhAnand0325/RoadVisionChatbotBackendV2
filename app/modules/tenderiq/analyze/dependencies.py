"""Dependency injection for TenderIQ Analyze module"""

from app.modules.tenderiq.analyze.services.analysis_service import AnalysisService
from app.modules.tenderiq.analyze.services.risk_assessment_service import RiskAssessmentService
from app.modules.tenderiq.analyze.services.rfp_extraction_service import RFPExtractionService
from app.modules.tenderiq.analyze.services.scope_extraction_service import ScopeExtractionService
from app.modules.tenderiq.analyze.services.report_generation_service import ReportGenerationService


def get_analysis_service() -> AnalysisService:
    """Get analysis service instance"""
    return AnalysisService()


def get_risk_assessment_service() -> RiskAssessmentService:
    """Get risk assessment service instance"""
    return RiskAssessmentService()


def get_rfp_extraction_service() -> RFPExtractionService:
    """Get RFP extraction service instance"""
    return RFPExtractionService()


def get_scope_extraction_service() -> ScopeExtractionService:
    """Get scope extraction service instance"""
    return ScopeExtractionService()


def get_report_generation_service() -> ReportGenerationService:
    """Get report generation service instance"""
    return ReportGenerationService()
