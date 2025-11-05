"""
Analysis Service - Orchestration layer for tender analysis.

Handles:
- Initiating async analysis
- Tracking analysis status
- Retrieving completed results
- Managing analysis lifecycle
"""

import os
import asyncio
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
import threading

from app.modules.tenderiq.db.repository import AnalyzeRepository
from app.modules.tenderiq.db.schema import AnalysisStatusEnum
from app.modules.tenderiq.models.pydantic_models import (
    AnalysisInitiatedResponse,
    AnalysisStatusResponse,
    AnalysisResultsResponse,
    AnalysisListItemResponse,
    PaginationResponse,
    AnalysesListResponse,
)
from app.modules.tenderiq.db.tenderiq_repository import TenderIQRepository
from app.modules.tenderiq.services.document_parser import DocumentParser
from app.modules.tenderiq.services.tender_info_extractor import TenderInfoExtractor
from app.modules.tenderiq.services.onepager_generator import OnePagerGenerator
from app.modules.tenderiq.services.scope_work_analyzer import ScopeOfWorkAnalyzer
from app.modules.tenderiq.services.rfp_section_analyzer import RFPSectionAnalyzer
from app.modules.tenderiq.services.advanced_intelligence import (
    SWOTAnalyzer,
    BidDecisionRecommender,
    EnhancedRiskEngine,
)
from app.modules.tenderiq.services.quality_indicators import (
    QualityIndicatorsService,
    AnalysisMetadata,
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
        summary_data = results.summary_json or {}
        risk_assessment_data = summary_data.get("advanced_intelligence", {}).get("risk_assessment", {})

        return AnalysisResultsResponse(
            analysis_id=analysis.id,
            tender_id=analysis.tender_id,
            status=analysis.status.value,
            results={
                "summary": summary_data,
                "riskAssessment": risk_assessment_data,
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
        from app.modules.tenderiq.tasks import process_analysis_sync

        # Run in background thread
        # In production, this should be a proper task queue (Celery, RQ, etc)
        thread = threading.Thread(
            target=process_analysis_sync,
            args=(analysis_id,),
            daemon=True,
            name=f"analysis-{analysis_id}",
        )
        thread.start()

    async def process_analysis(self, db: Session, analysis_id: UUID) -> bool:
        """
        Process a tender analysis end-to-end with all Phase 1-5 services.

        This method is called by a background task worker. It orchestrates
        the entire analysis pipeline from document parsing to quality assessment.

        Args:
            db: Database session
            analysis_id: The ID of the analysis to process

        Returns:
            True if successful, False otherwise
        """
        repo = AnalyzeRepository(db)
        tender_repo = TenderIQRepository(db)
        start_time = datetime.utcnow()

        analysis = repo.get_analysis_by_id(analysis_id)
        if not analysis:
            return False

        try:
            # === Initialization ===
            repo.update_analysis_status(
                analysis_id,
                AnalysisStatusEnum.processing,
                progress=5,
                current_step="initializing",
            )
            tender = tender_repo.get_tender_by_id(analysis.tender_id)
            if not tender:
                raise ValueError(f"Tender with ID {analysis.tender_id} not found.")

            # Instantiate services
            doc_parser = DocumentParser()
            tender_info_extractor = TenderInfoExtractor()
            onepager_generator = OnePagerGenerator()
            scope_analyzer = ScopeOfWorkAnalyzer()
            rfp_analyzer = RFPSectionAnalyzer()
            swot_analyzer = SWOTAnalyzer()
            risk_engine = EnhancedRiskEngine()
            bid_recommender = BidDecisionRecommender()
            quality_service = QualityIndicatorsService()

            # === Phase 1: Document Parsing ===
            repo.update_analysis_status(
                analysis_id, AnalysisStatusEnum.processing, progress=10, current_step="parsing-documents"
            )
            if not tender.files:
                raise ValueError("No documents found for this tender to analyze.")
            
            document_to_parse = tender.files[0]
            file_path = document_to_parse.dms_path
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Document file not found at path: {file_path}")

            extraction_result = await doc_parser.parse_document(
                db=db, analysis_id=analysis_id, file_path=file_path, file_size=os.path.getsize(file_path)
            )
            raw_text = extraction_result.raw_text

            # === Phase 2: Tender Info Extraction ===
            repo.update_analysis_status(
                analysis_id, AnalysisStatusEnum.processing, progress=20, current_step="extracting-tender-info"
            )
            tender_info = await tender_info_extractor.extract_tender_info(
                db=db, analysis_id=analysis_id, raw_text=raw_text
            )

            # === Phase 3: Core Analysis (run in parallel) ===
            repo.update_analysis_status(
                analysis_id, AnalysisStatusEnum.processing, progress=30, current_step="core-analysis"
            )
            onepager_task = onepager_generator.generate_onepager(
                db=db, analysis_id=analysis_id, raw_text=raw_text, extracted_tender_info=tender_info.model_dump()
            )
            scope_task = scope_analyzer.analyze_scope(
                db=db, analysis_id=analysis_id, raw_text=raw_text
            )
            rfp_task = rfp_analyzer.analyze_rfp_sections(
                db=db, analysis_id=analysis_id, raw_text=raw_text
            )
            onepager_data, scope_data, rfp_data = await asyncio.gather(onepager_task, scope_task, rfp_task)

            # === Phase 4: Advanced Intelligence (run in parallel) ===
            repo.update_analysis_status(
                analysis_id, AnalysisStatusEnum.processing, progress=60, current_step="advanced-intelligence"
            )
            financial_info = await tender_info_extractor.extract_financial_info(raw_text=raw_text)
            
            swot_task = swot_analyzer.analyze_swot(
                tender_info=tender_info.model_dump(), scope_data=scope_data, financials=financial_info.model_dump()
            )
            risk_task = risk_engine.assess_risks(
                tender_info=tender_info.model_dump(), scope_data=scope_data, financials=financial_info.model_dump()
            )
            swot_analysis, risk_assessment = await asyncio.gather(swot_task, risk_task)

            bid_recommendation = await bid_recommender.recommend_bid_decision(
                tender_info=tender_info.model_dump(), scope_data=scope_data, financials=financial_info.model_dump(),
                risk_level=risk_assessment.get("risk_level", "medium"), swot=swot_analysis
            )

            # === Phase 5: Quality Assessment and Saving Results ===
            repo.update_analysis_status(
                analysis_id, AnalysisStatusEnum.processing, progress=90, current_step="finalizing"
            )
            
            all_extraction_results = {
                "raw_text": bool(raw_text), "tender_info": tender_info.model_dump(), "onepager_data": onepager_data.model_dump(),
                "scope_data": scope_data, "rfp_data": rfp_data, "swot_analysis": swot_analysis,
                "risk_assessment": risk_assessment, "bid_recommendation": bid_recommendation
            }
            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            quality_assessment = quality_service.assess_analysis_quality(
                analysis_data={}, extraction_results=all_extraction_results,
                processing_metadata={"processing_time_ms": processing_time_ms, "errors": []}
            )

            metadata = quality_service.create_metadata(analysis.id, analysis.tender_id)
            metadata.completed_at = end_time.isoformat()
            metadata.processing_time_ms = processing_time_ms

            # Store results in the database
            repo.create_or_update_analysis_results(
                analysis_id=analysis_id,
                summary={
                    "tender_info": tender_info.model_dump(),
                    "advanced_intelligence": {
                        "swot_analysis": swot_analysis,
                        "risk_assessment": risk_assessment,
                        "bid_recommendation": bid_recommendation,
                    },
                    "quality_metrics": quality_assessment,
                    "metadata": metadata.to_dict(),
                },
                rfp=rfp_data,
                scope=scope_data,
                one_pager=onepager_data.model_dump(),
            )

            # === Mark as completed ===
            repo.update_analysis_status(
                analysis_id, AnalysisStatusEnum.completed, progress=100, current_step="completed"
            )
            return True

        except Exception as e:
            repo.update_analysis_status(
                analysis_id, AnalysisStatusEnum.failed, error_message=str(e)
            )
            return False
