from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional, List
from datetime import datetime

from app.modules.casetracker.models.schemas import (
    CaseResponse,
    CasesListResponse,
    UploadResponse,
    CaseUpdateRequest,
    CaseCreateRequest,
    SaveResearchCaseRequest
)
from app.modules.casetracker.services.document_service import DocumentService
from app.modules.casetracker.services.ai_analysis_service import AIAnalysisService
from app.modules.casetracker.services.case_service import CaseService
from app.modules.casetracker.services.save_research_case import SaveResearchCaseService


router = APIRouter()

# Initialize services
document_service = DocumentService()
ai_service = AIAnalysisService()
case_service = CaseService()
save_research_service = SaveResearchCaseService()


@router.post("/upload", response_model=UploadResponse)
async def upload_case_document(
    file: UploadFile = File(...),
    caseTitle: Optional[str] = Form(None),
    caseId: Optional[str] = Form(None),
    courtName: Optional[str] = Form(None),
    caseType: Optional[str] = Form("Arbitration"),
    litigationStatus: Optional[str] = Form("Pending")
):
    """
    Upload a legal document and create a new case with AI analysis
    
    Args:
        file: PDF file to upload
        caseTitle: Optional case title (overrides AI extraction)
        caseId: Optional case ID (overrides AI extraction)
        courtName: Optional court name (overrides AI extraction)
        caseType: Case type (default: Arbitration)
        litigationStatus: Litigation status (default: Pending)
        
    Returns:
        UploadResponse with created case
    """
    try:
        # Save document
        filename, file_path = await document_service.save_document(file)
        
        # Extract text from PDF
        document_text = document_service.extract_text_from_pdf(file_path)
        
        # Prepare user metadata
        user_metadata = {}
        if caseTitle:
            user_metadata['caseTitle'] = caseTitle
        if caseId:
            user_metadata['caseId'] = caseId
        if courtName:
            user_metadata['courtName'] = courtName
        if caseType:
            user_metadata['caseType'] = caseType
        if litigationStatus:
            user_metadata['litigationStatus'] = litigationStatus
        
        # Analyze document with AI
        ai_analysis = await ai_service.analyze_legal_document(
            document_text, 
            user_metadata
        )
        
        # Create case
        upload_date = datetime.now().strftime("%Y-%m-%d")
        new_case = case_service.create_case(
            ai_analysis=ai_analysis,
            document_filename=filename,
            upload_date=upload_date
        )
        
        return UploadResponse(
            message=f"Document '{filename}' uploaded and analyzed successfully",
            case=new_case
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )


@router.get("/cases", response_model=CasesListResponse)
async def get_all_cases():
    """
    Get all cases with summary statistics
    
    Returns:
        CasesListResponse with all cases and stats
    """
    try:
        cases = case_service.get_all_cases()
        stats = case_service.get_summary_stats()
        
        return CasesListResponse(
            cases=cases,
            totalActiveCases=stats['totalActiveCases'],
            upcomingHearings=stats['upcomingHearings'],
            avgCaseDuration=stats['avgCaseDuration']
        )
    
    except Exception as e:
        print(f"Error fetching cases: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch cases: {str(e)}"
        )


@router.get("/cases/{case_id}", response_model=CaseResponse)
async def get_case_by_id(case_id: int):
    """
    Get a specific case by ID
    
    Args:
        case_id: Case ID
        
    Returns:
        CaseResponse for the requested case
        
    Raises:
        HTTPException: If case not found
    """
    case = case_service.get_case_by_id(case_id)
    
    if not case:
        raise HTTPException(
            status_code=404,
            detail=f"Case with ID {case_id} not found"
        )
    
    return case


@router.put("/cases/{case_id}", response_model=CaseResponse)
async def update_case(case_id: int, update_data: CaseUpdateRequest):
    """
    Update a case
    
    Args:
        case_id: Case ID to update
        update_data: Updated case data
        
    Returns:
        Updated CaseResponse
        
    Raises:
        HTTPException: If case not found or update fails
    """
    updated_case = case_service.update_case(
        case_id=case_id,
        update_data=update_data.dict(exclude_unset=True)
    )
    
    if not updated_case:
        raise HTTPException(
            status_code=404,
            detail=f"Case with ID {case_id} not found"
        )
    
    return updated_case


@router.delete("/cases/{case_id}")
async def delete_case(case_id: int):
    """
    Delete a case
    
    Args:
        case_id: Case ID to delete
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If case not found
    """
    success = case_service.delete_case(case_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Case with ID {case_id} not found"
        )
    
    return {"message": f"Case {case_id} deleted successfully"}


@router.post("/save-research-case", response_model=CaseResponse)
async def save_research_case(request: SaveResearchCaseRequest):
    """
    Save a legal research case to Case Tracker
    
    Fetches full case text from Indian Kanoon API, analyzes it with AI,
    and saves to the case tracker database.
    
    Args:
        request: SaveResearchCaseRequest with case details
        
    Returns:
        CaseResponse with complete case data
        
    Raises:
        HTTPException: If fetching or analysis fails
    """
    try:
        print(f"Received save-research-case request:")
        print(f"  Title: {request.title}")
        print(f"  TID: {request.tid}")
        print(f"  Docsource: {request.docsource}")
        print(f"  Date: {request.date}")
        
        new_case = await save_research_service.save_research_case_to_tracker(
            title=request.title,
            tid=request.tid,
            docsource=request.docsource,
            decided_date=request.date
        )
        
        print(f"Successfully created case with ID: {new_case.caseId}")
        return new_case
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving research case: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save research case: {str(e)}"
        )
