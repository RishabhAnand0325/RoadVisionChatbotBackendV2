from fastapi import APIRouter
from app.modules.askai.endpoints import chats, documents

# This router consolidates all endpoints related to the "askai" feature.
router = APIRouter()

router.include_router(chats.router)
router.include_router(documents.router)
