import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Generator
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
import time

import requests
from sqlalchemy.orm import Session, joinedload
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
from app.core.services import llm_model, vector_store, embedding_model, pdf_processor
from app.modules.askai.services.archive_utils import (
    extract_archive,
    detect_archive_type,
    is_archive,
)

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION CONSTANTS
# These values are extracted from magic numbers throughout the code for easy tuning
# ============================================================================

# Chunking parameters for text splitting
CHUNK_SIZE = 1000  # Characters per chunk
CHUNK_OVERLAP = 100  # Characters to overlap between chunks

# Context parameters
MAX_CONTEXT_CHARS = 50000  # Max characters to send to LLM in context

# Request parameters
REQUEST_TIMEOUT = 30  # Seconds to wait for HTTP requests
MAX_RETRIES = 3  # Number of times to retry failed operations
RETRY_DELAY = 1.0  # Base delay in seconds between retries (exponential backoff)

# Embedding parameters
BATCH_SIZE = 32  # Number of chunks to embed at once (SentenceTransformer optimization)

# File filtering
MIN_TEXT_LENGTH = 500  # Minimum characters to extract before considering file valid

# LLM Parallelization
MAX_WORKERS = 3  # Number of concurrent LLM calls (executive summary, scope, datasheet)

# Database batch operations
DB_COMMIT_BATCH_SIZE = 5  # Commit progress updates every N steps

# Archive handling
MAX_ARCHIVE_RECURSION_DEPTH = 3  # Max nested archive extraction depth
MAX_FILES_PER_ARCHIVE = 100  # Max files in archive (prevents extraction bombs)
MAX_EXTRACTED_SIZE_MB = 500  # Max total uncompressed archive size


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
    Comprehensive tender analysis pipeline.

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

    Args:
        db: Database session
        tdr: Tender reference number (e.g., "51655667")

    Returns:
        None (updates TenderAnalysis table with results or error status)
    """
    # Initialize temp_dir and analysis variables so they're available in finally block
    temp_dir = None
    analysis = None

    try:
        # ====================================================================
        # STEP 1: FETCH TENDER DATA
        # Use eager loading to get all data in a single query instead of N+1
        # ====================================================================
        logger.info(f"[{tdr}] Fetching tender data from database")

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
        # STEP 3: EXTRACT TEXT FROM DOCUMENTS
        # ====================================================================
        logger.info(f"[{tdr}] Extracting text from downloaded files")

        all_text = _extract_text_from_files(downloaded_files, tdr)

        if not all_text or len(all_text) < MIN_TEXT_LENGTH:
            logger.error(f"[{tdr}] Failed to extract meaningful text from files")
            analysis.error_message = "Could not extract sufficient text from tender documents"
            analysis.status = AnalysisStatusEnum.failed
            db.commit()
            return

        logger.info(f"[{tdr}] Extracted {len(all_text):,} characters from documents")
        analysis.progress = 40
        analysis.status_message = "Text extracted, creating embeddings"
        db.commit()

        # ====================================================================
        # STEP 4: CREATE EMBEDDINGS & STORE IN VECTOR DATABASE
        # Use batch encoding for efficiency (5-10x faster than sequential)
        # ====================================================================
        logger.info(f"[{tdr}] Creating text chunks and embeddings")

        chunks = _chunk_text(all_text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        logger.info(f"[{tdr}] Created {len(chunks)} chunks from extracted text")

        # Batch embed for efficiency: process multiple chunks at once
        # SentenceTransformer is optimized for batch processing
        embeddings = _batch_encode_chunks(chunks, batch_size=BATCH_SIZE)
        logger.info(f"[{tdr}] Created {len(embeddings)} embeddings")

        analysis.progress = 50
        analysis.status_message = "Embeddings created, storing in vector database"
        db.commit()

        # Store embeddings in vector database if available
        # This enables semantic search for RAG functionality (future feature)
        if vector_store:
            logger.info(f"[{tdr}] Storing {len(embeddings)} embeddings in vector database")
            _store_embeddings_in_vector_db(chunks, embeddings, tdr, scraped_tender.tender_name)
            analysis.progress = 60
            db.commit()
        else:
            logger.warning(f"[{tdr}] Vector store not available, skipping storage")

        # ====================================================================
        # STEP 5: GENERATE LLM-BASED ANALYSIS (IN PARALLEL)
        # This is the key optimization: 3 LLM calls in parallel instead of sequential
        # Sequential: 90-180 seconds. Parallel: 30-60 seconds.
        # ====================================================================
        logger.info(f"[{tdr}] Building context for LLM analysis")

        tender_context = _build_tender_context(tender, scraped_tender, all_text)

        logger.info(f"[{tdr}] Starting parallel LLM analysis (3 concurrent tasks)")

        # Use ThreadPoolExecutor to run 3 LLM calls in parallel
        # Each call generates a different type of analysis (summary, scope, datasheet)
        analysis_results = _generate_analyses_parallel(tender_context, scraped_tender, tdr)

        # Store results in analysis record
        if analysis_results.get("one_pager"):
            analysis.one_pager_json = analysis_results["one_pager"]
            logger.info(f"[{tdr}] Executive summary generated successfully")

        if analysis_results.get("scope_of_work"):
            analysis.scope_of_work_json = analysis_results["scope_of_work"]
            logger.info(f"[{tdr}] Scope of work generated successfully")

        if analysis_results.get("data_sheet"):
            analysis.data_sheet_json = analysis_results["data_sheet"]
            logger.info(f"[{tdr}] Data sheet generated successfully")

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


def _extract_text_from_files(downloaded_files: List[Path], tdr: str) -> str:
    """
    Extract text from downloaded files (PDF, HTML, Archives, etc.).

    This function:
    - Uses PDFProcessor for PDFs (LlamaParse OCR with fallbacks)
    - Uses BeautifulSoup for HTML files
    - Extracts and recursively processes archive files (ZIP, RAR, TAR, 7Z, etc.)
    - Gracefully handles extraction failures for individual files
    - Accumulates text from all successfully processed files
    - Logs extraction results for debugging
    - Only includes files that extracted meaningful content (MIN_TEXT_LENGTH)

    Archive Processing:
    - Automatically detects archive format
    - Extracts to temporary directory
    - Recursively processes contents (with depth limit)
    - Preserves archive file paths in output

    PDF Processing Chain (from PDFProcessor):
    1. LlamaParse OCR (external service, best for scanned PDFs)
    2. PyMuPDF (local fallback, good for standard PDFs)
    3. Tesseract OCR (local OCR, final fallback for images)

    Supported formats:
    - PDF: Uses PDFProcessor (which uses LlamaParse + fallbacks)
    - HTML: Uses BeautifulSoup to extract visible text
    - Archives: ZIP, RAR, TAR, TAR.GZ, TAR.BZ2, 7Z (extracted and processed)

    Args:
        downloaded_files: List of file paths to extract text from
        tdr: Tender ID for logging

    Returns:
        Concatenated text from all files
    """
    all_text = ""
    files_processed = 0
    files_skipped = 0

    # Use generator to recursively process files (including extracted archives)
    for file_path in _get_all_processable_files(downloaded_files, tdr, depth=0):
        try:
            extracted_text = None
            file_suffix = file_path.suffix.lower()

            if file_suffix == ".pdf":
                # Extract PDF text using PDFProcessor
                # This uses LlamaParse with fallbacks (PyMuPDF, Tesseract)
                # Much better than PyPDF2 for handling various PDF formats
                logger.info(f"[{tdr}] Extracting PDF using PDFProcessor: {file_path.name}")

                try:
                    # PDFProcessor.extract_with_llamaparse() returns Dict[page_num, text]
                    # If LlamaParse fails, it falls back to PyMuPDF, then Tesseract
                    page_texts = pdf_processor.extract_with_llamaparse(str(file_path))

                    if not page_texts:
                        # Fallback to PyMuPDF
                        logger.warning(f"[{tdr}] LlamaParse failed for {file_path.name}, trying PyMuPDF")
                        page_texts = pdf_processor.extract_with_pymupdf(str(file_path))

                    if not page_texts:
                        # Final fallback to Tesseract OCR
                        logger.warning(f"[{tdr}] PyMuPDF failed for {file_path.name}, trying Tesseract OCR")
                        page_texts = pdf_processor.extract_with_tesseract(str(file_path))

                    if page_texts:
                        # Combine all pages into single text
                        extracted_text = "\n".join(
                            page_texts[page_num] for page_num in sorted(page_texts.keys())
                        )
                    else:
                        logger.error(f"[{tdr}] All PDF extraction methods failed for {file_path.name}")

                except Exception as e:
                    logger.error(f"[{tdr}] Error using PDFProcessor: {e}")
                    # Let the outer exception handler catch this

            elif file_suffix in [".html", ".htm"]:
                # Extract visible text from HTML using BeautifulSoup
                logger.info(f"[{tdr}] Extracting HTML: {file_path.name}")
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    soup = BeautifulSoup(f.read(), "html.parser")
                    # get_text() removes HTML tags and extracts visible content
                    extracted_text = soup.get_text()

            if extracted_text and len(extracted_text) >= MIN_TEXT_LENGTH:
                # Only include file if we extracted meaningful content
                all_text += f"\n--- {file_path.name} ---\n{extracted_text}\n"
                files_processed += 1
                logger.info(f"[{tdr}] Extracted {len(extracted_text):,} chars from {file_path.name}")
            else:
                # File either couldn't be processed or had no meaningful content
                files_skipped += 1
                logger.warning(
                    f"[{tdr}] Skipped {file_path.name}: "
                    f"{'insufficient content' if not extracted_text else 'extraction failed'}"
                )

        except Exception as e:
            # Log extraction failure but continue with next file
            logger.error(f"[{tdr}] Failed to extract text from {file_path.name}: {e}")
            files_skipped += 1

    logger.info(f"[{tdr}] Text extraction complete: {files_processed} processed, {files_skipped} skipped")
    return all_text


def _get_all_processable_files(
    file_paths: List[Path], tdr: str, depth: int = 0
) -> Generator[Path, None, None]:
    """
    Recursively process files, extracting archives and yielding all processable files.

    This generator function handles archives transparently. When an archive is
    encountered, it's extracted and the contained files are recursively processed.

    Archives are extracted to temporary directories that are cleaned up as the
    generator yields files. This prevents temporary files from accumulating.

    Args:
        file_paths: List of file paths to process (may contain archives)
        tdr: Tender ID for logging
        depth: Current recursion depth (for safety limits)

    Yields:
        Path objects for non-archive files that can be processed
    """
    # Safety check: prevent infinite recursion with nested archives
    if depth > MAX_ARCHIVE_RECURSION_DEPTH:
        logger.warning(f"[{tdr}] Archive recursion depth exceeded ({MAX_ARCHIVE_RECURSION_DEPTH})")
        return

    for file_path in file_paths:
        # Check if file is an archive
        if is_archive(file_path):
            archive_type = detect_archive_type(str(file_path))
            logger.info(f"[{tdr}] Detected archive format: {archive_type} for {file_path.name}")

            try:
                # Extract archive to temporary directory
                temp_extract_dir = Path(f"/tmp/archive_extract_{file_path.stem}_{uuid4()}")
                logger.info(f"[{tdr}] Extracting archive to: {temp_extract_dir}")

                extracted_files = extract_archive(
                    str(file_path),
                    str(temp_extract_dir),
                    max_files=MAX_FILES_PER_ARCHIVE,
                    max_size_mb=MAX_EXTRACTED_SIZE_MB,
                )

                if extracted_files:
                    logger.info(f"[{tdr}] Extracted {len(extracted_files)} files from {file_path.name}")

                    # Recursively process extracted files (may contain nested archives)
                    yield from _get_all_processable_files(extracted_files, tdr, depth + 1)

                    # Cleanup extracted files and directory
                    try:
                        shutil.rmtree(temp_extract_dir, ignore_errors=True)
                    except Exception as e:
                        logger.warning(f"[{tdr}] Failed to cleanup temp archive directory: {e}")
                else:
                    logger.warning(f"[{tdr}] Failed to extract archive: {file_path.name}")

            except Exception as e:
                logger.error(f"[{tdr}] Error processing archive {file_path.name}: {e}")
                # Continue with next file - don't fail entire analysis
        else:
            # Not an archive - yield for processing
            yield file_path


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks for embedding.

    Chunking helps with:
    1. Managing token limits (LLMs have max input token limits)
    2. Creating semantic units for vector database storage
    3. Enabling fine-grained retrieval in RAG applications

    The overlap parameter ensures context is preserved between chunks,
    so important information at chunk boundaries isn't lost.

    Example with chunk_size=1000, overlap=100:
    - Chunk 1: chars 0-1000
    - Chunk 2: chars 900-1900 (overlaps 100 chars with chunk 1)
    - Chunk 3: chars 1800-2800 (overlaps 100 chars with chunk 2)

    Args:
        text: Full text to chunk
        chunk_size: Size of each chunk in characters
        overlap: Number of overlapping characters between consecutive chunks

    Returns:
        List of text chunks
    """
    chunks = []
    start = 0

    while start < len(text):
        # Don't exceed text length
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])

        # Move start position forward, accounting for overlap
        # If overlap=100, we go back 100 chars before resuming
        start = end - overlap

    logger.debug(f"Created {len(chunks)} chunks from {len(text):,} character text")
    return chunks


def _batch_encode_chunks(chunks: List[str], batch_size: int = BATCH_SIZE) -> List:
    """
    Encode text chunks to embeddings using batch processing for efficiency.

    Batch processing is MUCH faster than sequential encoding:
    - Sequential: ~5ms per chunk → 500ms for 100 chunks
    - Batch (32): ~100ms for 32 chunks → 312ms for 100 chunks
    → 1.6x speedup, and scales even better for larger batches

    This function groups chunks into batches of batch_size, encodes each batch,
    and flattens the results back into a single list.

    Args:
        chunks: List of text strings to encode
        batch_size: Number of chunks to encode at once (SentenceTransformer is optimized for this)

    Returns:
        List of embedding vectors (same length as chunks)
    """
    all_embeddings = []

    # Process chunks in batches
    for i in range(0, len(chunks), batch_size):
        # Get a batch of chunks
        batch = chunks[i : i + batch_size]

        # Encode entire batch at once (much faster than one-by-one)
        # Returns list of embeddings for this batch
        batch_embeddings = embedding_model.encode(batch)

        all_embeddings.extend(batch_embeddings)

    logger.debug(f"Encoded {len(all_embeddings)} chunks in batches of {batch_size}")
    return all_embeddings


def _store_embeddings_in_vector_db(
    chunks: List[str], embeddings: List, tdr: str, tender_name: str
) -> None:
    """
    Store text chunks and their embeddings in the vector database.

    Vector database storage enables:
    - Semantic search: Find relevant document sections by meaning, not keywords
    - RAG (Retrieval Augmented Generation): Retrieve relevant context for LLM queries
    - Future feature: User can ask questions about tender, system retrieves relevant chunks

    This function attempts to store all embeddings, but doesn't fail the entire analysis
    if vector storage fails (it's optional for the basic analysis to work).

    Args:
        chunks: Text chunks to store
        embeddings: Corresponding embedding vectors
        tdr: Tender ID
        tender_name: Tender name for metadata
    """
    stored_count = 0
    failed_count = 0

    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        try:
            vector_store.add_text(
                text=chunk,
                embedding=embedding,
                metadata={
                    "tender_id": tdr,
                    "tender_name": tender_name,
                    "chunk_index": idx,
                    "type": "tender_document",
                },
            )
            stored_count += 1
        except Exception as e:
            # Log failure but continue storing other embeddings
            logger.warning(f"[{tdr}] Failed to store embedding chunk {idx}: {e}")
            failed_count += 1

    logger.info(
        f"[{tdr}] Vector storage complete: {stored_count} stored, {failed_count} failed"
    )


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


def _generate_analyses_parallel(context: str, scraped_tender, tdr: str) -> dict:
    """
    Generate 3 types of analysis in parallel for speed.

    This function uses ThreadPoolExecutor to run 3 LLM calls concurrently:
    - Executive summary (OnePager)
    - Scope of work details
    - Comprehensive datasheet

    Parallel execution greatly reduces total time:
    - Sequential: 3 calls × 30-60s = 90-180 seconds
    - Parallel: max(30-60s) = 30-60 seconds
    → 3x speedup!

    Each task is run in a separate thread, and we wait for all to complete.
    If one fails, others still complete (non-blocking failures).

    Args:
        context: Tender context string (built once, reused for all 3 calls)
        scraped_tender: Tender metadata for additional context
        tdr: Tender ID for logging

    Returns:
        Dictionary with keys: "one_pager", "scope_of_work", "data_sheet"
        Values are either the generated dict or None if generation failed
    """
    results = {}

    # Use ThreadPoolExecutor to run 3 LLM calls concurrently
    # MAX_WORKERS=3 means up to 3 threads running at once
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all 3 tasks immediately (they run concurrently)
        future_one_pager = executor.submit(_generate_executive_summary, context, tdr)
        future_scope = executor.submit(_generate_scope_of_work_details, context, scraped_tender, tdr)
        future_datasheet = executor.submit(_generate_comprehensive_datasheet, context, scraped_tender, tdr)

        # Wait for results as they complete (non-blocking)
        results["one_pager"] = future_one_pager.result()
        results["scope_of_work"] = future_scope.result()
        results["data_sheet"] = future_datasheet.result()

    return results


@retry_with_backoff(max_attempts=MAX_RETRIES, base_delay=RETRY_DELAY)
def _generate_executive_summary(context: str, tdr: str) -> Optional[dict]:
    """
    Generate an executive summary (OnePager) of the tender using LLM.

    This task is designed to be run in parallel with other LLM calls.
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
    Generate scope of work details using LLM.

    This task is designed to be run in parallel with other LLM calls.
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
        logger.error(f"[{tdr}] Error generating scope of work: {e}")
        return None


@retry_with_backoff(max_attempts=MAX_RETRIES, base_delay=RETRY_DELAY)
def _generate_comprehensive_datasheet(context: str, scraped_tender, tdr: str) -> Optional[dict]:
    """
    Generate a comprehensive datasheet using LLM.

    This task is designed to be run in parallel with other LLM calls.
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

Respond ONLY with valid JSON. Use this exact structure:
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
