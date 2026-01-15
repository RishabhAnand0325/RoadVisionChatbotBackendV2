# app/modules/legaliq/router.py
from fastapi import APIRouter
from app.modules.legaliq.endpoints import endpoints

api_router = APIRouter()

api_router.include_router(
    endpoints.router, 
    prefix="/legaliq", 
    tags=["LegalIQ"]
)