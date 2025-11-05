"""
Risk Assessment Service

Analyzes tender documents for risks and generates risk reports.
"""

from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository
from app.modules.tenderiq.analyze.db.schema import RiskLevelEnum, RiskCategoryEnum
from app.modules.tenderiq.analyze.models.pydantic_models import (
    RiskAssessmentResponse,
    RiskDetailResponse,
)


class RiskAssessmentService:
    """Service for risk assessment of tenders"""

    def __init__(self):
        pass

    def assess_risks(
        self,
        db: Session,
        analysis_id: UUID,
        tender_id: UUID,
        depth: str = "summary",
        include_historical: bool = False,
    ) -> RiskAssessmentResponse:
        """
        Perform risk assessment on a tender.

        Args:
            db: Database session
            analysis_id: Analysis record ID
            tender_id: Tender to assess
            depth: "summary" or "detailed"
            include_historical: Include historical risk data

        Returns:
            RiskAssessmentResponse with identified risks
        """
        repo = AnalyzeRepository(db)

        # TODO: Fetch tender documents from ScrapedTender
        # TODO: Extract text from documents
        # TODO: Analyze text for risks using LLM

        # For now, sample risk data to demonstrate structure
        sample_risks = [
            {
                "title": "Tight Deadline",
                "description": "Bid submission deadline is only 30 days away",
                "category": "operational",
                "impact": "high",
                "likelihood": "high",
            },
            {
                "title": "Complex Requirements",
                "description": "RFP contains 45+ requirements with interdependencies",
                "category": "operational",
                "impact": "high",
                "likelihood": "medium",
            },
            {
                "title": "Financial Constraints",
                "description": "Tender value may not cover all project costs",
                "category": "financial",
                "impact": "medium",
                "likelihood": "low",
            },
        ]

        # Create risk records in database
        created_risks = []
        for risk_data in sample_risks:
            risk = repo.create_risk(
                analysis_id=analysis_id,
                level=self._determine_risk_level(risk_data["impact"], risk_data["likelihood"]),
                category=self.categorize_risk(risk_data["description"]),
                title=risk_data["title"],
                description=risk_data["description"],
                impact=risk_data["impact"],
                likelihood=risk_data["likelihood"],
                mitigation_strategy=self.generate_mitigations(risk_data["description"]),
                recommended_action=self._get_recommended_action(risk_data["title"]),
            )
            created_risks.append(risk)

        # Calculate overall risk score
        risk_score = self.calculate_risk_score([r.__dict__ for r in created_risks])
        overall_level = self._score_to_level(risk_score)

        # Build response
        risk_details = [
            RiskDetailResponse(
                id=r.id,
                level=r.level.value,
                category=r.category.value,
                title=r.title,
                description=r.description,
                impact=r.impact,
                likelihood=r.likelihood,
                mitigation_strategy=r.mitigation_strategy,
                recommended_action=r.recommended_action,
                related_documents=r.related_documents,
            )
            for r in created_risks
        ]

        return RiskAssessmentResponse(
            tender_id=tender_id,
            overall_risk_level=overall_level,
            risk_score=risk_score,
            executive_summary=self._generate_executive_summary(created_risks, risk_score),
            risks=risk_details,
            analyzed_at=datetime.utcnow(),
        )

    def categorize_risk(self, risk_description: str) -> str:
        """
        Categorize a risk into one of: regulatory, financial, operational, contractual, market

        Uses keyword matching for now. TODO: Upgrade to LLM-based categorization.

        Args:
            risk_description: Description of the risk

        Returns:
            Risk category string
        """
        description_lower = risk_description.lower()

        # Keyword-based categorization (can be upgraded to LLM)
        category_keywords = {
            "regulatory": ["compliance", "legal", "regulation", "statute", "license", "permit", "approval"],
            "financial": ["cost", "budget", "price", "value", "payment", "cash flow", "revenue", "expense"],
            "operational": ["timeline", "deadline", "resource", "capacity", "schedule", "delivery", "performance"],
            "contractual": ["liability", "obligation", "penalty", "clause", "terms", "conditions", "agreement"],
            "market": ["competition", "demand", "supply", "price volatility", "market", "customer", "risk"],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in description_lower for keyword in keywords):
                return category

        # Default to operational if no match
        return "operational"

    def calculate_risk_score(self, risks: List[dict]) -> int:
        """
        Calculate overall risk score (0-100) from identified risks.

        Weighted by level and likelihood:
        - Critical + High likelihood = 10 points
        - High + Medium likelihood = 6 points
        - etc.

        Args:
            risks: List of identified risks

        Returns:
            Risk score from 0-100
        """
        if not risks:
            return 0

        level_scores = {
            "critical": 10,
            "high": 6,
            "medium": 3,
            "low": 1,
        }

        likelihood_multipliers = {
            "high": 1.0,
            "medium": 0.7,
            "low": 0.4,
        }

        total_score = 0
        for risk in risks:
            level = risk.get("level", "medium").lower() if isinstance(risk.get("level"), str) else "medium"
            likelihood = risk.get("likelihood", "medium").lower() if isinstance(risk.get("likelihood"), str) else "medium"

            # Get scores with defaults
            level_score = level_scores.get(level, 3)
            likelihood_mult = likelihood_multipliers.get(likelihood, 0.7)

            total_score += level_score * likelihood_mult

        # Normalize to 0-100 range
        # Max score = 10 risks * 10 points * 1.0 = 100
        # But cap at 100
        return min(int(total_score * 10), 100)

    def generate_mitigations(self, risk_description: str) -> str:
        """
        Generate mitigation strategies for a risk.

        TODO: Use LLM to generate better mitigations.

        Args:
            risk_description: Description of the risk

        Returns:
            Suggested mitigation strategy
        """
        description_lower = risk_description.lower()

        # Template-based mitigations (can be upgraded to LLM)
        if "deadline" in description_lower or "timeline" in description_lower:
            return "Establish internal project milestones, allocate dedicated team, prioritize critical tasks"
        elif "cost" in description_lower or "budget" in description_lower or "price" in description_lower:
            return "Conduct detailed cost analysis, identify cost-saving opportunities, negotiate better rates with suppliers"
        elif "requirement" in description_lower or "complexity" in description_lower:
            return "Break down complex requirements into smaller components, conduct feasibility study, allocate expert resources"
        elif "compliance" in description_lower or "legal" in description_lower:
            return "Engage legal counsel, ensure full understanding of regulations, establish compliance tracking mechanisms"
        elif "resource" in description_lower or "capacity" in description_lower:
            return "Assess resource availability, consider outsourcing, hire additional staff if needed"
        else:
            return "Conduct further analysis, engage subject matter experts, develop contingency plans"

    # ==================== Helper Methods ====================

    def _determine_risk_level(self, impact: str, likelihood: str) -> str:
        """
        Determine risk level based on impact and likelihood.

        Matrix:
        - High impact + High likelihood = Critical
        - High impact + Medium likelihood = High
        - etc.
        """
        impact_score = {"high": 3, "medium": 2, "low": 1}.get(impact.lower(), 2)
        likelihood_score = {"high": 3, "medium": 2, "low": 1}.get(likelihood.lower(), 2)

        combined_score = impact_score * likelihood_score

        if combined_score >= 8:
            return "critical"
        elif combined_score >= 5:
            return "high"
        elif combined_score >= 3:
            return "medium"
        else:
            return "low"

    def _score_to_level(self, score: int) -> str:
        """Convert numeric score to risk level"""
        if score >= 75:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 25:
            return "medium"
        else:
            return "low"

    def _generate_executive_summary(self, risks: List, risk_score: int) -> str:
        """Generate executive summary of risks"""
        if not risks:
            return "No significant risks identified in tender analysis."

        risk_counts = {}
        for risk in risks:
            level = risk.level.value if hasattr(risk.level, 'value') else str(risk.level)
            risk_counts[level] = risk_counts.get(level, 0) + 1

        summary_parts = [f"Risk score: {risk_score}/100. "]

        if risk_counts.get("critical", 0) > 0:
            summary_parts.append(f"{risk_counts['critical']} critical risk(s) identified that require immediate attention. ")
        if risk_counts.get("high", 0) > 0:
            summary_parts.append(f"{risk_counts['high']} high risk(s) identified. ")

        summary_parts.append("Refer to detailed risk list for mitigation strategies.")

        return "".join(summary_parts)

    def _get_recommended_action(self, risk_title: str) -> str:
        """Get recommended action for specific risk"""
        title_lower = risk_title.lower()

        actions = {
            "deadline": "Immediately establish project timeline and resource allocation plan",
            "complex": "Conduct comprehensive requirements analysis and feasibility study",
            "cost": "Perform detailed cost estimation and budget planning",
            "resource": "Assess team capacity and hire or outsource as needed",
            "compliance": "Engage legal and compliance team to review requirements",
            "financial": "Review financial viability and secure adequate funding",
        }

        for keyword, action in actions.items():
            if keyword in title_lower:
                return action

        return "Establish risk monitoring and mitigation plan"
