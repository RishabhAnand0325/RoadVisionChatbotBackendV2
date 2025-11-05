"""
Scope of Work Extraction Service

Extracts scope of work, deliverables, and effort estimation from tender documents.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository
from app.modules.tenderiq.analyze.models.pydantic_models import (
    ScopeOfWorkResponse,
    ScopeOfWorkDetailResponse,
    WorkItemResponse,
    DeliverableResponse,
    KeyDatesResponse,
)


class ScopeExtractionService:
    """Service for extracting scope of work from tender documents"""

    def __init__(self):
        pass

    def extract_scope(
        self,
        db: Session,
        analysis_id: UUID,
        tender_id: UUID,
    ) -> ScopeOfWorkResponse:
        """
        Extract scope of work from tender documents.

        Args:
            db: Database session
            analysis_id: Analysis record ID
            tender_id: Tender to analyze

        Returns:
            ScopeOfWorkResponse with extracted scope information
        """
        repo = AnalyzeRepository(db)

        # TODO: Fetch tender documents from ScrapedTender
        # TODO: Parse documents and extract scope of work using LLM

        # Sample scope data for demonstration
        sample_scope_text = """
        Design and implement a cloud-based document management system with:
        - User authentication and authorization
        - Document storage and versioning
        - Full-text search capability
        - Automated backup and disaster recovery
        - API for third-party integrations
        """

        # Extract work items, deliverables, and dates
        work_items = self.extract_work_items(sample_scope_text)
        deliverables = self.extract_deliverables(sample_scope_text)
        effort_estimate = self.estimate_effort(sample_scope_text, work_items)

        # Calculate key dates
        start_date = datetime.now()
        end_date = start_date + timedelta(days=effort_estimate["estimated_days"])

        key_dates = KeyDatesResponse(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )

        return ScopeOfWorkResponse(
            tender_id=tender_id,
            scope_of_work=ScopeOfWorkDetailResponse(
                description=sample_scope_text.strip(),
                work_items=work_items,
                key_deliverables=deliverables,
                estimated_total_effort=effort_estimate["estimated_days"],
                estimated_total_duration=effort_estimate["estimated_duration_text"],
                key_dates=key_dates,
            ),
            analyzed_at=datetime.utcnow(),
        )

    def extract_work_items(self, scope_text: str) -> List[WorkItemResponse]:
        """
        Extract individual work items from scope description.

        Args:
            scope_text: Scope of work text

        Returns:
            List of work items with descriptions and dependencies
        """
        if not scope_text:
            return []

        work_items = []

        # Parse bullet points and numbered items
        lines = scope_text.split("\n")
        item_descriptions = []

        for line in lines:
            line_clean = line.strip()
            # Check if line starts with bullet or number
            if line_clean.startswith("-") or line_clean.startswith("•"):
                item_desc = line_clean.lstrip("-•").strip()
                if item_desc:
                    item_descriptions.append(item_desc)
            elif line_clean and not line_clean.startswith(" "):
                # Might be a paragraph, split by common keywords
                if any(keyword in line_clean.lower() for keyword in ["and", "with", ","]):
                    parts = [p.strip() for p in line_clean.split(" and ") + line_clean.split(",")]
                    item_descriptions.extend([p for p in parts if len(p) > 5])

        # Create work items (limit to 5-7 items for clarity)
        complexity_levels = {"Authentication": "high", "Authorization": "high", "Search": "medium",
                            "Backup": "medium", "Integration": "high", "Storage": "medium"}

        for i, item_desc in enumerate(item_descriptions[:7]):
            # Estimate duration (in days)
            estimated_duration = self._estimate_item_duration(item_desc)

            work_items.append(
                WorkItemResponse(
                    id=None,  # Will be UUID in DB
                    description=item_desc,
                    estimated_duration=estimated_duration,
                    priority=self._determine_priority(i, len(item_descriptions)),
                    dependencies=[],
                )
            )

        return work_items

    def extract_deliverables(self, scope_text: str) -> List[DeliverableResponse]:
        """
        Extract key deliverables from scope description.

        Args:
            scope_text: Scope of work text

        Returns:
            List of deliverables with descriptions and dates
        """
        if not scope_text:
            return []

        deliverables = []

        # Common deliverable patterns
        deliverable_keywords = [
            "document", "report", "design", "specification", "manual",
            "code", "system", "framework", "API", "interface", "dashboard"
        ]

        text_lower = scope_text.lower()
        deliverable_list = []

        for keyword in deliverable_keywords:
            if keyword.lower() in text_lower:
                deliverable_list.append(f"{keyword.title()} Deliverable")

        # Add generic project deliverables
        base_deliverables = [
            "Technical Architecture Document",
            "System Implementation",
            "API Documentation",
            "User Guide and Training",
            "System Testing Report",
        ]

        for i, deliverable_name in enumerate(base_deliverables[:4]):
            # Calculate delivery date (spread over project timeline)
            delivery_offset_days = (i + 1) * 30

            deliverables.append(
                DeliverableResponse(
                    id=None,  # Will be UUID in DB
                    description=deliverable_name,
                    delivery_date=(datetime.now() + timedelta(days=delivery_offset_days)).strftime("%Y-%m-%d"),
                    acceptance_criteria=[
                        f"{deliverable_name} reviewed and approved",
                        "All requirements met",
                        "Quality standards met",
                    ],
                )
            )

        return deliverables

    def estimate_effort(
        self,
        scope_text: str,
        work_items: List[WorkItemResponse]
    ) -> dict:
        """
        Estimate total effort and duration for the scope.

        Args:
            scope_text: Scope description
            work_items: Identified work items

        Returns:
            Dict with estimated_days, estimated_duration_text, complexity_level
        """
        if not scope_text:
            return {
                "estimated_days": 30,
                "estimated_duration_text": "1 month",
                "complexity_level": "medium",
            }

        # Count complexity indicators
        high_complexity_keywords = [
            "integration", "migration", "architecture", "security",
            "performance", "scalability", "disaster recovery", "compliance"
        ]

        complexity_score = sum(
            scope_text.lower().count(keyword) for keyword in high_complexity_keywords
        )

        # Estimate based on scope length and complexity
        word_count = len(scope_text.split())
        item_count = len(work_items) if work_items else 1

        # Base estimate: 10 days per work item + complexity bonus
        base_days = item_count * 10
        complexity_bonus = complexity_score * 5

        estimated_days = base_days + complexity_bonus

        # Determine complexity level
        if complexity_score >= 3:
            complexity_level = "high"
        elif complexity_score >= 1:
            complexity_level = "medium"
        else:
            complexity_level = "low"

        # Format duration text
        if estimated_days > 180:
            duration_text = f"{estimated_days // 30} months"
        elif estimated_days > 30:
            duration_text = f"{estimated_days // 7} weeks"
        else:
            duration_text = f"{estimated_days} days"

        return {
            "estimated_days": min(estimated_days, 365),  # Cap at 1 year
            "estimated_duration_text": duration_text,
            "complexity_level": complexity_level,
        }

    # ==================== Helper Methods ====================

    def _estimate_item_duration(self, item_description: str) -> str:
        """Estimate duration for a single work item"""
        desc_lower = item_description.lower()

        # High effort keywords
        high_effort = ["complex", "integration", "security", "performance", "migration"]
        medium_effort = ["module", "component", "interface", "specification"]
        low_effort = ["documentation", "testing", "review"]

        if any(keyword in desc_lower for keyword in high_effort):
            return "3-4 weeks"
        elif any(keyword in desc_lower for keyword in medium_effort):
            return "2-3 weeks"
        elif any(keyword in desc_lower for keyword in low_effort):
            return "1-2 weeks"
        else:
            return "2-3 weeks"

    def _determine_priority(self, index: int, total_items: int) -> str:
        """Determine priority based on position (earlier items tend to be more critical)"""
        priority_ratio = index / max(total_items, 1)

        if priority_ratio < 0.33:
            return "high"
        elif priority_ratio < 0.66:
            return "medium"
        else:
            return "low"
