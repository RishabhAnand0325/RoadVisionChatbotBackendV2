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
from app.modules.tenderiq.analyze.services.risk_assessment_service import RiskAssessmentService
from app.modules.tenderiq.analyze.services.rfp_extraction_service import RFPExtractionService
from app.modules.tenderiq.analyze.services.scope_extraction_service import ScopeExtractionService
from app.modules.tenderiq.analyze.services.report_generation_service import ReportGenerationService

logger = logging.getLogger(__name__)


class AnalysisTaskProcessor:
    """Processes tender analysis tasks asynchronously"""

    def __init__(self):
        self.risk_service = RiskAssessmentService()
        self.rfp_service = RFPExtractionService()
        self.scope_service = ScopeExtractionService()
        self.report_service = ReportGenerationService()

    def process_analysis(self, analysis_id: UUID) -> bool:
        """
        Process a tender analysis end-to-end.

        This method orchestrates all analysis services:
        1. Risk assessment
        2. RFP section extraction
        3. Scope of work extraction
        4. Report generation

        Args:
            analysis_id: UUID of the analysis to process

        Returns:
            True if successful, False if failed
        """
        db = SessionLocal()
        repo = AnalyzeRepository(db)

        try:
            # Get the analysis record
            analysis = repo.get_analysis_by_id(analysis_id)
            if not analysis:
                logger.error(f"Analysis not found: {analysis_id}")
                return False

            logger.info(f"Starting analysis: {analysis_id}")

            # Update status to processing
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=10,
                current_step="initializing",
            )

            # Step 1: Risk Assessment (10-40%)
            if analysis.include_risk_assessment:
                logger.info(f"Step 1: Risk assessment for {analysis_id}")
                repo.update_analysis_status(
                    analysis_id,
                    AnalysisStatusEnum.processing,
                    progress=20,
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
                    logger.error(f"❌ Risk assessment failed: {e}")
                    # Continue with other analyses even if risk fails

            # Step 2: RFP Analysis (40-60%)
            if analysis.include_rfp_analysis:
                logger.info(f"Step 2: RFP extraction for {analysis_id}")
                repo.update_analysis_status(
                    analysis_id,
                    AnalysisStatusEnum.processing,
                    progress=40,
                    current_step="extracting-rfp",
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
                    logger.error(f"❌ RFP extraction failed: {e}")

            # Step 3: Scope Extraction (60-80%)
            if analysis.include_scope_of_work:
                logger.info(f"Step 3: Scope extraction for {analysis_id}")
                repo.update_analysis_status(
                    analysis_id,
                    AnalysisStatusEnum.processing,
                    progress=60,
                    current_step="extracting-scope",
                )

                try:
                    scope_response = self.scope_service.extract_scope(
                        db=db,
                        analysis_id=analysis_id,
                        tender_id=analysis.tender_id,
                    )
                    logger.info(f"✅ Scope extraction completed: effort={scope_response.scope_of_work.estimated_total_effort}d")
                except Exception as e:
                    logger.error(f"❌ Scope extraction failed: {e}")

            # Step 4: Summary Generation (80-95%)
            logger.info(f"Step 4: Summary generation for {analysis_id}")
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=80,
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
                logger.error(f"❌ Summary generation failed: {e}")

            # Mark as completed (95-100%)
            logger.info(f"Analysis completed: {analysis_id}")
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
