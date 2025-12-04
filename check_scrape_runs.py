from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapeRun
from sqlalchemy import desc

def check_scrape_runs():
    db = SessionLocal()
    try:
        runs = db.query(ScrapeRun).order_by(ScrapeRun.tender_release_date.desc()).limit(10).all()
        print(f"Found {len(runs)} scrape runs.")
        for r in runs:
            print(f"ID: {r.id}, Release Date: {r.tender_release_date}, Run At: {r.run_at}, Date Str: {r.date_str}")

    finally:
        db.close()

if __name__ == "__main__":
    check_scrape_runs()
