from fastapi import APIRouter
from .endpoints import tenders

router = APIRouter()

router.include_router(tenders.router)
