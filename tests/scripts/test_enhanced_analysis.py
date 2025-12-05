#!/usr/bin/env python3
"""
Test script to run enhanced analysis that populates ALL tables including RFP sections and document templates.

This will either:
1. Create a new analysis record if none exists
2. Re-run analysis to populate missing RFP sections and templates if analysis exists but they're missing

Usage: python test_enhanced_analysis.py [tender_id]
"""

import sys
import os

# Add project root to Python path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.db.database import SessionLocal
from app.modules.analyze.scripts.analyze_tender import analyze_tender
from app.modules.analyze.db.schema import TenderAnalysis, AnalysisRFPSection, AnalysisDocumentTemplate

def test_enhanced_analysis(tender_id="51705827"):
    """Test the enhanced analysis with RFP sections and document templates"""
    
    print(f"🧪 Testing Enhanced Analysis for Tender: {tender_id}")
    print("=" * 70)
    
    db = SessionLocal()
    try:
        # Check current state
        analysis = db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id).first()
        
        if analysis:
            sections_count = db.query(AnalysisRFPSection).filter(AnalysisRFPSection.analysis_id == analysis.id).count()
            templates_count = db.query(AnalysisDocumentTemplate).filter(AnalysisDocumentTemplate.analysis_id == analysis.id).count()
            
            print(f"📊 Current state:")
            print(f"   Analysis Status: {analysis.status}")
            print(f"   RFP Sections: {sections_count}")
            print(f"   Document Templates: {templates_count}")
            
            if sections_count == 0 or templates_count == 0:
                print(f"\n⚠️  Missing detailed analysis data. Re-running analysis...")
                # Delete existing analysis to force complete re-run
                db.query(AnalysisRFPSection).filter(AnalysisRFPSection.analysis_id == analysis.id).delete()
                db.query(AnalysisDocumentTemplate).filter(AnalysisDocumentTemplate.analysis_id == analysis.id).delete()
                db.delete(analysis)
                db.commit()
                print(f"✅ Cleaned up existing incomplete analysis")
            else:
                print(f"\n✅ Analysis already complete with detailed data!")
                return
        else:
            print(f"📝 No existing analysis found. Creating new analysis...")
        
        # Run the enhanced analysis
        print(f"\n🚀 Running enhanced analysis with RFP sections and document templates...")
        print("-" * 50)
        
        analyze_tender(db, tender_id)
        
        print(f"\n✅ Enhanced analysis completed!")
        
        # Verify results
        analysis = db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id).first()
        if analysis:
            sections_count = db.query(AnalysisRFPSection).filter(AnalysisRFPSection.analysis_id == analysis.id).count()
            templates_count = db.query(AnalysisDocumentTemplate).filter(AnalysisDocumentTemplate.analysis_id == analysis.id).count()
            
            print(f"🎯 Final Results:")
            print(f"   Analysis Status: {analysis.status}")
            print(f"   Progress: {analysis.progress}%")
            print(f"   RFP Sections: {sections_count}")
            print(f"   Document Templates: {templates_count}")
            print(f"   JSON Results: {sum([bool(analysis.one_pager_json), bool(analysis.scope_of_work_json), bool(analysis.data_sheet_json)])}/3")
            
            if sections_count > 0 and templates_count > 0:
                print(f"\n🎉 SUCCESS! All analysis data populated:")
                print(f"   ✅ Main analysis record")
                print(f"   ✅ JSON analysis results")  
                print(f"   ✅ RFP sections breakdown")
                print(f"   ✅ Document templates extraction")
                
                print(f"\n💡 Now run: python check_analysis_data.py {tender_id}")
            else:
                print(f"\n⚠️  Analysis completed but some detailed data may be missing")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def main():
    """Main function"""
    tender_id = sys.argv[1] if len(sys.argv) > 1 else "51705827"
    test_enhanced_analysis(tender_id)

if __name__ == "__main__":
    main()
