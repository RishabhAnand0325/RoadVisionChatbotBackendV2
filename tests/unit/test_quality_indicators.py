"""
Unit tests for Phase 5: Quality Indicators and Metadata Service

Tests for:
- QualityIndicator
- QualityAssessment
- AnalysisMetadata
- QualityIndicatorsService
"""

import pytest
from uuid import uuid4
from datetime import datetime

from app.modules.tenderiq.analyze.services.quality_indicators import (
    QualityIndicator,
    QualityAssessment,
    AnalysisMetadata,
    QualityIndicatorsService,
    QualityLevel,
    ConfidenceLevel,
)


# ===== QualityIndicator Tests =====


class TestQualityIndicator:
    """Test QualityIndicator class"""

    def test_indicator_instantiates(self):
        """Test QualityIndicator can be instantiated"""
        indicator = QualityIndicator(
            name="Test Indicator",
            score=85.0,
            weight=1.5,
            description="Test description",
        )
        assert indicator is not None
        assert indicator.name == "Test Indicator"
        assert indicator.score == 85.0
        assert indicator.weight == 1.5

    def test_indicator_score_clamping(self):
        """Test score is clamped to 0-100 range"""
        # Test over 100
        indicator = QualityIndicator("Test", score=150.0)
        assert indicator.score == 100.0

        # Test under 0
        indicator = QualityIndicator("Test", score=-50.0)
        assert indicator.score == 0.0

        # Test valid range
        indicator = QualityIndicator("Test", score=75.5)
        assert indicator.score == 75.5

    def test_indicator_with_issues(self):
        """Test indicator with issue tracking"""
        issues = ["Issue 1", "Issue 2"]
        indicator = QualityIndicator(
            name="Test", score=50.0, issues=issues
        )
        assert len(indicator.issues) == 2
        assert "Issue 1" in indicator.issues

    def test_indicator_to_dict(self):
        """Test indicator serialization"""
        indicator = QualityIndicator(
            name="Test Indicator",
            score=80.0,
            weight=2.0,
            description="Test description",
            issues=["Issue 1"],
        )

        data = indicator.to_dict()
        assert data["name"] == "Test Indicator"
        assert data["score"] == 80.0
        assert data["weight"] == 2.0
        assert data["description"] == "Test description"
        assert "Issue 1" in data["issues"]


# ===== QualityAssessment Tests =====


class TestQualityAssessment:
    """Test QualityAssessment class"""

    def test_assessment_instantiates(self):
        """Test QualityAssessment can be instantiated"""
        assessment = QualityAssessment()
        assert assessment is not None
        assert len(assessment.indicators) == 0
        assert assessment.overall_score == 0.0

    def test_assessment_add_indicator(self):
        """Test adding indicators to assessment"""
        assessment = QualityAssessment()
        indicator = QualityIndicator("Test", score=80.0, weight=1.0)

        assessment.add_indicator(indicator)
        assert len(assessment.indicators) == 1
        assert assessment.overall_score == 80.0

    def test_assessment_quality_level_excellent(self):
        """Test quality level determination for excellent"""
        assessment = QualityAssessment()
        assessment.add_indicator(QualityIndicator("Test", score=95.0, weight=1.0))

        assert assessment.overall_score >= 90
        assert assessment.quality_level == QualityLevel.EXCELLENT

    def test_assessment_quality_level_good(self):
        """Test quality level determination for good"""
        assessment = QualityAssessment()
        assessment.add_indicator(QualityIndicator("Test", score=80.0, weight=1.0))

        assert 75 <= assessment.overall_score < 90
        assert assessment.quality_level == QualityLevel.GOOD

    def test_assessment_quality_level_fair(self):
        """Test quality level determination for fair"""
        assessment = QualityAssessment()
        assessment.add_indicator(QualityIndicator("Test", score=65.0, weight=1.0))

        assert 60 <= assessment.overall_score < 75
        assert assessment.quality_level == QualityLevel.FAIR

    def test_assessment_quality_level_poor(self):
        """Test quality level determination for poor"""
        assessment = QualityAssessment()
        assessment.add_indicator(QualityIndicator("Test", score=40.0, weight=1.0))

        assert assessment.overall_score < 60
        assert assessment.quality_level == QualityLevel.POOR

    def test_assessment_weighted_score(self):
        """Test weighted score calculation"""
        assessment = QualityAssessment()

        assessment.add_indicator(QualityIndicator("High", score=100.0, weight=2.0))
        assessment.add_indicator(QualityIndicator("Low", score=50.0, weight=1.0))

        # (100*2 + 50*1) / (2+1) = 250/3 ≈ 83.33
        expected = (100 * 2 + 50 * 1) / 3
        assert abs(assessment.overall_score - expected) < 0.1

    def test_assessment_to_dict(self):
        """Test assessment serialization"""
        assessment = QualityAssessment()
        assessment.add_indicator(QualityIndicator("Test", score=80.0, weight=1.0))

        data = assessment.to_dict()
        assert "overall_score" in data
        assert "quality_level" in data
        assert "indicators" in data
        assert "assessment_timestamp" in data
        assert len(data["indicators"]) == 1


# ===== AnalysisMetadata Tests =====


class TestAnalysisMetadata:
    """Test AnalysisMetadata class"""

    def test_metadata_instantiates(self):
        """Test AnalysisMetadata can be instantiated"""
        analysis_id = uuid4()
        tender_id = uuid4()

        metadata = AnalysisMetadata(analysis_id, tender_id)
        assert metadata is not None
        assert metadata.analysis_id == analysis_id
        assert metadata.tender_id == tender_id

    def test_metadata_timestamps(self):
        """Test metadata timestamps"""
        analysis_id = uuid4()
        tender_id = uuid4()

        metadata = AnalysisMetadata(analysis_id, tender_id)
        assert metadata.created_at is not None
        assert metadata.updated_at is not None
        assert metadata.completed_at is None

    def test_metadata_data_sources(self):
        """Test metadata data source tracking"""
        metadata = AnalysisMetadata(uuid4(), uuid4())

        metadata.data_sources["document"] = {"id": "doc-123", "name": "tender.pdf"}
        metadata.tags.append("high_priority")

        assert "document" in metadata.data_sources
        assert "high_priority" in metadata.tags

    def test_metadata_to_dict(self):
        """Test metadata serialization"""
        analysis_id = uuid4()
        tender_id = uuid4()

        metadata = AnalysisMetadata(analysis_id, tender_id)
        metadata.tags.append("test_tag")
        metadata.metadata_fields["custom"] = "value"

        data = metadata.to_dict()
        assert str(analysis_id) in str(data["analysis_id"])
        assert str(tender_id) in str(data["tender_id"])
        assert "test_tag" in data["tags"]
        assert data["metadata_fields"]["custom"] == "value"


# ===== QualityIndicatorsService Tests =====


class TestQualityIndicatorsService:
    """Test QualityIndicatorsService"""

    def test_service_instantiates(self):
        """Test QualityIndicatorsService can be instantiated"""
        service = QualityIndicatorsService()
        assert service is not None

    def test_assess_analysis_quality(self):
        """Test comprehensive quality assessment"""
        service = QualityIndicatorsService()

        analysis_data = {}
        extraction_results = {
            "tender_info": {
                "referenceNumber": "TEST-001",
                "title": "Test Tender",
                "emdAmount": {"amount": 100},
                "contractValue": {"amount": 1000},
                "confidence": 85.0,
            },
            "scope_data": {
                "work_items": [{"id": "WI-001", "title": "Work 1"}],
                "average_confidence": 80.0,
            },
            "onepager_data": {
                "projectOverview": {"description": "Overview"},
                "financialRequirements": {"emdAmount": 100},
                "eligibilityHighlights": {"minimumExperience": "5 years"},
                "extractionConfidence": 75.0,
            },
        }
        processing_metadata = {
            "processing_time_ms": 5000,
            "errors": [],
        }

        assessment = service.assess_analysis_quality(
            analysis_data, extraction_results, processing_metadata
        )

        assert assessment is not None
        assert "overall_score" in assessment
        assert "quality_level" in assessment
        assert "indicators" in assessment
        assert 0 <= assessment["overall_score"] <= 100

    def test_assess_data_completeness(self):
        """Test data completeness assessment"""
        service = QualityIndicatorsService()

        extraction_results = {
            "tender_info": {
                "referenceNumber": "TEST",
                "title": "Title",
                "emdAmount": 100,
                "contractValue": 1000,
            },
            "scope_data": {"work_items": [{"id": "WI-001"}]},
        }

        completeness = service._assess_data_completeness(extraction_results)
        assert 0 <= completeness <= 100
        assert completeness > 50  # Should be good due to filled fields

    def test_assess_extraction_accuracy(self):
        """Test extraction accuracy assessment"""
        service = QualityIndicatorsService()

        extraction_results = {
            "tender_info": {"confidence": 85.0},
            "scope_data": {"average_confidence": 80.0},
            "rfp_data": {"confidence": 75.0},
        }

        accuracy = service._assess_extraction_accuracy(extraction_results)
        assert 0 <= accuracy <= 100
        assert accuracy > 70  # Should reflect provided confidence values

    def test_assess_confidence_metrics(self):
        """Test confidence metrics assessment"""
        service = QualityIndicatorsService()

        extraction_results = {
            "tender_info": {"confidence": 90.0},
            "scope_data": {"average_confidence": 85.0},
            "rfp_data": {"confidence": 80.0},
            "onepager_data": {"extractionConfidence": 75.0},
        }

        confidence = service._assess_confidence_metrics(extraction_results)
        assert 0 <= confidence <= 100
        assert confidence >= 75  # Average of high confidence scores

    def test_assess_processing_health(self):
        """Test processing health assessment"""
        service = QualityIndicatorsService()

        # Good health case
        metadata = {"errors": [], "processing_time_ms": 5000}
        health = service._assess_processing_health(metadata)
        assert health == 100.0

        # With errors
        metadata = {"errors": ["Error 1"], "processing_time_ms": 5000}
        health = service._assess_processing_health(metadata)
        assert health < 100.0

        # Slow processing
        metadata = {"errors": [], "processing_time_ms": 45000}
        health = service._assess_processing_health(metadata)
        assert health < 100.0

    def test_assess_coverage(self):
        """Test analysis coverage assessment"""
        service = QualityIndicatorsService()

        extraction_results = {
            "raw_text": "Some text",
            "tender_info": {"title": "Test"},
            "onepager_data": {"description": "Test"},
            "scope_data": {"items": []},
            "rfp_data": {"sections": []},
        }

        coverage = service._assess_coverage(extraction_results)
        assert 0 <= coverage <= 100
        assert coverage > 50  # Should have decent coverage

    def test_create_metadata(self):
        """Test metadata creation"""
        service = QualityIndicatorsService()
        analysis_id = uuid4()
        tender_id = uuid4()

        metadata = service.create_metadata(analysis_id, tender_id)
        assert metadata is not None
        assert metadata.analysis_id == analysis_id
        assert metadata.tender_id == tender_id

    def test_enrich_with_quality_metrics(self):
        """Test enriching results with quality metrics"""
        service = QualityIndicatorsService()
        analysis_id = uuid4()
        tender_id = uuid4()

        analysis_results = {"data": "value"}
        quality_assessment = {"overall_score": 85.0, "quality_level": "good"}
        metadata = service.create_metadata(analysis_id, tender_id)

        enriched = service.enrich_with_quality_metrics(
            analysis_results, quality_assessment, metadata
        )

        assert "data" in enriched
        assert "quality_metrics" in enriched
        assert "metadata" in enriched
        assert "enriched_at" in enriched
        assert enriched["quality_metrics"]["overall_score"] == 85.0

    def test_generate_quality_report(self):
        """Test quality report generation"""
        service = QualityIndicatorsService()

        assessment = {
            "overall_score": 85.0,
            "quality_level": "good",
            "indicators": [
                {"name": "Test", "score": 85.0, "description": "Description"}
            ],
        }

        report = service.generate_quality_report(assessment)

        assert "overall_score" in report
        assert "quality_level" in report
        assert "summary" in report
        assert "recommendations" in report
        assert "detailed_assessment" in report
        assert "report_timestamp" in report

    def test_get_confidence_level_category(self):
        """Test confidence level categorization"""
        service = QualityIndicatorsService()

        assert (
            service.get_confidence_level_category(95.0)
            == ConfidenceLevel.VERY_HIGH.value
        )
        assert (
            service.get_confidence_level_category(80.0) == ConfidenceLevel.HIGH.value
        )
        assert (
            service.get_confidence_level_category(70.0)
            == ConfidenceLevel.MEDIUM.value
        )
        assert (
            service.get_confidence_level_category(50.0) == ConfidenceLevel.LOW.value
        )
        assert (
            service.get_confidence_level_category(30.0)
            == ConfidenceLevel.VERY_LOW.value
        )

    def test_batch_assess_quality(self):
        """Test batch quality assessment"""
        service = QualityIndicatorsService()

        analyses = [
            {
                "analysis_data": {},
                "extraction_results": {
                    "tender_info": {"confidence": 85.0}
                },
                "processing_metadata": {"errors": []},
            },
            {
                "analysis_data": {},
                "extraction_results": {
                    "tender_info": {"confidence": 75.0}
                },
                "processing_metadata": {"errors": []},
            },
        ]

        results = service.batch_assess_quality(analyses)
        assert len(results) == 2
        assert all("overall_score" in r for r in results)
        assert all("quality_level" in r for r in results)


# ===== Integration Tests =====


class TestQualityIndicatorsIntegration:
    """Integration tests for Quality Indicators"""

    def test_full_quality_assessment_workflow(self):
        """Test complete quality assessment workflow"""
        service = QualityIndicatorsService()
        analysis_id = uuid4()
        tender_id = uuid4()

        # Step 1: Create metadata
        metadata = service.create_metadata(analysis_id, tender_id)
        assert metadata is not None

        # Step 2: Assess quality
        analysis_data = {}
        extraction_results = {
            "tender_info": {
                "referenceNumber": "TEST",
                "title": "Test",
                "emdAmount": 100,
                "contractValue": 1000,
                "confidence": 85.0,
            },
            "scope_data": {
                "work_items": [{"id": "WI-001"}],
                "average_confidence": 80.0,
            },
            "onepager_data": {
                "projectOverview": {},
                "financialRequirements": {},
                "eligibilityHighlights": {},
                "extractionConfidence": 75.0,
            },
        }
        processing_metadata = {
            "processing_time_ms": 5000,
            "errors": [],
        }

        assessment = service.assess_analysis_quality(
            analysis_data, extraction_results, processing_metadata
        )

        assert assessment["overall_score"] > 0

        # Step 3: Enrich results
        analysis_results = {"extraction_results": extraction_results}
        enriched = service.enrich_with_quality_metrics(
            analysis_results, assessment, metadata
        )

        assert "quality_metrics" in enriched
        assert "metadata" in enriched

        # Step 4: Generate report
        report = service.generate_quality_report(assessment)
        assert "recommendations" in report
        assert len(report["recommendations"]) > 0
