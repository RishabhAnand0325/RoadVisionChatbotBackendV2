from fastapi import APIRouter
from .endpoints import synopsis

router = APIRouter()

# Include the synopsis router with /synopsis prefix
router.include_router(synopsis.router)