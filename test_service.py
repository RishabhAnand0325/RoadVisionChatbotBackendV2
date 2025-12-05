#!/usr/bin/env python3
from app.db.database import SessionLocal
from app.modules.tenderiq.services import tender_service

db = SessionLocal()
try:
    print("Testing tender_service.get_latest_daily_tenders()...")
    result = tender_service.get_latest_daily_tenders(db)
    print(f"✓ Result type: {type(result)}")
    if result:
        print(f"✓ Got data")
        if hasattr(result, '__dict__'):
            keys = list(result.__dict__.keys())[:5]
            print(f"  Keys: {keys}")
    else:
        print("✗ Got None")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
