from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapeRun, ScrapedTender, ScrapedTenderQuery
from sqlalchemy import desc

def check_latest_run_tenders():
    db = SessionLocal()
    try:
        # Get latest run
        latest_run = db.query(ScrapeRun).order_by(ScrapeRun.tender_release_date.desc()).first()
        if not latest_run:
            print("No runs found.")
            return

        print(f"Latest Run ID: {latest_run.id}")
        print(f"Release Date: {latest_run.tender_release_date}")
        
        # Get tenders for this run
        tenders = (
            db.query(ScrapedTender)
            .join(ScrapedTenderQuery)
            .filter(ScrapedTenderQuery.scrape_run_id == latest_run.id)
            .limit(10)
            .all()
        )
        
        print(f"Found {len(tenders)} tenders (showing top 10).")
        for t in tenders:
            print(f"Tender ID: {t.tender_id_str}, Publish Date: {t.publish_date}")

    finally:
        db.close()

if __name__ == "__main__":
    check_latest_run_tenders()
