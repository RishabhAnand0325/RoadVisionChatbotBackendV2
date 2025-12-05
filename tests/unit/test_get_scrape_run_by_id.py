from app.db.database import SessionLocal
from app.modules.tenderiq.repositories import repository as repo


db = SessionLocal()

def main():
    run = repo.get_scrape_run_by_id(db, "146e3472-c353-4a5f-8f14-1394bedf7796")
    print(run.no_of_new_tenders)

if __name__ == "__main__":
    main()
