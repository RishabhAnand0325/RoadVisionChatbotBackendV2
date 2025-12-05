from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender
from sqlalchemy import func, text
from sqlalchemy.exc import DataError

def test_date_conversion():
    db = SessionLocal()
    try:
        # Try to execute the sorting query to see if it fails
        try:
            db.query(ScrapedTender.id).order_by(
                func.to_date(ScrapedTender.publish_date, 'DD-MM-YYYY')
            ).all()
            print("Sorting query executed successfully.")
        except DataError as e:
            print(f"Sorting query failed: {e}")
            
            # Now try to find the specific bad row
            tenders = db.query(ScrapedTender.id, ScrapedTender.publish_date).all()
            print(f"Checking {len(tenders)} tenders...")
            for t in tenders:
                try:
                    # We can't easily test to_date row-by-row in python without making 1000s of queries
                    # But we can validate in python
                    from datetime import datetime
                    datetime.strptime(t.publish_date, '%d-%m-%Y')
                except ValueError as ve:
                    print(f"Invalid date found: ID={t.id}, Date='{t.publish_date}', Error={ve}")

    finally:
        db.close()

if __name__ == "__main__":
    test_date_conversion()
