from app.core.helpers import get_number_from_currency_string
from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender

db = SessionLocal()

tenders = db.query(ScrapedTender).all()

try:
    for tender in tenders:
        tender.tender_value = get_number_from_currency_string(str(tender.tender_value))
    db.commit()
except Exception as e:
    print(e)
