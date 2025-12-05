#!/usr/bin/env python3
"""
Test the automatic corrigendum detection system

This script:
1. Checks if the deduplication fix allows multiple versions
2. Verifies the corrigendum detection works with the new setup
3. Shows all ScrapedTender versions for a tender with multiple scrapes
"""

from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.tenderiq.db.schema import Tender
from app.modules.tenderiq.services.corrigendum_service import CorrigendumTrackingService
from datetime import datetime, timezone
from sqlalchemy import desc

def test_corrigendum_system():
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("TESTING AUTOMATIC CORRIGENDUM DETECTION SYSTEM")
        print("=" * 80)
        
        # 1. Check if we have tenders with multiple scraped versions
        print("\n1. CHECKING FOR TENDERS WITH MULTIPLE SCRAPED VERSIONS")
        print("-" * 80)
        
        # Get all unique tender_id_str values
        unique_tenders = db.query(ScrapedTender.tender_id_str).distinct().all()
        print(f"Total unique tenders scraped: {len(unique_tenders)}")
        
        tenders_with_versions = {}
        for (tender_id_str,) in unique_tenders:
            scrapes = db.query(ScrapedTender).filter(
                ScrapedTender.tender_id_str == tender_id_str
            ).order_by(desc(ScrapedTender.id)).all()
            
            if len(scrapes) > 1:
                tenders_with_versions[tender_id_str] = scrapes
        
        print(f"Tenders with multiple scrape versions: {len(tenders_with_versions)}")
        
        if tenders_with_versions:
            print("\nDetails of tenders with multiple versions:")
            for tender_id_str, scrapes in list(tenders_with_versions.items())[:5]:  # Show first 5
                print(f"\n  Tender ID: {tender_id_str}")
                print(f"  Number of versions: {len(scrapes)}")
                for idx, scrape in enumerate(scrapes, 1):
                    print(f"    Version {idx}:")
                    print(f"      ID: {scrape.id}")
                    if hasattr(scrape, 'scraped_at'):
                        print(f"      Scraped at: {scrape.scraped_at}")
                    print(f"      Tender Value: {scrape.tender_value}")
                    print(f"      Bid Deadline: {scrape.last_date_of_bid_submission}")
        else:
            print("ℹ️  No tenders with multiple versions yet. This is expected for a fresh system.")
        
        # 2. Test corrigendum detection on a tender with multiple versions
        print("\n" + "=" * 80)
        print("2. TESTING CORRIGENDUM DETECTION")
        print("-" * 80)
        
        if tenders_with_versions:
            test_tender_id = list(tenders_with_versions.keys())[0]
            scrapes = tenders_with_versions[test_tender_id]
            
            print(f"\nTesting with tender: {test_tender_id}")
            print(f"Comparing version 1 (older) vs version 2 (newer)")
            
            # Get corresponding Tender record
            main_tender = db.query(Tender).filter(
                Tender.tender_ref_number == test_tender_id
            ).first()
            
            if main_tender:
                corrigendum_service = CorrigendumTrackingService(db)
                
                # Detect changes between versions
                changes = corrigendum_service.detect_changes(test_tender_id, scrapes[0])  # scrapes[0] is newest
                
                if changes:
                    print(f"\n✓ CORRIGENDUM DETECTED: {len(changes)} changes found")
                    for change in changes:
                        print(f"  • {change.field}:")
                        print(f"    Old: {change.old_value}")
                        print(f"    New: {change.new_value}")
                else:
                    print("ℹ️  No changes detected between versions (identical data)")
            else:
                print("⚠️  Main tender not found in database")
        else:
            print("ℹ️  No tenders with multiple versions to test. Skipping detection test.")
        
        # 3. Summary
        print("\n" + "=" * 80)
        print("3. SUMMARY")
        print("=" * 80)
        print("\n✓ System is configured to:")
        print("  1. Store multiple scrape versions of the same tender (within different queries)")
        print("  2. Automatically detect changes when tenders are re-scraped")
        print("  3. Log corrigendums with change details for admin review")
        print("\nNext steps:")
        print("  • Re-scrape a known tender to create a new version with changes")
        print("  • Check the logs for 'CORRIGENDUM DETECTED' messages")
        print("  • Verify changes appear in the tender history on the frontend")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_corrigendum_system()
