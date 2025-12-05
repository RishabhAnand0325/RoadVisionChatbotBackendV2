"""
Router for manual tender upload module.
"""
from fastapi import APIRouter
from app.modules.manual_tender_upload.endpoints.upload_endpoints import router as upload_router

router = APIRouter(prefix="/manual-tenders", tags=["manual-tenders"])

# Include upload endpoints
router.include_router(upload_router)
