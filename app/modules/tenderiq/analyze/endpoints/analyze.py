"""
API Endpoints for TenderIQ Analyze module.

Implements all 10 analyze endpoints for tender document analysis.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.db.database import get_db_session
from app.modules.auth.services.auth_service import get_current_active_user
from app.modules.tenderiq.analyze.models.pydantic_models import (
    AnalyzeTenderRequest,
    GenerateOnePagerRequest,
    AnalysisInitiatedResponse,
    AnalysisStatusResponse,
    AnalysisResultsResponse,
    RiskAssessmentResponse,
    RFPAnalysisResponse,
    ScopeOfWorkResponse,
    OnePagerResponse,
    DataSheetResponse,
    AnalysesListResponse,
    DeleteAnalysisResponse,
)
from app.modules.tenderiq.analyze.services.analysis_service import AnalysisService
from app.modules.tenderiq.analyze.services.risk_assessment_service import RiskAssessmentService
from app.modules.tenderiq.analyze.services.rfp_extraction_service import RFPExtractionService
from app.modules.tenderiq.analyze.services.scope_extraction_service import ScopeExtractionService
from app.modules.tenderiq.analyze.services.report_generation_service import ReportGenerationService

router = APIRouter()


# ==================== Endpoint 1: Initiate Analysis ====================

@router.post(
    "/tender/{tender_id}",
    response_model=AnalysisInitiatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Analyze"],
    summary="Initiate tender document analysis",
)
def initiate_analysis(
    tender_id: UUID,
    request: AnalyzeTenderRequest,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Initiate analysis of a tender document.

    Starts asynchronous analysis of tender documents. Returns immediately with
    analysisId which can be used to check status and retrieve results.

    **Request:**
    ```json
    {
      "documentIds": ["uuid"],  // Optional: specific documents to analyze
      "analysisType": "full|summary|risk-only",  // Optional
      "includeRiskAssessment": true,
      "includeRfpAnalysis": true,
      "includeScopeOfWork": true
    }
    ```

    **Response (202 Accepted):**
    ```json
    {
      "analysisId": "uuid",
      "tenderId": "uuid",
      "status": "pending",
      "createdAt": "2025-11-05T10:30:00Z",
      "estimatedCompletionTime": 30000
    }
    ```

    **Status Codes:**
    - `202 Accepted` - Analysis initiated
    - `400 Bad Request` - Invalid tender or document ID
    - `404 Not Found` - Tender not found
    - `503 Service Unavailable` - Analysis service unavailable
    """
    try:
        service = AnalysisService()

        # TODO: Verify tender exists
        # TODO: Verify documents exist if specified

        response = service.initiate_analysis(
            db=db,
            tender_id=tender_id,
            user_id=current_user.id,
            analysis_type=request.analysis_type,
            include_risk_assessment=request.include_risk_assessment,
            include_rfp_analysis=request.include_rfp_analysis,
            include_scope_of_work=request.include_scope_of_work,
        )

        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        print(f"❌ Error initiating analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis service temporarily unavailable",
        )


# ==================== Endpoint 2: Get Analysis Results ====================

@router.get(
    "/results/{analysis_id}",
    response_model=AnalysisResultsResponse,
    tags=["Analyze"],
    summary="Get completed analysis results",
)
def get_analysis_results(
    analysis_id: UUID,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Retrieve completed analysis results for a tender.

    Returns full analysis results if completed, still processing, or expired.

    **Response (200 OK):**
    ```json
    {
      "analysisId": "uuid",
      "tenderId": "uuid",
      "status": "completed",
      "results": {
        "summary": {...},
        "riskAssessment": {...},
        "rfpAnalysis": {...},
        "scopeOfWork": {...},
        "onePager": {...}
      },
      "completedAt": "2025-11-05T10:35:00Z",
      "processingTimeMs": 305000
    }
    ```

    **Status Codes:**
    - `200 OK` - Results retrieved
    - `202 Accepted` - Still processing
    - `404 Not Found` - Analysis ID not found
    - `410 Gone` - Analysis results expired
    """
    try:
        service = AnalysisService()

        results = service.get_analysis_results(
            db=db,
            analysis_id=analysis_id,
            user_id=current_user.id,
        )

        if results is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found or results expired",
            )

        return results

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving analysis results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving results",
        )


# ==================== Endpoint 3: Get Analysis Status ====================

@router.get(
    "/status/{analysis_id}",
    response_model=AnalysisStatusResponse,
    tags=["Analyze"],
    summary="Check analysis status",
)
def get_analysis_status(
    analysis_id: UUID,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Get current status of an ongoing analysis.

    Lightweight endpoint to check processing progress without retrieving full results.

    **Response (200 OK):**
    ```json
    {
      "analysisId": "uuid",
      "tenderId": "uuid",
      "status": "processing",
      "progress": 45,
      "currentStep": "analyzing-risk",
      "errorMessage": null
    }
    ```

    **Status Codes:**
    - `200 OK` - Status retrieved
    - `404 Not Found` - Analysis ID not found
    """
    try:
        service = AnalysisService()

        status_response = service.get_analysis_status(
            db=db,
            analysis_id=analysis_id,
            user_id=current_user.id,
        )

        if status_response is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found",
            )

        return status_response

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting analysis status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving status",
        )


# ==================== Endpoint 4: Get Risk Assessment ====================

@router.get(
    "/tender/{tender_id}/risks",
    response_model=RiskAssessmentResponse,
    tags=["Analyze"],
    summary="Get risk assessment for tender",
)
def get_risk_assessment(
    tender_id: UUID,
    depth: str = Query("summary", description="summary or detailed"),
    include_historical: bool = Query(False, description="Include historical risks"),
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Retrieve risk assessment for a tender.

    Can be used independently from full analysis.

    **Query Parameters:**
    - `depth`: "summary" or "detailed" (default: summary)
    - `includeHistorical`: boolean (default: false)

    **Response (200 OK):**
    ```json
    {
      "tenderId": "uuid",
      "overallRiskLevel": "high",
      "riskScore": 72,
      "executiveSummary": "...",
      "risks": [
        {
          "id": "uuid",
          "level": "high",
          "category": "financial",
          "title": "...",
          "description": "...",
          "impact": "high",
          "likelihood": "medium",
          "mitigationStrategy": "...",
          "recommendedAction": "...",
          "relatedDocuments": ["uuid"]
        }
      ],
      "analyzedAt": "2025-11-05T10:35:00Z"
    }
    ```

    **Status Codes:**
    - `200 OK` - Risk assessment retrieved
    - `202 Accepted` - Analysis in progress
    - `404 Not Found` - Tender not found
    """
    try:
        # For now, create a temporary analysis record for this request
        # TODO: Check for existing analysis or create new one
        from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository

        repo = AnalyzeRepository(db)
        analysis = repo.create_analysis(
            tender_id=tender_id,
            user_id=current_user.id,
            analysis_type="risk-only",
        )

        service = RiskAssessmentService()

        risk_response = service.assess_risks(
            db=db,
            analysis_id=analysis.id,
            tender_id=tender_id,
            depth=depth,
            include_historical=include_historical,
        )

        return risk_response

    except Exception as e:
        print(f"❌ Error getting risk assessment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving risk assessment",
        )


# ==================== Endpoint 5: Get RFP Section Analysis ====================

@router.get(
    "/tender/{tender_id}/rfp-sections",
    response_model=RFPAnalysisResponse,
    tags=["Analyze"],
    summary="Get RFP section analysis",
)
def get_rfp_sections(
    tender_id: UUID,
    section_number: Optional[str] = Query(None, description="Get specific section"),
    include_compliance: bool = Query(False, description="Include compliance info"),
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Extract and analyze RFP sections from tender documents.

    **Query Parameters:**
    - `sectionNumber`: Optional section number (e.g., "1.1")
    - `includeCompliance`: boolean (default: false)

    **Response (200 OK):**
    ```json
    {
      "tenderId": "uuid",
      "totalSections": 15,
      "sections": [
        {
          "id": "uuid",
          "number": "1.1",
          "title": "Eligibility Criteria",
          "description": "...",
          "keyRequirements": ["..."],
          "compliance": {
            "status": "compliant",
            "issues": []
          },
          "estimatedComplexity": "medium",
          "relatedSections": ["1.2"],
          "documentReferences": [{"documentId": "uuid", "pageNumber": 5}]
        }
      ],
      "summary": {
        "totalRequirements": 45,
        "criticality": {"high": 12, "medium": 23, "low": 10}
      }
    }
    ```

    **Status Codes:**
    - `200 OK` - RFP analysis retrieved
    - `202 Accepted` - Analysis in progress
    - `404 Not Found` - Tender not found
    """
    try:
        from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository

        repo = AnalyzeRepository(db)
        analysis = repo.create_analysis(
            tender_id=tender_id,
            user_id=current_user.id,
            analysis_type="full",
            include_rfp_analysis=True,
        )

        service = RFPExtractionService()

        rfp_response = service.extract_rfp_sections(
            db=db,
            analysis_id=analysis.id,
            tender_id=tender_id,
            section_number=section_number,
            include_compliance=include_compliance,
        )

        return rfp_response

    except Exception as e:
        print(f"❌ Error getting RFP sections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving RFP sections",
        )


# ==================== Endpoint 6: Get Scope of Work ====================

@router.get(
    "/tender/{tender_id}/scope-of-work",
    response_model=ScopeOfWorkResponse,
    tags=["Analyze"],
    summary="Get scope of work analysis",
)
def get_scope_of_work(
    tender_id: UUID,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Extract and analyze the scope of work from tender documents.

    **Response (200 OK):**
    ```json
    {
      "tenderId": "uuid",
      "scopeOfWork": {
        "description": "...",
        "workItems": [
          {
            "id": "uuid",
            "description": "...",
            "estimatedDuration": "30 days",
            "priority": "high",
            "dependencies": ["uuid"]
          }
        ],
        "keyDeliverables": [
          {
            "id": "uuid",
            "description": "...",
            "deliveryDate": "2025-12-31",
            "acceptanceCriteria": ["..."]
          }
        ],
        "estimatedTotalEffort": 120,
        "estimatedTotalDuration": "120 days",
        "keyDates": {
          "startDate": "2025-12-01",
          "endDate": "2026-04-09"
        }
      },
      "analyzedAt": "2025-11-05T10:35:00Z"
    }
    ```

    **Status Codes:**
    - `200 OK` - Scope analysis retrieved
    - `202 Accepted` - Analysis in progress
    - `404 Not Found` - Tender not found
    """
    try:
        from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository

        repo = AnalyzeRepository(db)
        analysis = repo.create_analysis(
            tender_id=tender_id,
            user_id=current_user.id,
            analysis_type="full",
            include_scope_of_work=True,
        )

        service = ScopeExtractionService()

        scope_response = service.extract_scope(
            db=db,
            analysis_id=analysis.id,
            tender_id=tender_id,
        )

        return scope_response

    except Exception as e:
        print(f"❌ Error getting scope of work: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving scope of work",
        )


# ==================== Endpoint 7: Generate One-Pager ====================

@router.post(
    "/tender/{tender_id}/one-pager",
    response_model=OnePagerResponse,
    tags=["Analyze"],
    summary="Generate one-pager executive summary",
)
def generate_one_pager(
    tender_id: UUID,
    request: GenerateOnePagerRequest,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Generate a one-page executive summary of the tender analysis.

    **Request:**
    ```json
    {
      "format": "markdown|html|pdf",
      "includeRiskAssessment": true,
      "includeScopeOfWork": true,
      "includeFinancials": true,
      "maxLength": 800
    }
    ```

    **Response (200 OK):**
    ```json
    {
      "tenderId": "uuid",
      "onePager": {
        "content": "# Tender Summary...",
        "format": "markdown",
        "generatedAt": "2025-11-05T10:35:00Z"
      }
    }
    ```

    **Status Codes:**
    - `200 OK` - One-pager generated
    - `202 Accepted` - Generation in progress
    - `404 Not Found` - Tender not found
    - `503 Service Unavailable` - Generation service unavailable
    """
    try:
        from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository

        repo = AnalyzeRepository(db)
        analysis = repo.create_analysis(
            tender_id=tender_id,
            user_id=current_user.id,
            analysis_type="summary",
        )

        service = ReportGenerationService()

        one_pager = service.generate_one_pager(
            db=db,
            analysis_id=analysis.id,
            tender_id=tender_id,
            format=request.format,
            include_risk_assessment=request.include_risk_assessment,
            include_scope_of_work=request.include_scope_of_work,
            include_financials=request.include_financials,
            max_length=request.max_length,
        )

        return one_pager

    except Exception as e:
        print(f"❌ Error generating one-pager: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating one-pager",
        )


# ==================== Endpoint 8: Generate Data Sheet ====================

@router.get(
    "/tender/{tender_id}/data-sheet",
    response_model=DataSheetResponse,
    tags=["Analyze"],
    summary="Generate data sheet",
)
def generate_data_sheet(
    tender_id: UUID,
    format: str = Query("json", description="json, csv, or excel"),
    include_analysis: bool = Query(True, description="Include analysis results"),
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Generate a structured data sheet with key tender information.

    **Query Parameters:**
    - `format`: "json", "csv", or "excel" (default: json)
    - `includeAnalysis`: boolean (default: true)

    **Response (200 OK - JSON):**
    ```json
    {
      "tenderId": "uuid",
      "dataSheet": {
        "basicInfo": {
          "tenderNumber": "...",
          "tenderName": "...",
          "tenderingAuthority": "...",
          "tenderURL": "..."
        },
        "financialInfo": {
          "estimatedValue": 10000000,
          "currency": "INR",
          "emd": 500000,
          "bidSecurityRequired": true
        },
        "temporal": {
          "releaseDate": "2025-11-05",
          "dueDate": "2025-12-15",
          "openingDate": "2025-12-20"
        },
        "scope": {
          "location": "Mumbai",
          "category": "Civil",
          "description": "..."
        },
        "analysis": {
          "riskLevel": "medium",
          "estimatedEffort": 120,
          "complexityLevel": "medium"
        }
      },
      "generatedAt": "2025-11-05T10:35:00Z"
    }
    ```

    **Status Codes:**
    - `200 OK` - Data sheet retrieved
    - `202 Accepted` - Generation in progress
    - `404 Not Found` - Tender not found
    """
    try:
        service = ReportGenerationService()

        data_sheet = service.generate_data_sheet(
            db=db,
            tender_id=tender_id,
            format=format,
            include_analysis=include_analysis,
        )

        # TODO: Handle CSV/Excel format conversion
        # For now, always return JSON structured data

        return data_sheet

    except Exception as e:
        print(f"❌ Error generating data sheet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating data sheet",
        )


# ==================== Endpoint 9: List Recent Analyses ====================

@router.get(
    "/analyses",
    response_model=AnalysesListResponse,
    tags=["Analyze"],
    summary="List recent analyses",
)
def list_analyses(
    limit: int = Query(20, description="Results per page (max 100)"),
    offset: int = Query(0, description="Offset for pagination"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tender_id: Optional[UUID] = Query(None, description="Filter by tender"),
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    List recent analyses for the authenticated user.

    **Query Parameters:**
    - `limit`: Results per page (default: 20, max: 100)
    - `offset`: Offset for pagination (default: 0)
    - `status`: Optional filter by status (pending, processing, completed, failed)
    - `tenderId`: Optional filter by tender ID

    **Response (200 OK):**
    ```json
    {
      "analyses": [
        {
          "analysisId": "uuid",
          "tenderId": "uuid",
          "tenderName": "...",
          "status": "completed",
          "createdAt": "2025-11-05T10:30:00Z",
          "completedAt": "2025-11-05T10:35:00Z",
          "processingTimeMs": 305000
        }
      ],
      "pagination": {
        "total": 150,
        "limit": 20,
        "offset": 0
      }
    }
    ```

    **Status Codes:**
    - `200 OK` - Analyses retrieved
    - `401 Unauthorized` - Authentication required
    """
    try:
        service = AnalysisService()

        analyses_response = service.list_user_analyses(
            db=db,
            user_id=current_user.id,
            status=status,
            tender_id=tender_id,
            limit=limit,
            offset=offset,
        )

        return analyses_response

    except Exception as e:
        print(f"❌ Error listing analyses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing analyses",
        )


# ==================== Endpoint 10: Delete Analysis ====================

@router.delete(
    "/results/{analysis_id}",
    response_model=DeleteAnalysisResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analyze"],
    summary="Delete analysis",
)
def delete_analysis(
    analysis_id: UUID,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Delete a completed analysis and its results.

    **Response (200 OK):**
    ```json
    {
      "success": true,
      "message": "Analysis deleted successfully"
    }
    ```

    **Status Codes:**
    - `200 OK` - Deletion successful
    - `404 Not Found` - Analysis ID not found
    - `403 Forbidden` - Insufficient permissions
    """
    try:
        service = AnalysisService()

        success = service.delete_analysis(
            db=db,
            analysis_id=analysis_id,
            user_id=current_user.id,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found",
            )

        return DeleteAnalysisResponse(
            success=True,
            message="Analysis deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting analysis",
        )
