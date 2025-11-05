"""
Report Generation Service

Generates one-pagers and data sheets from analysis results.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository
from app.modules.tenderiq.analyze.models.pydantic_models import (
    OnePagerResponse,
    DataSheetResponse,
    DataSheetContentResponse,
    BasicInfoResponse,
    FinancialInfoResponse,
    TemporalInfoResponse,
    ScopeInfoResponse,
    AnalysisInfoResponse,
)


class ReportGenerationService:
    """Service for generating reports from analysis results"""

    def __init__(self):
        pass

    def generate_one_pager(
        self,
        db: Session,
        analysis_id: UUID,
        tender_id: UUID,
        format: str = "markdown",
        include_risk_assessment: bool = True,
        include_scope_of_work: bool = True,
        include_financials: bool = True,
        max_length: int = 800,
    ) -> OnePagerResponse:
        """
        Generate a one-page executive summary of the analysis.

        Args:
            db: Database session
            analysis_id: Analysis record ID
            tender_id: Tender ID
            format: Output format: "markdown", "html", or "pdf"
            include_risk_assessment: Include risk summary
            include_scope_of_work: Include scope summary
            include_financials: Include financial information
            max_length: Maximum word count

        Returns:
            OnePagerResponse with generated document
        """
        repo = AnalyzeRepository(db)

        # TODO: Fetch analysis results from repo
        # TODO: Fetch tender data from ScrapedTender table
        # For now, generate sample one-pager

        one_pager_content = self._generate_sample_one_pager(
            tender_id=tender_id,
            include_risk=include_risk_assessment,
            include_scope=include_scope_of_work,
            include_financial=include_financials,
        )

        # Format the content
        formatted_content = self.format_for_output(one_pager_content, format)

        return OnePagerResponse(
            tender_id=tender_id,
            one_pager={
                "content": formatted_content,
                "format": format,
                "generatedAt": datetime.utcnow().isoformat(),
            },
        )

    def generate_data_sheet(
        self,
        db: Session,
        tender_id: UUID,
        format: str = "json",
        include_analysis: bool = True,
    ) -> DataSheetResponse:
        """
        Generate a structured data sheet with key tender information.

        Args:
            db: Database session
            tender_id: Tender ID
            format: Output format: "json", "csv", or "excel"
            include_analysis: Include analysis results in sheet

        Returns:
            DataSheetResponse with generated data sheet
        """
        # TODO: Fetch tender data from ScrapedTender
        # TODO: Fetch analysis results if include_analysis=True

        # Sample tender and analysis data
        basic_info = BasicInfoResponse(
            tender_number="TEN-2024-001",
            tender_name="Cloud Infrastructure Migration Project",
            tendering_authority="Ministry of Technology",
            tender_url="https://example.com/tender/001",
        )

        financial_info = FinancialInfoResponse(
            estimated_value=5000000.0,
            currency="INR",
            emd=250000.0,
            bid_security_required=True,
        )

        temporal_info = TemporalInfoResponse(
            release_date="2024-11-01",
            due_date="2024-12-15",
            opening_date="2024-12-20",
        )

        scope_info = ScopeInfoResponse(
            location="New Delhi",
            category="Cloud Services",
            description="Migrate legacy infrastructure to cloud with minimal downtime",
        )

        analysis_info = None
        if include_analysis:
            analysis_info = AnalysisInfoResponse(
                risk_level="medium",
                estimated_effort=120,
                complexity_level="high",
            )

        data_sheet = DataSheetContentResponse(
            basic_info=basic_info,
            financial_info=financial_info,
            temporal=temporal_info,
            scope=scope_info,
            analysis=analysis_info,
        )

        return DataSheetResponse(
            tender_id=tender_id,
            data_sheet=data_sheet,
            generated_at=datetime.utcnow(),
        )

    def format_for_output(
        self,
        content: str,
        format: str = "markdown",
    ) -> str:
        """
        Convert content to desired output format.

        Args:
            content: Content to format
            format: Target format: "markdown", "html", or "pdf"

        Returns:
            Formatted content
        """
        if format == "markdown":
            return content
        elif format == "html":
            return self._markdown_to_html(content)
        elif format == "pdf":
            # TODO: Use library like reportlab or weasyprint
            return content  # For now, return markdown
        else:
            return content

    # ==================== Helper Methods ====================

    def _generate_sample_one_pager(
        self,
        tender_id: UUID,
        include_risk: bool = True,
        include_scope: bool = True,
        include_financial: bool = True,
    ) -> str:
        """Generate sample one-pager content in markdown"""
        lines = [
            "# Tender Analysis Executive Summary",
            f"\n**Tender ID:** {tender_id}",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "\n## Overview",
            "Cloud Infrastructure Migration Project for Ministry of Technology.",
            "Estimated project duration: 120 days with high complexity level.",
        ]

        if include_financial:
            lines.extend([
                "\n## Financial Summary",
                "- **Estimated Value:** ₹50,00,000",
                "- **EMD:** ₹2,50,000",
                "- **Budget Security:** Required",
            ])

        if include_scope:
            lines.extend([
                "\n## Scope of Work",
                "- Design cloud architecture (3-4 weeks)",
                "- Migrate legacy systems (4-5 weeks)",
                "- Performance optimization (2-3 weeks)",
                "- Testing and UAT (2-3 weeks)",
                "- Go-live support (1-2 weeks)",
            ])

        if include_risk:
            lines.extend([
                "\n## Key Risks",
                "- **Critical:** Complex system integration required",
                "- **High:** Tight timeline for migration window",
                "- **Medium:** Resource availability during peak periods",
                "\n**Risk Score:** 65/100 (Medium-High Risk)",
            ])

        lines.extend([
            "\n## Recommendations",
            "1. Establish dedicated project team with DevOps expertise",
            "2. Create detailed migration plan with rollback procedures",
            "3. Schedule regular stakeholder reviews and risk assessments",
            "4. Plan adequate testing and validation phases",
            "\n---",
            "*This is an automated analysis. Please review with domain experts.*",
        ])

        return "\n".join(lines)

    def _markdown_to_html(self, markdown_content: str) -> str:
        """
        Convert markdown to basic HTML.

        TODO: Use markdown library for proper conversion.

        Args:
            markdown_content: Markdown formatted string

        Returns:
            Basic HTML string
        """
        html = "<html><body>\n"

        lines = markdown_content.split("\n")
        for line in lines:
            if line.startswith("# "):
                html += f"<h1>{line[2:]}</h1>\n"
            elif line.startswith("## "):
                html += f"<h2>{line[3:]}</h2>\n"
            elif line.startswith("### "):
                html += f"<h3>{line[4:]}</h3>\n"
            elif line.startswith("- "):
                html += f"<li>{line[2:]}</li>\n"
            elif line.startswith("**") and line.endswith("**"):
                content = line[2:-2]
                html += f"<strong>{content}</strong>\n"
            elif line.startswith("*") and line.endswith("*"):
                content = line[1:-1]
                html += f"<em>{content}</em>\n"
            elif line.strip() == "---":
                html += "<hr/>\n"
            elif line.strip():
                html += f"<p>{line}</p>\n"

        html += "\n</body></html>"
        return html

    def _format_markdown_one_pager(
        self,
        title: str,
        sections: Dict[str, Any],
    ) -> str:
        """
        Format one-pager content as markdown.

        Args:
            title: Document title
            sections: Dict of section_name -> content

        Returns:
            Markdown formatted string
        """
        lines = [f"# {title}", ""]

        for section_name, section_content in sections.items():
            lines.append(f"## {section_name}")
            if isinstance(section_content, dict):
                for key, value in section_content.items():
                    lines.append(f"- **{key}:** {value}")
            elif isinstance(section_content, list):
                for item in section_content:
                    lines.append(f"- {item}")
            else:
                lines.append(str(section_content))
            lines.append("")

        return "\n".join(lines)

    def _format_markdown_data_sheet(
        self,
        tender_data: Dict[str, Any],
        analysis_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Format data sheet content as markdown table.

        Args:
            tender_data: Basic tender information
            analysis_data: Analysis results (optional)

        Returns:
            Markdown formatted string with table
        """
        lines = ["# Tender Data Sheet", ""]

        # Create markdown table
        lines.append("| Property | Value |")
        lines.append("|----------|-------|")

        # Add tender data rows
        for key, value in tender_data.items():
            lines.append(f"| {key} | {value} |")

        if analysis_data:
            lines.append("")
            lines.append("## Analysis Results")
            lines.append("")
            for key, value in analysis_data.items():
                lines.append(f"| {key} | {value} |")

        return "\n".join(lines)
