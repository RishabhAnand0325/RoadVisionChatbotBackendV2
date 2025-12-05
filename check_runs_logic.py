from app.db.database import SessionLocal
from app.modules.tenderiq.repositories import repository as tenderiq_repo
from app.modules.scraper.db.schema import ScrapeRun

def check_runs_logic():
    db = SessionLocal()
    try:
        # Check total runs
        total_runs = db.query(ScrapeRun).count()
        print(f"Total ScrapeRuns in DB: {total_runs}")
        
        # Check last 2 days
        runs_2_days = tenderiq_repo.get_scrape_runs_by_date_range(db, 2)
        print(f"Runs in last 2 days: {len(runs_2_days)}")
        for r in runs_2_days:
            print(f"  ID: {r.id}, Date: {r.tender_release_date}, Tenders: {r.no_of_new_tenders}")
            
        # Check last 30 days
        runs_30_days = tenderiq_repo.get_scrape_runs_by_date_range(db, 30)
        print(f"Runs in last 30 days: {len(runs_30_days)}")

    finally:
        db.close()

if __name__ == "__main__":
    check_runs_logic()
