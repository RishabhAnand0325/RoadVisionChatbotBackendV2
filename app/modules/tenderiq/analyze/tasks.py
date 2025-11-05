"""
Async Task Processing for Tender Analysis

Handles async processing of tender analyses using background tasks.
Currently uses simple background execution (can be upgraded to Celery/RQ).
"""

import asyncio
import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository
from app.modules.tenderiq.analyze.db.schema import AnalysisStatusEnum
from app.modules.tenderiq.analyze.services.document_parser import DocumentParser
from app.modules.tenderiq.analyze.services.tender_info_extractor import TenderInfoExtractor
from app.modules.tenderiq.analyze.services.onepager_generator import OnePagerGenerator
from app.modules.tenderiq.analyze.services.scope_work_analyzer import ScopeOfWorkAnalyzer
from app.modules.tenderiq.analyze.services.rfp_section_analyzer import RFPSectionAnalyzer
from app.modules.tenderiq.analyze.services.risk_assessment_service import RiskAssessmentService
from app.modules.tenderiq.analyze.services.rfp_extraction_service import RFPExtractionService
from app.modules.tenderiq.analyze.services.scope_extraction_service import ScopeExtractionService
from app.modules.tenderiq.analyze.services.report_generation_service import ReportGenerationService

logger = logging.getLogger(__name__)


class AnalysisTaskProcessor:
    """Processes tender analysis tasks asynchronously"""

    def __init__(self):
        # Phase 1: Document Parsing
        self.document_parser = DocumentParser()

        # Phase 2: Structured Data Extraction
        self.tender_info_extractor = TenderInfoExtractor()

        # Phase 3: Semantic Analysis
        self.onepager_generator = OnePagerGenerator()
        self.scope_analyzer = ScopeOfWorkAnalyzer()
        self.rfp_analyzer = RFPSectionAnalyzer()

        # Existing services
        self.risk_service = RiskAssessmentService()
        self.rfp_service = RFPExtractionService()
        self.scope_service = ScopeExtractionService()
        self.report_service = ReportGenerationService()

    def process_analysis(self, analysis_id: UUID) -> bool:
        """
        Process a tender analysis end-to-end with all Phase 1-3 services.

        Orchestrates the complete analysis pipeline:
        - Phase 1: Document parsing and text extraction
        - Phase 2: Structured data extraction (tender info, financial, etc.)
        - Phase 3: Semantic analysis (onepager, scope, RFP sections)
        - Legacy services: Risk assessment, RFP analysis, scope extraction, reports

        Args:
            analysis_id: UUID of the analysis to process

        Returns:
            True if successful, False if failed
        """
        db = SessionLocal()
        repo = AnalyzeRepository(db)
        raw_text = ""
        tender_info = None

        try:
            # Get the analysis record
            analysis = repo.get_analysis_by_id(analysis_id)
            if not analysis:
                logger.error(f"Analysis not found: {analysis_id}")
                return False

            logger.info(f"Starting comprehensive analysis: {analysis_id}")

            # Update status to processing
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=5,
                current_step="initializing",
            )

            # ===== PHASE 1: Document Parsing (5-20%) =====
            # TODO: Get file path from tender document association
            # For now, we'll work with raw text if available
            logger.info(f"Phase 1: Document parsing for {analysis_id}")
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=10,
                current_step="parsing-document",
            )

            # Phase 1 would process document here if file available
            # document_result = await self.document_parser.parse_document(...)
            # raw_text = document_result.raw_text

            # ===== PHASE 2: Structured Data Extraction (20-40%) =====
            logger.info(f"Phase 2: Structured extraction for {analysis_id}")
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=25,
                current_step="extracting-tender-info",
            )

            try:
                tender_info = self.tender_info_extractor.extract_tender_info(
                    db=db,
                    analysis_id=analysis_id,
                    raw_text=raw_text if raw_text else "",
                    use_llm=True,
                )
                logger.info(f"✅ Tender info extracted: {tender_info.referenceNumber}")
            except Exception as e:
                logger.warning(f"⚠️ Tender info extraction failed: {e}")
                # Continue with other phases even if this fails

            # ===== PHASE 3: Semantic Analysis (40-70%) =====
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=40,
                current_step="generating-onepager",
            )

            try:
                onepager_data = self.onepager_generator.generate_onepager(
                    db=db,
                    analysis_id=analysis_id,
                    raw_text=raw_text if raw_text else "",
                    extracted_tender_info=tender_info.model_dump() if tender_info else None,
                    use_llm=True,
                )
                logger.info(f"✅ OnePager generated with confidence: {onepager_data.extractionConfidence}%")
            except Exception as e:
                logger.warning(f"⚠️ OnePager generation failed: {e}")

            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=55,
                current_step="analyzing-scope",
            )

            scope_result = None
            try:
                scope_result = self.scope_analyzer.analyze_scope(
                    db=db,
                    analysis_id=analysis_id,
                    raw_text=raw_text if raw_text else "",
                    use_llm=True,
                )
                logger.info(
                    f"✅ Scope analysis completed: {scope_result['item_count']} items, "
                    f"{scope_result['total_effort_days']} days"
                )
            except Exception as e:
                logger.warning(f"⚠️ Scope analysis failed: {e}")

            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=65,
                current_step="analyzing-rfp-sections",
            )

            rfp_result = None
            try:
                rfp_result = self.rfp_analyzer.analyze_rfp_sections(
                    db=db,
                    analysis_id=analysis_id,
                    raw_text=raw_text if raw_text else "",
                    use_llm=True,
                )
                logger.info(
                    f"✅ RFP analysis completed: {rfp_result['total_sections']} sections, "
                    f"{rfp_result['total_requirements']} requirements"
                )
            except Exception as e:
                logger.warning(f"⚠️ RFP analysis failed: {e}")

            # ===== Legacy Services (70-90%) =====
            # Step 1: Risk Assessment
            if analysis.include_risk_assessment:
                logger.info(f"Legacy Step 1: Risk assessment for {analysis_id}")
                repo.update_analysis_status(
                    analysis_id,
                    AnalysisStatusEnum.processing,
                    progress=70,
                    current_step="analyzing-risk",
                )

                try:
                    risk_response = self.risk_service.assess_risks(
                        db=db,
                        analysis_id=analysis_id,
                        tender_id=analysis.tender_id,
                        depth="summary",
                    )
                    logger.info(f"✅ Risk assessment completed: score={risk_response.risk_score}")
                except Exception as e:
                    logger.warning(f"⚠️ Risk assessment failed: {e}")

            # Step 2: RFP Analysis (legacy)
            if analysis.include_rfp_analysis:
                logger.info(f"Legacy Step 2: RFP extraction for {analysis_id}")
                repo.update_analysis_status(
                    analysis_id,
                    AnalysisStatusEnum.processing,
                    progress=75,
                    current_step="extracting-rfp-legacy",
                )

                try:
                    rfp_response = self.rfp_service.extract_rfp_sections(
                        db=db,
                        analysis_id=analysis_id,
                        tender_id=analysis.tender_id,
                        include_compliance=False,
                    )
                    logger.info(f"✅ RFP extraction completed: sections={rfp_response.total_sections}")
                except Exception as e:
                    logger.warning(f"⚠️ RFP extraction failed: {e}")

            # Step 3: Scope Extraction (legacy)
            if analysis.include_scope_of_work:
                logger.info(f"Legacy Step 3: Scope extraction for {analysis_id}")
                repo.update_analysis_status(
                    analysis_id,
                    AnalysisStatusEnum.processing,
                    progress=80,
                    current_step="extracting-scope-legacy",
                )

                try:
                    scope_response = self.scope_service.extract_scope(
                        db=db,
                        analysis_id=analysis_id,
                        tender_id=analysis.tender_id,
                    )
                    logger.info(f"✅ Scope extraction completed: effort={scope_response.scope_of_work.estimated_total_effort}d")
                except Exception as e:
                    logger.warning(f"⚠️ Scope extraction failed: {e}")

            # Step 4: Summary Generation (85-95%)
            logger.info(f"Step 4: Summary generation for {analysis_id}")
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=85,
                current_step="generating-summary",
            )

            try:
                one_pager = self.report_service.generate_one_pager(
                    db=db,
                    analysis_id=analysis_id,
                    tender_id=analysis.tender_id,
                    format="markdown",
                    include_risk_assessment=analysis.include_risk_assessment,
                    include_scope_of_work=analysis.include_scope_of_work,
                    include_financials=True,
                )
                logger.info(f"✅ Summary generation completed")

                # Store results in database
                repo.create_analysis_results(
                    analysis_id=analysis_id,
                    one_pager_json=one_pager.one_pager,
                )
            except Exception as e:
                logger.warning(f"⚠️ Summary generation failed: {e}")

            # Mark as completed (95-100%)
            logger.info(f"✅ Analysis completed: {analysis_id}")
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.completed,
                progress=100,
                current_step="completed",
            )

            return True

        except Exception as e:
            logger.error(f"❌ Unexpected error in analysis: {e}", exc_info=True)
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.failed,
                error_message=str(e),
            )
            return False

        finally:
            db.close()


# Global task processor instance
task_processor = AnalysisTaskProcessor()


def process_analysis_sync(analysis_id: UUID) -> bool:
    """
    Process analysis synchronously.

    This is a wrapper that can be used by background job workers.

    Args:
        analysis_id: UUID of analysis to process

    Returns:
        True if successful, False otherwise
    """
    return task_processor.process_analysis(analysis_id)


async def process_analysis_async(analysis_id: UUID) -> bool:
    """
    Process analysis asynchronously using asyncio.

    This is for integration with async frameworks.

    Args:
        analysis_id: UUID of analysis to process

    Returns:
        True if successful, False otherwise
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, process_analysis_sync, analysis_id)
