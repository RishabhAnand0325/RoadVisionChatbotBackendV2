from app.db.database import SessionLocal
from app.modules.tenderiq.repositories import repository as tenderiq_repo
from app.modules.tenderiq.services import tender_service_sse as service


db = SessionLocal()

def main():
    result = service.get_daily_tenders_sse(db, 0, 1000, None)
    for value in result:
        print(value)

if __name__ == "__main__":
    main()
