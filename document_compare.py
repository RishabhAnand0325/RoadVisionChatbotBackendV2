import os
import difflib
from typing import List, Dict, Any, Tuple
import fitz  # PyMuPDF
from docx import Document
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import tempfile
import shutil

router = APIRouter()

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

class ComparisonResult(BaseModel):
    summary: ComparisonSummary
    changes: List[ChangeItem]

def extract_text_from_pdf(file_path: str) -> List[str]:
    """Extract text from PDF, returning a list of strings per page."""
    doc = fitz.open(file_path)
    pages_text = []
    for page in doc:
        pages_text.append(page.get_text())
    return pages_text

def extract_text_from_docx(file_path: str) -> List[str]:
    """Extract text from DOCX. Note: DOCX doesn't have fixed pages like PDF.
    We'll treat paragraphs as chunks or try to approximate pages if needed.
    For simplicity, we'll return the whole text as one 'page' or split by some logic.
    Here, we'll just return the full text as a single page for now, or split by paragraphs.
    Let's split by reasonable chunks to simulate pages if needed, or just return one big page.
    """
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

        similarity = calculate_similarity(full_text1, full_text2)
        similarity_score = f"{int(similarity * 100)}%"

        # Detailed Diff
        d = difflib.Differ()
        diff = list(d.compare(full_text1.splitlines(), full_text2.splitlines()))

        additions = 0
        deletions = 0
        modifications = 0
        changes = []

        # Simple heuristic to group changes
        # This is a basic implementation. For production, you'd want a more robust diffing algorithm
        # that handles block moves and fuzzy matching better.
        
        for i, line in enumerate(diff):
            if line.startswith('+ '):
                additions += 1
                # Try to find page number (approximate)
                # In a real implementation, we'd map lines back to page numbers
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
            elif line.startswith('? '):
                # This indicates a modification in the previous line(s)
                # We might count this as modification instead of add/delete pair if we parse carefully
                pass

        # Refine modifications: if we have a delete followed immediately by an add, it's a modification
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
                # Adjust counts
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

        return {
            "summary": {
                "additions": additions,
                "deletions": deletions,
                "modifications": modifications,
                "similarityScore": similarity_score
            },
            "changes": refined_changes[:50] # Limit to 50 changes for performance/display
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir)
