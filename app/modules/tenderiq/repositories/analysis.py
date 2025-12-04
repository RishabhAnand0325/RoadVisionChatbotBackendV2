
from typing import Optional
from uuid import UUID
from sqlalchemy import Row
from sqlalchemy.orm import Session

from app.modules.analyze.db.schema import TenderAnalysis


def get_analysis_data(db: Session, tender_id: str) -> Optional[TenderAnalysis]:
    return (
        db.query(TenderAnalysis)
        .filter(TenderAnalysis.tender_id == tender_id)
        .first()
    )
