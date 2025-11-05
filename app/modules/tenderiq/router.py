from fastapi import APIRouter

from app.modules.tenderiq.endpoints import tenders
from app.modules.tenderiq.analyze.router import router as analyze_router

router = APIRouter()

router.include_router(tenders.router)
router.include_router(analyze_router, prefix="/analyze", tags=["Analyze"])
