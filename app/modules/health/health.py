from fastapi import APIRouter
from app.modules.health.models.health import HealthResponse
from app.utils import get_consistent_timestamp
from app.core.services import pdf_processor

router = APIRouter()

@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "timestamp": get_consistent_timestamp(),
        "llamaparse": "available" if pdf_processor.has_llamaparse else "unavailable"
    }
