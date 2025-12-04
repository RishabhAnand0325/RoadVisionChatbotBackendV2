"""Service for fetching and transforming document templates."""
import logging
from uuid import UUID
from sqlalchemy.orm import Session

from app.modules.analyze.models.pydantic_models import DocumentTemplateSchema, TemplatesResponseSchema
from app.modules.analyze.repositories import repository as analyze_repo

logger = logging.getLogger(__name__)


def categorize_template(template_name: str, description: str = None) -> str:
    """
    Categorize template based on name and description.

    Returns one of: bid_submission_forms, financial_formats, technical_documents, compliance_formats
    """
    name_lower = template_name.lower()
    desc_lower = (description or "").lower()

    # Bid Submission Forms
    if any(keyword in name_lower or keyword in desc_lower for keyword in [
        'bid', 'submission', 'proposal', 'cover', 'letter', 'form', 'declaration', 'undertaking'
    ]):
        return 'bid_submission_forms'

    # Financial Formats
    if any(keyword in name_lower or keyword in desc_lower for keyword in [
        'financial', 'price', 'cost', 'budget', 'emd', 'earnest money', 'bank guarantee', 'bid security'
    ]):
        return 'financial_formats'

    # Technical Documents
    if any(keyword in name_lower or keyword in desc_lower for keyword in [
        'technical', 'specification', 'drawing', 'design', 'methodology', 'work plan', 'schedule'
    ]):
        return 'technical_documents'

    # Compliance Formats (default)
    return 'compliance_formats'


def get_templates(db: Session, analysis_id: UUID) -> TemplatesResponseSchema:
    """
    Fetch all document templates for an analysis and group them by category.

    Args:
        db: Database session
        analysis_id: UUID of the tender analysis

    Returns:
        TemplatesResponseSchema with templates grouped by category
    """
    try:
        # Fetch all templates from database
        templates = analyze_repo.get_document_templates(db, analysis_id)

        # Initialize categorized lists
        categorized = {
            'bid_submission_forms': [],
            'financial_formats': [],
            'technical_documents': [],
            'compliance_formats': []
        }

        # Categorize each template
        for template in templates:
            # Determine format from required_format field
            format_type = 'pdf'
            if template.required_format:
                format_lower = template.required_format.lower()
                if 'excel' in format_lower or 'xlsx' in format_lower or 'xls' in format_lower:
                    format_type = 'excel'
                elif 'word' in format_lower or 'docx' in format_lower or 'doc' in format_lower:
                    format_type = 'word'
                elif 'dwg' in format_lower or 'autocad' in format_lower:
                    format_type = 'dwg'

            # Determine if mandatory (default to True if not specified)
            # You can add logic here based on template name/description
            is_mandatory = 'optional' not in (template.description or "").lower()

            # Extract annex/reference from file_reference or page_references
            annex = template.file_reference or ""
            if not annex and template.page_references:
                annex = f"Page {', '.join(map(str, template.page_references))}"

            # Create template schema
            template_schema = DocumentTemplateSchema(
                id=str(template.id),
                name=template.template_name,
                description=template.description,
                format=format_type,
                mandatory=is_mandatory,
                annex=annex
            )

            # Categorize and add to appropriate list
            category = categorize_template(template.template_name, template.description)
            categorized[category].append(template_schema)

        logger.info(f"Fetched {len(templates)} templates for analysis {analysis_id}")

        return TemplatesResponseSchema(
            bid_submission_forms=categorized['bid_submission_forms'],
            financial_formats=categorized['financial_formats'],
            technical_documents=categorized['technical_documents'],
            compliance_formats=categorized['compliance_formats']
        )

    except Exception as e:
        logger.error(f"Error fetching templates for analysis {analysis_id}: {e}", exc_info=True)
        # Return empty response instead of raising
        return TemplatesResponseSchema(
            bid_submission_forms=[],
            financial_formats=[],
            technical_documents=[],
            compliance_formats=[]
        )
