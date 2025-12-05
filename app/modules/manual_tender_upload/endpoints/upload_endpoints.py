"""
Endpoints for manual tender upload functionality.
"""
import logging
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db_session
from app.modules.auth.services.auth_service import get_current_active_user
from app.modules.manual_tender_upload.models.pydantic_models import (
    ManualTenderUploadRequest,
    ManualTenderUploadResponse,
    ManualTenderDetailsResponse,
    ManualTenderListResponse,
)
from app.modules.manual_tender_upload.repositories.repository import ManualTenderUploadRepository
from app.modules.manual_tender_upload.services.upload_service import (
    ManualTenderUploadService,
    PDFProcessingService,
)
from app.modules.analyze.db.schema import TenderAnalysis, AnalysisStatusEnum
from app.modules.analyze.repositories import repository as analyze_repo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/upload",
    response_model=ManualTenderUploadResponse,
    summary="Upload a manual tender/RFP document",
    tags=["Manual Tender Upload"],
)
async def upload_tender(
    file: UploadFile = File(..., description="PDF or DOCX file of the RFP/Tender"),
    tender_title: str = Form(..., description="Title of the tender"),
    tender_description: Optional[str] = Form(None),
    employer_name: Optional[str] = Form(None),
    estimated_cost: Optional[float] = Form(None),
    submission_deadline: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    opportunity_name: Optional[str] = Form(None),
    opportunity_description: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Upload a manual tender/RFP document.
    
    The file will be validated, stored, and an analysis task will be triggered.
    
    Parameters:
    - file: PDF or DOCX file containing the RFP/Tender document
    - tender_title: Title/name of the tender
    - tender_description: Optional description
    - employer_name: Name of employer/issuing authority
    - estimated_cost: Estimated contract value (in crore)
    - submission_deadline: Bid submission deadline
    - location: Project location
    - category: Tender category/type
    - opportunity_name: Name of business opportunity
    - opportunity_description: Opportunity description
    
    Returns:
    - Upload confirmation with upload reference and analysis tracking
    """
    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file
        is_valid, error_msg = ManualTenderUploadService.validate_file(
            file.filename,
            file_size,
            file.content_type or ""
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Generate upload reference
        upload_reference = ManualTenderUploadService.generate_upload_reference()
        
        # Save file
        try:
            file_path, relative_path = ManualTenderUploadService.save_uploaded_file(
                file_content,
                file.filename,
                upload_reference,
                current_user.id
            )
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save uploaded file"
            )
        
        # Create upload record
        mime_type = ManualTenderUploadService.get_file_mime_type(file.filename)
        
        # Parse submission deadline if provided
        submission_dt = None
        if submission_deadline:
            try:
                submission_dt = __import__('datetime').datetime.fromisoformat(submission_deadline)
            except:
                pass
        
        # Create database record
        upload_record = ManualTenderUploadRepository.create_upload(
            db=db,
            user_id=current_user.id,
            tender_title=tender_title,
            file_name=file.filename,
            file_path=file_path,
            file_size=file_size,
            file_mime_type=mime_type,
            upload_reference=upload_reference,
            tender_description=tender_description,
            employer_name=employer_name,
            estimated_cost=estimated_cost,
            submission_deadline=submission_dt,
            location=location,
            category=category,
            opportunity_name=opportunity_name,
            opportunity_description=opportunity_description,
        )
        
        logger.info(f"Manual tender uploaded: {upload_reference} by user {current_user.id}")
        
        # Trigger background analysis task
        background_tasks.add_task(
            trigger_manual_tender_analysis,
            upload_id=str(upload_record.id),
            file_path=file_path,
            tender_title=tender_title,
        )
        
        return ManualTenderUploadResponse(
            id=str(upload_record.id),
            upload_reference=upload_record.upload_reference,
            tender_title=upload_record.tender_title,
            file_name=upload_record.file_name,
            file_size=upload_record.file_size,
            created_at=upload_record.created_at,
            is_analyzed=upload_record.is_analyzed,
            analysis_id=str(upload_record.analysis_id) if upload_record.analysis_id else None,
            opportunity_name=upload_record.opportunity_name,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading tender: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading tender document"
        )


@router.get(
    "/uploads",
    response_model=list[ManualTenderListResponse],
    summary="List user's manual tender uploads",
    tags=["Manual Tender Upload"],
)
def list_user_uploads(
    limit: int = 50,
    offset: int = 0,
    only_unanalyzed: bool = False,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Get list of user's manual tender uploads.
    
    Parameters:
    - limit: Number of records to return (default: 50)
    - offset: Number of records to skip (default: 0)
    - only_unanalyzed: Filter to show only unanalyzed uploads
    
    Returns:
    - List of manual tender uploads with metadata
    """
    try:
        uploads = ManualTenderUploadRepository.get_user_uploads(
            db,
            current_user.id,
            limit=limit,
            offset=offset,
            only_unanalyzed=only_unanalyzed
        )
        return [ManualTenderListResponse.from_orm(u) for u in uploads]
    except Exception as e:
        logger.error(f"Error fetching uploads: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching tender uploads"
        )


@router.get(
    "/uploads/{upload_id}",
    response_model=ManualTenderDetailsResponse,
    summary="Get details of a manual tender upload",
    tags=["Manual Tender Upload"],
)
def get_upload_details(
    upload_id: str,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Get full details of a manual tender upload including analysis status.
    
    Parameters:
    - upload_id: UUID of the upload record
    
    Returns:
    - Detailed information about the upload and its analysis status
    """
    try:
        upload_uuid = uuid.UUID(upload_id)
        upload = ManualTenderUploadRepository.get_upload_by_id(db, upload_uuid)
        
        if not upload:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload not found"
            )
        
        # Verify ownership
        if upload.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return ManualTenderDetailsResponse.from_orm(upload)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching upload details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching upload details"
        )


@router.delete(
    "/uploads/{upload_id}",
    summary="Delete a manual tender upload",
    tags=["Manual Tender Upload"],
)
def delete_upload(
    upload_id: str,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Delete a manual tender upload and associated files.
    
    Parameters:
    - upload_id: UUID of the upload record
    
    Returns:
    - Success message
    """
    try:
        upload_uuid = uuid.UUID(upload_id)
        upload = ManualTenderUploadRepository.get_upload_by_id(db, upload_uuid)
        
        if not upload:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload not found"
            )
        
        # Verify ownership
        if upload.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Delete file from disk
        ManualTenderUploadService.delete_uploaded_file(upload.file_path)
        
        # Delete record
        ManualTenderUploadRepository.delete_upload(db, upload_uuid)
        
        logger.info(f"Upload deleted: {upload_id}")
        return {"message": "Upload deleted successfully"}
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting upload"
        )


def trigger_manual_tender_analysis(
    upload_id: str,
    file_path: str,
    tender_title: str,
):
    """
    Background task to analyze manually uploaded tender.
    
    This creates a TenderAnalysis record and triggers the analysis workflow.
    """
    try:
        from app.db.database import SessionLocal
        db = SessionLocal()
        
        upload_uuid = uuid.UUID(upload_id)
        upload = ManualTenderUploadRepository.get_upload_by_id(db, upload_uuid)
        
        if not upload:
            logger.error(f"Upload not found for analysis: {upload_id}")
            return
        
        # Extract text from PDF
        text_content = PDFProcessingService.extract_text_from_pdf(file_path)
        if not text_content:
            logger.warning(f"Could not extract text from PDF: {file_path}")
            text_content = tender_title  # Fallback
        
        # Create TenderAnalysis record
        # Using upload reference as tender_id for manual uploads
        analysis = TenderAnalysis(
            tender_id=upload.upload_reference,
            user_id=upload.user_id,
            status=AnalysisStatusEnum.pending,
            progress=0,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        # Link analysis to upload
        ManualTenderUploadRepository.mark_analyzed(db, upload_uuid, analysis.id)
        
        logger.info(f"Analysis record created for upload {upload_id}: {analysis.id}")
        
        # TODO: Trigger actual analysis task using Celery
        # from app.celery_app import analyze_tender_task
        # analyze_tender_task.delay(str(analysis.id), text_content)
        
        db.close()
    except Exception as e:
        logger.error(f"Error triggering analysis for upload {upload_id}: {e}", exc_info=True)
