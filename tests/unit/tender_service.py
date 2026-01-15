from app.db.database import SessionLocal
from app.modules.tenderiq.services import tender_service


db = SessionLocal()

def main():
    tenders = tender_service.get_daily_tenders(db)
    print(tenders.model_dump_json())
    pass

if __name__ == "__main__":
    main()
