"""
Router configuration for the Analyze module.
Aggregates all endpoints and registers them with the API.
"""
from fastapi import APIRouter
from app.modules.analyze.endpoints.endpoints import router as analyze_router
from app.modules.analyze.endpoints.opportunity_ai_endpoints import router as opportunity_ai_router

# Create the main router for the analyze module
router = APIRouter()

# Include all analyze endpoints
router.include_router(analyze_router, tags=["analyze"])

# Include opportunity AI endpoints
router.include_router(opportunity_ai_router, tags=["analyze"])
