import json
import logging
import shutil
import os
import gc
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4
from functools import wraps
import time

import requests
from sqlalchemy.orm import Session, joinedload

from app.modules.scraper.db.schema import ScrapedTender, ScrapedTenderFile
from app.modules.tenderiq.db.schema import Tender
from app.modules.analyze.db.schema import TenderAnalysis, AnalysisStatusEnum, AnalysisRFPSection, AnalysisDocumentTemplate
from app.modules.analyze.models.pydantic_models import (
    OnePagerSchema,
    ScopeOfWorkSchema,
    DataSheetSchema,
)
from app.core.services import llm_model, vector_store, pdf_processor
from app.modules.askai.services.document_service import DocumentService

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION CONSTANTS
# These values are extracted from magic numbers throughout the code for easy tuning
# ============================================================================

# Context parameters
MAX_CONTEXT_CHARS = 50000  # Max characters to send to LLM in context

# Request parameters
REQUEST_TIMEOUT = 30  # Seconds to wait for HTTP requests
MAX_RETRIES = 3  # Number of times to retry failed operations
RETRY_DELAY = 1.0  # Base delay in seconds between retries (exponential backoff)


# ============================================================================
# MEMORY OPTIMIZATION 
# Prevents system from killing the process due to memory exhaustion
# ============================================================================

def _optimize_environment():
    """Set environment variables for memory optimization."""
    # Disable tokenizer parallelism to save memory
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    # Reduce TensorFlow memory usage
    os.environ["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    
    # Reduce PyTorch memory usage
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"
    
    # Use CPU only to avoid CUDA memory issues
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

def _check_memory_available():
    """Check if sufficient memory is available."""
    try:
        import psutil
        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024**3)
        
        if available_gb < 0.5:  # Less than 500MB
            logger.warning(f"Low memory available: {available_gb:.1f}GB")
            return False
        return True
    except ImportError:
        # psutil not available, assume OK
        return True
    except Exception:
        # Error checking memory, assume OK
        return True

# Initialize memory optimization when module is imported
_optimize_environment()


# ============================================================================
# RETRY DECORATOR
# Implements exponential backoff for transient failures (network issues, rate limits)
# ============================================================================

def retry_with_backoff(max_attempts: int = MAX_RETRIES, base_delay: float = RETRY_DELAY):
    """
    Decorator for retrying failed operations with exponential backoff.

    Attempts the operation up to max_attempts times. If it fails, waits
    base_delay * (2 ^ attempt_number) seconds before retrying.

    This handles:
    - Network timeouts
    - Temporary service unavailability
    - Rate limiting from APIs

    Args:
        max_attempts: Number of times to try the operation
        base_delay: Initial delay in seconds (doubles each retry)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        # Calculate exponential backoff: delay * 2^attempt
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")

            # If all retries failed, raise the last exception
            raise last_exception

        return wrapper
    return decorator


# --- Main Analysis Function ---
def analyze_tender(db: Session, tdr: str):
    """
    Comprehensive tender analysis pipeline with memory optimization.

    This function orchestrates the entire tender analysis workflow:
    1. Fetch tender data from database (with eager loading)
    2. Download documents to temporary storage
    3. Extract text from documents
    4. Create embeddings and store in vector database
    5. Generate 3 types of LLM-based analysis (in parallel for speed)
    6. Store results and clean up temporary files

    The process uses granular error handling at each step so that failures
    in one step don't cascade to the entire analysis. It also uses retries
    for transient failures (network issues, API rate limits).

    Memory optimization features:
    - Automatic garbage collection
    - Memory usage monitoring (if psutil available)
    - Environment optimization for low-memory systems

    Args:
        db: Database session
        tdr: Tender reference number (e.g., "51655667")

    Returns:
        None (updates TenderAnalysis table with results or error status)
    """
    # Initialize temp_dir and analysis variables so they're available in finally block
    temp_dir = None
    analysis = None

    # Memory optimization: Force garbage collection and check memory
    gc.collect()
    _check_memory_available()

    try:
        # ====================================================================
        # STEP 1: FETCH TENDER DATA
        # Use eager loading to get all data in a single query instead of N+1
        # ====================================================================
        logger.info(f"[{tdr}] Starting analysis with memory optimization")

        # Optimize: Single eager-loaded query instead of 3 separate queries
        # This reduces database round-trips from 3 to 1
        scraped_tender = (
            db.query(ScrapedTender)
            .options(joinedload(ScrapedTender.files))
            .filter(ScrapedTender.tender_id_str == tdr)
            .first()
        )

        # Also get tender from tenderiq module (separate query is OK here)
        tender = db.query(Tender).filter(Tender.tender_ref_number == tdr).first()

        # Validate that we have the required data
        if not tender or not scraped_tender:
            logger.error(f"[{tdr}] Tender not found in database")
            return

        logger.info(f"[{tdr}] Found tender: {scraped_tender.tender_name}")

        # Get or create analysis record
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

        # Mark analysis as started
        analysis.status = AnalysisStatusEnum.parsing
        analysis.status_message = "Downloading and extracting documents"
        analysis.analysis_started_at = datetime.utcnow()
        db.commit()

        # ====================================================================
        # STEP 2: VALIDATE FILES & DOWNLOAD
        # ====================================================================
        files = scraped_tender.files  # Already loaded via eager loading above

        print(f"📋 Found {len(files) if files else 0} files")

        if not files:
            logger.warning(f"[{tdr}] No files found for tender")
            analysis.error_message = "No files found for this tender"
            analysis.status = AnalysisStatusEnum.failed
            db.commit()
            return

        logger.info(f"[{tdr}] Found {len(files)} files to process")

        # Create temporary directory for downloads
        # Using uuid4() ensures each run has a unique directory (prevents collisions)
        temp_dir = Path(f"/tmp/tender_analysis_{tdr}_{uuid4()}")
        temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[{tdr}] Created temp directory: {temp_dir}")

        # Download all files with retry logic for transient failures
        downloaded_files = _download_files_with_retry(files, temp_dir, tdr)

        if not downloaded_files:
            logger.error(f"[{tdr}] Failed to download any files")
            analysis.error_message = "Failed to download any files from tender URLs"
            analysis.status = AnalysisStatusEnum.failed
            db.commit()
            return

        logger.info(f"[{tdr}] Successfully downloaded {len(downloaded_files)} files")

        # ====================================================================
        # STEP 3: PROCESS PDFS & EXTRACT TEXT WITH CHUNKING
        # ====================================================================
        # Key difference from old approach: Use pdf_processor.process_pdf() which
        # returns pre-chunked and formatted chunks with metadata already cleaned.
        # This is the same approach used in process_tender.py (which works).
        #
        # OLD APPROACH (broken):
        #   1. Extract raw text with _extract_text_from_files()
        #   2. Manually chunk text with _chunk_text()
        #   3. Manually encode embeddings with _batch_encode_chunks()
        #   4. Store with _store_embeddings_in_vector_db()
        # → This approach crashed at progress 40 (during embedding generation)
        #
        # NEW APPROACH (working):
        #   1. Use pdf_processor.process_pdf() for each PDF
        #   2. Collect all chunks (already properly formatted with metadata)
        #   3. Pass directly to vector_store.add_tender_chunks()
        #   4. vector_store handles vectorization internally
        # → This matches the proven pattern in process_tender.py
        # ====================================================================
        logger.info(f"[{tdr}] Processing documents and extracting text with chunking")

        # Collect all chunks from all processed files
        all_tender_chunks = []
        total_chunks_created = 0

        # Process each downloaded file with comprehensive DocumentService
        # Supports PDF, Excel, HTML, and archive files
        document_service = DocumentService()
        
        for file_path in downloaded_files:
            try:
                file_suffix = file_path.suffix.lower()
                logger.info(f"[{tdr}] Processing file with DocumentService: {file_path.name} (format: {file_suffix})")

                # Use DocumentService which supports PDF, Excel, HTML, and archives
                import uuid as uuid_module
                doc_id = str(uuid_module.uuid4())
                job_id = f"analyze_tender_{tdr}_{uuid_module.uuid4()}"

                chunks, stats = document_service.process_document(
                    job_id=job_id,
                    file_path=str(file_path),
                    doc_id=doc_id,
                    filename=file_path.name,
                    save_json=False  # Don't save JSON files during analysis
                )

                if chunks:
                    all_tender_chunks.extend(chunks)
                    total_chunks_created += len(chunks)
                    logger.info(f"[{tdr}] Processed {file_path.name}: {len(chunks)} chunks created (type: {file_suffix})")
                    logger.info(f"[{tdr}] File stats: {stats}")
                else:
                    logger.warning(f"[{tdr}] No chunks extracted from {file_path.name}")

            except ValueError as e:
                logger.warning(f"[{tdr}] Skipping unsupported file: {file_path.name} - {e}")
            except Exception as e:
                logger.error(f"[{tdr}] Failed to process {file_path.name}: {e}", exc_info=True)
                # Continue with other files - don't fail entire analysis

        # Validate that we extracted meaningful chunks
        if not all_tender_chunks:
            logger.error(f"[{tdr}] Failed to extract any chunks from downloaded files")
            analysis.error_message = "Could not extract meaningful content from tender documents"
            analysis.status = AnalysisStatusEnum.failed
            db.commit()
            return

        logger.info(f"[{tdr}] Successfully extracted {total_chunks_created} chunks from documents")
        analysis.progress = 40
        analysis.status_message = f"Extracted {total_chunks_created} chunks, storing in vector database"
        db.commit()

        # ====================================================================
        # STEP 4: STORE CHUNKS IN VECTOR DATABASE
        # ====================================================================
        # The vector_store.add_tender_chunks() method handles:
        # - Vectorization using embedding_model.encode()
        # - Batch insertion for efficiency
        # - Metadata preservation
        # This is much more efficient than manual embedding and storing individually.
        # ====================================================================
        if vector_store:
            try:
                logger.info(f"[{tdr}] Creating Weaviate collection and storing chunks")

                # Create a new collection for this tender
                # Deletes any existing collection to ensure freshness
                tender_collection = vector_store.create_tender_collection(tdr)
                logger.info(f"[{tdr}] Created Weaviate collection: {tender_collection.name}")

                # Add all chunks with vectorization handled internally
                # This uses batch processing for efficiency (batch_size=32)
                chunks_added = vector_store.add_tender_chunks(tender_collection, all_tender_chunks)
                logger.info(f"[{tdr}] Successfully added {chunks_added} chunks to vector database")

                analysis.progress = 60
                analysis.status_message = f"Stored {chunks_added} chunks in vector database"
                db.commit()

            except Exception as e:
                logger.error(f"[{tdr}] Failed to store chunks in vector database: {e}", exc_info=True)
                analysis.error_message = f"Vector database storage failed: {str(e)[:500]}"
                analysis.status = AnalysisStatusEnum.failed
                db.commit()
                return
        else:
            logger.warning(f"[{tdr}] Vector store not initialized, skipping vector database storage")

        # ====================================================================
        # STEP 5: GENERATE LLM-BASED ANALYSIS (SEQUENTIAL)
        # Generate analyses one after another for stability and predictability
        # ====================================================================
        logger.info(f"[{tdr}] Building context for LLM analysis")

        # Reconstruct text from chunks for LLM context
        # Each chunk is a dict with 'content' key
        all_text = "\n\n".join([chunk.get('content', '') for chunk in all_tender_chunks if chunk.get('content')])
        logger.info(f"[{tdr}] Reconstructed {len(all_text):,} characters from {len(all_tender_chunks)} chunks for LLM context")

        tender_context = _build_tender_context(tender, scraped_tender, all_text)

        logger.info(f"[{tdr}] Starting sequential LLM analysis")

        # ====================================================================
        # Generate analyses sequentially (one after another)
        # Each call processes: 1) Executive summary, 2) Scope of work, 3) Data sheet
        # ====================================================================

        # Step 1: Generate executive summary (OnePager)
        logger.info(f"[{tdr}] Generating executive summary (OnePager)")
        analysis.progress = 70
        analysis.status_message = "Generating executive summary"
        db.commit()

        one_pager = _generate_executive_summary(tender_context, tdr)
        if one_pager:
            analysis.one_pager_json = one_pager
            logger.info(f"[{tdr}] Executive summary generated successfully")
        else:
            logger.warning(f"[{tdr}] Failed to generate executive summary")

        # Step 2: Generate scope of work
        logger.info(f"[{tdr}] Generating scope of work details")
        analysis.progress = 80
        analysis.status_message = "Generating scope of work"
        db.commit()

        scope_of_work = _generate_scope_of_work_details(tender_context, scraped_tender, tdr)
        if scope_of_work:
            analysis.scope_of_work_json = scope_of_work
            logger.info(f"[{tdr}] Scope of work generated successfully")
        else:
            logger.warning(f"[{tdr}] Failed to generate scope of work")

        # Step 3: Generate comprehensive datasheet
        logger.info(f"[{tdr}] Generating comprehensive datasheet")
        analysis.progress = 90
        analysis.status_message = "Generating datasheet"
        db.commit()

        data_sheet = _generate_comprehensive_datasheet(tender_context, scraped_tender, tdr)
        if data_sheet:
            analysis.data_sheet_json = data_sheet
            logger.info(f"[{tdr}] Data sheet generated successfully")
        else:
            logger.warning(f"[{tdr}] Failed to generate datasheet")

        # ====================================================================
        # STEP 5.1: GENERATE RFP SECTIONS ANALYSIS
        # ====================================================================
        analysis.status_message = "Analyzing RFP sections"
        db.commit()

        rfp_sections = _generate_rfp_sections(tender_context, analysis.id, db, tdr)
        logger.info(f"[{tdr}] Generated {len(rfp_sections)} RFP sections")

        # ====================================================================
        # STEP 5.2: EXTRACT DOCUMENT TEMPLATES
        # ====================================================================
        analysis.status_message = "Extracting document templates"
        db.commit()

        doc_templates = _extract_document_templates(tender_context, analysis.id, db, tdr)
        logger.info(f"[{tdr}] Extracted {len(doc_templates)} document templates")

        # ====================================================================
        # STEP 6: MARK ANALYSIS AS COMPLETE
        # ====================================================================
        analysis.status = AnalysisStatusEnum.completed
        analysis.progress = 100
        analysis.status_message = "Analysis completed successfully"
        analysis.analysis_completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"[{tdr}] Analysis pipeline completed successfully")

    except Exception as e:
        # Granular error handling: log and mark analysis as failed
        logger.error(f"[{tdr}] Error during analysis: {e}", exc_info=True)
        if analysis:
            analysis.status = AnalysisStatusEnum.failed
            analysis.error_message = f"Analysis failed: {str(e)[:500]}"  # Truncate to DB limit
            db.commit()

    finally:
        # ====================================================================
        # CLEANUP: ALWAYS remove temporary files, even if analysis failed
        # This prevents disk space leaks when errors occur
        # ====================================================================
        if temp_dir and temp_dir.exists():
            try:
                logger.info(f"[{tdr}] Cleaning up temporary files")
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.error(f"[{tdr}] Failed to clean up temp directory: {e}")
        
        # Memory optimization: Force garbage collection after cleanup
        gc.collect()
        logger.info(f"[{tdr}] Analysis cleanup complete")


# ============================================================================
# HELPER FUNCTIONS - DATA FETCHING & PROCESSING
# ============================================================================

def _download_files_with_retry(
    files: List[ScrapedTenderFile], temp_dir: Path, tdr: str
) -> List[Path]:
    """
    Download files from URLs with retry logic for transient failures.

    This function implements robust file downloading with:
    - Retry logic for transient network failures
    - Graceful handling of partial failures (if 1 file fails, others proceed)
    - Logging of each download attempt

    Args:
        files: List of ScrapedTenderFile objects containing file_url and file_name
        temp_dir: Path to directory where files should be downloaded
        tdr: Tender ID for logging

    Returns:
        List of successfully downloaded file paths (may be partial list if some failed)
    """
    downloaded_files = []

    for file in files:
        try:
            # Download with retry decorator for transient failures
            file_path = _download_single_file_with_retry(file, temp_dir)
            downloaded_files.append(file_path)
            logger.info(f"[{tdr}] Downloaded: {file.file_name}")
        except Exception as e:
            # Log failure but continue with other files
            # This prevents 1 bad file from stopping the entire analysis
            logger.error(f"[{tdr}] Failed to download {file.file_name}: {e}")

    return downloaded_files


@retry_with_backoff(max_attempts=MAX_RETRIES, base_delay=RETRY_DELAY)
def _download_single_file_with_retry(file: ScrapedTenderFile, temp_dir: Path) -> Path:
    """
    Download a single file with automatic retry on failure.

    The @retry_with_backoff decorator handles:
    - Network timeouts
    - Temporary unavailability
    - Rate limiting from servers

    Args:
        file: ScrapedTenderFile object
        temp_dir: Directory to save the file

    Returns:
        Path to downloaded file
    """
    response = requests.get(file.file_url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()  # Raise exception if status is not 200-299

    file_path = temp_dir / file.file_name
    with open(file_path, "wb") as f:
        f.write(response.content)

    return file_path












# ============================================================================
# HELPER FUNCTIONS - LLM ANALYSIS (PARALLELIZED)
# ============================================================================

def _build_tender_context(tender, scraped_tender, all_text: str) -> str:
    """
    Build a comprehensive context string for LLM analysis.

    This context includes:
    - Tender metadata (ID, name, authority, dates, etc.)
    - Extracted document content (truncated to MAX_CONTEXT_CHARS to stay under token limits)

    The context is reused for all 3 LLM calls (executive summary, scope, datasheet),
    so building it once and reusing is more efficient than building it separately
    for each call.

    Args:
        tender: Tender object from tenderiq module
        scraped_tender: ScrapedTender object with metadata
        all_text: Full extracted text from documents

    Returns:
        Formatted context string for LLM prompts
    """
    # Truncate to MAX_CONTEXT_CHARS to stay within LLM token limits
    # Gemini 2.0 has large context window, but we limit for efficiency and cost
    truncated_text = all_text[:MAX_CONTEXT_CHARS]

    context = f"""TENDER INFORMATION:
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
{truncated_text}
"""
    return context


@retry_with_backoff(max_attempts=MAX_RETRIES, base_delay=RETRY_DELAY)
def _generate_executive_summary(context: str, tdr: str) -> Optional[dict]:
    """
    Generate an executive summary (OnePager) of the tender using LLM.

    The @retry_with_backoff decorator handles transient API failures.

    Args:
        context: Tender context for the LLM
        tdr: Tender ID for logging

    Returns:
        OnePager analysis dict or None if generation failed
    """
    try:
        logger.info(f"[{tdr}] Generating executive summary (OnePager)")

        prompt = f"""Based on the tender document, generate a structured executive summary in JSON format.

Respond ONLY with valid JSON. Use this exact structure:
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

Generate JSON only, no explanations:"""

        # Call LLM to generate response
        response = llm_model.generate_content(prompt)
        response_text = response.text.strip()

        # Parse JSON from response (may be wrapped in code fences)
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```"):
            response_text = response_text[3:-3].strip()

        # Validate response matches OnePagerSchema
        result = json.loads(response_text)
        validated = OnePagerSchema(**result)
        logger.debug(f"[{tdr}] OnePager validation successful")
        return validated.model_dump()

    except json.JSONDecodeError as e:
        logger.error(f"[{tdr}] Failed to parse JSON in executive summary: {e}")
        return None
    except Exception as e:
        logger.error(f"[{tdr}] Error generating executive summary: {e}")
        return None


@retry_with_backoff(max_attempts=MAX_RETRIES, base_delay=RETRY_DELAY)
def _generate_scope_of_work_details(context: str, scraped_tender, tdr: str) -> Optional[dict]:
    """
    Generate comprehensive scope of work details using LLM.

    Generates detailed work packages, components, technical specifications, deliverables,
    and exclusions. Uses the comprehensive ScopeOfWorkSchema that matches frontend expectations.

    The @retry_with_backoff decorator handles transient API failures.

    Args:
        context: Tender context for the LLM
        scraped_tender: Tender metadata (currently unused, kept for future extensions)
        tdr: Tender ID for logging

    Returns:
        Scope of work analysis dict or None if generation failed
    """
    try:
        logger.info(f"[{tdr}] Generating scope of work details")

        prompt = f"""Based on the tender document, extract and structure the scope of work in JSON format.

Respond ONLY with valid JSON. Use this exact structure:
{{
    "project_details": {{
        "project_name": "Project name/title",
        "location": "Project location/address",
        "total_length": "length in km if applicable",
        "total_area": "total area in square meters or relevant units",
        "duration": "project duration/timeline",
        "contract_value": "total project value with currency"
    }},
    "work_packages": [
        {{
            "id": "wp-001",
            "name": "Work package name",
            "description": "Brief description of the work package",
            "components": [
                {{
                    "item": "Component item name",
                    "description": "Description of the work/component",
                    "quantity": 1000,
                    "unit": "unit of measurement (Sq.m, Cu.m, etc.)",
                    "specifications": "Technical specifications or standards to follow"
                }}
            ],
            "estimated_duration": "Duration for this work package",
            "dependencies": ["wp-001", "wp-002"]
        }}
    ],
    "technical_specifications": {{
        "standards": ["Standard 1 (e.g., IRC guidelines)", "Standard 2"],
        "quality_requirements": ["Quality requirement 1", "Quality requirement 2"],
        "materials_specification": [
            {{
                "material": "Material name",
                "specification": "Detailed specification (e.g., OPC Grade 53)",
                "source": "Source or approval requirement",
                "testing_standard": "Standard for testing (e.g., IS 4031)"
            }}
        ],
        "testing_requirements": ["Testing requirement 1", "Testing requirement 2"]
    }},
    "deliverables": [
        {{
            "item": "Deliverable name",
            "description": "Description of the deliverable",
            "timeline": "When it should be delivered"
        }}
    ],
    "exclusions": [
        "What is NOT included in the scope",
        "What the client is responsible for"
    ]
}}

IMPORTANT NOTES:
- Extract ALL work packages with their components and dependencies
- Include detailed technical specifications with standards and materials
- List ALL project deliverables with timelines
- Clearly identify scope exclusions
- Provide realistic quantities and units for components
- Use actual values from the tender document

CONTEXT:
{context}

Generate JSON only, no explanations:"""

        response = llm_model.generate_content(prompt)
        response_text = response.text.strip()

        # Parse JSON from response (may be wrapped in code fences)
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```"):
            response_text = response_text[3:-3].strip()

        result = json.loads(response_text)
        validated = ScopeOfWorkSchema(**result)
        logger.debug(f"[{tdr}] Scope of work validation successful")
        return validated.model_dump()

    except json.JSONDecodeError as e:
        logger.error(f"[{tdr}] Failed to parse JSON in scope of work: {e}")
        return None
    except Exception as e:
        logger.error(f"[{tdr}] Error generating scope of work: {e}", exc_info=True)
        return None


@retry_with_backoff(max_attempts=MAX_RETRIES, base_delay=RETRY_DELAY)
def _generate_comprehensive_datasheet(context: str, scraped_tender, tdr: str) -> Optional[dict]:
    """
    Generate a comprehensive datasheet using LLM.

    The @retry_with_backoff decorator handles transient API failures.

    Args:
        context: Tender context for the LLM
        scraped_tender: Tender metadata (currently unused, kept for future extensions)
        tdr: Tender ID for logging

    Returns:
        Data sheet analysis dict or None if generation failed
    """
    try:
        logger.info(f"[{tdr}] Generating comprehensive datasheet")

        prompt = f"""Based on the tender document, create a comprehensive datasheet in JSON format.

Extract specific information and structure it as items with label, value, type, and highlight fields.

Use this EXACT JSON structure:
{{
    "project_information": [
        {{"label": "Project Name", "value": "Extracted project name", "type": "text", "highlight": true}},
        {{"label": "Location", "value": "Project location", "type": "text", "highlight": false}},
        {{"label": "Project Type", "value": "Road/Bridge/Building etc", "type": "text", "highlight": false}},
        {{"label": "Tendering Authority", "value": "Authority name", "type": "text", "highlight": false}},
        {{"label": "Tender Category", "value": "Category", "type": "text", "highlight": false}}
    ],
    "contract_details": [
        {{"label": "Contract Value", "value": "Rs. X Crores", "type": "money", "highlight": true}},
        {{"label": "Contract Duration", "value": "X months", "type": "text", "highlight": false}},
        {{"label": "Contract Type", "value": "Item Rate/Lump Sum etc", "type": "text", "highlight": false}},
        {{"label": "Work Classification", "value": "Class A/B etc", "type": "text", "highlight": false}}
    ],
    "financial_details": [
        {{"label": "EMD Amount", "value": "Rs. X Lakhs", "type": "money", "highlight": true}},
        {{"label": "Tender Fee", "value": "Rs. X", "type": "money", "highlight": false}},
        {{"label": "Performance Guarantee", "value": "X% of contract value", "type": "text", "highlight": false}},
        {{"label": "Retention Money", "value": "X%", "type": "percentage", "highlight": false}},
        {{"label": "Payment Terms", "value": "Monthly/Quarterly", "type": "text", "highlight": false}}
    ],
    "technical_summary": [
        {{"label": "Work Type", "value": "Construction/Maintenance", "type": "text", "highlight": false}},
        {{"label": "Key Materials", "value": "Cement, Steel, Bitumen", "type": "text", "highlight": false}},
        {{"label": "Standards", "value": "IRC, IS codes", "type": "text", "highlight": false}},
        {{"label": "Quality Requirements", "value": "As per specifications", "type": "text", "highlight": false}}
    ],
    "important_dates": [
        {{"label": "Publication Date", "value": "DD/MM/YYYY", "type": "date", "highlight": false}},
        {{"label": "Pre-bid Meeting", "value": "DD/MM/YYYY", "type": "date", "highlight": true}},
        {{"label": "Site Visit Deadline", "value": "DD/MM/YYYY", "type": "date", "highlight": false}},
        {{"label": "Bid Submission Deadline", "value": "DD/MM/YYYY", "type": "date", "highlight": true}},
        {{"label": "Bid Opening Date", "value": "DD/MM/YYYY", "type": "date", "highlight": true}}
    ]
}}

IMPORTANT:
- Extract ACTUAL values from the tender document
- If a value is not found, use "N/A" 
- For money values, use proper Indian format (Rs. X Crores/Lakhs)
- For dates, use DD/MM/YYYY format
- Set highlight=true for critical information
- Generate realistic data based on the tender content

TENDER DOCUMENT:
{context}

Generate JSON only, no explanations:"""

        response = llm_model.generate_content(prompt)
        response_text = response.text.strip()

        # Parse JSON from response (may be wrapped in code fences)
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```"):
            response_text = response_text[3:-3].strip()

        result = json.loads(response_text)
        validated = DataSheetSchema(**result)
        logger.debug(f"[{tdr}] Datasheet validation successful")
        return validated.model_dump()

    except json.JSONDecodeError as e:
        logger.error(f"[{tdr}] Failed to parse JSON in datasheet: {e}")
        return None
    except Exception as e:
        logger.error(f"[{tdr}] Error generating datasheet: {e}")
        return None


# ============================================================================
# RFP SECTIONS ANALYSIS
# ============================================================================

def _generate_rfp_sections(context: str, analysis_id, db: Session, tdr: str) -> List[AnalysisRFPSection]:
    """
    Generate detailed RFP section breakdown and store in database.
    """
    try:
        logger.info(f"[{tdr}] Generating RFP sections analysis...")

        # Truncate context if too long
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "... [truncated]"

        prompt = f"""
        Analyze this tender document and break it down into logical sections.
        For each section, provide a detailed analysis.

        Tender Document:
        {context}

        IMPORTANT INSTRUCTIONS:
        1. Identify major sections (e.g., "1.1 Eligibility", "2.1 Technical Requirements", "3.1 Financial Criteria", "Annexure A - BOQ")
        2. For each section, provide:
           - section_number: SHORT identifier (e.g., "1.1", "2.3.1", "A", "Annexure-A") - MAXIMUM 100 characters
           - section_title: Clear descriptive title of the section (e.g., "Eligibility Criteria", "Technical Requirements")
           - summary: Brief summary of what this section covers
           - key_requirements: List of important requirements/criteria
           - compliance_issues: List of potential compliance concerns or unclear items
           - page_references: List of page numbers where this section appears (estimate if not clear)

        CRITICAL: section_number must be SHORT (under 100 chars) - use numbers, letters, or brief codes.
        The descriptive text should go in section_title, NOT section_number.

        Return a JSON array of sections:
        [
          {{
            "section_number": "1.1",
            "section_title": "Eligibility Criteria", 
            "summary": "This section outlines the minimum eligibility requirements...",
            "key_requirements": ["Minimum turnover Rs. 50 Cr in last 3 years", "Experience in highway projects"],
            "compliance_issues": ["Turnover calculation method unclear", "Similar work definition ambiguous"],
            "page_references": [5, 6, 7]
          }}
        ]

        Focus on creating comprehensive sections that cover all important aspects.
        """

        response = llm_model.generate_content(prompt)
        if not response or not response.text:
            logger.error(f"[{tdr}] No response from LLM for RFP sections")
            return []

        # Parse JSON response
        json_text = response.text.strip()
        if json_text.startswith('```json'):
            json_text = json_text[7:]
        if json_text.endswith('```'):
            json_text = json_text[:-3]
        
        sections_data = json.loads(json_text)
        
        # Create AnalysisRFPSection objects
        sections = []
        for section_data in sections_data:
            # Validate and truncate section_number if too long
            section_number = section_data.get('section_number', '')
            if section_number and len(section_number) > 200:
                logger.warning(f"[{tdr}] Truncating long section_number: '{section_number[:50]}...' (was {len(section_number)} chars)")
                section_number = section_number[:197] + "..."
            
            # Ensure section_title is not too long
            section_title = section_data.get('section_title', 'Untitled Section')
            if len(section_title) > 255:
                logger.warning(f"[{tdr}] Truncating long section_title: '{section_title[:50]}...' (was {len(section_title)} chars)")
                section_title = section_title[:252] + "..."
                
            section = AnalysisRFPSection(
                analysis_id=analysis_id,
                section_number=section_number,
                section_title=section_title,
                summary=section_data.get('summary'),
                key_requirements=section_data.get('key_requirements', []),
                compliance_issues=section_data.get('compliance_issues', []),
                page_references=section_data.get('page_references', [])
            )
            db.add(section)
            sections.append(section)
        
        db.commit()
        logger.info(f"[{tdr}] Created {len(sections)} RFP sections in database")
        return sections

    except json.JSONDecodeError as e:
        logger.error(f"[{tdr}] Failed to parse JSON for RFP sections: {e}")
        return []
    except Exception as e:
        logger.error(f"[{tdr}] Error generating RFP sections: {e}")
        return []


# ============================================================================
# DOCUMENT TEMPLATES EXTRACTION
# ============================================================================

def _extract_document_templates(context: str, analysis_id, db: Session, tdr: str) -> List[AnalysisDocumentTemplate]:
    """
    Extract document templates and forms from the tender and store in database.
    """
    try:
        logger.info(f"[{tdr}] Extracting document templates...")

        # Truncate context if too long
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "... [truncated]"

        prompt = f"""
        Analyze this tender document and identify all document templates, forms, and formats that bidders need to submit.

        Tender Document:
        {context}

        Instructions:
        1. Look for sections that mention forms, templates, declarations, certificates, or specific submission formats
        2. Common templates include: EMD format, Technical bid format, Financial bid format, Experience certificate format, etc.
        3. For each template, provide:
           - template_name: Clear name of the template/form
           - description: What this template is for and when it's required
           - required_format: Format required (PDF, Excel, Hard Copy, etc.)
           - content_preview: Brief preview of template content or structure
           - page_references: Page numbers where this template is mentioned

        Return a JSON array of templates:
        [
          {{
            "template_name": "EMD Bank Guarantee Format",
            "description": "Format for submitting Earnest Money Deposit bank guarantee as per Annexure",
            "required_format": "Original hard copy + PDF scan",
            "content_preview": "Bank Guarantee for Rs. [Amount] in favor of [Authority]...",
            "page_references": [25, 26]
          }}
        ]

        Focus on actual submission requirements and formats that bidders must follow.
        """

        response = llm_model.generate_content(prompt)
        if not response or not response.text:
            logger.error(f"[{tdr}] No response from LLM for document templates")
            return []

        # Parse JSON response
        json_text = response.text.strip()
        if json_text.startswith('```json'):
            json_text = json_text[7:]
        if json_text.endswith('```'):
            json_text = json_text[:-3]
        
        templates_data = json.loads(json_text)
        
        # Create AnalysisDocumentTemplate objects
        templates = []
        for template_data in templates_data:
            # Validate and truncate fields if too long
            template_name = template_data.get('template_name', 'Untitled Template')
            if len(template_name) > 255:
                logger.warning(f"[{tdr}] Truncating long template_name: '{template_name[:50]}...' (was {len(template_name)} chars)")
                template_name = template_name[:252] + "..."
            
            required_format = template_data.get('required_format', '')
            if required_format and len(required_format) > 100:
                logger.warning(f"[{tdr}] Truncating long required_format: '{required_format[:50]}...' (was {len(required_format)} chars)")
                required_format = required_format[:97] + "..."
                
            template = AnalysisDocumentTemplate(
                analysis_id=analysis_id,
                template_name=template_name,
                description=template_data.get('description'),
                required_format=required_format,
                content_preview=template_data.get('content_preview'),
                page_references=template_data.get('page_references', [])
            )
            db.add(template)
            templates.append(template)
        
        db.commit()
        logger.info(f"[{tdr}] Created {len(templates)} document templates in database")
        return templates

    except json.JSONDecodeError as e:
        logger.error(f"[{tdr}] Failed to parse JSON for document templates: {e}")
        return []
    except Exception as e:
        logger.error(f"[{tdr}] Error extracting document templates: {e}")
        return []
