"""
Unit tests for Phase 4: Advanced Intelligence Services

Tests for:
- SWOTAnalyzer
- BidDecisionRecommender
- EnhancedRiskEngine
- ComplianceChecker
- CostBreakdownGenerator
- WinProbabilityCalculator
"""

import pytest
from unittest.mock import Mock
from uuid import uuid4

from app.modules.tenderiq.analyze.services.advanced_intelligence import (
    SWOTAnalyzer,
    BidDecisionRecommender,
    EnhancedRiskEngine,
    ComplianceChecker,
    CostBreakdownGenerator,
    WinProbabilityCalculator,
)


@pytest.fixture
def sample_tender_info():
    """Sample tender info for testing"""
    return {
        "referenceNumber": "PWD/NH-44/2024/ROAD/001",
        "title": "Construction and Maintenance of NH-44 Highway Project",
        "description": "25 km highway stretch construction",
        "department": "Public Works Department",
        "emdAmount": {"amount": 31.00, "currency": "INR"},
    }


@pytest.fixture
def sample_scope_data():
    """Sample scope data for testing"""
    return {
        "work_items": [
            {
                "id": "WI-001",
                "title": "Site Survey",
                "estimatedDays": 15,
                "complexity": "medium",
            },
            {
                "id": "WI-002",
                "title": "Design and Engineering",
                "estimatedDays": 30,
                "complexity": "high",
            },
            {
                "id": "WI-003",
                "title": "Construction Phase 1",
                "estimatedDays": 120,
                "complexity": "high",
            },
        ],
        "total_effort_days": 165,
        "item_count": 3,
    }


@pytest.fixture
def sample_financials():
    """Sample financial data for testing"""
    return {
        "contractValue": {"amount": 1550.0, "currency": "INR"},
        "emdAmount": {"amount": 31.0, "currency": "INR"},
        "pbgAmount": {"amount": 155.0, "currency": "INR"},
    }


@pytest.fixture
def sample_company_capabilities():
    """Sample company capabilities for testing"""
    return {
        "yearsOfExperience": 10,
        "minimumTurnover": 50.0,
        "completedProjects": 5,
        "certifications": ["ISO 9001", "ISO 14001"],
    }


# ===== SWOTAnalyzer Tests =====


class TestSWOTAnalyzer:
    """Test SWOTAnalyzer service"""

    def test_analyzer_instantiates(self):
        """Test SWOTAnalyzer can be instantiated"""
        analyzer = SWOTAnalyzer()
        assert analyzer is not None

    @pytest.mark.asyncio
    async def test_analyze_swot_keyword(
        self, sample_tender_info, sample_scope_data, sample_financials
    ):
        """Test SWOT analysis with keyword fallback"""
        analyzer = SWOTAnalyzer()

        swot = await analyzer.analyze_swot(
            tender_info=sample_tender_info,
            scope_data=sample_scope_data,
            financials=sample_financials,
            use_llm=False,
        )

        assert swot is not None
        assert "strengths" in swot
        assert "weaknesses" in swot
        assert "opportunities" in swot
        assert "threats" in swot
        assert "confidence" in swot
        assert isinstance(swot["strengths"], list)
        assert isinstance(swot["weaknesses"], list)
        assert isinstance(swot["opportunities"], list)
        assert isinstance(swot["threats"], list)

    @pytest.mark.asyncio
    async def test_swot_analysis_returns_valid_structure(
        self, sample_tender_info, sample_scope_data, sample_financials
    ):
        """Test SWOT returns valid structure"""
        analyzer = SWOTAnalyzer()

        # Test with keyword extraction (use_llm=False)
        swot = await analyzer._analyze_with_keywords(
            sample_tender_info, sample_scope_data, sample_financials
        )

        assert swot is not None
        assert len(swot["strengths"]) > 0
        assert len(swot["weaknesses"]) > 0
        assert 0 <= swot["confidence"] <= 100


# ===== BidDecisionRecommender Tests =====


class TestBidDecisionRecommender:
    """Test BidDecisionRecommender service"""

    def test_recommender_instantiates(self):
        """Test BidDecisionRecommender can be instantiated"""
        recommender = BidDecisionRecommender()
        assert recommender is not None

    @pytest.mark.asyncio
    async def test_recommend_bid_decision_keyword(
        self, sample_tender_info, sample_scope_data, sample_financials
    ):
        """Test bid decision recommendation"""
        recommender = BidDecisionRecommender()

        swot = {
            "strengths": ["Experience", "Resources"],
            "weaknesses": ["Limited team"],
            "opportunities": ["Market growth"],
            "threats": ["Competition"],
            "confidence": 75.0,
        }

        recommendation = await recommender.recommend_bid_decision(
            tender_info=sample_tender_info,
            scope_data=sample_scope_data,
            financials=sample_financials,
            risk_level="medium",
            swot=swot,
        )

        assert recommendation is not None
        assert "recommendation" in recommendation
        assert "score" in recommendation
        assert "rationale" in recommendation
        assert recommendation["recommendation"] in [
            "STRONG BID",
            "CONDITIONAL BID",
            "CAUTION",
            "NO BID",
        ]
        assert 0 <= recommendation["score"] <= 100

    @pytest.mark.asyncio
    async def test_recommendation_confidence_threshold(
        self, sample_tender_info, sample_scope_data, sample_financials
    ):
        """Test recommendation changes based on confidence"""
        recommender = BidDecisionRecommender()

        low_confidence_swot = {
            "strengths": [],
            "weaknesses": ["Many gaps"],
            "opportunities": [],
            "threats": ["High risk"],
            "confidence": 30.0,
        }

        recommendation = await recommender.recommend_bid_decision(
            tender_info=sample_tender_info,
            scope_data=sample_scope_data,
            financials=sample_financials,
            risk_level="high",
            swot=low_confidence_swot,
        )

        assert recommendation["score"] < 60  # Should be lower for low confidence


# ===== EnhancedRiskEngine Tests =====


class TestEnhancedRiskEngine:
    """Test EnhancedRiskEngine service"""

    def test_engine_instantiates(self):
        """Test EnhancedRiskEngine can be instantiated"""
        engine = EnhancedRiskEngine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_assess_risks_keyword(
        self, sample_tender_info, sample_scope_data, sample_financials
    ):
        """Test risk assessment"""
        engine = EnhancedRiskEngine()

        risks = await engine.assess_risks(
            tender_info=sample_tender_info,
            scope_data=sample_scope_data,
            financials=sample_financials,
        )

        assert risks is not None
        assert "overall_score" in risks
        assert "risk_level" in risks
        assert "individual_risks" in risks
        assert 0 <= risks["overall_score"] <= 100
        assert risks["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    @pytest.mark.asyncio
    async def test_risk_score_range(self, sample_tender_info, sample_scope_data, sample_financials):
        """Test risk scores are within valid range"""
        engine = EnhancedRiskEngine()

        risks = await engine.assess_risks(
            sample_tender_info, sample_scope_data, sample_financials
        )

        assert 0 <= risks["overall_score"] <= 100
        for risk in risks.get("individual_risks", []):
            # Risk items may have likelihood or other fields, ensure they are valid
            assert isinstance(risk, dict)
            assert "likelihood" in risk or "impact" in risk


# ===== ComplianceChecker Tests =====


class TestComplianceChecker:
    """Test ComplianceChecker service"""

    def test_checker_instantiates(self):
        """Test ComplianceChecker can be instantiated"""
        checker = ComplianceChecker()
        assert checker is not None

    @pytest.mark.asyncio
    async def test_check_compliance_keyword(self, sample_tender_info, sample_company_capabilities):
        """Test compliance checking"""
        checker = ComplianceChecker()

        compliance = await checker.check_compliance(
            tender_info=sample_tender_info,
            company_capabilities=sample_company_capabilities,
        )

        assert compliance is not None
        assert "overall_compliance" in compliance
        assert "compliance_score" in compliance
        assert "items" in compliance
        assert "gaps" in compliance
        assert 0 <= compliance["compliance_score"] <= 100
        assert compliance["overall_compliance"] in ["COMPLIANT", "PARTIALLY_COMPLIANT", "NON-COMPLIANT"]

    @pytest.mark.asyncio
    async def test_compliance_score_calculation(self, sample_tender_info, sample_company_capabilities):
        """Test compliance score calculation"""
        checker = ComplianceChecker()

        # Test through the async main method
        compliance = await checker.check_compliance(
            tender_info=sample_tender_info,
            company_capabilities=sample_company_capabilities,
        )

        assert compliance is not None
        assert 0 <= compliance["compliance_score"] <= 100
        assert isinstance(compliance["items"], list)


# ===== CostBreakdownGenerator Tests =====


class TestCostBreakdownGenerator:
    """Test CostBreakdownGenerator service"""

    def test_generator_instantiates(self):
        """Test CostBreakdownGenerator can be instantiated"""
        generator = CostBreakdownGenerator()
        assert generator is not None

    @pytest.mark.asyncio
    async def test_generate_cost_breakdown_keyword(self, sample_scope_data, sample_financials):
        """Test cost breakdown generation"""
        generator = CostBreakdownGenerator()

        breakdown = await generator.generate_cost_breakdown(
            scope_data=sample_scope_data,
            financials=sample_financials,
        )

        assert breakdown is not None
        assert "line_items" in breakdown
        assert "subtotal" in breakdown
        assert "contingency" in breakdown
        assert "overhead" in breakdown
        assert "total_estimate" in breakdown
        assert "margin" in breakdown
        assert len(breakdown["line_items"]) > 0
        assert breakdown["subtotal"] > 0

    @pytest.mark.asyncio
    async def test_cost_breakdown_calculation(self, sample_scope_data, sample_financials):
        """Test cost breakdown values"""
        generator = CostBreakdownGenerator()

        breakdown = await generator.generate_cost_breakdown(sample_scope_data, sample_financials)

        assert breakdown["subtotal"] > 0
        assert breakdown["total_estimate"] >= breakdown["subtotal"]
        assert 0 <= breakdown["margin"] <= 100


# ===== WinProbabilityCalculator Tests =====


class TestWinProbabilityCalculator:
    """Test WinProbabilityCalculator service"""

    def test_calculator_instantiates(self):
        """Test WinProbabilityCalculator can be instantiated"""
        calculator = WinProbabilityCalculator()
        assert calculator is not None

    @pytest.mark.asyncio
    async def test_calculate_win_probability(self):
        """Test win probability calculation"""
        calculator = WinProbabilityCalculator()

        probability = await calculator.calculate_win_probability(
            bid_recommendation_score=75.0,
            risk_level="medium",
            compliance_score=85.0,
            competitive_complexity="high",
        )

        assert probability is not None
        assert "win_probability" in probability
        assert "category" in probability
        assert "interpretation" in probability
        assert "confidence" in probability
        assert "factors" in probability
        assert 0 <= probability["win_probability"] <= 100
        assert probability["category"] in ["VERY_HIGH", "HIGH", "MODERATE", "LOW", "VERY_LOW"]

    @pytest.mark.asyncio
    async def test_win_probability_varies_by_inputs(self):
        """Test win probability changes based on inputs"""
        calculator = WinProbabilityCalculator()

        # High score scenario
        high_score = await calculator.calculate_win_probability(
            bid_recommendation_score=90.0,
            risk_level="low",
            compliance_score=95.0,
            competitive_complexity="low",
        )

        # Low score scenario
        low_score = await calculator.calculate_win_probability(
            bid_recommendation_score=30.0,
            risk_level="high",
            compliance_score=40.0,
            competitive_complexity="high",
        )

        assert high_score["win_probability"] > low_score["win_probability"]

    @pytest.mark.asyncio
    async def test_win_probability_bounds(self):
        """Test win probability stays within bounds"""
        calculator = WinProbabilityCalculator()

        # Extreme positive
        result = await calculator.calculate_win_probability(
            bid_recommendation_score=100.0,
            risk_level="low",
            compliance_score=100.0,
            competitive_complexity="low",
        )
        assert 0 <= result["win_probability"] <= 100

        # Extreme negative
        result = await calculator.calculate_win_probability(
            bid_recommendation_score=0.0,
            risk_level="critical",
            compliance_score=0.0,
            competitive_complexity="high",
        )
        assert 0 <= result["win_probability"] <= 100


# ===== Integration Tests =====


class TestPhase4Integration:
    """Integration tests for Phase 4 services"""

    @pytest.mark.asyncio
    async def test_full_advanced_intelligence_workflow(
        self, sample_tender_info, sample_scope_data, sample_financials, sample_company_capabilities
    ):
        """Test complete Phase 4 workflow"""
        swot_analyzer = SWOTAnalyzer()
        bid_recommender = BidDecisionRecommender()
        risk_engine = EnhancedRiskEngine()
        compliance_checker = ComplianceChecker()
        cost_generator = CostBreakdownGenerator()
        win_calculator = WinProbabilityCalculator()

        # Step 1: SWOT Analysis
        swot = await swot_analyzer.analyze_swot(
            tender_info=sample_tender_info,
            scope_data=sample_scope_data,
            financials=sample_financials,
            use_llm=False,
        )
        assert swot is not None
        assert "confidence" in swot

        # Step 2: Risk Assessment
        risks = await risk_engine.assess_risks(
            tender_info=sample_tender_info,
            scope_data=sample_scope_data,
            financials=sample_financials,
        )
        assert risks is not None
        assert "risk_level" in risks

        # Step 3: Compliance Check
        compliance = await compliance_checker.check_compliance(
            tender_info=sample_tender_info,
            company_capabilities=sample_company_capabilities,
        )
        assert compliance is not None
        assert "overall_compliance" in compliance

        # Step 4: Bid Decision
        recommendation = await bid_recommender.recommend_bid_decision(
            tender_info=sample_tender_info,
            scope_data=sample_scope_data,
            financials=sample_financials,
            risk_level=risks["risk_level"],
            swot=swot,
        )
        assert recommendation is not None
        assert "recommendation" in recommendation

        # Step 5: Cost Breakdown
        breakdown = await cost_generator.generate_cost_breakdown(
            scope_data=sample_scope_data,
            financials=sample_financials,
        )
        assert breakdown is not None
        assert "total_estimate" in breakdown

        # Step 6: Win Probability
        win_prob = await win_calculator.calculate_win_probability(
            bid_recommendation_score=recommendation["score"],
            risk_level=risks["risk_level"],
            compliance_score=compliance["compliance_score"],
            competitive_complexity="high",
        )
        assert win_prob is not None
        assert "win_probability" in win_prob

    @pytest.mark.asyncio
    async def test_service_output_compatibility(
        self, sample_tender_info, sample_scope_data, sample_financials, sample_company_capabilities
    ):
        """Test that service outputs are compatible for composition"""
        swot_analyzer = SWOTAnalyzer()
        bid_recommender = BidDecisionRecommender()
        risk_engine = EnhancedRiskEngine()

        # SWOT output should work as input to bid recommender
        swot = await swot_analyzer._analyze_with_keywords(
            sample_tender_info, sample_scope_data, sample_financials
        )

        risks = await risk_engine.assess_risks(
            sample_tender_info, sample_scope_data, sample_financials
        )

        # Should not raise any errors when composing services
        recommendation = await bid_recommender.recommend_bid_decision(
            tender_info=sample_tender_info,
            scope_data=sample_scope_data,
            financials=sample_financials,
            risk_level=risks["risk_level"],
            swot=swot,
        )

        assert recommendation is not None
        assert "score" in recommendation
