from app.db.database import SessionLocal
from app.modules.analyze.repositories import repository as analyze_repo

db = SessionLocal()

wishlisted = analyze_repo.get_wishlisted_tenders(db)

for tender in wishlisted:
    print(tender.tender_title)
