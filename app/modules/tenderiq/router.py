from fastapi import APIRouter
from .endpoints import tenders, corrigendum

router = APIRouter()

router.include_router(tenders.router)
router.include_router(corrigendum.router)
