"""
DMS Module Router
Aggregates all DMS endpoints into a single router.
"""

from fastapi import APIRouter
from .endpoints import endpoints

router = APIRouter()
router.include_router(endpoints.router)
