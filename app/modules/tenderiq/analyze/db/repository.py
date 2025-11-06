"""
Repository for TenderIQ analysis data access operations.
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session, joinedload

from .schema import TenderAnalysis

class AnalyzeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_tender_id(self, tender_id: UUID) -> Optional[TenderAnalysis]:
        """
        Retrieves a tender analysis record by the tender_id,
        eagerly loading related data.
        """
        return (
            self.db.query(TenderAnalysis)
            .filter_by(tender_id=tender_id)
            .options(
                joinedload(TenderAnalysis.rfp_sections),
                joinedload(TenderAnalysis.document_templates)
            )
            .first()
        )

    def get_by_id(self, analysis_id: UUID) -> Optional[TenderAnalysis]:
        """Retrieves a tender analysis record by its own ID."""
        return self.db.query(TenderAnalysis).filter_by(id=analysis_id).first()

    def create_for_tender(self, tender_id: UUID, user_id: UUID) -> TenderAnalysis:
        """
        Creates a new, pending tender analysis record for a given tender.
        """
        analysis = TenderAnalysis(tender_id=tender_id, user_id=user_id)
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def update(self, analysis: TenderAnalysis, updates: dict) -> TenderAnalysis:
        """
        Updates a TenderAnalysis instance with a dictionary of changes.
        """
        for key, value in updates.items():
            setattr(analysis, key, value)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis
