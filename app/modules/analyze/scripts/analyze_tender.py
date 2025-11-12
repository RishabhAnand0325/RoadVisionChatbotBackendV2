import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

import requests
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup

from app.modules.askai.services.document_service import PDFProcessor 
from app.modules.scraper.db.schema import ScrapedTender, ScrapedTenderFile
from app.modules.tenderiq.db.schema import Tender
from app.modules.analyze.db.schema import TenderAnalysis, AnalysisStatusEnum
from app.modules.analyze.models.pydantic_models import (
    OnePagerSchema,
    ScopeOfWorkSchema,
    DataSheetSchema,
)
from app.core.services import llm_model, vector_store, embedding_model, tokenizer, pdf_processor

logger = logging.getLogger(__name__)

# --- Helper function kept for non-PDF/HTML files ---
def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100, max_text_length: int = 100000) -> List[str]:
    """Split text into overlapping chunks with safety limits."""
    if not text:
        return []
    
    # Safety limit to prevent memory issues
    if len(text) > max_text_length:
        print(f"⚠️ Text too large ({len(text)} chars), truncating to {max_text_length} chars")
        text = text[:max_text_length]
    
    chunks = []
    start = 0
    max_chunks = 200  # Safety limit
    
    while start < len(text) and len(chunks) < max_chunks:
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap
    
    if len(chunks) >= max_chunks:
        print(f"⚠️ Reached maximum chunk limit ({max_chunks})")
    
    return chunks

# --- Main Analysis Function ---
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
    analysis = None  # Initialize analysis object outside the try block
    temp_dir = None  # Initialize temp_dir outside the try block
    try:
        print(f"🔍 Starting analysis for tender {tdr}")
        logger.info(f"DEBUG: Starting database queries for {tdr}")
        
        print(f"🔍 Querying Tender table for {tdr}")
        tender = db.query(Tender).filter(Tender.tender_ref_number == tdr).first()
        
        print(f"🔍 Querying ScrapedTender table for {tdr}")
        scraped_tender = db.query(ScrapedTender).filter(
            ScrapedTender.tender_id_str == tdr
        ).first()

        if not tender or not scraped_tender:
            print(f"❌ Tender {tdr} not found in database")
            logger.error(f"Tender {tdr} not found in database")
            return

        print(f"✅ Found tender: {tender.tender_ref_number if tender else 'None'}")
        print(f"✅ Found scraped tender: {scraped_tender.tender_id_str if scraped_tender else 'None'}")
        logger.info(f"DEBUG: Found tender, checking analysis record.")

        print(f"🔍 Checking for existing analysis record...")
        analysis = db.query(TenderAnalysis).filter(
            TenderAnalysis.tender_id == tdr
        ).first()
        
        if not analysis:
            print(f"🆕 Creating new analysis record...")
            analysis = TenderAnalysis(
                id=uuid4(),
                tender_id=tdr,
                status=AnalysisStatusEnum.pending
            )
            db.add(analysis)
            db.commit()
        else:
            print(f"✅ Found existing analysis record with status: {analysis.status}")

        print(f"🔄 Updating analysis status to parsing...")
        analysis.status = AnalysisStatusEnum.parsing
        analysis.status_message = "Initializing tender analysis"
        analysis.analysis_started_at = datetime.utcnow()
        db.commit()

        print(f"📁 Fetching associated files...")
        logger.info("Fetching associated files")

        files = db.query(ScrapedTenderFile).filter(
            ScrapedTenderFile.tender_id == scraped_tender.id
        ).all()

        print(f"📋 Found {len(files) if files else 0} files")

        if not files:
            logger.warning(f"No files found for tender {tdr}")
            analysis.error_message = "No files found for this tender"
            analysis.status = AnalysisStatusEnum.failed
            db.commit()
            return

        logger.info(f"Found {len(files)} files")

        logger.info("Downloading files to temporary storage")

        print(f"📥 Starting file downloads to temporary directory...")
        temp_dir = Path(f"/tmp/tender_analysis_{tdr}_{uuid4()}")
        temp_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created temp directory: {temp_dir}")

        downloaded_files: List[Path] = []
        for i, file in enumerate(files, 1):
            try:
                print(f"📥 Downloading file {i}/{len(files)}: {file.file_name}")
                print(f"🌐 URL: {file.file_url}")
                logger.info(f"DEBUG: Attempting to download {file.file_url}")
                
                response = requests.get(file.file_url, timeout=15)  # Reduced timeout from 30 to 15
                
                print(f"📊 Response status: {response.status_code}")
                if response.status_code == 200:
                    file_path = temp_dir / file.file_name
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    downloaded_files.append(file_path)
                    print(f"✅ Downloaded: {file.file_name} ({len(response.content)} bytes)")
                    logger.info(f"Downloaded: {file.file_name}")
                else:
                    print(f"❌ Failed to download {file.file_name}: HTTP {response.status_code}")
            except Exception as e:
                print(f"❌ Error downloading {file.file_name}: {e}")
                logger.error(f"Failed to download {file.file_name}: {e}")

        if not downloaded_files:
            print(f"❌ No files were successfully downloaded")
            logger.error("No files were successfully downloaded")
            analysis.error_message = "Failed to download any files"
            analysis.status = AnalysisStatusEnum.failed
            db.commit()
            return

        print(f"✅ Downloaded {len(downloaded_files)} files successfully")
        logger.info("Extracting text from files")

        print(f"🔍 Starting text extraction from files...")
        all_chunks = []
        # Use the pre-initialized pdf_processor from core services to avoid double initialization
        # pdf_processor_instance = PDFProcessor(embedding_model, tokenizer)

        total_extracted_text_length = 0
        for i, filepath in enumerate(downloaded_files, 1):
            print(f"📄 Processing file {i}/{len(downloaded_files)}: {filepath.name} ({filepath.suffix.lower()})")
            
            if filepath.suffix.lower() == ".pdf":
                try:
                    print(f"🔍 Processing PDF: {filepath.name}")
                    chunks, stats = pdf_processor.process_pdf(
                        job_id="analyze_tender",
                        pdf_path=str(filepath),
                        doc_id=tdr,
                        filename=filepath.name
                    )
                    if chunks:
                        all_chunks.extend(chunks)
                        total_extracted_text_length += sum(len(c.get('content', '')) for c in chunks)
                        print(f"✅ Extracted {len(chunks)} chunks from PDF: {filepath.name}")
                        logger.info(f"Extracted {len(chunks)} chunks from PDF: {filepath.name}")
                    else:
                        print(f"⚠️ No chunks extracted from PDF: {filepath.name}")
                        logger.warning(f"PDFProcessor returned no chunks for {filepath.name}")
                except Exception as e:
                    print(f"❌ PDF processing failed for {filepath.name}: {e}")
                    logger.error(f"PDF Extraction failed for {filepath.name}: {e}")

            # Added basic HTML/HTM processing back in case of HTML files
            elif filepath.suffix.lower() in ['.html', '.htm']:
                try:
                    print(f"🌐 Processing HTML: {filepath.name}")
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        html_content = f.read()
                        print(f"📊 HTML file size: {len(html_content)} characters")
                        
                        soup = BeautifulSoup(html_content, 'html.parser')
                        text = soup.get_text()
                        print(f"📊 Extracted text size: {len(text)} characters")
                        
                        if text:
                            # Simple chunking for non-PDF/HTML text not using the full processor
                            print(f"✂️ Chunking HTML text...")
                            html_chunks_list = _chunk_text(text, chunk_size=1000, overlap=100) 
                            for chunk_content in html_chunks_list:
                                all_chunks.append({
                                    "content": chunk_content,
                                    # Add simple metadata to match PDFProcessor format for consistency
                                    "metadata": {"doc_id": tdr, "source": filepath.name, "type": "text", "doc_type": "html"}
                                })
                            total_extracted_text_length += len(text)
                            print(f"✅ Extracted {len(html_chunks_list)} chunks from HTML: {filepath.name}")
                            logger.info(f"Extracted and chunked text from HTML: {filepath.name}")
                        else:
                            print(f"⚠️ No text extracted from HTML: {filepath.name}")
                            
                except Exception as e:
                    print(f"❌ HTML processing failed for {filepath.name}: {e}")
                    logger.error(f"HTML Extraction failed for {filepath.name}: {e}")
            else:
                print(f"⚠️ Skipping unsupported file type: {filepath.name}")
                
        # --- New failure check uses the collected chunks ---
        if not all_chunks:
            logger.error("No chunks were extracted from any file")
            analysis.error_message = "Failed to extract and chunk text from files"
            analysis.status = AnalysisStatusEnum.failed
            db.commit()
            return

        logger.info(f"Extracted {total_extracted_text_length} characters total across {len(all_chunks)} chunks")
        analysis.progress = 50
        analysis.status_message = "Text extraction complete, creating embeddings"
        db.commit()

        # --- MEMORY OPTIMIZATION START ---
        logger.info("Creating embeddings for collected chunks and storing sequentially")

        # Prepare for sequential embedding and storage
        all_text_for_llm = []
        
        if vector_store and embedding_model:
            print(f"🔍 Creating embeddings and storing {len(all_chunks)} chunks in vector database...")
            
            # Prepare chunks for vector storage
            chunks_for_storage = []
            for idx, chunk_data in enumerate(all_chunks):
                try:
                    text_content = chunk_data.get('content', '')
                    if not text_content:
                        continue
                        
                    # Store text content for later LLM context build
                    all_text_for_llm.append(text_content)
                    
                    # Prepare metadata
                    metadata = chunk_data.get('metadata', {})
                    metadata["tender_id"] = tdr
                    metadata["tender_name"] = scraped_tender.tender_name
                    metadata["chunk_index"] = idx
                    metadata["type"] = metadata.get("type", "tender_document")
                    
                    # Prepare chunk for batch storage
                    chunks_for_storage.append({
                        'content': text_content,
                        'metadata': metadata
                    })
                    
                    if idx % 100 == 0 and idx > 0:
                         logger.info(f"Prepared {idx} chunks for storage...")
                    
                except Exception as e:
                    logger.warning(f"Failed to prepare chunk {idx}: {e}")
            
            # Store chunks in batch using vector_store collection
            if chunks_for_storage:
                try:
                    print(f"💾 Storing {len(chunks_for_storage)} chunks to vector database...")
                    collection = vector_store.get_or_create_collection(f"tender_{tdr}")
                    stored_count = vector_store.add_chunks(collection, chunks_for_storage)
                    print(f"✅ Successfully stored {stored_count} chunks in vector database")
                    logger.info(f"Stored {stored_count} embeddings in vector database")
                except Exception as e:
                    print(f"❌ Failed to store chunks in vector database: {e}")
                    logger.error(f"Failed to store chunks in vector database: {e}")
        else:
            print("⚠️ Vector store or embedding model not available, skipping embedding and storage")
            logger.warning("Vector store or embedding model not available, skipping embedding and storage")
            # Still need to build text for LLM
            for chunk_data in all_chunks:
                text_content = chunk_data.get('content', '')
                if text_content:
                    all_text_for_llm.append(text_content)
            
        # --- MEMORY OPTIMIZATION END ---

        analysis.progress = 70
        analysis.status_message = "Vector storage complete, generating semantic analysis"
        db.commit()

        logger.info("Starting semantic analysis")
        
        # Build context by combining all chunk content (now in all_text_for_llm) for the LLM prompt
        llm_context_string = " ".join(all_text_for_llm)
        
        tender_context = _build_tender_context(tender, scraped_tender, llm_context_string)

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

    except Exception as e:
        logger.error(f"Error analyzing tender {tdr}: {e}", exc_info=True)
        if analysis:
            analysis.status = AnalysisStatusEnum.failed
            analysis.error_message = str(e)
            db.commit()
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


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
        return None