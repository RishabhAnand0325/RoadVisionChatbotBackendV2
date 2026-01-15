"""
Migration script to analyze existing PDFs in Case-traker-data folder
and populate cases_metadata.json with AI-analyzed data.
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import from app
sys.path.insert(0, str(Path(__file__).parent))

from app.modules.casetracker.services.document_service import DocumentService
from app.modules.casetracker.services.ai_analysis_service import AIAnalysisService


def analyze_existing_cases():
    """Analyze existing PDF files and create case metadata"""
    
    # Initialize services
    doc_service = DocumentService()
    ai_service = AIAnalysisService()
    
    # Define case groupings
    cases_config = [
        {
            "name": "GMDA Case",
            "files": [
                "GMDA- Award_05.12.2024_Ceigall_v_GMADA.pdf",
                "GMDA- SOC-1.pdf",
                "GMDA- SOC-2.pdf",
                "GMDA- SOC-3.pdf"
            ],
            "primary_file": "GMDA- Award_05.12.2024_Ceigall_v_GMADA.pdf"
        },
        {
            "name": "Hamirpur Case",
            "files": [
                "Dt. 04.07.2025 Final Award CIL & Shimla Hamirpur PWD Shimla.pdf",
                "Rejoinder on behalf of the Claimant to the Statement of Defence filed by the Respondent.pdf",
                "SOC - CLAM Hamirpur_Statement of Claim on behalf of the Claimant.pdf",
                "SOD- Statement of Defence - Hamirpur Arbitration case (1).pdf"
            ],
            "primary_file": "Dt. 04.07.2025 Final Award CIL & Shimla Hamirpur PWD Shimla.pdf"
        }
    ]
    
    cases = []
    case_id = 1
    
    for case_config in cases_config:
        print(f"\n{'='*60}")
        print(f"Processing: {case_config['name']}")
        print(f"{'='*60}")
        
        # Extract text from primary file for AI analysis
        primary_file_path = doc_service.storage_path / case_config['primary_file']
        
        if not primary_file_path.exists():
            print(f"❌ Primary file not found: {case_config['primary_file']}")
            continue
        
        print(f"📄 Extracting text from: {case_config['primary_file']}")
        
        try:
            document_text = doc_service.extract_text_from_pdf(str(primary_file_path))
            print(f"✅ Extracted {len(document_text)} characters")
        except Exception as e:
            print(f"❌ Error extracting text: {e}")
            continue
        
        # Analyze with AI
        print("🤖 Analyzing with AI...")
        try:
            # Use asyncio to run the async function
            import asyncio
            ai_analysis = asyncio.run(ai_service.analyze_legal_document(document_text))
            print("✅ AI analysis complete")
        except Exception as e:
            print(f"❌ AI analysis failed: {e}")
            print("Using fallback data...")
            ai_analysis = ai_service._get_default_analysis()
        
        # Create documents list
        documents = []
        for filename in case_config['files']:
            file_path = doc_service.storage_path / filename
            if file_path.exists():
                # Try to determine document type from filename
                doc_type = "Legal Document"
                if "SOC" in filename:
                    doc_type = "Statement of Claim"
                elif "SOD" in filename:
                    doc_type = "Statement of Defence"
                elif "Award" in filename:
                    doc_type = "Award"
                elif "Rejoinder" in filename:
                    doc_type = "Rejoinder"
                
                documents.append({
                    "name": filename,
                    "uploadDate": datetime.now().strftime("%Y-%m-%d"),
                    "type": doc_type
                })
        
        # Create case entry
        case_entry = {
            "id": case_id,
            "caseTitle": ai_analysis.get("caseTitle", case_config['name']),
            "caseId": ai_analysis.get("caseId", f"CASE/{case_id:03d}"),
            "courtName": ai_analysis.get("courtName", "N/A"),
            "caseType": ai_analysis.get("caseType", "Arbitration"),
            "litigationStatus": ai_analysis.get("litigationStatus", "Pending"),
            "filingDate": ai_analysis.get("filingDate", datetime.now().strftime("%Y-%m-%d")),
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
            "documents": documents,
            "aiInsights": ai_analysis.get("aiInsights", {
                "summary": "Migrated case from existing documents.",
                "winProbability": "N/A",
                "estimatedDuration": "N/A",
                "recommendedAction": "Review case documents."
            })
        }
        
        cases.append(case_entry)
        case_id += 1
        
        print(f"✅ Case created: {case_entry['caseTitle']}")
        print(f"   Case ID: {case_entry['caseId']}")
        print(f"   Documents: {len(documents)}")
    
    # Save to cases_metadata.json
    metadata_path = doc_service.storage_path / "cases_metadata.json"
    
    print(f"\n{'='*60}")
    print("Saving to cases_metadata.json...")
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Successfully saved {len(cases)} cases to {metadata_path}")
    print(f"{'='*60}\n")
    
    # Print summary
    print("\n📊 SUMMARY")
    print(f"{'='*60}")
    for case in cases:
        print(f"\nCase {case['id']}: {case['caseTitle']}")
        print(f"  - Case ID: {case['caseId']}")
        print(f"  - Court: {case['courtName']}")
        print(f"  - Status: {case['litigationStatus']}")
        print(f"  - Documents: {len(case['documents'])}")
        print(f"  - Hearings: {len(case['hearings'])}")


if __name__ == "__main__":
    print("\n🔄 Starting migration of existing cases...")
    print("This will analyze PDF files and populate cases_metadata.json\n")
    
    try:
        analyze_existing_cases()
        print("\n✅ Migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
