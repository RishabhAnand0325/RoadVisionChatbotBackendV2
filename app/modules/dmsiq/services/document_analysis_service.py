import json
import logging
from datetime import datetime
from uuid import UUID
from typing import Dict, Any, Optional
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.services import get_llm_model, get_pdf_processor, get_excel_processor
from app.modules.dmsiq.services.dms_service import DmsService
from app.modules.dmsiq.models.pydantic_models import AISummary, KeyEntities, ImportantDate

logger = logging.getLogger(__name__)

class DocumentAnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self.dms_service = DmsService(db)

    def _extract_text(self, file_path: Path, mime_type: str) -> str:
        """Extract text from document based on file type."""
        file_ext = file_path.suffix.lower()
        
        try:
            if file_ext == '.pdf':
                processor = get_pdf_processor()
                # We use a dummy job_id and doc_id since we just want text
                chunks, _ = processor.process_pdf(
                    job_id="analysis_request", 
                    pdf_path=str(file_path), 
                    doc_id="temp", 
                    filename=file_path.name
                )
                return "\n".join([c['content'] for c in chunks])
            
            elif file_ext in ['.xlsx', '.xls']:
                processor = get_excel_processor()
                chunks, _ = processor.process_excel(
                    job_id="analysis_request",
                    excel_path=str(file_path),
                    doc_id="temp",
                    filename=file_path.name
                )
                return "\n".join([c['content'] for c in chunks])
            
            else:
                # Fallback for text files
                with open(file_path, 'r', errors='ignore') as f:
                    return f.read()
                    
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            raise ValueError(f"Failed to extract text from document: {e}")

    async def analyze_document(self, document_id: UUID) -> AISummary:
        """
        Analyze a document using Gemini to generate a structured summary.
        """
        try:
            # 1. Get document file path
            file_path, filename = self.dms_service.get_document_for_download(document_id)
            document = self.dms_service.get_document(document_id)
            
            if not file_path.exists():
                raise ValueError(f"File not found at path: {file_path}")

            # 2. Extract text
            logger.info(f"Extracting text from {filename}...")
            text_content = self._extract_text(file_path, document.mime_type)
            
            if not text_content:
                raise ValueError("No text content could be extracted from the document")

            # Truncate if too long (approx 30k tokens for safety, though Gemini handles more)
            # 1 token ~= 4 chars
            max_chars = 120000 
            if len(text_content) > max_chars:
                text_content = text_content[:max_chars] + "...[truncated]"

            # 3. Construct Prompt
            prompt = f"""
            You are an expert legal and business document analyst. Analyze the following document text and provide a structured summary in JSON format.

            DOCUMENT TEXT:
            {text_content}

            OUTPUT FORMAT (JSON ONLY):
            {{
                "documentType": "Contract | Invoice | Report | Proposal | Other",
                "keyTopic": "Brief 3-5 word topic",
                "language": "English",
                "executiveSummary": "Concise 2-3 sentence summary of the document's purpose and main content.",
                "keyInformation": {{
                    "Contract Value": "$X,XXX or N/A",
                    "Effective Date": "YYYY-MM-DD or N/A",
                    "Duration": "X months/years or N/A",
                    "Payment Terms": "Brief description or N/A"
                }},
                "importantDates": [
                    {{ "date": "YYYY-MM-DD", "description": "Event description" }}
                ],
                "keyEntities": {{
                    "organizations": ["Org 1", "Org 2"],
                    "people": ["Person 1", "Person 2"],
                    "locations": ["Location 1", "Location 2"]
                }},
                "riskFlags": ["Risk 1", "Risk 2"],
                "tags": ["Tag 1", "Tag 2"],
                "confidenceScore": 0.95
            }}
            
            Ensure the output is valid JSON. Do not include markdown formatting like ```json ... ```.
            """

            # 4. Call Gemini
            logger.info(f"Sending analysis request to Gemini for {document_id}")
            llm = get_llm_model()
            response = llm.generate_content(prompt)
            
            response_text = response.text
            # Clean up potential markdown code blocks
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()

            # 5. Parse JSON
            data = json.loads(response_text)
            
            # Add generated metadata
            data['generatedAt'] = datetime.utcnow().isoformat()
            
            # Validate with Pydantic
            summary = AISummary(**data)
            
            return summary

        except Exception as e:
            logger.error(f"Error analyzing document {document_id}: {e}", exc_info=True)
            # Return a fallback error summary or re-raise
            raise ValueError(f"Document analysis failed: {str(e)}")
