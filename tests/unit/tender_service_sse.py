from app.db.database import SessionLocal
from app.modules.tenderiq.repositories import repository as tenderiq_repo
from app.modules.tenderiq.services import tender_service_sse as service


db = SessionLocal()

def main():
    # result = service.get_daily_tenders_sse(db, 0, 1000, None)
    result = service.get_daily_tenders_sse(db, 0, 1000, "146e3472-c353-4a5f-8f14-1394bedf7796")
    # result = service.get_daily_tenders_sse(db, 0, 1000, "017a1d26-73d4-4710-ace1-3f9ae0f360cf")
    for value in result:
        print(value)

if __name__ == "__main__":
    main()
