"""
Dependency injection for DMS module.
Provides FastAPI dependencies for DMS services.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db_session
from app.modules.dmsiq.services.dms_service import DmsService


def get_dms_service(db: Session = Depends(get_db_session)) -> DmsService:
    """Dependency to get DMS service instance."""
    return DmsService(db)
