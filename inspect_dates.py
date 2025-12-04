from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender
from sqlalchemy import func, distinct

def check_dates():
    db = SessionLocal()
    try:
        # Get distinct publish_date values
        dates = db.query(distinct(ScrapedTender.publish_date)).all()
        print(f"Found {len(dates)} distinct publish dates.")
        for d in dates[:20]:
            print(f"'{d[0]}'")
            
        # Check for nulls
        null_count = db.query(func.count(ScrapedTender.id)).filter(ScrapedTender.publish_date == None).scalar()
        print(f"Null publish_dates: {null_count}")

    finally:
        db.close()

if __name__ == "__main__":
    check_dates()
