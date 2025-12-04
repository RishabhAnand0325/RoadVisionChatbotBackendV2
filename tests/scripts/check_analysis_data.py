#!/usr/bin/env python3
"""
Script to check tender analysis data after running analyze_tender.py

Usage:
    python check_analysis_data.py [tender_id]
    
Example:
    python check_analysis_data.py 51705827
"""

import sys
import json
import os

# Add project root to Python path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.db.database import SessionLocal
from app.modules.analyze.db.schema import TenderAnalysis, AnalysisRFPSection, AnalysisDocumentTemplate

def check_analysis_data(tender_id="51705827"):
    """Check analysis data for a specific tender ID"""
    
    print(f"🔍 Checking Analysis Data for Tender ID: {tender_id}")
    print("=" * 70)
    
    db = SessionLocal()
    try:
        # 1. Check main analysis record
        analysis = db.query(TenderAnalysis).filter(
            TenderAnalysis.tender_id == tender_id
        ).first()
        
        if not analysis:
            print("❌ No analysis found for this tender ID")
            print(f"\n💡 To create analysis data, run:")
            print(f"   python -m tests.unit.run_analyze_tender")
            return
        
        print("✅ MAIN ANALYSIS RECORD:")
        print("-" * 40)
        print(f"Analysis ID: {analysis.id}")
        print(f"Status: {analysis.status}")
        print(f"Progress: {analysis.progress}%")
        print(f"Created: {analysis.created_at}")
        if analysis.analysis_completed_at:
            print(f"Completed: {analysis.analysis_completed_at}")
        if analysis.status_message:
            print(f"Status Message: {analysis.status_message}")
        if analysis.error_message:
            print(f"Error Message: {analysis.error_message}")
        
        # 2. Check JSON analysis results
        print(f"\n📊 ANALYSIS RESULTS:")
        print("-" * 40)
        
        if analysis.one_pager_json:
            print("✅ One-Pager JSON: Available")
            print(f"   Keys: {list(analysis.one_pager_json.keys())}")
        else:
            print("❌ One-Pager JSON: Not available")
        
        if analysis.scope_of_work_json:
            print("✅ Scope of Work JSON: Available")
            print(f"   Keys: {list(analysis.scope_of_work_json.keys())}")
        else:
            print("❌ Scope of Work JSON: Not available")
            
        if analysis.data_sheet_json:
            print("✅ Data Sheet JSON: Available")
            print(f"   Keys: {list(analysis.data_sheet_json.keys())}")
        else:
            print("❌ Data Sheet JSON: Not available")
        
        # 3. Check RFP sections
        rfp_sections = db.query(AnalysisRFPSection).filter(
            AnalysisRFPSection.analysis_id == analysis.id
        ).all()
        
        print(f"\n📑 RFP SECTIONS: {len(rfp_sections)} sections found")
        print("-" * 40)
        
        if rfp_sections:
            for i, section in enumerate(rfp_sections[:5], 1):  # Show first 5
                print(f"{i}. Section {section.section_number or 'N/A'}: {section.section_title}")
                if section.summary:
                    print(f"   Summary: {section.summary[:100]}...")
                if section.key_requirements:
                    print(f"   Requirements: {len(section.key_requirements)} items")
                print()
            
            if len(rfp_sections) > 5:
                print(f"   ... and {len(rfp_sections) - 5} more sections")
        else:
            print("❌ No RFP sections found")
        
        # 4. Check document templates
        templates = db.query(AnalysisDocumentTemplate).filter(
            AnalysisDocumentTemplate.analysis_id == analysis.id
        ).all()
        
        print(f"\n📄 DOCUMENT TEMPLATES: {len(templates)} templates found")
        print("-" * 40)
        
        if templates:
            for i, template in enumerate(templates, 1):
                print(f"{i}. {template.template_name}")
                if template.description:
                    print(f"   Description: {template.description[:80]}...")
                if template.required_format:
                    print(f"   Format: {template.required_format}")
                if template.file_reference:
                    print(f"   Source File: {template.file_reference}")
                if template.page_references:
                    print(f"   Pages: {template.page_references}")
                else:
                    print(f"   Pages: Not specified")
                print()
        else:
            print("❌ No document templates found")
        
        # 5. Export to JSON file
        export_data = {
            "tender_id": tender_id,
            "analysis_status": analysis.status,
            "analysis_progress": analysis.progress,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "completed_at": analysis.analysis_completed_at.isoformat() if analysis.analysis_completed_at else None,
            "one_pager": analysis.one_pager_json,
            "scope_of_work": analysis.scope_of_work_json,
            "data_sheet": analysis.data_sheet_json,
            "rfp_sections": [
                {
                    "section_number": section.section_number,
                    "section_title": section.section_title,
                    "summary": section.summary,
                    "key_requirements": section.key_requirements,
                    "compliance_issues": section.compliance_issues,
                    "page_references": section.page_references
                }
                for section in rfp_sections
            ],
            "document_templates": [
                {
                    "template_name": template.template_name,
                    "description": template.description,
                    "required_format": template.required_format,
                    "content_preview": template.content_preview,
                    "file_reference": template.file_reference,
                    "page_references": template.page_references
                }
                for template in templates
            ]
        }
        
        export_filename = f"analysis_data_{tender_id}.json"
        with open(export_filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 EXPORTED COMPLETE DATA:")
        print("-" * 40)
        print(f"File: {export_filename}")
        print(f"Size: {len(json.dumps(export_data, default=str))} characters")
        
        print(f"\n🎯 SUMMARY:")
        print("-" * 40)
        print(f"✅ Analysis Status: {analysis.status}")
        print(f"✅ Progress: {analysis.progress}%")
        print(f"✅ RFP Sections: {len(rfp_sections)}")
        print(f"✅ Templates: {len(templates)}")
        print(f"✅ JSON Results: {sum([bool(analysis.one_pager_json), bool(analysis.scope_of_work_json), bool(analysis.data_sheet_json)])}/3")
        
    finally:
        db.close()

def main():
    """Main function"""
    tender_id = sys.argv[1] if len(sys.argv) > 1 else "51705827"
    check_analysis_data(tender_id)

if __name__ == "__main__":
    main()