from fastapi import APIRouter

from fastapi import APIRouter

from app.modules.tenderiq.endpoints import tenders

router = APIRouter()

router.include_router(tenders.router)
