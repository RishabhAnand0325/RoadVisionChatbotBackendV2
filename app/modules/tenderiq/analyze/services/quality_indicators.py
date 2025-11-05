"""
Quality Indicators and Metadata Service (Phase 5).

Provides comprehensive quality assessment, confidence scoring, and metadata tracking
for tender analysis results.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

logger = logging.getLogger(__name__)


class QualityLevel(str, Enum):
    """Quality assessment levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class ConfidenceLevel(str, Enum):
    """Confidence score levels"""
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class QualityIndicator:
    """Individual quality indicator"""

    def __init__(
        self,
        name: str,
        score: float,
        weight: float = 1.0,
        description: str = "",
        issues: Optional[List[str]] = None,
    ):
        self.name = name
        self.score = max(0, min(100, score))  # Clamp to 0-100
        self.weight = weight
        self.description = description
        self.issues = issues or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "score": self.score,
            "weight": self.weight,
            "description": self.description,
            "issues": self.issues,
        }


class QualityAssessment:
    """Comprehensive quality assessment for analysis"""

    def __init__(self):
        self.indicators: List[QualityIndicator] = []
        self.overall_score: float = 0.0
        self.quality_level: QualityLevel = QualityLevel.FAIR
        self.assessment_timestamp = datetime.utcnow().isoformat()

    def add_indicator(self, indicator: QualityIndicator):
        """Add a quality indicator"""
        self.indicators.append(indicator)
        self._recalculate()

    def _recalculate(self):
        """Recalculate overall quality score"""
        if not self.indicators:
            self.overall_score = 0.0
            self.quality_level = QualityLevel.POOR
            return

        total_weight = sum(ind.weight for ind in self.indicators)
        if total_weight == 0:
            self.overall_score = 0.0
            self.quality_level = QualityLevel.POOR
            return

        weighted_sum = sum(ind.score * ind.weight for ind in self.indicators)
        self.overall_score = weighted_sum / total_weight

        # Determine quality level
        if self.overall_score >= 90:
            self.quality_level = QualityLevel.EXCELLENT
        elif self.overall_score >= 75:
            self.quality_level = QualityLevel.GOOD
        elif self.overall_score >= 60:
            self.quality_level = QualityLevel.FAIR
        else:
            self.quality_level = QualityLevel.POOR

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "overall_score": self.overall_score,
            "quality_level": self.quality_level.value,
            "indicators": [ind.to_dict() for ind in self.indicators],
            "assessment_timestamp": self.assessment_timestamp,
        }


class AnalysisMetadata:
    """Metadata tracking for analysis"""

    def __init__(self, analysis_id: UUID, tender_id: UUID):
        self.analysis_id = analysis_id
        self.tender_id = tender_id
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at
        self.completed_at: Optional[str] = None
        self.processing_time_ms: int = 0
        self.data_sources: Dict[str, Any] = {}
        self.version = "1.0"
        self.tags: List[str] = []
        self.metadata_fields: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "analysis_id": str(self.analysis_id),
            "tender_id": str(self.tender_id),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "processing_time_ms": self.processing_time_ms,
            "data_sources": self.data_sources,
            "version": self.version,
            "tags": self.tags,
            "metadata_fields": self.metadata_fields,
        }


class QualityIndicatorsService:
    """
    Comprehensive quality assessment and metadata service.

    Evaluates quality across multiple dimensions:
    - Data completeness
    - Extraction accuracy
    - Confidence scores
    - Processing health
    - Coverage metrics
    """

    def __init__(self):
        """Initialize quality service"""
        logger.info("✅ QualityIndicatorsService initialized")

    def assess_analysis_quality(
        self,
        analysis_data: Dict[str, Any],
        extraction_results: Dict[str, Any],
        processing_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Assess overall quality of analysis.

        Args:
            analysis_data: Complete analysis data
            extraction_results: Results from all extraction phases
            processing_metadata: Processing performance metrics

        Returns:
            Comprehensive quality assessment
        """
        logger.info("Starting comprehensive quality assessment")

        assessment = QualityAssessment()

        # 1. Data Completeness Assessment
        completeness_score = self._assess_data_completeness(extraction_results)
        assessment.add_indicator(
            QualityIndicator(
                name="Data Completeness",
                score=completeness_score,
                weight=1.5,
                description="Percentage of expected fields extracted successfully",
            )
        )

        # 2. Extraction Accuracy Assessment
        accuracy_score = self._assess_extraction_accuracy(extraction_results)
        assessment.add_indicator(
            QualityIndicator(
                name="Extraction Accuracy",
                score=accuracy_score,
                weight=1.5,
                description="Confidence in extracted values and relationships",
            )
        )

        # 3. Confidence Score Assessment
        confidence_score = self._assess_confidence_metrics(extraction_results)
        assessment.add_indicator(
            QualityIndicator(
                name="Overall Confidence",
                score=confidence_score,
                weight=2.0,
                description="Average confidence across all extractions",
            )
        )

        # 4. Processing Health Assessment
        health_score = self._assess_processing_health(processing_metadata)
        assessment.add_indicator(
            QualityIndicator(
                name="Processing Health",
                score=health_score,
                weight=1.0,
                description="System health and processing performance",
            )
        )

        # 5. Coverage Assessment
        coverage_score = self._assess_coverage(extraction_results)
        assessment.add_indicator(
            QualityIndicator(
                name="Analysis Coverage",
                score=coverage_score,
                weight=1.0,
                description="Percentage of tender aspects analyzed",
            )
        )

        return assessment.to_dict()

    def _assess_data_completeness(self, extraction_results: Dict[str, Any]) -> float:
        """Assess completeness of extracted data"""
        completeness_scores = []

        # Check tender info completeness
        if "tender_info" in extraction_results:
            tender_info = extraction_results["tender_info"]
            required_fields = [
                "referenceNumber",
                "title",
                "emdAmount",
                "contractValue",
            ]
            found = sum(1 for f in required_fields if tender_info.get(f))
            completeness_scores.append((found / len(required_fields)) * 100)

        # Check scope completeness
        if "scope_data" in extraction_results:
            scope = extraction_results["scope_data"]
            if scope.get("work_items"):
                completeness_scores.append(80.0)
            else:
                completeness_scores.append(40.0)

        # Check RFP completeness
        if "rfp_data" in extraction_results:
            rfp = extraction_results["rfp_data"]
            if rfp.get("sections"):
                completeness_scores.append(75.0)
            else:
                completeness_scores.append(35.0)

        # Check onepager completeness
        if "onepager_data" in extraction_results:
            onepager = extraction_results["onepager_data"]
            sections = [
                "projectOverview",
                "financialRequirements",
                "eligibilityHighlights",
            ]
            found = sum(1 for s in sections if onepager.get(s))
            completeness_scores.append((found / len(sections)) * 100)

        if not completeness_scores:
            return 50.0

        return sum(completeness_scores) / len(completeness_scores)

    def _assess_extraction_accuracy(self, extraction_results: Dict[str, Any]) -> float:
        """Assess accuracy of extracted data"""
        accuracy_scores = []

        # Get confidence from each component
        if "tender_info" in extraction_results:
            if isinstance(extraction_results["tender_info"], dict):
                conf = extraction_results["tender_info"].get("confidence", 70)
                accuracy_scores.append(conf)

        if "scope_data" in extraction_results:
            if isinstance(extraction_results["scope_data"], dict):
                conf = extraction_results["scope_data"].get(
                    "average_confidence", 70
                )
                accuracy_scores.append(conf)

        if "rfp_data" in extraction_results:
            if isinstance(extraction_results["rfp_data"], dict):
                conf = extraction_results["rfp_data"].get("confidence", 70)
                accuracy_scores.append(conf)

        if "onepager_data" in extraction_results:
            if isinstance(extraction_results["onepager_data"], dict):
                conf = extraction_results["onepager_data"].get(
                    "extractionConfidence", 70
                )
                accuracy_scores.append(conf)

        if not accuracy_scores:
            return 70.0

        return sum(accuracy_scores) / len(accuracy_scores)

    def _assess_confidence_metrics(self, extraction_results: Dict[str, Any]) -> float:
        """Assess overall confidence metrics"""
        confidence_scores = []

        for key in ["tender_info", "scope_data", "rfp_data", "onepager_data"]:
            if key in extraction_results:
                result = extraction_results[key]
                if isinstance(result, dict):
                    # Look for various confidence field names
                    conf = (
                        result.get("confidence")
                        or result.get("average_confidence")
                        or result.get("extractionConfidence")
                        or result.get("confidence_score", 70)
                    )
                    confidence_scores.append(float(conf))

        if not confidence_scores:
            return 70.0

        return sum(confidence_scores) / len(confidence_scores)

    def _assess_processing_health(self, processing_metadata: Dict[str, Any]) -> float:
        """Assess system health during processing"""
        health_score = 100.0

        # Check for errors
        if processing_metadata.get("errors"):
            health_score -= 20.0

        # Check processing time (expect <30 seconds for normal case)
        processing_time_ms = processing_metadata.get("processing_time_ms", 0)
        if processing_time_ms > 30000:
            health_score -= 10.0
        elif processing_time_ms > 60000:
            health_score -= 20.0

        # Check for fallback usage
        if processing_metadata.get("used_llm_fallback"):
            health_score -= 5.0

        return max(0, min(100, health_score))

    def _assess_coverage(self, extraction_results: Dict[str, Any]) -> float:
        """Assess analysis coverage of tender aspects"""
        coverage_score = 0.0
        covered_aspects = 0

        # Check Phase 1: Document Parsing
        if extraction_results.get("raw_text"):
            coverage_score += 15
            covered_aspects += 1

        # Check Phase 2: Tender Info
        if extraction_results.get("tender_info"):
            coverage_score += 20
            covered_aspects += 1

        # Check Phase 3a: OnePager
        if extraction_results.get("onepager_data"):
            coverage_score += 15
            covered_aspects += 1

        # Check Phase 3b: Scope
        if extraction_results.get("scope_data"):
            coverage_score += 20
            covered_aspects += 1

        # Check Phase 3c: RFP
        if extraction_results.get("rfp_data"):
            coverage_score += 15
            covered_aspects += 1

        # Check Phase 4: Advanced Intelligence
        if extraction_results.get("swot_analysis"):
            coverage_score += 5
            covered_aspects += 1

        if extraction_results.get("risk_assessment"):
            coverage_score += 5
            covered_aspects += 1

        if extraction_results.get("bid_recommendation"):
            coverage_score += 5
            covered_aspects += 1

        return max(0, min(100, coverage_score))

    def create_metadata(
        self, analysis_id: UUID, tender_id: UUID
    ) -> AnalysisMetadata:
        """Create metadata record for analysis"""
        metadata = AnalysisMetadata(analysis_id, tender_id)
        logger.info(f"✅ Created metadata for analysis {analysis_id}")
        return metadata

    def enrich_with_quality_metrics(
        self,
        analysis_results: Dict[str, Any],
        quality_assessment: Dict[str, Any],
        metadata: AnalysisMetadata,
    ) -> Dict[str, Any]:
        """
        Enrich analysis results with quality metrics and metadata.

        Args:
            analysis_results: Complete analysis results
            quality_assessment: Quality assessment data
            metadata: Analysis metadata

        Returns:
            Enriched results with quality and metadata
        """
        enriched = {
            **analysis_results,
            "quality_metrics": quality_assessment,
            "metadata": metadata.to_dict(),
            "enriched_at": datetime.utcnow().isoformat(),
        }

        return enriched

    def generate_quality_report(
        self, quality_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate human-readable quality report.

        Args:
            quality_assessment: Quality assessment data

        Returns:
            Formatted quality report
        """
        overall_score = quality_assessment.get("overall_score", 0)
        quality_level = quality_assessment.get("quality_level", "poor")

        # Generate recommendations
        recommendations = []

        if overall_score < 60:
            recommendations.append(
                "⚠️ Review tender documents for completeness"
            )
            recommendations.append(
                "Consider manual validation of extracted data"
            )
        elif overall_score < 75:
            recommendations.append(
                "Verify extracted data for accuracy"
            )
            recommendations.append(
                "Review low-confidence fields manually"
            )
        else:
            recommendations.append(
                "✅ Analysis quality is high, proceed with confidence"
            )

        # Check specific indicators
        for indicator in quality_assessment.get("indicators", []):
            if indicator["score"] < 60:
                recommendations.append(
                    f"⚠️ {indicator['name']}: {indicator['description']}"
                )

        return {
            "overall_score": overall_score,
            "quality_level": quality_level,
            "summary": f"Analysis quality is {quality_level.upper()}",
            "recommendations": recommendations,
            "detailed_assessment": quality_assessment,
            "report_timestamp": datetime.utcnow().isoformat(),
        }

    def get_confidence_level_category(self, confidence_score: float) -> str:
        """
        Categorize confidence score.

        Args:
            confidence_score: Confidence score (0-100)

        Returns:
            Confidence level category
        """
        if confidence_score >= 90:
            return ConfidenceLevel.VERY_HIGH.value
        elif confidence_score >= 75:
            return ConfidenceLevel.HIGH.value
        elif confidence_score >= 60:
            return ConfidenceLevel.MEDIUM.value
        elif confidence_score >= 40:
            return ConfidenceLevel.LOW.value
        else:
            return ConfidenceLevel.VERY_LOW.value

    def batch_assess_quality(
        self,
        analyses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Assess quality for multiple analyses in batch.

        Args:
            analyses: List of analysis data

        Returns:
            List of quality assessments
        """
        results = []

        for analysis in analyses:
            try:
                assessment = self.assess_analysis_quality(
                    analysis_data=analysis.get("analysis_data", {}),
                    extraction_results=analysis.get("extraction_results", {}),
                    processing_metadata=analysis.get(
                        "processing_metadata", {}
                    ),
                )
                results.append(assessment)
            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to assess quality for analysis: {e}"
                )
                results.append(
                    {
                        "overall_score": 0,
                        "quality_level": "poor",
                        "error": str(e),
                    }
                )

        logger.info(f"✅ Batch assessed {len(results)} analyses")
        return results
