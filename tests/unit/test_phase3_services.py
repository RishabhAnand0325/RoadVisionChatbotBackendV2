"""
Unit tests for Phase 3: Semantic Analysis Services

Tests for:
- OnePagerGenerator
- ScopeOfWorkAnalyzer
- RFPSectionAnalyzer
"""

import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

from app.modules.tenderiq.analyze.services.onepager_generator import OnePagerGenerator
from app.modules.tenderiq.analyze.services.scope_work_analyzer import (
    ScopeOfWorkAnalyzer,
    WorkItem,
)
from app.modules.tenderiq.analyze.services.rfp_section_analyzer import (
    RFPSectionAnalyzer,
    RFPSection,
)


@pytest.fixture
def sample_tender_text():
    """Sample tender document for testing"""
    return """
    TENDER REFERENCE: PWD/NH-44/2024/ROAD/001

    CONSTRUCTION AND MAINTENANCE OF NH-44 HIGHWAY PROJECT

    Contract Value: ₹15.50 Crores
    EMD: ₹31.00 Lakhs (2%)
    PBG: ₹1.55 Crores (10%)

    PROJECT OVERVIEW:
    Construction of a 25 km highway stretch including
    - Earthwork and paving
    - Bridge structures
    - Drainage systems
    - Safety installations

    SCOPE OF WORK:
    1. Site Survey and Investigation (15 days)
    2. Design and Engineering (30 days)
    3. Procurement (20 days)
    4. Construction Phase 1 (120 days)
    5. Construction Phase 2 (100 days)
    6. Testing and Commissioning (30 days)
    7. Handover and Training (10 days)

    ELIGIBILITY CRITERIA:
    - Minimum 7 years experience
    - Minimum turnover ₹25 Crores
    - Similar projects: 2 projects of minimum ₹10 Cr
    - Special relaxation for MSME

    KEY DATES:
    - Bid Submission: 2024-04-25
    - Technical Evaluation: 2024-04-26
    - Financial Bid Opening: 2024-05-05
    - Project Duration: 24 months

    RISK FACTORS:
    This is a complex project with challenging terrain.
    Weather conditions may impact schedule.
    Strict compliance with IRC standards required.

    TECHNICAL REQUIREMENTS:
    - IRC road standards compliance
    - Quality concrete specifications
    - Advanced surveying equipment required
    - Environmental compliance mandatory
    """


# ===== OnePagerGenerator Tests =====

class TestOnePagerGenerator:
    """Test OnePagerGenerator service"""

    def test_onepager_instantiates(self):
        """Test OnePagerGenerator can be instantiated"""
        generator = OnePagerGenerator()
        assert generator is not None

    @pytest.mark.asyncio
    async def test_generate_onepager_keyword(self, sample_tender_text):
        """Test onepager generation with keyword fallback"""
        generator = OnePagerGenerator()
        db = Mock()
        analysis_id = uuid4()

        onepager = await generator.generate_onepager(
            db=db,
            analysis_id=analysis_id,
            raw_text=sample_tender_text,
            use_llm=False,
        )

        assert onepager is not None
        assert onepager.extractionConfidence >= 50.0
        assert onepager.extractionConfidence <= 100.0

    @pytest.mark.asyncio
    async def test_project_overview_extraction(self, sample_tender_text):
        """Test project overview extraction"""
        generator = OnePagerGenerator()

        overview = generator._extract_project_overview(sample_tender_text)

        assert overview is not None
        assert overview.description is not None
        assert len(overview.description) > 0
        assert overview.keyHighlights is not None

    @pytest.mark.asyncio
    async def test_financial_extraction(self, sample_tender_text):
        """Test financial requirements extraction"""
        generator = OnePagerGenerator()

        financial = generator._extract_financial_requirements(sample_tender_text)

        assert financial is not None
        assert financial.contractValue is not None
        assert financial.contractValue.amount > 0
        assert financial.emdAmount is not None
        assert financial.emdAmount.amount > 0

    @pytest.mark.asyncio
    async def test_eligibility_extraction(self, sample_tender_text):
        """Test eligibility criteria extraction"""
        generator = OnePagerGenerator()

        eligibility = generator._extract_eligibility_highlights(sample_tender_text)

        assert eligibility is not None
        assert eligibility.minimumExperience is not None
        # Should extract either experience string or at least get a value
        assert len(eligibility.minimumExperience) > 0

    @pytest.mark.asyncio
    async def test_key_dates_extraction(self, sample_tender_text):
        """Test key dates extraction"""
        generator = OnePagerGenerator()

        key_dates = generator._extract_key_dates(sample_tender_text)

        assert key_dates is not None
        # Should extract some date information
        assert key_dates.bidSubmissionDeadline or key_dates.projectDuration

    @pytest.mark.asyncio
    async def test_risk_assessment(self, sample_tender_text):
        """Test risk factor assessment"""
        generator = OnePagerGenerator()

        risk_factors = generator._assess_risk_factors(sample_tender_text)

        assert risk_factors is not None
        assert risk_factors.level in ["low", "medium", "high"]
        assert len(risk_factors.factors) > 0

    def test_confidence_calculation(self):
        """Test confidence score calculation"""
        generator = OnePagerGenerator()

        from app.modules.tenderiq.analyze.models.structured_extraction_models import (
            OnePagerData,
            ProjectOverview,
            MoneyAmount,
            Currency,
        )

        onepager = OnePagerData(
            projectOverview=ProjectOverview(
                description="Test project",
                keyHighlights=["Highlight 1"],
                projectScope="Test scope",
            ),
            extractionConfidence=50.0,
        )

        confidence = generator._calculate_confidence(onepager)
        assert confidence > 50.0


# ===== ScopeOfWorkAnalyzer Tests =====

class TestScopeOfWorkAnalyzer:
    """Test ScopeOfWorkAnalyzer service"""

    def test_analyzer_instantiates(self):
        """Test ScopeOfWorkAnalyzer can be instantiated"""
        analyzer = ScopeOfWorkAnalyzer()
        assert analyzer is not None

    def test_work_item_to_dict(self):
        """Test WorkItem conversion to dictionary"""
        item = WorkItem(
            id="WI-001",
            title="Test Work Item",
            description="Test description",
            category="testing",
            complexity="medium",
            estimated_days=15,
            confidence=80.0,
        )

        data = item.to_dict()
        assert data["id"] == "WI-001"
        assert data["title"] == "Test Work Item"
        assert data["estimatedDays"] == 15
        assert data["complexity"] == "medium"

    @pytest.mark.asyncio
    async def test_analyze_scope_keyword(self, sample_tender_text):
        """Test scope analysis with keyword fallback"""
        analyzer = ScopeOfWorkAnalyzer()
        db = Mock()
        analysis_id = uuid4()

        result = await analyzer.analyze_scope(
            db=db,
            analysis_id=analysis_id,
            raw_text=sample_tender_text,
            use_llm=False,
        )

        assert result is not None
        assert "work_items" in result
        assert "total_effort_days" in result
        assert "item_count" in result
        assert len(result["work_items"]) > 0

    def test_section_splitting(self):
        """Test section splitting functionality"""
        analyzer = ScopeOfWorkAnalyzer()
        text = """
        1. First Section
        Some content here
        2. Second Section
        More content
        3. Third Section
        """

        sections = analyzer._split_into_sections(text)
        assert len(sections) >= 2

    def test_category_determination(self):
        """Test work item category determination"""
        analyzer = ScopeOfWorkAnalyzer()

        # Test planning category
        category = analyzer._determine_category("planning and design activities")
        assert category == "planning"

        # Test construction category
        category = analyzer._determine_category("construction and installation work")
        assert category == "construction"

        # Test testing category
        category = analyzer._determine_category("testing and quality assurance")
        assert category == "testing"

    def test_complexity_distribution(self):
        """Test complexity distribution calculation"""
        analyzer = ScopeOfWorkAnalyzer()

        items = [
            WorkItem("WI-001", "Item 1", "Desc", "cat", "low", 10),
            WorkItem("WI-002", "Item 2", "Desc", "cat", "medium", 20),
            WorkItem("WI-003", "Item 3", "Desc", "cat", "high", 30),
            WorkItem("WI-004", "Item 4", "Desc", "cat", "high", 40),
        ]

        distribution = analyzer._calculate_complexity_distribution(items)
        assert distribution["low"] == 1
        assert distribution["medium"] == 1
        assert distribution["high"] == 2


# ===== RFPSectionAnalyzer Tests =====

class TestRFPSectionAnalyzer:
    """Test RFPSectionAnalyzer service"""

    def test_analyzer_instantiates(self):
        """Test RFPSectionAnalyzer can be instantiated"""
        analyzer = RFPSectionAnalyzer()
        assert analyzer is not None

    def test_rfp_section_to_dict(self):
        """Test RFPSection conversion to dictionary"""
        section = RFPSection(
            section_number="1",
            title="Test Section",
            content="Test content",
            section_type="technical",
            requirements=["Requirement 1", "Requirement 2"],
        )

        data = section.to_dict()
        assert data["sectionNumber"] == "1"
        assert data["title"] == "Test Section"
        assert data["sectionType"] == "technical"
        assert len(data["requirements"]) == 2

    @pytest.mark.asyncio
    async def test_analyze_rfp_sections_keyword(self, sample_tender_text):
        """Test RFP section analysis with keyword fallback"""
        analyzer = RFPSectionAnalyzer()
        db = Mock()
        analysis_id = uuid4()

        result = await analyzer.analyze_rfp_sections(
            db=db,
            analysis_id=analysis_id,
            raw_text=sample_tender_text,
            use_llm=False,
        )

        assert result is not None
        assert "sections" in result
        assert "total_sections" in result
        assert "total_requirements" in result
        assert result["total_sections"] >= 1

    def test_section_type_determination(self):
        """Test section type determination"""
        analyzer = RFPSectionAnalyzer()

        # Test technical section
        section_type = analyzer._determine_section_type(
            "Technical Requirements", "Database and integration requirements"
        )
        assert section_type == "technical"

        # Test commercial section
        section_type = analyzer._determine_section_type(
            "Commercial Terms", "Payment schedule and cost breakdown"
        )
        assert section_type == "commercial"

        # Test evaluation section
        section_type = analyzer._determine_section_type(
            "Evaluation Criteria", "Selection criteria and scoring"
        )
        assert section_type == "evaluation"

    def test_requirement_extraction(self):
        """Test requirement extraction from text"""
        analyzer = RFPSectionAnalyzer()

        text = """
        Requirements:
        - Requirement 1 is important
        - Requirement 2 is also needed
        1. Third requirement
        2. Fourth requirement
        """

        requirements = analyzer._extract_requirements(text)
        assert len(requirements) > 0
        assert any("Requirement" in req for req in requirements)

    def test_section_type_distribution(self):
        """Test section type distribution"""
        analyzer = RFPSectionAnalyzer()

        sections = [
            RFPSection("1", "Tech", "content", "technical", []),
            RFPSection("2", "Comm", "content", "commercial", []),
            RFPSection("3", "Tech", "content", "technical", []),
        ]

        distribution = analyzer._get_section_types(sections)
        assert distribution["technical"] == 2
        assert distribution["commercial"] == 1


# ===== Integration Tests =====

class TestPhase3Integration:
    """Integration tests for Phase 3 services"""

    @pytest.mark.asyncio
    async def test_full_analysis_workflow(self, sample_tender_text):
        """Test complete Phase 3 analysis workflow"""
        onepager_gen = OnePagerGenerator()
        scope_analyzer = ScopeOfWorkAnalyzer()
        rfp_analyzer = RFPSectionAnalyzer()

        db = Mock()
        analysis_id = uuid4()

        # Generate onepager
        onepager = await onepager_gen.generate_onepager(
            db=db,
            analysis_id=analysis_id,
            raw_text=sample_tender_text,
            use_llm=False,
        )
        assert onepager is not None

        # Analyze scope
        scope_result = await scope_analyzer.analyze_scope(
            db=db,
            analysis_id=analysis_id,
            raw_text=sample_tender_text,
            use_llm=False,
        )
        assert scope_result["item_count"] > 0

        # Analyze RFP
        rfp_result = await rfp_analyzer.analyze_rfp_sections(
            db=db,
            analysis_id=analysis_id,
            raw_text=sample_tender_text,
            use_llm=False,
        )
        assert rfp_result["total_sections"] > 0
