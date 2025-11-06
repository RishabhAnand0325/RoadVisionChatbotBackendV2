"""
Main router for the TenderIQ analysis submodule.
"""
from fastapi import APIRouter
from .endpoints import endpoints

router = APIRouter()

# Include all endpoint routers from this submodule
router.include_router(endpoints.router)
