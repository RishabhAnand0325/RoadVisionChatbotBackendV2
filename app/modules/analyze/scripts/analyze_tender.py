import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

import requests
from sqlalchemy.orm import Session
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

from app.modules.scraper.db.schema import ScrapedTender, ScrapedTenderFile
from app.modules.tenderiq.db.schema import Tender
from app.modules.analyze.db.schema import TenderAnalysis, AnalysisStatusEnum
from app.modules.analyze.models.pydantic_models import (
    OnePagerSchema,
    ScopeOfWorkSchema,
    DataSheetSchema,
)
from app.core.services import llm_model, vector_store, embedding_model

logger = logging.getLogger(__name__)


def analyze_tender(db: Session, tdr: str):
    """
    Comprehensive tender analysis pipeline.
    
    Fetches tender data, downloads documents, extracts text, creates embeddings,
    stores in vector database, and generates semantic analysis using LLM.
    
    Args:
        db: Database session
        tdr: Tender reference number (e.g., "51655667")
    
    Returns:
        None (updates TenderAnalysis table)
    """
    try:
        logger.info(f"Fetching tender data for TDR: {tdr}")

        tender = db.query(Tender).filter(Tender.tender_ref_number == tdr).first()
        scraped_tender = db.query(ScrapedTender).filter(
            ScrapedTender.tender_id_str == tdr
        ).first()

        if not tender or not scraped_tender:
            logger.error(f"Tender {tdr} not found in database")
            return

        logger.info(f"Found tender: {scraped_tender.tender_name}")

        analysis = db.query(TenderAnalysis).filter(
            TenderAnalysis.tender_id == tdr
        ).first()
        if not analysis:
            analysis = TenderAnalysis(
                id=uuid4(),
                tender_id=tdr,
                status=AnalysisStatusEnum.pending
            )
            db.add(analysis)
            db.commit()

        analysis.status = AnalysisStatusEnum.parsing
        analysis.status_message = "Initializing tender analysis"
        analysis.analysis_started_at = datetime.utcnow()
        db.commit()

        logger.info("Fetching associated files")

        files = db.query(ScrapedTenderFile).filter(
            ScrapedTenderFile.tender_id == scraped_tender.id
        ).all()

        if not files:
            logger.warning(f"No files found for tender {tdr}")
            analysis.error_message = "No files found for this tender"
            analysis.status = AnalysisStatusEnum.failed
            db.commit()
            return

        logger.info(f"Found {len(files)} files")

        logger.info("Downloading files to temporary storage")

        temp_dir = Path(f"/tmp/tender_analysis_{tdr}_{uuid4()}")
        temp_dir.mkdir(parents=True, exist_ok=True)

        downloaded_files: List[Path] = []
        for file in files:
            try:
                response = requests.get(file.file_url, timeout=30)
                if response.status_code == 200:
                    file_path = temp_dir / file.file_name
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    downloaded_files.append(file_path)
                    logger.info(f"Downloaded: {file.file_name}")
            except Exception as e:
                logger.error(f"Failed to download {file.file_name}: {e}")

        if not downloaded_files:
            logger.error("No files were successfully downloaded")
            analysis.error_message = "Failed to download any files"
            analysis.status = AnalysisStatusEnum.failed
            db.commit()
            return

        logger.info("Extracting text from files")

        all_text = ""
        for file_path in downloaded_files:
            try:
                if file_path.suffix.lower() == '.pdf':
                    reader = PdfReader(file_path)
                    text = "\n".join(
                        [page.extract_text() for page in reader.pages if page.extract_text()]
                    )
                    all_text += f"\n--- {file_path.name} ---\n{text}\n"
                    logger.info(f"Extracted text from PDF: {file_path.name}")
                elif file_path.suffix.lower() in ['.html', '.htm']:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        soup = BeautifulSoup(f.read(), 'html.parser')
                        text = soup.get_text()
                        all_text += f"\n--- {file_path.name} ---\n{text}\n"
                    logger.info(f"Extracted text from HTML: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to extract text from {file_path.name}: {e}")

        if not all_text:
            logger.error("No text was extracted from any file")
            analysis.error_message = "Failed to extract text from files"
            analysis.status = AnalysisStatusEnum.failed
            db.commit()
            return

        logger.info(f"Extracted {len(all_text)} characters total")
        analysis.progress = 50
        analysis.status_message = "Text extraction complete, creating embeddings"
        db.commit()

        logger.info("Creating text chunks and embeddings")

        chunks = _chunk_text(all_text, chunk_size=1000, overlap=100)
        embeddings = [embedding_model.encode(chunk) for chunk in chunks]

        logger.info(f"Created {len(embeddings)} embeddings")
        analysis.progress = 60
        db.commit()

        logger.info("Storing embeddings in vector database")

        if vector_store:
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                try:
                    vector_store.add_text(
                        text=chunk,
                        embedding=embedding,
                        metadata={
                            "tender_id": tdr,
                            "tender_name": scraped_tender.tender_name,
                            "chunk_index": idx,
                            "type": "tender_document"
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to store chunk {idx}: {e}")
            logger.info("Stored all embeddings in vector database")
        else:
            logger.warning("Vector store not available, skipping storage")

        analysis.progress = 70
        analysis.status_message = "Vector storage complete, generating semantic analysis"
        db.commit()

        logger.info("Starting semantic analysis")

        tender_context = _build_tender_context(tender, scraped_tender, all_text)

        logger.info("Generating executive summary")
        one_pager = _generate_executive_summary(tender_context)
        if one_pager:
            analysis.one_pager_json = one_pager

        analysis.progress = 75
        db.commit()

        logger.info("Generating scope of work")
        scope_of_work = _generate_scope_of_work_details(tender_context, scraped_tender)
        if scope_of_work:
            analysis.scope_of_work_json = scope_of_work

        analysis.progress = 85
        db.commit()

        logger.info("Generating comprehensive datasheet")
        data_sheet = _generate_comprehensive_datasheet(tender_context, scraped_tender)
        if data_sheet:
            analysis.data_sheet_json = data_sheet

        analysis.progress = 95
        db.commit()

        analysis.status = AnalysisStatusEnum.completed
        analysis.progress = 100
        analysis.status_message = "Analysis completed successfully"
        analysis.analysis_completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Analysis completed for tender {tdr}")

        shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        logger.error(f"Error analyzing tender {tdr}: {e}", exc_info=True)
        if 'analysis' in locals():
            analysis.status = AnalysisStatusEnum.failed
            analysis.error_message = str(e)
            db.commit()


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _build_tender_context(tender, scraped_tender, all_text: str) -> str:
    """Build comprehensive context for LLM analysis."""
    return f"""
    TENDER INFORMATION:
    Tender ID: {scraped_tender.tender_id_str}
    Tender Name: {scraped_tender.tender_name}
    Tendering Authority: {scraped_tender.tendering_authority}
    State: {scraped_tender.state}
    Tender Value: {scraped_tender.tender_value}
    EMD/Bid Security: {scraped_tender.emd}
    Tender Type: {scraped_tender.tender_type}
    Bidding Type: {scraped_tender.bidding_type}
    Publication Date: {scraped_tender.publish_date}
    Due Date: {scraped_tender.due_date}
    Tender Opening Date: {scraped_tender.tender_opening_date}

    EXTRACTED DOCUMENT CONTENT:
    {all_text[:40000]}
    """


def _generate_executive_summary(context: str) -> Optional[dict]:
    """Generate OnePager summary using LLM."""
    try:
        prompt = f"""Based on the tender document, generate a structured executive summary in JSON format.
                            
                    Respond ONLY with valid JSON. Structure:
                    {{
                        "project_overview": "2-3 sentence executive summary of the project/tender",
                        "eligibility_highlights": ["criterion 1", "criterion 2", "criterion 3"],
                        "important_dates": ["submission deadline: DD-MM-YYYY", "tender opening: DD-MM-YYYY"],
                        "financial_requirements": ["EMD amount and terms", "document fees if any"],
                        "risk_analysis": {{
                            "high_risk_factors": ["factor1", "factor2"],
                            "low_risk_areas": ["area1", "area2"],
                            "compliance_concerns": ["concern1"]
                        }}
                    }}

CONTEXT:
{context}

Generate JSON:"""
        
        response = llm_model.generate_content(prompt)
        response_text = response.text.strip()
        
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```"):
            response_text = response_text[3:-3].strip()
        
        result = json.loads(response_text)
        validated = OnePagerSchema(**result)
        return validated.model_dump()
        
    except Exception as e:
        logger.error(f"Error generating executive summary: {e}")
        return None


def _generate_scope_of_work_details(context: str, scraped_tender) -> Optional[dict]:
    """Generate scope of work details using LLM."""
    try:
        prompt = f"""Based on the tender document, extract and structure the scope of work in JSON format.
        
Respond ONLY with valid JSON. Structure:
{{
    "project_overview": {{
        "name": "Project name/title",
        "location": "Project location/address",
        "total_length": "length in km if applicable",
        "duration": "project duration/timeline",
        "value": "total project value with currency"
    }},
    "major_work_components": [
        "Component 1: description",
        "Component 2: description"
    ],
    "technical_standards_and_specifications": [
        "Standard/Spec 1",
        "Standard/Spec 2"
    ]
}}

CONTEXT:
{context}

Generate JSON:"""
        
        response = llm_model.generate_content(prompt)
        response_text = response.text.strip()
        
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```"):
            response_text = response_text[3:-3].strip()
        
        result = json.loads(response_text)
        validated = ScopeOfWorkSchema(**result)
        return validated.model_dump()
        
    except Exception as e:
        logger.error(f"Error generating scope of work: {e}")
        return None


def _generate_comprehensive_datasheet(context: str, scraped_tender) -> Optional[dict]:
    """Generate comprehensive datasheet using LLM."""
    try:
        prompt = f"""Based on the tender document, create a comprehensive datasheet in JSON format.
        
Respond ONLY with valid JSON. Structure:
{{
    "key_tender_details": {{
        "tender_id": "Tender reference number",
        "tender_category": "Category of tender",
        "tendering_authority": "Authority name",
        "skills_required": ["skill1", "skill2"],
        "experience_level": "Junior/Mid/Senior",
        "team_size_required": "Number of resources",
        "compliance_requirements": ["requirement1"]
    }},
    "financial_summary": {{
        "total_tender_value": "Value in INR",
        "estimated_monthly_cost": "Cost if known",
        "bid_security_amount": "EMD amount",
        "payment_terms": "Payment terms",
        "currency": "INR"
    }},
    "timeline": {{
        "publish_date": "Publication date",
        "submission_deadline": "Bid submission deadline",
        "tender_opening_date": "Bid opening date",
        "pre_bid_meeting_date": "Pre-bid date if any",
        "project_duration": "Total duration",
        "expected_start_date": "Start date"
    }}
}}

CONTEXT:
{context}

Generate JSON:"""
        
        response = llm_model.generate_content(prompt)
        response_text = response.text.strip()
        
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```"):
            response_text = response_text[3:-3].strip()
        
        result = json.loads(response_text)
        validated = DataSheetSchema(**result)
        return validated.model_dump()
        
    except Exception as e:
        logger.error(f"Error generating datasheet: {e}")