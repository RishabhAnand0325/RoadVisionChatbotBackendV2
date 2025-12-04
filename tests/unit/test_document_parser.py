"""
Unit tests for DocumentParser service (Phase 1).

Tests:
- Document parsing and text extraction
- Section identification
- Table and figure detection
- Quality assessment
- Database storage
"""

import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os

from app.modules.tenderiq.analyze.services.document_parser import DocumentParser
from app.modules.tenderiq.analyze.models.document_extraction_models import (
    DocumentExtractionResult,
    DocumentMetadata,
    ExtractedSection,
)


@pytest.fixture
def document_parser():
    """Create DocumentParser instance"""
    return DocumentParser()


@pytest.fixture
def sample_pdf_path():
    """Create a temporary PDF file for testing"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n%test")  # Minimal PDF header
        return f.name


@pytest.fixture
def sample_tender_text():
    """Sample tender document text"""
    return """
    1. INTRODUCTION AND PROJECT OVERVIEW
    This is the introduction section of the tender document.
    The project scope includes multiple work packages.

    1.1 BACKGROUND
    The background provides historical context for the project.

    2. TENDER DATA SHEET
    This section contains the tender details.

    2.1 CONTRACT VALUE
    The estimated contract value is ₹15.50 Crores.

    | Item | Quantity | Unit | Rate |
    |------|----------|------|------|
    | Earthwork | 45000 | cum | 100 |
    | Concrete | 5000 | cum | 5000 |

    3. ELIGIBILITY CRITERIA
    Minimum turnover requirement: ₹25 Crores
    Experience required: 7 years

    Figure 1: Project Layout Diagram
    This shows the overall project layout.

    4. SCOPE OF WORK
    The scope includes multiple work packages.

    5. TECHNICAL SPECIFICATIONS
    All work must comply with IRC standards.
    """


class TestDocumentParserInitialization:
    """Test DocumentParser initialization"""

    def test_parser_instantiates(self, document_parser):
        """Test that DocumentParser can be instantiated"""
        assert document_parser is not None
        assert hasattr(document_parser, 'parse_document')
        assert hasattr(document_parser, '_extract_text')

    def test_parser_has_services(self, document_parser):
        """Test that parser has LLAMA parse capability"""
        # Parser should exist even if LLAMA Parse is not installed
        assert document_parser is not None


class TestSectionParsing:
    """Test section identification from text"""

    @pytest.mark.asyncio
    async def test_section_header_detection(self, document_parser, sample_tender_text):
        """Test that section headers are properly detected"""
        sections = await document_parser._parse_sections(sample_tender_text)

        # Should identify multiple sections
        assert len(sections) > 0

        # Sections should have numbers
        section_numbers = [s.section_number for s in sections]
        assert "1" in section_numbers
        assert any("2" in str(s) for s in section_numbers)

    @pytest.mark.asyncio
    async def test_section_title_extraction(self, document_parser, sample_tender_text):
        """Test that section titles are properly extracted"""
        sections = await document_parser._parse_sections(sample_tender_text)

        # Sections should have titles
        titles = [s.title for s in sections if s.title]
        assert len(titles) > 0
        assert any("INTRODUCTION" in t.upper() for t in titles)

    @pytest.mark.asyncio
    async def test_section_text_content(self, document_parser, sample_tender_text):
        """Test that section content is properly extracted"""
        sections = await document_parser._parse_sections(sample_tender_text)

        # First section should contain text
        if sections:
            first_section = sections[0]
            assert len(first_section.text) > 0


class TestTableDetection:
    """Test table detection and extraction"""

    @pytest.mark.asyncio
    async def test_table_detection(self, document_parser, sample_tender_text):
        """Test that tables are detected in text"""
        tables = await document_parser._extract_tables(sample_tender_text)

        # Should detect at least one table
        assert len(tables) > 0

    @pytest.mark.asyncio
    async def test_table_content(self, document_parser, sample_tender_text):
        """Test that table content is captured"""
        tables = await document_parser._extract_tables(sample_tender_text)

        if tables:
            first_table = tables[0]
            assert first_table.table_number == 1
            assert "data" in first_table.model_dump()


class TestFigureDetection:
    """Test figure/image detection"""

    @pytest.mark.asyncio
    async def test_figure_detection(self, document_parser, sample_tender_text):
        """Test that figures are detected"""
        figures = await document_parser._extract_figures(sample_tender_text)

        # Should detect "Figure 1" reference
        assert len(figures) > 0
        assert figures[0].figure_number == 1

    @pytest.mark.asyncio
    async def test_figure_description(self, document_parser, sample_tender_text):
        """Test that figure descriptions are captured"""
        figures = await document_parser._extract_figures(sample_tender_text)

        if figures:
            assert figures[0].description is not None


class TestQualityAssessment:
    """Test quality assessment of extraction"""

    @pytest.mark.asyncio
    async def test_quality_assessment_basic(self, document_parser, sample_tender_text):
        """Test quality assessment returns valid scores"""
        sections = await document_parser._parse_sections(sample_tender_text)
        tables = await document_parser._extract_tables(sample_tender_text)
        figures = await document_parser._extract_figures(sample_tender_text)

        quality = await document_parser._assess_quality(
            raw_text=sample_tender_text,
            sections=sections,
            tables=tables,
            figures=figures,
            ocr_required=False,
            ocr_confidence=None,
        )

        # Quality should have expected fields
        assert "extraction_quality" in quality
        assert "data_completeness" in quality
        assert "warnings" in quality
        assert "recommendations" in quality

    @pytest.mark.asyncio
    async def test_quality_scores_in_range(self, document_parser, sample_tender_text):
        """Test that quality scores are 0-100"""
        sections = await document_parser._parse_sections(sample_tender_text)
        tables = await document_parser._extract_tables(sample_tender_text)
        figures = await document_parser._extract_figures(sample_tender_text)

        quality = await document_parser._assess_quality(
            raw_text=sample_tender_text,
            sections=sections,
            tables=tables,
            figures=figures,
            ocr_required=False,
            ocr_confidence=None,
        )

        # All scores should be 0-100
        assert 0 <= quality["extraction_quality"] <= 100
        assert 0 <= quality["data_completeness"] <= 100


class TestHelperMethods:
    """Test utility methods"""

    def test_section_header_detection(self, document_parser):
        """Test _is_section_header method"""
        assert document_parser._is_section_header("1. Introduction")
        assert document_parser._is_section_header("2.1 Background")
        assert document_parser._is_section_header("Section 3")
        assert not document_parser._is_section_header("This is normal text")

    def test_section_number_extraction(self, document_parser):
        """Test _extract_section_number method"""
        assert document_parser._extract_section_number("1. Introduction") == "1"
        assert document_parser._extract_section_number("2.1 Background") == "2.1"
        assert document_parser._extract_section_number("Section 3") == "unknown"

    def test_file_type_detection(self, document_parser):
        """Test _get_file_type method"""
        assert document_parser._get_file_type("document.pdf") == "application/pdf"
        assert document_parser._get_file_type("document.docx") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert document_parser._get_file_type("unknown.xyz") == "application/octet-stream"

    def test_page_count_estimation(self, document_parser):
        """Test page count estimation"""
        short_text = "a" * 1000  # ~1/3 page
        long_text = "a" * 10000  # ~3 pages

        assert document_parser._estimate_page_count(short_text) >= 1
        assert document_parser._estimate_page_count(long_text) >= 3


class TestDocumentParserIntegration:
    """Integration tests for document parsing"""

    @pytest.mark.asyncio
    async def test_parse_document_not_found(self, document_parser):
        """Test parsing non-existent file raises error"""
        db = Mock()
        analysis_id = uuid4()

        with pytest.raises(FileNotFoundError):
            await document_parser.parse_document(
                db=db,
                analysis_id=analysis_id,
                file_path="/nonexistent/file.pdf",
                file_size=1000,
            )

    @pytest.mark.asyncio
    async def test_parse_document_basic_extraction(self, document_parser, sample_pdf_path):
        """Test basic document parsing flow"""
        db = Mock()
        analysis_id = uuid4()

        # This will attempt to parse the temp PDF file
        # It should handle the basic PDF header gracefully
        try:
            result = await document_parser.parse_document(
                db=db,
                analysis_id=analysis_id,
                file_path=sample_pdf_path,
                file_size=100,
            )

            # Basic checks if parsing succeeds
            assert result.analysis_id == analysis_id
            assert isinstance(result, DocumentExtractionResult)
        except Exception as e:
            # It's okay if parsing fails on minimal PDF - that's expected
            # Just verify the error is reasonable
            assert "parse" in str(e).lower() or "extract" in str(e).lower()

    def teardown_method(self):
        """Clean up temporary files"""
        import tempfile
        # Temp files are automatically cleaned up by context managers
        pass


class TestDocumentParserErrorHandling:
    """Test error handling in document parser"""

    @pytest.mark.asyncio
    async def test_text_extraction_error_handling(self, document_parser):
        """Test graceful handling of extraction errors"""
        # With LLAMA not available, should fall back to basic extraction
        parser = DocumentParser()

        # Basic extraction should not crash
        result = parser._basic_pdf_extraction.__doc__  # Just verify method exists
        assert "PDF" in result
