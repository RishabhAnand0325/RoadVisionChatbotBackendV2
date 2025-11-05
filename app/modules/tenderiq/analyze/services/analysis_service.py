"""
Analysis Service - Orchestration layer for tender analysis.

Handles:
- Initiating async analysis
- Tracking analysis status
- Retrieving completed results
- Managing analysis lifecycle
"""

from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
import threading

from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository
from app.modules.tenderiq.analyze.db.schema import AnalysisStatusEnum
from app.modules.tenderiq.analyze.models.pydantic_models import (
    AnalysisInitiatedResponse,
    AnalysisStatusResponse,
    AnalysisResultsResponse,
    AnalysisListItemResponse,
    PaginationResponse,
    AnalysesListResponse,
)


class AnalysisService:
    """Service for orchestrating tender analysis operations"""

    def __init__(self):
        pass

    def initiate_analysis(
        self,
        db: Session,
        tender_id: UUID,
        user_id: UUID,
        analysis_type: str = "full",
        include_risk_assessment: bool = True,
        include_rfp_analysis: bool = True,
        include_scope_of_work: bool = True,
    ) -> AnalysisInitiatedResponse:
        """
        Initiate a new tender analysis.

        Returns 202 Accepted response with analysisId.
        Analysis will be processed asynchronously.

        Args:
            db: Database session
            tender_id: Tender to analyze
            user_id: User initiating analysis
            analysis_type: "full", "summary", or "risk-only"
            include_risk_assessment: Include risk analysis
            include_rfp_analysis: Include RFP analysis
            include_scope_of_work: Include scope analysis

        Returns:
            AnalysisInitiatedResponse with analysisId and status
        """
        repo = AnalyzeRepository(db)

        # Create analysis record in pending state
        analysis = repo.create_analysis(
            tender_id=tender_id,
            user_id=user_id,
            analysis_type=analysis_type,
            include_risk_assessment=include_risk_assessment,
            include_rfp_analysis=include_rfp_analysis,
            include_scope_of_work=include_scope_of_work,
        )

        # Start async task processing in background thread
        self._queue_analysis_processing(analysis.id)

        return AnalysisInitiatedResponse(
            analysis_id=analysis.id,
            tender_id=analysis.tender_id,
            status="pending",
            created_at=analysis.created_at,
            estimated_completion_time=30000,  # 30 seconds estimated
        )

    def get_analysis_status(
        self,
        db: Session,
        analysis_id: UUID,
        user_id: UUID,
    ) -> Optional[AnalysisStatusResponse]:
        """
        Get current status of an analysis.

        Args:
            db: Database session
            analysis_id: Analysis ID to check
            user_id: User checking status (for auth)

        Returns:
            AnalysisStatusResponse or None if not found/unauthorized
        """
        repo = AnalyzeRepository(db)
        analysis = repo.get_analysis_by_id(analysis_id)

        if not analysis or analysis.user_id != user_id:
            return None

        return AnalysisStatusResponse(
            analysis_id=analysis.id,
            tender_id=analysis.tender_id,
            status=analysis.status.value,
            progress=analysis.progress,
            current_step=analysis.current_step,
            error_message=analysis.error_message,
        )

    def get_analysis_results(
        self,
        db: Session,
        analysis_id: UUID,
        user_id: UUID,
    ) -> Optional[AnalysisResultsResponse]:
        """
        Get analysis results if completed.

        Args:
            db: Database session
            analysis_id: Analysis ID
            user_id: User requesting results (for auth)

        Returns:
            AnalysisResultsResponse if completed, None otherwise
        """
        repo = AnalyzeRepository(db)
        analysis = repo.get_analysis_by_id(analysis_id)

        if not analysis or analysis.user_id != user_id:
            return None

        # Check if analysis is completed
        if analysis.status != AnalysisStatusEnum.completed:
            return None

        # Check if results exist and haven't expired
        results = repo.get_analysis_results(analysis_id)
        if not results:
            # Results expired (410 Gone)
            return None

        # Build complete results response
        return AnalysisResultsResponse(
            analysis_id=analysis.id,
            tender_id=analysis.tender_id,
            status=analysis.status.value,
            results={
                "summary": results.summary_json or {},
                "riskAssessment": results.rfp_analysis_json or {},
                "rfpAnalysis": results.rfp_analysis_json or {},
                "scopeOfWork": results.scope_of_work_json or {},
                "onePager": results.one_pager_json or {},
            },
            completed_at=analysis.completed_at,
            processing_time_ms=analysis.processing_time_ms,
        )

    def list_user_analyses(
        self,
        db: Session,
        user_id: UUID,
        status: Optional[str] = None,
        tender_id: Optional[UUID] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> AnalysesListResponse:
        """
        Get paginated list of analyses for a user.

        Args:
            db: Database session
            user_id: User to list analyses for
            status: Optional status filter
            tender_id: Optional tender filter
            limit: Results per page (max 100)
            offset: Number of results to skip

        Returns:
            AnalysesListResponse with paginated results
        """
        repo = AnalyzeRepository(db)

        # Validate and clamp limit
        limit = min(limit, 100)

        # Convert status string to enum if provided
        status_enum = None
        if status:
            try:
                status_enum = AnalysisStatusEnum(status)
            except ValueError:
                status_enum = None

        # Get analyses
        analyses, total = repo.get_user_analyses(
            user_id=user_id,
            status=status_enum,
            tender_id=tender_id,
            limit=limit,
            offset=offset,
        )

        # Build response
        analyses_items = [
            AnalysisListItemResponse(
                analysis_id=a.id,
                tender_id=a.tender_id,
                tender_name=None,  # TODO: Join with ScrapedTender to get name
                status=a.status.value,
                created_at=a.created_at,
                completed_at=a.completed_at,
                processing_time_ms=a.processing_time_ms,
            )
            for a in analyses
        ]

        return AnalysesListResponse(
            analyses=analyses_items,
            pagination=PaginationResponse(
                total=total,
                limit=limit,
                offset=offset,
            ),
        )

    def delete_analysis(
        self,
        db: Session,
        analysis_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete an analysis record.

        Args:
            db: Database session
            analysis_id: Analysis to delete
            user_id: User deleting (must own analysis)

        Returns:
            True if deleted, False if not found or unauthorized
        """
        repo = AnalyzeRepository(db)
        return repo.delete_analysis(analysis_id, user_id)

    # ==================== Internal Methods for Async Processing ====================

    def _queue_analysis_processing(self, analysis_id: UUID) -> None:
        """
        Queue analysis for background processing.

        Currently uses a background thread. Can be upgraded to:
        - Celery for distributed task queue
        - RQ (Redis Queue) for job queue
        - APScheduler for scheduled processing

        Args:
            analysis_id: Analysis ID to process
        """
        # Import here to avoid circular imports
        from app.modules.tenderiq.analyze.tasks import process_analysis_sync

        # Run in background thread
        # In production, this should be a proper task queue (Celery, RQ, etc)
        thread = threading.Thread(
            target=process_analysis_sync,
            args=(analysis_id,),
            daemon=True,
            name=f"analysis-{analysis_id}",
        )
        thread.start()

    async def process_analysis(
        self,
        db: Session,
        analysis_id: UUID,
        # Services to be injected
        risk_service: "RiskAssessmentService" = None,
        rfp_service: "RFPExtractionService" = None,
        scope_service: "ScopeExtractionService" = None,
    ) -> bool:
        """
        Process analysis asynchronously.

        This method would be called by a task queue (Celery, etc).
        It orchestrates the various analysis services.

        Args:
            db: Database session
            analysis_id: Analysis to process
            risk_service: Risk assessment service
            rfp_service: RFP extraction service
            scope_service: Scope extraction service

        Returns:
            True if successful, False if failed
        """
        repo = AnalyzeRepository(db)

        analysis = repo.get_analysis_by_id(analysis_id)
        if not analysis:
            return False

        try:
            # Update status to processing
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=10,
                current_step="initializing",
            )

            # Step 1: Parse documents
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=20,
                current_step="parsing-documents",
            )
            # TODO: Extract text from documents

            # Step 2: Risk assessment
            if analysis.include_risk_assessment:
                repo.update_analysis_status(
                    analysis_id,
                    AnalysisStatusEnum.processing,
                    progress=40,
                    current_step="analyzing-risk",
                )
                # TODO: Call risk_service.assess_risks()

            # Step 3: RFP analysis
            if analysis.include_rfp_analysis:
                repo.update_analysis_status(
                    analysis_id,
                    AnalysisStatusEnum.processing,
                    progress=60,
                    current_step="extracting-rfp",
                )
                # TODO: Call rfp_service.extract_sections()

            # Step 4: Scope extraction
            if analysis.include_scope_of_work:
                repo.update_analysis_status(
                    analysis_id,
                    AnalysisStatusEnum.processing,
                    progress=80,
                    current_step="extracting-scope",
                )
                # TODO: Call scope_service.extract_scope()

            # Step 5: Generate summary
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=90,
                current_step="generating-summary",
            )
            # TODO: Generate summary

            # Mark as completed
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.completed,
                progress=100,
                current_step="completed",
            )

            return True

        except Exception as e:
            # Mark as failed
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.failed,
                error_message=str(e),
            )
            return False
