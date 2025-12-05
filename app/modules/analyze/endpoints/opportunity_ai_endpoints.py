"""
Endpoints for AI interactions within a specific opportunity context.
"""
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db_session
from app.modules.auth.services.auth_service import get_current_active_user
from app.modules.analyze.services.opportunity_ai_service import OpportunityAIService, ConversationManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/opportunity-ai", tags=["Opportunity AI"])


class OpportunityQuestion(BaseModel):
    """Request model for opportunity question."""
    question: str
    include_analysis: bool = True
    conversation_history: Optional[list] = None


class OpportunitySummaryRequest(BaseModel):
    """Request model for opportunity summary."""
    summary_type: str = "executive"  # executive, detailed, compliance


class ComplianceExtractionRequest(BaseModel):
    """Request model for compliance extraction."""
    focus_areas: Optional[list] = None


class OpportunityComparisonRequest(BaseModel):
    """Request model for opportunity comparison."""
    opportunity_id_2: str
    comparison_criteria: Optional[list] = None


@router.post(
    "/{opportunity_id}/ask",
    summary="Ask AI about an opportunity",
    tags=["Opportunity AI"],
)
async def ask_opportunity_question(
    opportunity_id: str,
    request: OpportunityQuestion,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Ask a question about a specific opportunity/tender within its context.
    
    The AI will consider:
    - Tender analysis data (one-pager, scope, risks)
    - RFP sections and requirements
    - Document templates needed
    - Historical context from conversation
    
    Parameters:
    - opportunity_id: UUID or upload reference of the tender
    - question: Your question about the opportunity
    - include_analysis: Include AI analysis data in response
    - conversation_history: Previous messages for continuity
    
    Returns:
    - AI response with answer and source references
    """
    try:
        # Verify opportunity exists and user has access
        # TODO: Add proper access control
        
        response = await OpportunityAIService.ask_opportunity_question(
            opportunity_id=opportunity_id,
            question=request.question,
            include_analysis=request.include_analysis,
            conversation_history=request.conversation_history,
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/{opportunity_id}/summary",
    summary="Generate AI summary of opportunity",
    tags=["Opportunity AI"],
)
async def generate_opportunity_summary(
    opportunity_id: str,
    request: OpportunitySummaryRequest,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Generate an AI-powered summary of an opportunity.
    
    Summary types:
    - **executive**: High-level overview for quick briefing
    - **detailed**: Comprehensive analysis with all details
    - **compliance**: Focus on compliance and qualification requirements
    
    Parameters:
    - opportunity_id: UUID or upload reference
    - summary_type: Type of summary needed
    
    Returns:
    - Generated summary with key points
    """
    try:
        response = await OpportunityAIService.generate_opportunity_summary(
            opportunity_id=opportunity_id,
            summary_type=request.summary_type,
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/{opportunity_id}/insights",
    summary="Get AI insights for opportunity",
    tags=["Opportunity AI"],
)
async def get_opportunity_insights(
    opportunity_id: str,
    focus_areas: Optional[str] = None,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Get key insights and identified risks from an opportunity analysis.
    
    Focus areas (comma-separated):
    - scope: Project scope and deliverables
    - timeline: Deadlines and schedule
    - compliance: Qualification and compliance requirements
    - finance: Financial and cost aspects
    - risk: Identified risks and mitigation
    
    Parameters:
    - opportunity_id: UUID or upload reference
    - focus_areas: Comma-separated areas to focus on
    
    Returns:
    - Key insights, identified risks, and recommendations
    """
    try:
        focus_list = None
        if focus_areas:
            focus_list = [f.strip() for f in focus_areas.split(",")]
        
        response = await OpportunityAIService.get_key_insights(
            opportunity_id=opportunity_id,
            focus_areas=focus_list,
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error fetching insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/{opportunity_id}/compare",
    summary="Compare two opportunities",
    tags=["Opportunity AI"],
)
async def compare_opportunities(
    opportunity_id: str,
    request: OpportunityComparisonRequest,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Compare two opportunities side-by-side.
    
    Comparison can focus on:
    - cost: Financial aspects and contract value
    - timeline: Deadlines and schedules
    - scope: Work scope and deliverables
    - compliance: Requirements differences
    - all: Compare all aspects
    
    Parameters:
    - opportunity_id: First opportunity (UUID or upload reference)
    - opportunity_id_2: Second opportunity to compare
    - comparison_criteria: What to compare
    
    Returns:
    - Comparison analysis and differences
    """
    try:
        response = await OpportunityAIService.compare_opportunities(
            opportunity_id_1=opportunity_id,
            opportunity_id_2=request.opportunity_id_2,
            comparison_criteria=request.comparison_criteria,
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error comparing opportunities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/{opportunity_id}/compliance",
    summary="Extract compliance requirements",
    tags=["Opportunity AI"],
)
async def extract_compliance_requirements(
    opportunity_id: str,
    db: Session = Depends(get_db_session),
    current_user = Depends(get_current_active_user),
):
    """
    Extract all compliance and qualification requirements from an opportunity.
    
    Returns structured information about:
    - Mandatory compliance requirements
    - Qualification criteria
    - Required documentation
    - Certification needs
    
    Parameters:
    - opportunity_id: UUID or upload reference
    
    Returns:
    - Compliance requirements, qualifications, and documentation needed
    """
    try:
        response = await OpportunityAIService.extract_compliance_requirements(
            opportunity_id=opportunity_id,
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error extracting compliance requirements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
