#!/usr/bin/env python3
"""
Check Latest Tenders for Corrigendum Implementation

This script queries tenders from the last 1-2 days and checks if they have
corrigendum data implemented in the tender history/changes tracking system.
"""

from app.db.database import SessionLocal
from app.modules.tenderiq.db.schema import Tender, TenderActionHistory, TenderActionEnum
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.tenderiq.services.corrigendum_service import CorrigendumTrackingService
from datetime import datetime, timezone, timedelta
from sqlalchemy import desc, and_
from dateutil import parser as date_parser
import json

def check_latest_tenders_with_corrigendums():
    """Query latest tenders and check for corrigendum data."""
    db = SessionLocal()
    
    try:
        # Time ranges to check
        now = datetime.now(timezone.utc)
        one_day_ago = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        
        print("=" * 80)
        print("CHECKING LATEST TENDERS FOR CORRIGENDUM IMPLEMENTATION")
        print("=" * 80)
        print(f"\nCurrent Time (UTC): {now.isoformat()}")
        print(f"Checking tenders from last 1-2 days")
        print(f"1 day ago: {one_day_ago.isoformat()}")
        print(f"2 days ago: {two_days_ago.isoformat()}")
        print("\n" + "-" * 80 + "\n")
        
        # Query tenders created or updated in last 1-2 days
        # Check both created_at and updated_at
        recent_tenders = db.query(Tender).filter(
            (Tender.created_at >= two_days_ago) | (Tender.updated_at >= two_days_ago)
        ).order_by(desc(Tender.created_at)).limit(50).all()
        
        print(f"Found {len(recent_tenders)} tenders created/updated in last 2 days\n")
        
        corrigendum_service = CorrigendumTrackingService(db)
        tenders_with_corrigendums = []
        tenders_without_corrigendums = []
        
        for idx, tender in enumerate(recent_tenders, 1):
            print(f"\n[{idx}] Tender: {tender.tender_ref_number}")
            title = tender.tender_title or "N/A"
            print(f"    Title: {title[:60]}..." if len(title) > 60 else f"    Title: {title}")
            print(f"    Created: {tender.created_at.isoformat() if tender.created_at else 'N/A'}")
            print(f"    Updated: {tender.updated_at.isoformat() if tender.updated_at else 'N/A'}")
            
            # Get corrigendum history for this tender
            try:
                history = corrigendum_service.get_tender_change_history(tender.tender_ref_number)
                
                if history:
                    print(f"    ✓ CORRIGENDUM HISTORY FOUND: {len(history)} changes tracked")
                    tenders_with_corrigendums.append({
                        "tender_id": tender.tender_ref_number,
                        "title": tender.tender_title,
                        "created_at": tender.created_at.isoformat() if tender.created_at else None,
                        "history_count": len(history),
                        "history": history
                    })
                    
                    # Show details of each change
                    for h_idx, h in enumerate(history, 1):
                        print(f"\n      Change {h_idx}:")
                        print(f"        Type: {h.get('type', 'N/A')}")
                        print(f"        Timestamp: {h.get('timestamp', 'N/A')}")
                        print(f"        Note: {h.get('note', 'N/A')[:100]}")
                        if h.get('date_change'):
                            print(f"        Date Change: {h['date_change'].get('from_date')} → {h['date_change'].get('to_date')}")
                else:
                    print(f"    ✗ No corrigendum history found")
                    tenders_without_corrigendums.append({
                        "tender_id": tender.tender_ref_number,
                        "title": tender.tender_title,
                        "created_at": tender.created_at.isoformat() if tender.created_at else None
                    })
            except Exception as e:
                print(f"    ✗ Error checking corrigendum history: {str(e)}")
                tenders_without_corrigendums.append({
                    "tender_id": tender.tender_ref_number,
                    "title": tender.title,
                    "error": str(e)
                })
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total tenders checked: {len(recent_tenders)}")
        print(f"Tenders WITH corrigendum history: {len(tenders_with_corrigendums)}")
        print(f"Tenders WITHOUT corrigendum history: {len(tenders_without_corrigendums)}")
        
        if tenders_with_corrigendums:
            print("\n" + "-" * 80)
            print("TENDERS WITH CORRIGENDUM DATA IMPLEMENTED:")
            print("-" * 80)
            for t in tenders_with_corrigendums:
                print(f"\n• {t['tender_id']}")
                print(f"  Title: {t['title']}")
                print(f"  Created: {t['created_at']}")
                print(f"  Changes tracked: {t['history_count']}")
                
                # Show sample changes
                if t['history']:
                    for h in t['history'][:2]:  # Show first 2 changes
                        print(f"    - {h.get('type', 'corrigendum')}: {h.get('note', '')[:80]}")
                    if len(t['history']) > 2:
                        print(f"    ... and {len(t['history']) - 2} more changes")
        
        if tenders_without_corrigendums:
            print("\n" + "-" * 80)
            print("TENDERS WITHOUT CORRIGENDUM DATA:")
            print("-" * 80)
            for t in tenders_without_corrigendums[:10]:  # Show first 10
                title = t.get('title', 'N/A')
                display_title = title[:60] if len(str(title)) > 60 else title
                print(f"• {t['tender_id']}: {display_title}")
            if len(tenders_without_corrigendums) > 10:
                print(f"... and {len(tenders_without_corrigendums) - 10} more")
        
        # Detailed JSON export for reference
        print("\n" + "=" * 80)
        print("DETAILED EXPORT (JSON)")
        print("=" * 80)
        
        export_data = {
            "timestamp": now.isoformat(),
            "summary": {
                "total_checked": len(recent_tenders),
                "with_corrigendums": len(tenders_with_corrigendums),
                "without_corrigendums": len(tenders_without_corrigendums)
            },
            "tenders_with_corrigendums": tenders_with_corrigendums,
            "sample_tenders_without": tenders_without_corrigendums[:5]
        }
        
        print(json.dumps(export_data, indent=2, default=str))
        
        return tenders_with_corrigendums, tenders_without_corrigendums
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    check_latest_tenders_with_corrigendums()
