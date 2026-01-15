"""
Service to save legal research cases to case tracker.
Fetches full case text from Indian Kanoon API and uses AI analysis.
"""
import os
import asyncio
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException

from app.modules.casetracker.services.ai_analysis_service import AIAnalysisService
from app.modules.casetracker.services.case_service import CaseService
from app.modules.casetracker.models.schemas import CaseResponse
from app.config import settings


class SaveResearchCaseService:
    """Service for saving legal research cases to case tracker"""
    
    def __init__(self):
        self.ai_service = AIAnalysisService()
        self.case_service = CaseService()
    
    async def save_research_case_to_tracker(
        self,
        title: str,
        tid: str,
        docsource: str,
        decided_date: Optional[str] = None
    ) -> CaseResponse:
        """
        Save a legal research case to the case tracker
        
        Args:
            title: Case title from Indian Kanoon
            tid: Indian Kanoon document ID
            docsource: Source of the document (e.g., "Supreme Court")
            decided_date: Date the case was decided
            
        Returns:
            CaseResponse object with all case details
            
        Raises:
            HTTPException: If fetching or processing fails
        """
        try:
            # Step 1: Fetch full case text from Indian Kanoon API
            case_html = self._fetch_case_text_from_api(tid)
            
            if not case_html or len(case_html.strip()) < 100:
                raise HTTPException(
                    status_code=400,
                    detail="Could not fetch sufficient case text from Indian Kanoon API"
                )
            
            # Step 2: Strip HTML tags to get clean text for AI analysis
            case_text = self._strip_html(case_html)
            
            print(f"Fetched case text length: {len(case_text)} characters")
            print(f"First 500 chars: {case_text[:500]}")
            
            # Step 3: Prepare metadata to guide AI analysis
            user_metadata = {
                "caseTitle": title,
                "courtName": docsource,
                "filingDate": decided_date if decided_date else "N/A",
            }
            
            # Step 4: Analyze case text using AI
            ai_analysis = await self.ai_service.analyze_legal_document(
                case_text,
                user_metadata
            )
            
            # Step 5: Create document entry for the source
            doc_type = "Judgment"
            if "act" in docsource.lower():
                doc_type = "Act"
            elif "statute" in docsource.lower():
                doc_type = "Statute"
            
            # Clean filename: remove special characters
            safe_filename = "".join(c for c in title[:50] if c.isalnum() or c in (' ', '-', '_'))
            safe_filename = safe_filename.strip().replace(' ', '_')
            
            # Add document reference
            ai_analysis["documents"] = [{
                "name": f"{safe_filename}_IndianKanoon.txt",
                "uploadDate": datetime.now().strftime("%Y-%m-%d"),
                "type": doc_type
            }]
            
            # Step 6: Save to case tracker
            upload_date = datetime.now().strftime("%Y-%m-%d")
            new_case = self.case_service.create_case(
                ai_analysis=ai_analysis,
                document_filename=f"{safe_filename}_IndianKanoon.txt",
                upload_date=upload_date
            )
            
            return new_case
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save research case: {str(e)}"
            )
    
    def _strip_html(self, html_text: str) -> str:
        """
        Strip HTML tags from text to get clean content for AI analysis
        
        Args:
            html_text: HTML content from Indian Kanoon
            
        Returns:
            Clean text without HTML tags
        """
        import re
        
        # Remove script and style elements
        html_text = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r'<style[^>]*>.*?</style>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html_text)
        
        # Replace HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _fetch_case_text_from_api(self, tid: str) -> str:
        """
        Fetch full case text from Indian Kanoon API
        
        Args:
            tid: Indian Kanoon document ID
            
        Returns:
            Full case text as string
            
        Raises:
            HTTPException: If API call fails
        """
        try:
            url = f"https://api.indiankanoon.org/doc/{tid}/"
            
            # Get API key from settings
            api_key = getattr(settings, 'LEGAL_CASE_API_KEY', None)
            
            if not api_key:
                raise HTTPException(
                    status_code=500,
                    detail="Indian Kanoon API key not configured"
                )
            
            # Use Authorization header as per Indian Kanoon API documentation
            headers = {
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Use POST request (as per documentation and existing code)
            response = requests.post(url, headers=headers, timeout=30)
            
            if response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Case document {tid} not found on Indian Kanoon"
                )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Indian Kanoon API returned status {response.status_code}"
                )
            
            # Response is JSON with 'doc' field containing the HTML/text
            try:
                result = response.json()
                # Get the document text - might be in 'doc' field
                doc_text = result.get('doc', '')
                
                if not doc_text:
                    # Try to get raw text if available
                    doc_text = response.text
                
                return doc_text
            except ValueError:
                # If not JSON, return raw text
                return response.text
            
        except requests.exceptions.Timeout:
            raise HTTPException(
                status_code=504,
                detail="Request to Indian Kanoon API timed out"
            )
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch case from Indian Kanoon: {str(e)}"
            )
