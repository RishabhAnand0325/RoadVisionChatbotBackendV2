from fastapi import APIRouter
from .endpoints import endpoints

router = APIRouter()
router.include_router(endpoints.router)
