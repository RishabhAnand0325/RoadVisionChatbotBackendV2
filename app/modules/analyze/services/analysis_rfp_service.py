import json
from uuid import UUID
from sqlalchemy.orm import Session

from app.modules.analyze.models.pydantic_models import RFPSectionSchema, RFPSectionsResponseSchema, RFPSummarySchema
from app.modules.analyze.repositories import repository as analyze_repo


def get_rfp_sections(db: Session, analysis_id: UUID) -> RFPSectionsResponseSchema:
    analysis_rfp_sections = analyze_repo.get_rfp_sections(db, analysis_id)
    total_requirements = 0

    for section in analysis_rfp_sections:
        total_requirements += len(section.compliance_issues or [])
    rfp_summary = RFPSummarySchema(
        total_sections=len(analysis_rfp_sections),
        total_requirements=total_requirements
    )
    for section in analysis_rfp_sections:
        print(section.compliance_issues)

    return RFPSectionsResponseSchema(
        rfp_summary=rfp_summary,
        sections=[
            RFPSectionSchema(
                section_name=section.section_number or "",
                section_title=section.section_title or "",
                summary=section.summary or "",
                key_requirements=section.key_requirements or [],
                compliance_issues=[str(item) for item in section.compliance_issues] if section.compliance_issues else [],
                page_references=[
                    int(ref) if isinstance(ref, (int, float)) or (isinstance(ref, str) and ref.isdigit()) else 0
                    for ref in (section.page_references or [])
                ] if section.page_references else []
            ) for section in analysis_rfp_sections
        ]
    )
