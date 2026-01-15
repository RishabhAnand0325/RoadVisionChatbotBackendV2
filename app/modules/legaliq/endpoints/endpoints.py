# app/modules/legaliq/endpoints/legal_endpoints.py
import os
import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from app.modules.legaliq.services.legal_chat_service import legal_service
from app.modules.legaliq.services.indian_kanoon_service import indian_kanoon_service

router = APIRouter()

class ChatRequest(BaseModel):
    query: str
    history: List[dict] = []

class AnalysisReportRequest(BaseModel):
    riskLevel: str
    riskMessage: str
    extractedFacts: dict
    aiSummary: str
    riskAnalysis: List[dict]
    nextSteps: List[str]

@router.post("/upload")
async def upload_legal_docs(files: List[UploadFile] = File(...)):
    """Uploads PDFs and loads them into context."""
    return await legal_service.process_uploads(files)

@router.post("/query")
async def query_legal_bot(request: ChatRequest):
    """Asks a question to the bot based on uploaded docs."""
    result = await legal_service.ask_question(request.query, request.history)
    # result already contains {"response": str, "sources": [...]}
    return result

@router.post("/analyze-document")
async def analyze_legal_document(file: UploadFile = File(...)):
    """Analyze a legal document and return structured analysis results."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        allowed_extensions = ['.pdf', '.doc', '.docx']
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        logger.info(f"Analyzing document: {file.filename}")
        result = await legal_service.analyze_document(file)
        
        if "error" in result:
            logger.error(f"Analysis error: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])
        
        logger.info(f"Analysis completed successfully for: {file.filename}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error analyzing document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/analyze-document/report")
async def download_legal_analysis_report(request: AnalysisReportRequest):
    """Generate and download a PDF report for legal document analysis."""
    from fastapi.responses import StreamingResponse
    import io
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Convert Pydantic model to dict
        analysis_data = request.model_dump()
        
        # Generate PDF report
        pdf_content, filename = legal_service.generate_analysis_report(analysis_data)
        
        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

class DraftRequest(BaseModel):
    template_id: str
    form_values: dict
    content: str

@router.post("/save-draft")
async def save_draft(request: DraftRequest):
    """Save a document draft."""
    # In a real app, this would save to a database
    # For now, we'll just return success
    return {"status": "success", "message": "Draft saved successfully"}

# --- DOCUMENT COMPARE ---
import difflib
import shutil
import tempfile
from docx import Document
import fitz  # PyMuPDF
import google.generativeai as genai
from app.config import settings

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

class ComparisonSummary(BaseModel):
    additions: int
    deletions: int
    modifications: int
    similarityScore: str

class ChangeItem(BaseModel):
    type: str
    page: int
    content: str
    original: str = ""

class DiffSegment(BaseModel):
    type: str
    text: str
    old_text: Optional[str] = None

class ComparisonResult(BaseModel):
    summary: ComparisonSummary
    changes: List[ChangeItem]
    unified_view: List[DiffSegment]
    original_text: str
    revised_text: str

def extract_text_from_pdf(file_path: str) -> List[str]:
    """Extract text from PDF, returning a list of strings per page."""
    doc = fitz.open(file_path)
    pages_text = []
    for page in doc:
        pages_text.append(page.get_text())
    return pages_text

def extract_text_from_docx(file_path: str) -> List[str]:
    """Extract text from DOCX."""
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return ["\n".join(full_text)]

def get_file_text(file_path: str, filename: str) -> List[str]:
    if filename.lower().endswith('.pdf'):
        return extract_text_from_pdf(file_path)
    elif filename.lower().endswith('.docx') or filename.lower().endswith('.doc'):
        return extract_text_from_docx(file_path)
    else:
        # Fallback for text files
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return [f.read()]

def calculate_similarity(text1: str, text2: str) -> float:
    return difflib.SequenceMatcher(None, text1, text2).ratio()

@router.post("/compare-documents", response_model=ComparisonResult)
async def compare_documents(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):
    temp_dir = tempfile.mkdtemp()
    try:
        file1_path = os.path.join(temp_dir, file1.filename)
        file2_path = os.path.join(temp_dir, file2.filename)

        with open(file1_path, "wb") as buffer:
            shutil.copyfileobj(file1.file, buffer)
        with open(file2_path, "wb") as buffer:
            shutil.copyfileobj(file2.file, buffer)

        text1_pages = get_file_text(file1_path, file1.filename)
        text2_pages = get_file_text(file2_path, file2.filename)

        # Flatten text for global comparison metrics
        full_text1 = "\n".join(text1_pages)
        full_text2 = "\n".join(text2_pages)

        # Use Gemini to analyze the differences
        prompt = f"""
        You are an expert legal document analyst. Compare the following two versions of a document and identify the changes.
        
        Original Document:
        {full_text1}
        
        Revised Document:
        {full_text2}
        
        Please provide a detailed analysis of the changes, including:
        1. A summary of additions, deletions, and modifications.
        2. A similarity score (percentage).
        3. A list of specific changes with their type (addition, deletion, modification), page number (approximate), and content.
        
        Format the output as a JSON object with the following structure:
        {{
            "summary": {{
                "additions": int,
                "deletions": int,
                "modifications": int,
                "similarityScore": "str"
            }},
            "changes": [
                {{
                    "type": "str",
                    "page": int,
                    "content": "str",
                    "original": "str"
                }}
            ]
        }}
        """
        
        try:
            response = model.generate_content(prompt)
            ai_analysis = json.loads(response.text.replace("```json", "").replace("```", ""))
            
            additions = ai_analysis["summary"]["additions"]
            deletions = ai_analysis["summary"]["deletions"]
            modifications = ai_analysis["summary"]["modifications"]
            similarity_score = ai_analysis["summary"]["similarityScore"]
            changes = ai_analysis["changes"]
            
            # Ensure 'original' and 'content' fields are always strings to prevent validation errors
            for change in changes:
                if "original" not in change or change["original"] is None:
                    change["original"] = ""
                if "content" not in change or change["content"] is None:
                    change["content"] = ""
            
        except Exception as e:
            # Fallback to difflib if AI fails
            print(f"AI Analysis failed: {e}. Falling back to difflib.")
            similarity = calculate_similarity(full_text1, full_text2)
            similarity_score = f"{int(similarity * 100)}%"

            # Detailed Diff
            d = difflib.Differ()
            diff = list(d.compare(full_text1.splitlines(), full_text2.splitlines()))

            additions = 0
            deletions = 0
            modifications = 0
            changes = []

            for i, line in enumerate(diff):
                if line.startswith('+ '):
                    additions += 1
                    changes.append({
                        "type": "addition",
                        "page": 1, # Placeholder
                        "content": line[2:].strip(),
                        "original": ""
                    })
                elif line.startswith('- '):
                    deletions += 1
                    changes.append({
                        "type": "deletion",
                        "page": 1, # Placeholder
                        "content": line[2:].strip(),
                        "original": line[2:].strip()
                    })

            # Refine modifications
            refined_changes = []
            skip_next = False
            
            for i in range(len(changes)):
                if skip_next:
                    skip_next = False
                    continue
                    
                current = changes[i]
                next_change = changes[i+1] if i+1 < len(changes) else None
                
                if (current['type'] == 'deletion' and next_change and next_change['type'] == 'addition'):
                    # It's a modification
                    modifications += 1
                    deletions -= 1
                    additions -= 1
                    
                    refined_changes.append({
                        "type": "modification",
                        "page": current['page'],
                        "content": next_change['content'],
                        "original": current['content']
                    })
                    skip_next = True
                else:
                    refined_changes.append(current)
            changes = refined_changes

        # Generate Unified View Segments
        unified_view = []
        d = difflib.Differ() # Re-initialize for unified view generation regardless of AI usage for summary
        
        # Re-run diff to capture all segments including unchanged text
        # Filter out the hint lines starting with '? ' which break the adjacency check for modifications
        full_diff = [line for line in d.compare(full_text1.splitlines(keepends=True), full_text2.splitlines(keepends=True)) if not line.startswith('? ')]
        
        i = 0
        while i < len(full_diff):
            line = full_diff[i]
            code = line[:2]
            text = line[2:]
            
            if code == '  ':
                unified_view.append({"type": "unchanged", "text": text})
                i += 1
            elif code == '- ':
                # Check if next line is an addition (modification)
                if i + 1 < len(full_diff) and full_diff[i+1].startswith('+ '):
                    old_line = text
                    new_line = full_diff[i+1][2:]
                    
                    # Word-level diff for this line
                    # Use None for autojunk to avoid treating spaces as junk which can split words weirdly
                    s = difflib.SequenceMatcher(None, old_line, new_line)
                    
                    # We need to process the opcodes to merge adjacent changes if they are part of the same word
                    # But difflib works on characters if we pass strings.
                    # To work on words, we should split by spaces.
                    
                    old_words = old_line.split()
                    new_words = new_line.split()
                    
                    s_words = difflib.SequenceMatcher(None, old_words, new_words)
                    
                    for tag, i1, i2, j1, j2 in s_words.get_opcodes():
                        if tag == 'equal':
                            unified_view.append({"type": "unchanged", "text": " ".join(old_words[i1:i2]) + " "})
                        elif tag == 'replace':
                            unified_view.append({"type": "deletion", "text": " ".join(old_words[i1:i2]) + " "})
                            unified_view.append({"type": "addition", "text": " ".join(new_words[j1:j2]) + " "})
                        elif tag == 'delete':
                            unified_view.append({"type": "deletion", "text": " ".join(old_words[i1:i2]) + " "})
                        elif tag == 'insert':
                            unified_view.append({"type": "addition", "text": " ".join(new_words[j1:j2]) + " "})
                    
                    if old_line.endswith('\n') or new_line.endswith('\n'):
                        unified_view.append({"type": "unchanged", "text": "\n"})

                    i += 2 # Skip both lines
                else:
                    unified_view.append({"type": "deletion", "text": text})
                    i += 1
            elif code == '+ ':
                unified_view.append({"type": "addition", "text": text})
                i += 1
            else:
                i += 1

        return {
            "summary": {
                "additions": additions,
                "deletions": deletions,
                "modifications": modifications,
                "similarityScore": similarity_score
            },
            "changes": changes[:100], # Limit changes
            "unified_view": unified_view,
            "original_text": full_text1,
            "revised_text": full_text2
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir)

class LegalSearchRequest(BaseModel):
    query: str
    page: Optional[int] = 0

@router.post("/legal-research")
async def legal_research(request: LegalSearchRequest):
    """Performs a search on the Indian Kanoon API."""
    try:
        result = await indian_kanoon_service.search_cases(request.query, request.page)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))