#!/usr/bin/env python3
from app.db.database import SessionLocal
from app.modules.tenderiq.db.schema import Tender

db = SessionLocal()
try:
    count = db.query(Tender).count()
    print(f"✓ Tender table accessible: {count} tenders")
    
    tender = db.query(Tender).first()
    if tender:
        print(f"✓ First tender: {tender.tender_ref_number}")
        print(f"  ID: {tender.id}")
        print(f"  Title: {tender.tender_title}")
    else:
        print("ℹ️  No tenders in database")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
