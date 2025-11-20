from typing import List
import uuid
import tempfile
import os
import stat
import asyncio
import json
from fastapi import APIRouter, HTTPException, Path, UploadFile, File, BackgroundTasks, status, Depends, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from app.modules.askai.models.document import AddDriveRequest, ChatDocumentsResponse, DriveFolder, ProcessingJob, ProcessingStage, ProcessingStatus, UploadAcceptedResponse, DocumentMetadata, UploadJob
from app.modules.askai.db.models import Chat as SQLChat, Document as SQLDocument
from app.core import services
from app.core.global_stores import upload_jobs
from app.db.database import get_db_session
from app.config import settings
from app.modules.askai.services import drive_service, chat_service
from app.modules.askai.services.document_processing_service import process_uploaded_pdf

router = APIRouter()

@router.post("/chats/{chat_id}/upload-pdf", response_model=UploadAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, tags=["AskAI - Documents"])
async def upload_pdf(
    chat_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    pdf: UploadFile = File(..., description="The PDF file to upload", alias="pdf")
):
    """Upload a PDF for RAG processing. This is an asynchronous operation."""
    if not (pdf.filename or "unknown").lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a PDF")

    chat = db.get(SQLChat, chat_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    if len(chat.documents) >= settings.MAX_PDFS_PER_CHAT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Maximum {settings.MAX_PDFS_PER_CHAT} PDFs per chat")

    if any(doc.filename == pdf.filename for doc in chat.documents):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"PDF '{pdf.filename}' already uploaded")

    # Save to a temporary file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await pdf.read()
            if len(content) > settings.MAX_PDF_SIZE_MB * 1024 * 1024:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File too large. Max: {settings.MAX_PDF_SIZE_MB}MB")
            
            tmp.write(content)
            temp_path = tmp.name
        
        os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not save uploaded file: {e}")

    # Start background processing
    job_id = str(uuid.uuid4())
    upload_jobs[job_id] = UploadJob(
        job_id = job_id,
        status=ProcessingStatus.QUEUED,
        chat_id=str(chat_id),
        filename=pdf.filename or "unknown-file.pdf",
        progress=0,
        stage=ProcessingStage.NOT_PROCESSING,
        finished_at="",
        chunks_added=0,
        error=None
    )
    background_tasks.add_task(process_uploaded_pdf, temp_path, str(chat_id), pdf.filename or "unknown-file.pdf", job_id)

    return {"message": "Upload accepted", "job_id": job_id, "processing": True}

@router.post("/chats/{chat_id}/add-drive", response_model=DriveFolder, tags=["AskAI - Documents"])
def add_drive_folder(
    chat_id: uuid.UUID,
    payload: AddDriveRequest,
    db: Session = Depends(get_db_session)
):
    """
    Scans a public Google Drive folder and adds its file structure to the chat
    without downloading the files.
    """
    chat = db.get(SQLChat, chat_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    
    try:
        folder_structure = drive_service.add_drive_folder_to_chat(db, chat_id, payload.driveUrl)
        return folder_structure
    except (ValueError, Exception) as e:
        # Catches invalid URLs from service logic and other potential errors.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/upload-status/{job_id}", tags=["AskAI - Documents"])
def get_upload_status(job_id: str = Path(..., description="The ID of the upload job")):
    """Get the status of an asynchronous upload job"""
    status = upload_jobs.get(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status

def _get_chat_docs_data(chat_id: uuid.UUID, db: Session) -> dict:
    """Helper function to fetch and structure document data for a chat."""
    chat = db.get(SQLChat, chat_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    
    pdfs = [DocumentMetadata(name=doc.filename, chunks=len(doc.chunks), status=doc.status) for doc in chat.documents if doc.doc_type == 'pdf']
    excel = [DocumentMetadata(name=doc.filename, chunks=len(doc.chunks), status=doc.status) for doc in chat.documents if doc.doc_type == 'excel']

    processing_jobs: List[ProcessingJob] = []
    for jid, job in upload_jobs.items():
        if job.chat_id == str(chat_id):
            processing_job = ProcessingJob(name=job.filename, job_id=jid, status=job.status, stage=job.stage, progress=job.progress)
            processing_jobs.append(processing_job)
    
    response_data = ChatDocumentsResponse(
        pdfs=pdfs,
        xlsx=excel,
        processing=processing_jobs,
        drive_folders=chat.drive_folders,
        total_docs=len(pdfs) + len(excel) + len(processing_jobs),
        chat_id=str(chat_id)
    )
    return response_data.model_dump()

@router.get("/chats/{chat_id}/docs", response_model=ChatDocumentsResponse, tags=["AskAI - Documents"])
def get_chat_docs(chat_id: uuid.UUID, db: Session = Depends(get_db_session)):
    """Get all active and processing documents for a specific chat"""
    return _get_chat_docs_data(chat_id, db)

@router.get("/chats/{chat_id}/docs-sse", tags=["AskAI - Documents"])
async def stream_chat_docs(
    chat_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db_session)
):
    """
    Streams document status for a chat using Server-Sent Events (SSE).
    Sends an update whenever the status of a document processing job changes.
    """
    async def event_generator():
        last_data = None
        while True:
            if await request.is_disconnected():
                break
            
            try:
                current_data = _get_chat_docs_data(chat_id, db)
                if current_data != last_data:
                    yield json.dumps(current_data)
                    last_data = current_data
            except HTTPException:
                # This can happen if the chat is deleted during an active stream.
                break
            except Exception as e:
                print(f"Error in SSE stream for chat {chat_id}: {e}")
                break
                
            await asyncio.sleep(1)
            
    return EventSourceResponse(event_generator())

@router.delete("/chats/{chat_id}/pdfs/{pdf_name}", tags=["AskAI - Documents"])
def delete_chat_pdf(chat_id: uuid.UUID, pdf_name: str, db: Session = Depends(get_db_session)):
    """Delete a specific PDF from a chat"""
    success, message = chat_service.remove_document_from_chat(db, chat_id, pdf_name)
    if not success:
        # Use 404 for not found, which covers both chat and document cases
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    
    return {"message": message, "chat_id": str(chat_id), "pdf_name": pdf_name}
