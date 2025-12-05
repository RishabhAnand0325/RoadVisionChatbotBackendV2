from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender
from sqlalchemy import text

def check_invalid_dates():
    db = SessionLocal()
    try:
        # Regex for DD-MM-YYYY
        # \d{2}-\d{2}-\d{4}
        
        # Find dates that do NOT match the regex
        invalid_dates = db.query(ScrapedTender.publish_date).filter(
            text("scraped_tenders.publish_date !~ '^\\d{2}-\\d{2}-\\d{4}$'")
        ).all()
        
        print(f"Found {len(invalid_dates)} invalid publish dates.")
        for d in invalid_dates:
            print(f"Invalid: '{d[0]}'")

    finally:
        db.close()

if __name__ == "__main__":
    check_invalid_dates()
