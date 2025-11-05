"""
RFP Extraction Service

Extracts and analyzes RFP (Request for Proposal) sections from tender documents.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository
from app.modules.tenderiq.analyze.models.pydantic_models import (
    RFPAnalysisResponse,
    RFPSectionResponse,
    RFPSectionSummaryResponse,
    RFPSectionComplianceResponse,
)


class RFPExtractionService:
    """Service for extracting and analyzing RFP sections"""

    def __init__(self):
        pass

    def extract_rfp_sections(
        self,
        db: Session,
        analysis_id: UUID,
        tender_id: UUID,
        section_number: Optional[str] = None,
        include_compliance: bool = False,
    ) -> RFPAnalysisResponse:
        """
        Extract RFP sections from tender documents.

        Args:
            db: Database session
            analysis_id: Analysis record ID
            tender_id: Tender to analyze
            section_number: Optional specific section to retrieve
            include_compliance: Include compliance assessment

        Returns:
            RFPAnalysisResponse with extracted sections
        """
        repo = AnalyzeRepository(db)

        # TODO: Fetch tender documents from ScrapedTender
        # TODO: Parse documents and extract RFP sections using LLM

        # Sample RFP sections for demonstration
        sample_sections = [
            {
                "number": "1.0",
                "title": "Eligibility Criteria",
                "description": "Vendor must be registered and in good standing for minimum 3 years",
                "requirements": [
                    "Valid business registration",
                    "Minimum 3 years operational history",
                    "No pending litigation",
                    "GST registration",
                ],
                "complexity": "low",
            },
            {
                "number": "2.0",
                "title": "Technical Requirements",
                "description": "Technical specifications for proposed solution and resources",
                "requirements": [
                    "System architecture design",
                    "Technology stack specification",
                    "Disaster recovery plan",
                    "Security framework",
                    "Performance benchmarks",
                ],
                "complexity": "high",
            },
            {
                "number": "3.0",
                "title": "Commercial Terms",
                "description": "Pricing and commercial conditions",
                "requirements": [
                    "Detailed price quotation",
                    "Payment terms (Net 30)",
                    "Warranty period (12 months)",
                    "Service level agreement",
                ],
                "complexity": "medium",
            },
        ]

        # Create RFP section records
        created_sections = []
        criticality_counts = {"high": 0, "medium": 0, "low": 0}

        for section_data in sample_sections:
            # Determine criticality
            if section_data["complexity"] == "high":
                criticality = "high"
                criticality_counts["high"] += 1
            elif section_data["complexity"] == "medium":
                criticality = "medium"
                criticality_counts["medium"] += 1
            else:
                criticality = "low"
                criticality_counts["low"] += 1

            section = repo.create_rfp_section(
                analysis_id=analysis_id,
                section_number=section_data["number"],
                title=section_data["title"],
                description=section_data["description"],
                key_requirements=section_data["requirements"],
                estimated_complexity=section_data["complexity"],
                compliance_status="requires-review" if include_compliance else None,
                related_sections=self._find_related_sections(section_data["number"]),
                document_references=[],
            )
            created_sections.append(section)

        # Build response
        section_responses = []
        for section in created_sections:
            # Only include requested section if specified
            if section_number and section.section_number != section_number:
                continue

            compliance = None
            if include_compliance:
                compliance = RFPSectionComplianceResponse(
                    status=section.compliance_status or "requires-review",
                    issues=section.compliance_issues,
                )

            section_responses.append(
                RFPSectionResponse(
                    id=section.id,
                    number=section.section_number,
                    title=section.title,
                    description=section.description,
                    key_requirements=section.key_requirements,
                    compliance=compliance,
                    estimated_complexity=section.estimated_complexity,
                    related_sections=section.related_sections,
                )
            )

        total_requirements = sum(len(s.key_requirements) for s in created_sections)

        return RFPAnalysisResponse(
            tender_id=tender_id,
            total_sections=len(created_sections),
            sections=section_responses,
            summary=RFPSectionSummaryResponse(
                total_requirements=total_requirements,
                criticality=criticality_counts,
            ),
        )

    def identify_requirements(self, section_text: str) -> List[str]:
        """
        Extract key requirements from an RFP section.

        Uses sentence-based parsing. TODO: Upgrade to LLM-based extraction.

        Args:
            section_text: Text of the RFP section

        Returns:
            List of identified requirements
        """
        if not section_text:
            return []

        requirements = []

        # Split by common requirement keywords
        requirement_keywords = ["must", "shall", "required", "should", "need", "provide"]
        sentences = section_text.split(".")

        for sentence in sentences:
            sentence_clean = sentence.strip()
            if any(keyword in sentence_clean.lower() for keyword in requirement_keywords):
                if len(sentence_clean) > 10:  # Filter out very short strings
                    requirements.append(sentence_clean)

        # Remove duplicates while preserving order
        seen = set()
        unique_requirements = []
        for req in requirements:
            if req not in seen:
                seen.add(req)
                unique_requirements.append(req)

        return unique_requirements[:10]  # Return top 10 requirements

    def assess_section_complexity(self, section_text: str) -> str:
        """
        Estimate complexity of an RFP section (low/medium/high).

        Uses heuristics based on section length and keywords.

        Args:
            section_text: Text of the RFP section

        Returns:
            Complexity level: "low", "medium", or "high"
        """
        if not section_text:
            return "medium"

        text_lower = section_text.lower()

        # High complexity indicators
        high_complexity_keywords = [
            "architecture", "implementation", "security", "performance",
            "integration", "compliance", "regulation", "technical",
            "infrastructure", "enterprise", "scalability", "recovery"
        ]

        # Low complexity indicators
        low_complexity_keywords = [
            "basic", "simple", "standard", "general", "eligibility",
            "registration", "name", "address", "contact"
        ]

        high_score = sum(text_lower.count(keyword) for keyword in high_complexity_keywords)
        low_score = sum(text_lower.count(keyword) for keyword in low_complexity_keywords)
        word_count = len(section_text.split())

        # Calculate complexity
        if high_score > low_score and word_count > 200:
            return "high"
        elif low_score > high_score or word_count < 100:
            return "low"
        else:
            return "medium"

    def identify_missing_documents(
        self,
        sections: List[dict],
        provided_documents: List[str]
    ) -> List[str]:
        """
        Identify documents referenced in RFP but not provided.

        Args:
            sections: RFP sections with requirements
            provided_documents: List of document names provided

        Returns:
            List of missing document names
        """
        if not sections:
            return []

        document_keywords = [
            "document", "certificate", "letter", "report", "statement",
            "plan", "proposal", "specification", "design", "drawing"
        ]

        mentioned_documents = set()
        provided_lower = [doc.lower() for doc in provided_documents]

        for section in sections:
            description = section.get("description", "").lower()
            requirements = [req.lower() for req in section.get("requirements", [])]

            # Search for document references
            all_text = " ".join([description] + requirements)

            for keyword in document_keywords:
                if keyword in all_text:
                    # Extract document type (e.g., "Technical Document", "Audit Report")
                    words = all_text.split()
                    for i, word in enumerate(words):
                        if keyword in word.lower() and i > 0:
                            doc_name = " ".join(words[max(0, i-2):i+1])
                            mentioned_documents.add(doc_name)

        # Find missing documents
        missing = []
        for doc in mentioned_documents:
            if not any(doc.lower() in prov.lower() or prov.lower() in doc.lower()
                      for prov in provided_lower):
                missing.append(doc)

        return list(missing)[:5]  # Return top 5 missing documents

    # ==================== Helper Methods ====================

    def _find_related_sections(self, section_number: str) -> List[str]:
        """Find related section numbers"""
        # In a real implementation, would use semantic analysis
        # For now, return sections with adjacent numbers
        try:
            num = float(section_number)
            related = [
                str(num + 0.1),
                str(num + 1.0),
            ]
            return [r for r in related if r != section_number]
        except ValueError:
            return []
