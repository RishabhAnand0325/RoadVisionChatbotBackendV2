from app.core.helpers import remove_starting_numbers
from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.tenderiq.db.schema import Tender


db = SessionLocal()

def main():
    scraped_tenders = db.query(ScrapedTender).all()
    tenders = db.query(Tender).all()
    for tender in scraped_tenders:
        tender.tender_name = remove_starting_numbers(str(tender.tender_name))
    db.commit()
    for tender in tenders:
        tender.tender_title = remove_starting_numbers(str(tender.tender_title))
    db.commit()


if __name__ == "__main__":
    main()
