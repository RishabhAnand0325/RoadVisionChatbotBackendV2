import time
from app.db.database import SessionLocal
from app.modules.analyze.db.schema import TenderAnalysis
from app.modules.analyze.scripts import analyze_tender
from app.modules.tenderiq.db.schema import Tender


db = SessionLocal()

def main():
    while True:
        # Get wishlisted tenders
        query = db.query(Tender).filter(Tender.is_wishlisted == True)
        query = query.outerjoin(TenderAnalysis, Tender.tender_ref_number == TenderAnalysis.tender_id)
        query = query.filter(TenderAnalysis.id == None)
        tenders = query.all()
        for tender in tenders:
            print("Analyzing tender: ", tender.tender_ref_number)
            analyze_tender.analyze_tender(db, str(tender.tender_ref_number))
        time.sleep(10)


if __name__ == "__main__":
    main()
