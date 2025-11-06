"""
API endpoints for the TenderIQ analysis submodule.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db_session
from app.modules.auth.services.auth_service import get_current_active_user
from app.modules.auth.db.schema import User
from ..services.orchestrator_service import AnalysisOrchestratorService

router = APIRouter()

@router.get("/{tender_id}")
async def get_analysis_stream(
    tender_id: UUID,
    request: Request,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Initiates and streams the result of a tender analysis.

    This endpoint uses Server-Sent Events (SSE) to provide real-time updates.
    - If the analysis has never been run, it triggers a new background task.
    - If the analysis is already running, it streams the current progress.
    - If the analysis is complete, it streams the full result and closes.
    """
    orchestrator = AnalysisOrchestratorService(db)
    return await orchestrator.stream_analysis(tender_id, current_user.id, request)
