from fastapi import APIRouter
from .endpoints import tenders
from .analyze.router import router as analyze_router

router = APIRouter()

router.include_router(tenders.router)
router.include_router(analyze_router, prefix="/analyze", tags=["TenderIQ - Analyze"])
