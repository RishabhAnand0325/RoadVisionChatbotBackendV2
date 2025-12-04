from fastapi import APIRouter
from app.modules.dashboard.endpoints import endpoints

router = APIRouter()

router.include_router(endpoints.router)
