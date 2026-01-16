import json
import google.genai as genai
from typing import Dict, Any, Optional
from fastapi import HTTPException
from app.config import settings


class AIAnalysisService:
    """Service for AI-powered document analysis using Google Gemini"""
    
    def __init__(self):
        """Initialize AI service with Google Gemini"""
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not configured")
        
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.model = 'gemini-2.0-flash-exp'
    
    async def analyze_legal_document(
        self, 
        document_text: str,
        user_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze legal document and extract case information
        
        Args:
            document_text: Extracted text from the legal document
            user_metadata: Optional user-provided metadata (caseTitle, caseId, courtName)
            
        Returns:
            Dictionary with extracted case information and AI insights
            
        Raises:
            HTTPException: If analysis fails
        """
        try:
            # Build the analysis prompt
            prompt = self._build_analysis_prompt(document_text, user_metadata)
            
            # Generate analysis
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            # Parse the JSON response
            analysis_result = self._parse_ai_response(response.text)
            
            # Override with user-provided metadata if available
            if user_metadata:
                if user_metadata.get('caseTitle'):
                    analysis_result['caseTitle'] = user_metadata['caseTitle']
                if user_metadata.get('caseId'):
                    analysis_result['caseId'] = user_metadata['caseId']
                if user_metadata.get('courtName'):
                    analysis_result['courtName'] = user_metadata['courtName']
                if user_metadata.get('caseType'):
                    analysis_result['caseType'] = user_metadata['caseType']
                if user_metadata.get('litigationStatus'):
                    analysis_result['litigationStatus'] = user_metadata['litigationStatus']
            
            return analysis_result
        
        except Exception as e:
            print(f"AI Analysis Error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"AI analysis failed: {str(e)}"
            )
    
    def _build_analysis_prompt(
        self, 
        document_text: str,
        user_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the prompt for AI analysis"""
        
        # Truncate document text if too long (keep first 30000 chars for context)
        if len(document_text) > 30000:
            document_text = document_text[:30000] + "\n\n[Document truncated for analysis]"
        
        prompt = f"""You are an expert Legal Document Analyst AI. Analyze the following legal document and extract all relevant case information with high accuracy.

LEGAL DOCUMENT TEXT:
{document_text}

TASK: Extract and structure the following information from the document. Return ONLY valid JSON without any markdown formatting or code blocks.

IMPORTANT EXTRACTION GUIDELINES:
1. Look carefully for dates in various formats (DD-MM-YYYY, DD/MM/YYYY, Month DD, YYYY, etc.)
2. Case numbers can appear as: "Case No.", "Petition No.", "Appeal No.", "ARB/", "SCC", "AIR", etc.
3. For Acts: Extract FULL act names like "Arbitration and Conciliation Act, 1996" or "Indian Contract Act, 1872"
4. For Sections: Extract section numbers like "Section 21", "Section 34", "Articles 74(2), 163, 355"
5. Court names can be: "Supreme Court", "High Court of [State]", "District Court", "Arbitral Tribunal"
6. Judge names often appear after "BEFORE:", "CORAM:", "Hon'ble Justice", "Hon'ble Judge"
7. Parties: Look for "Petitioner", "Appellant", "Claimant" vs "Respondent", "Defendant"
8. Filing/Registration: Look for "Filed on", "Registered on", "Date of filing", "Registration No.", "Presented on"
9. CNR: Look for "CNR No.", "CNR Number", "Case Number Registry" - this is a 16-digit alphanumeric code
10. FIR: Look for "FIR No.", "FIR Number", "First Information Report" - ONLY for criminal cases
11. Police Station: Usually mentioned with FIR details - ONLY for criminal cases
12. Court Number: Look for "Court No.", "Court Number", "Bench", "Division Bench", "Single Bench"
13. Advocates: Look for "Adv.", "Advocate", "Counsel for", "Appearing for", "Sr. Adv.", "AOR"
14. Case Status: Determine from words like "disposed", "dismissed", "allowed", "pending", "award passed"
15. Hearings: Extract dates with context like "hearing on", "next date", "adjourned to", "order dated"

SPECIAL NOTES FOR MISSING FIELDS:
- CNR Number: Modern cases have this, old cases (pre-2010) typically don't - if not found, use "N/A"
- Filing/Registration Dates: Search the beginning of the document thoroughly - often in the header or first page
- Police Station & FIR: ONLY applicable to criminal cases involving police complaints - for civil/constitutional cases, use "N/A"
- Court Number: Look for bench information, division number, or courtroom number - if not mentioned, use "N/A"
- Advocate names: Search near party names and at the end of the judgment - if not mentioned, use "N/A"
- If this is a constitutional/writ petition/civil case: Police Station and FIR will be "N/A"
- If this is an old case (before 2010): CNR will likely be "N/A"

Required JSON structure:
{{
    "caseTitle": "Full case title exactly as mentioned (e.g., 'Petitioner Name vs Respondent Name')",
    "caseId": "Primary case number/citation (look for Case No., SCC, AIR, Appeal No., etc.)",
    "courtName": "Full court name (e.g., 'Supreme Court of India', 'Delhi High Court', 'Arbitral Tribunal')",
    "caseType": "Type: Civil Suit, Criminal, Arbitration, Writ Petition, Appeal, etc.",
    "litigationStatus": "Current status: Pending, Under Review, Disposed, Dismissed, Allowed, Closed, etc.",
    "filingDate": "Filing date in YYYY-MM-DD format (search thoroughly for filing/presentation date)",
    "filingNumber": "Filing number if different from case number, otherwise same as caseId",
    "registrationNumber": "Registration number (often appears as 'Regd. No.' or 'Registration No.')",
    "registrationDate": "Registration date in YYYY-MM-DD format",
    "cnrNumber": "CNR (Case Number Registry) - usually alphanumeric like 'DLCT01-012345-2025'",
    "jurisdiction": "State/Territory jurisdiction (e.g., 'Delhi', 'Maharashtra', 'Punjab')",
    "courtNumber": "Court number/division (e.g., 'Court No. 5', 'Division Bench')",
    "judgeName": "Full name(s) of judge(s) - look after BEFORE/CORAM (e.g., 'Hon'ble Justice ABC')",
    "caseStage": "Current stage: Initial Filing, Arguments, Evidence, Final Arguments, Judgment Reserved, Disposed, etc.",
    "underActs": "Complete Act name(s) separated by semicolon (e.g., 'Arbitration and Conciliation Act, 1996; Indian Contract Act, 1872')",
    "sections": "Section/Article numbers with full details (e.g., 'Section 34, Section 36; Articles 74(2), 163, 355')",
    "policeStation": "Police Station name if FIR-related case, otherwise 'N/A'",
    "firNumber": "FIR number with year if criminal case (e.g., 'FIR No. 123/2024'), otherwise 'N/A'",
    "petitioner": "Petitioner/Appellant/Claimant name (individual or organization)",
    "petitionerAdvocate": "Advocate name for petitioner (look for 'for Petitioner:', 'Adv. for Appellant')",
    "respondent": "Respondent/Defendant name (individual or organization)",
    "respondentAdvocate": "Advocate name for respondent (look for 'for Respondent:', 'Adv. for Defendant')",
    "hearings": [
        {{
            "date": "YYYY-MM-DD format - extract all hearing/order dates from document",
            "judge": "Judge name for this hearing",
            "purpose": "Purpose: First Hearing, Arguments, Evidence Recording, Final Order, etc.",
            "outcome": "Outcome/Order: Adjourned, Admitted, Dismissed, Award Passed, etc.",
            "document": "Document reference if mentioned, otherwise 'Order_dated_DD.MM.YYYY.pdf'"
        }}
    ],
    "aiInsights": {{
        "summary": "2-3 sentence summary of the case - what it's about, current status, key points",
        "winProbability": "If case is CLOSED/DISPOSED: State clearly 'Won by [Party Name]' or 'Lost - dismissed' or 'Partially allowed'. If PENDING: Estimate like '65%' or 'Favorable' or 'Uncertain'",
        "estimatedDuration": "If CLOSED: 'Completed ([X] months/years)'. If PENDING: Estimate in months like '8-12 months' or '1-2 years'",
        "recommendedAction": "If CLOSED/DISPOSED: 'No action required - case concluded' or 'Monitor for execution' or 'Consider appeal if applicable'. If PENDING: Specific next steps like 'File reply by [date]', 'Prepare for next hearing', 'Gather additional evidence'"
    }}
}}

CRITICAL INSTRUCTIONS:
1. Search the ENTIRE document for each field - information may appear anywhere
2. For dates: Convert all date formats to YYYY-MM-DD (e.g., "5th December 2024" → "2024-12-05")
3. If a field cannot be found after thorough search, use "N/A" - DO NOT guess or invent
4. For closed/disposed cases: Clearly state outcome in winProbability and set appropriate recommendedAction
5. Extract ALL hearings/order dates mentioned with as much detail as available
6. Be precise with Act names and Section numbers - copy exactly as written
7. Return ONLY the JSON object with no additional text, markdown, or code blocks
8. Ensure valid JSON structure - properly escape quotes and special characters
"""
        
        return prompt
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """Parse AI response and extract JSON"""
        try:
            # Clean the response - remove markdown code blocks if present
            cleaned_text = response_text.strip()
            
            # Remove markdown code block markers
            if cleaned_text.startswith('```'):
                # Find the first newline after ```json or ```
                first_newline = cleaned_text.find('\n')
                if first_newline != -1:
                    cleaned_text = cleaned_text[first_newline + 1:]
                
                # Remove the closing ```
                if cleaned_text.endswith('```'):
                    cleaned_text = cleaned_text[:-3]
            
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            result = json.loads(cleaned_text)
            
            # Validate required fields
            required_fields = [
                'caseTitle', 'caseId', 'courtName', 'caseType', 
                'litigationStatus', 'aiInsights'
            ]
            
            for field in required_fields:
                if field not in result:
                    result[field] = "N/A" if field != 'aiInsights' else {
                        "summary": "Analysis pending.",
                        "winProbability": "Calculating...",
                        "estimatedDuration": "Estimating...",
                        "recommendedAction": "Review document details."
                    }
            
            # Ensure hearings is a list and sort by date
            if 'hearings' not in result or not isinstance(result['hearings'], list):
                result['hearings'] = []
            else:
                # Sort hearings by date (ascending)
                try:
                    def get_date_key(h):
                        d = h.get('date', '')
                        # Handle N/A or empty dates by putting them at the end
                        if not d or d == 'N/A':
                            return '9999-12-31'
                        return d
                    
                    result['hearings'].sort(key=get_date_key)
                except Exception as e:
                    print(f"Error sorting hearings: {e}")
            
            return result
        
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {e}")
            print(f"Response text: {response_text[:500]}")
            
            # Return default structure if parsing fails
            return self._get_default_analysis()
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """Return default analysis when AI fails"""
        return {
            "caseTitle": "",
            "caseId": "",
            "courtName": "",
            "caseType": "Arbitration",
            "litigationStatus": "Pending",
            "filingDate": "N/A",
            "filingNumber": "N/A",
            "registrationNumber": "N/A",
            "registrationDate": "N/A",
            "cnrNumber": "N/A",
            "jurisdiction": "N/A",
            "courtNumber": "N/A",
            "judgeName": "N/A",
            "caseStage": "N/A",
            "underActs": "N/A",
            "sections": "N/A",
            "policeStation": "N/A",
            "firNumber": "N/A",
            "petitioner": "N/A",
            "petitionerAdvocate": "N/A",
            "respondent": "N/A",
            "respondentAdvocate": "N/A",
            "hearings": [],
            "aiInsights": {
                "summary": "New case created. Analysis pending.",
                "winProbability": "Calculating...",
                "estimatedDuration": "Estimating...",
                "recommendedAction": "Upload relevant documents for analysis."
            }
        }
