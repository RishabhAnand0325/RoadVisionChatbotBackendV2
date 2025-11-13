from fastapi import APIRouter
from app.modules.health import health
from app.modules.askai.router import router as askai_router
from app.modules.auth.route import router as auth_router
from app.modules.tenderiq.router import router as tenderiq_router
from app.modules.dmsiq.route import router as dmsiq_router
from app.modules.bidsynopsis.router import router as bidsynopsis_router
from app.modules.analyze.router import router as analyze_router

api_v1_router = APIRouter()

# General v1 endpoints
api_v1_router.include_router(health.router)

# Feature module routers
api_v1_router.include_router(auth_router, prefix="/auth")
api_v1_router.include_router(askai_router, prefix="/askai")
api_v1_router.include_router(tenderiq_router, prefix="/tenderiq")
api_v1_router.include_router(dmsiq_router, prefix="/dms", tags=["DMS"])
api_v1_router.include_router(bidsynopsis_router, prefix="/bidsynopsis", tags=["Bid Synopsis"])
api_v1_router.include_router(analyze_router, prefix="/analyze", tags=["Analyze"])


# In the future, you can add other module routers here:
# from app.modules.dashboard.router import router as dashboard_router
# api_v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
