"""
Unit tests for TenderInfoExtractor service (Phase 2).

Tests:
- Tender information extraction (LLM and keyword-based)
- Financial information extraction
- Confidence scoring
- Error handling and fallbacks
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime

from app.modules.tenderiq.analyze.services.tender_info_extractor import TenderInfoExtractor
from app.modules.tenderiq.analyze.models.structured_extraction_models import (
    TenderInfo,
    FinancialRequirements,
    MoneyAmount,
    TenderType,
    TenderStatus,
    Currency,
)


@pytest.fixture
def extractor():
    """Create TenderInfoExtractor instance"""
    return TenderInfoExtractor()


@pytest.fixture
def sample_tender_text():
    """Sample tender document text"""
    return """
    TENDER REFERENCE: PWD/NH-44/2024/ROAD/001

    TENDER FOR CONSTRUCTION AND MAINTENANCE OF NH-44 HIGHWAY PROJECT

    Issued by: Public Works Department, Government of Karnataka
    Department: PWD Karnataka

    Estimated Contract Value: ₹15.50 Crores

    Category: Road Construction
    Sub-Category: Highway
    Tender Type: Open
    Status: Active

    Location: Karnataka, Bangalore Urban District

    KEY FINANCIAL REQUIREMENTS:
    - Earnest Money Deposit (EMD): ₹31.00 Lakhs (2% of contract value)
    - Performance Bank Guarantee: ₹1.55 Crores (10% of contract value)
    - Tender Document Fee: ₹25,000
    - Processing Fee: ₹5,000

    ELIGIBILITY CRITERIA:
    - Minimum Experience: 7 years in road construction
    - Minimum Turnover: ₹25.00 Crores
    - Similar Projects: 2 projects of minimum ₹10 Crores in last 5 years

    Important Dates:
    - Published Date: 2024-03-15
    - Submission Deadline: 2024-04-25 5:00 PM
    - Technical Bid Opening: 2024-04-26 11:00 AM
    - Financial Bid Opening: 2024-05-05 11:00 AM

    PROJECT OVERVIEW:
    Construction and maintenance of a 25 km stretch of National Highway-44.
    The project includes 2 major flyovers, comprehensive drainage system,
    and safety barriers. Modern traffic management systems will be installed.

    Project Duration: 24 months
    """


class TestTenderInfoExtractorInitialization:
    """Test TenderInfoExtractor initialization"""

    def test_extractor_instantiates(self, extractor):
        """Test that TenderInfoExtractor can be instantiated"""
        assert extractor is not None

    def test_extractor_has_methods(self, extractor):
        """Test that extractor has required methods"""
        assert hasattr(extractor, 'extract_tender_info')
        assert hasattr(extractor, 'extract_financial_info')
        assert callable(extractor.extract_tender_info)
        assert callable(extractor.extract_financial_info)


class TestKeywordExtraction:
    """Test keyword-based extraction methods"""

    def test_extract_reference_number(self, extractor, sample_tender_text):
        """Test reference number extraction"""
        ref_num = extractor._extract_reference_number(sample_tender_text)
        assert ref_num is not None
        assert "PWD" in ref_num or "NH-44" in ref_num

    def test_extract_title(self, extractor, sample_tender_text):
        """Test title extraction"""
        title = extractor._extract_title(sample_tender_text)
        assert title is not None
        assert len(title) > 10
        # Check case-insensitively
        assert "construction" in title.lower() or "highway" in title.lower()

    def test_extract_organization(self, extractor, sample_tender_text):
        """Test organization extraction"""
        org = extractor._extract_organization(sample_tender_text)
        assert org is not None
        assert len(org) > 0

    def test_extract_category(self, extractor, sample_tender_text):
        """Test category extraction"""
        category = extractor._extract_category(sample_tender_text)
        assert category is not None
        assert "Road" in category or "Construction" in category

    def test_extract_estimated_value(self, extractor, sample_tender_text):
        """Test contract value extraction"""
        value = extractor._extract_estimated_value(sample_tender_text)
        assert value is not None
        assert isinstance(value, MoneyAmount)
        assert value.amount > 0
        assert "15" in str(value.amount) or "1550" in str(value.amount)

    def test_extract_emd_amount(self, extractor, sample_tender_text):
        """Test EMD amount extraction"""
        emd = extractor._extract_emd_amount(sample_tender_text)
        assert emd is not None
        assert emd.amount > 0
        assert "31" in str(emd.amount)

    def test_extract_emd_percentage(self, extractor, sample_tender_text):
        """Test EMD percentage extraction"""
        percentage = extractor._extract_emd_percentage(sample_tender_text)
        assert percentage is not None
        assert percentage == 2.0

    def test_extract_pbg_amount(self, extractor, sample_tender_text):
        """Test PBG amount extraction"""
        pbg = extractor._extract_pbg_amount(sample_tender_text)
        assert pbg is not None
        assert pbg.amount > 0

    def test_extract_pbg_percentage(self, extractor, sample_tender_text):
        """Test PBG percentage extraction"""
        percentage = extractor._extract_pbg_percentage(sample_tender_text)
        assert percentage is not None
        assert percentage == 10.0


class TestConfidenceCalculation:
    """Test confidence score calculation"""

    @pytest.mark.asyncio
    async def test_confidence_calculation_good_extraction(self, extractor):
        """Test confidence score for good extraction"""
        tender_info = await extractor._extract_with_keywords(
            "Reference: PWD/001 Title: Highway Construction issued by PWD ₹1550 Lakhs"
        )
        confidence = extractor._calculate_confidence(tender_info)
        assert confidence > 50.0
        assert confidence <= 100.0

    @pytest.mark.asyncio
    async def test_confidence_calculation_minimal_extraction(self, extractor):
        """Test confidence score for minimal extraction"""
        tender_info = await extractor._extract_with_keywords("Some random text")
        confidence = extractor._calculate_confidence(tender_info)
        assert confidence >= 50.0  # Base confidence
        assert confidence <= 100.0

    def test_financial_confidence_calculation(self, extractor):
        """Test financial confidence calculation"""
        financial = FinancialRequirements(
            contractValue=MoneyAmount(
                amount=1550,
                currency=Currency.INR,
                displayText="₹15.50 Cr"
            ),
            emdAmount=MoneyAmount(
                amount=31,
                currency=Currency.INR,
                displayText="₹31 L"
            ),
            extractionConfidence=50.0,
        )
        confidence = extractor._calculate_financial_confidence(financial)
        assert confidence > 50.0
        assert confidence <= 100.0


class TestAsyncExtraction:
    """Test async extraction methods"""

    @pytest.mark.asyncio
    async def test_extract_tender_info_keyword_fallback(self, extractor, sample_tender_text):
        """Test tender info extraction with keyword fallback"""
        db = Mock()
        analysis_id = uuid4()

        tender_info = await extractor.extract_tender_info(
            db=db,
            analysis_id=analysis_id,
            raw_text=sample_tender_text,
            use_llm=False,  # Force keyword extraction
        )

        assert tender_info is not None
        assert isinstance(tender_info, TenderInfo)
        assert tender_info.referenceNumber is not None
        assert tender_info.title is not None
        assert tender_info.estimatedValue.amount > 0
        assert tender_info.extractionConfidence >= 50.0

    @pytest.mark.asyncio
    async def test_extract_financial_info_keyword_fallback(self, extractor, sample_tender_text):
        """Test financial extraction with keyword fallback"""
        financial = await extractor.extract_financial_info(
            raw_text=sample_tender_text,
            use_llm=False,
        )

        assert financial is not None
        assert isinstance(financial, FinancialRequirements)
        assert financial.contractValue.amount > 0
        assert financial.emdAmount is not None
        assert financial.emdAmount.amount > 0
        assert financial.extractionConfidence >= 50.0

    @pytest.mark.asyncio
    async def test_extract_tender_info_empty_text(self, extractor):
        """Test extraction with empty text"""
        db = Mock()
        analysis_id = uuid4()

        tender_info = await extractor.extract_tender_info(
            db=db,
            analysis_id=analysis_id,
            raw_text="",
            use_llm=False,
        )

        assert tender_info is not None
        # Should still return a valid object with default values
        assert tender_info.referenceNumber is not None


class TestPromptBuilding:
    """Test prompt construction for LLM"""

    def test_tender_extraction_prompt_building(self, extractor, sample_tender_text):
        """Test that tender extraction prompt is built correctly"""
        prompt = extractor._build_tender_extraction_prompt(sample_tender_text)
        assert prompt is not None
        assert "JSON" in prompt
        assert "referenceNumber" in prompt
        assert "title" in prompt
        assert "estimatedValue" in prompt

    def test_financial_extraction_prompt_building(self, extractor, sample_tender_text):
        """Test that financial extraction prompt is built correctly"""
        prompt = extractor._build_financial_extraction_prompt(sample_tender_text)
        assert prompt is not None
        assert "JSON" in prompt
        assert "contractValue" in prompt
        assert "emdAmount" in prompt


class TestDataBuilding:
    """Test data building from extracted dictionaries"""

    def test_build_tender_info_from_dict(self, extractor):
        """Test building TenderInfo from dictionary"""
        data = {
            "referenceNumber": "PWD/001",
            "title": "Highway Construction",
            "issuingOrganization": "PWD",
            "category": "Road",
            "tenderType": "open",
            "status": "active",
            "estimatedValue": {
                "amount": 1550,
                "currency": "INR",
                "displayText": "₹15.50 Cr"
            },
        }

        tender_info = extractor._build_tender_info_from_dict(data)
        assert tender_info.referenceNumber == "PWD/001"
        assert tender_info.title == "Highway Construction"
        assert tender_info.tenderType == TenderType.OPEN
        assert tender_info.extractionConfidence == 85.0

    def test_build_financial_requirements_from_dict(self, extractor):
        """Test building FinancialRequirements from dictionary"""
        data = {
            "contractValue": {
                "amount": 1550,
                "currency": "INR",
                "displayText": "₹15.50 Cr"
            },
            "emdAmount": {
                "amount": 31,
                "currency": "INR",
                "displayText": "₹31 L"
            },
            "emdPercentage": 2.0,
        }

        financial = extractor._build_financial_requirements_from_dict(data)
        assert financial.contractValue.amount == 1550
        assert financial.emdAmount.amount == 31
        assert financial.emdPercentage == 2.0
        assert financial.extractionConfidence == 85.0


class TestErrorHandling:
    """Test error handling in extraction"""

    @pytest.mark.asyncio
    async def test_extraction_error_handling(self, extractor):
        """Test that extraction handles errors gracefully"""
        db = Mock()
        analysis_id = uuid4()

        # Should not raise, but return valid default object
        tender_info = await extractor.extract_tender_info(
            db=db,
            analysis_id=analysis_id,
            raw_text="Some random unstructured text",
            use_llm=False,
        )

        assert tender_info is not None
        assert isinstance(tender_info, TenderInfo)
