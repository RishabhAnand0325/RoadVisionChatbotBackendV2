from app.db.database import SessionLocal
from app.modules.tenderiq.repositories import repository as tenderiq_repo
from sqlalchemy.exc import DataError, StatementError

def reproduce_crash():
    db = SessionLocal()
    try:
        print("Attempting to fetch run by date string '2025-11-21'...")
        try:
            tenderiq_repo.get_scrape_run_by_id(db, "2025-11-21")
            print("Success (unexpected)")
        except (DataError, StatementError) as e:
            print(f"Caught expected error: {e}")
            
    finally:
        db.close()

if __name__ == "__main__":
    reproduce_crash()
