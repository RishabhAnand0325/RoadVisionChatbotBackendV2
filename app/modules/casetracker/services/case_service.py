import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from fastapi import HTTPException
from app.modules.casetracker.models.schemas import (
    CaseResponse, 
    CaseDocument,
    AIInsights,
    Hearing
)


class CaseService:
    """Service for managing case data and metadata"""
    
    def __init__(self, metadata_path: str = "Case-traker-data/cases_metadata.json"):
        """
        Initialize case service
        
        Args:
            metadata_path: Path to cases metadata JSON file
        """
        # Get the backend root directory
        backend_root = Path(__file__).parent.parent.parent.parent.parent
        self.metadata_path = backend_root / metadata_path
        
        # Ensure parent directory exists
        self.metadata_path.parent.mkdir(exist_ok=True)
        
        # Create metadata file if it doesn't exist
        if not self.metadata_path.exists():
            self._initialize_metadata_file()
    
    def _initialize_metadata_file(self):
        """Create empty metadata file"""
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2)
    
    def get_all_cases(self) -> List[CaseResponse]:
        """
        Get all cases from metadata
        
        Returns:
            List of all cases
        """
        try:
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                cases_data = json.load(f)
            
            # Convert to CaseResponse objects
            cases = []
            for case_data in cases_data:
                try:
                    cases.append(CaseResponse(**case_data))
                except Exception as e:
                    print(f"Error parsing case {case_data.get('id')}: {e}")
                    continue
            
            return cases
        
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            print("Error: Corrupted metadata file")
            return []
        except Exception as e:
            print(f"Error reading cases: {e}")
            return []
    
    def get_case_by_id(self, case_id: int) -> Optional[CaseResponse]:
        """
        Get a specific case by ID
        
        Args:
            case_id: Case ID
            
        Returns:
            Case object or None if not found
        """
        cases = self.get_all_cases()
        for case in cases:
            if case.id == case_id:
                return case
        return None
    
    def create_case(
        self, 
        ai_analysis: Dict[str, Any],
        document_filename: str,
        upload_date: str
    ) -> CaseResponse:
        """
        Create a new case from AI analysis
        
        Args:
            ai_analysis: AI analysis results
            document_filename: Name of uploaded document
            upload_date: Date of upload in YYYY-MM-DD format
            
        Returns:
            Created case object
        """
        try:
            # Load existing cases
            cases = self.get_all_cases()
            
            # Generate new ID
            new_id = max([c.id for c in cases], default=0) + 1
            
            # Create case data
            case_data = {
                "id": new_id,
                "caseTitle": ai_analysis.get("caseTitle", ""),
                "caseId": ai_analysis.get("caseId", ""),
                "courtName": ai_analysis.get("courtName", ""),
                "caseType": ai_analysis.get("caseType", "Arbitration"),
                "litigationStatus": ai_analysis.get("litigationStatus", "Pending"),
                "filingDate": ai_analysis.get("filingDate", upload_date),
                "filingNumber": ai_analysis.get("filingNumber", "N/A"),
                "registrationNumber": ai_analysis.get("registrationNumber", "N/A"),
                "registrationDate": ai_analysis.get("registrationDate", "N/A"),
                "cnrNumber": ai_analysis.get("cnrNumber", "N/A"),
                "jurisdiction": ai_analysis.get("jurisdiction", "N/A"),
                "courtNumber": ai_analysis.get("courtNumber", "N/A"),
                "judgeName": ai_analysis.get("judgeName", "N/A"),
                "caseStage": ai_analysis.get("caseStage", "N/A"),
                "underActs": ai_analysis.get("underActs", "N/A"),
                "sections": ai_analysis.get("sections", "N/A"),
                "policeStation": ai_analysis.get("policeStation", "N/A"),
                "firNumber": ai_analysis.get("firNumber", "N/A"),
                "petitioner": ai_analysis.get("petitioner", "N/A"),
                "petitionerAdvocate": ai_analysis.get("petitionerAdvocate", "N/A"),
                "respondent": ai_analysis.get("respondent", "N/A"),
                "respondentAdvocate": ai_analysis.get("respondentAdvocate", "N/A"),
                "hearings": ai_analysis.get("hearings", []),
                "documents": [
                    {
                        "name": document_filename,
                        "uploadDate": upload_date,
                        "type": "Uploaded Document"
                    }
                ],
                "aiInsights": ai_analysis.get("aiInsights", {
                    "summary": "New case created. Analysis pending.",
                    "winProbability": "Calculating...",
                    "estimatedDuration": "Estimating...",
                    "recommendedAction": "Upload relevant documents for analysis."
                })
            }
            
            # Create case object
            new_case = CaseResponse(**case_data)
            
            # Save to metadata
            self._save_case(new_case)
            
            return new_case
        
        except Exception as e:
            print(f"Error creating case: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create case: {str(e)}"
            )
    
    def update_case(self, case_id: int, update_data: Dict[str, Any]) -> Optional[CaseResponse]:
        """
        Update an existing case
        
        Args:
            case_id: Case ID to update
            update_data: Dictionary with fields to update
            
        Returns:
            Updated case object or None if not found
        """
        try:
            cases = self.get_all_cases()
            
            for i, case in enumerate(cases):
                if case.id == case_id:
                    # Update case data
                    case_dict = case.dict()
                    case_dict.update(update_data)
                    
                    # Create updated case
                    updated_case = CaseResponse(**case_dict)
                    cases[i] = updated_case
                    
                    # Save all cases
                    self._save_all_cases(cases)
                    
                    return updated_case
            
            return None
        
        except Exception as e:
            print(f"Error updating case: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update case: {str(e)}"
            )
    
    def delete_case(self, case_id: int) -> bool:
        """
        Delete a case
        
        Args:
            case_id: Case ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            cases = self.get_all_cases()
            
            # Filter out the case to delete
            updated_cases = [c for c in cases if c.id != case_id]
            
            if len(updated_cases) == len(cases):
                return False  # Case not found
            
            # Save updated list
            self._save_all_cases(updated_cases)
            
            return True
        
        except Exception as e:
            print(f"Error deleting case: {e}")
            return False
    
    def _save_case(self, case: CaseResponse):
        """Save a new case to metadata"""
        cases = self.get_all_cases()
        cases.append(case)
        self._save_all_cases(cases)
    
    def _save_all_cases(self, cases: List[CaseResponse]):
        """Save all cases to metadata file"""
        try:
            # Convert to dict for JSON serialization
            cases_data = [case.dict() for case in cases]
            
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(cases_data, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            print(f"Error saving cases: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save cases: {str(e)}"
            )
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics for all cases
        
        Returns:
            Dictionary with summary stats
        """
        cases = self.get_all_cases()
        
        # Count active cases
        active_cases = len([c for c in cases if c.litigationStatus.lower() != "closed"])
        
        # Count upcoming hearings
        today = datetime.now().date()
        upcoming_hearings = 0
        
        for case in cases:
            for hearing in case.hearings:
                try:
                    hearing_date = datetime.strptime(hearing.date, "%Y-%m-%d").date()
                    if hearing_date >= today:
                        upcoming_hearings += 1
                except:
                    continue
        
        # Calculate average duration (simplified)
        total_duration = 0
        for case in cases:
            try:
                filing_date = datetime.strptime(case.filingDate, "%Y-%m-%d")
                duration_months = (datetime.now() - filing_date).days / 30.44
                total_duration += duration_months
            except:
                continue
        
        avg_duration = total_duration / len(cases) if cases else 0
        
        return {
            "totalActiveCases": active_cases,
            "upcomingHearings": upcoming_hearings,
            "avgCaseDuration": round(avg_duration, 1)
        }
