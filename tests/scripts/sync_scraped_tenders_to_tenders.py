import json
from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.tenderiq.db.repository import TenderRepository
from app.modules.tenderiq.db.schema import Tender


db = SessionLocal()
tender_repo = TenderRepository(db)

orphans = db.query(ScrapedTender).outerjoin(Tender, ScrapedTender.id == Tender.id).filter(Tender.id == None).all()

for orphan in orphans:
    print(orphan.id, orphan.tender_name)
    try:
        tender = tender_repo.get_or_create_by_id(orphan)
        print(tender.id, tender.tender_title)
    except Exception as e:
        print(e)

