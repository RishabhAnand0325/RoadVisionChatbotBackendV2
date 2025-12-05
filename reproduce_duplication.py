from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender
from sqlalchemy import func

def check_duplicates():
    db = SessionLocal()
    try:
        # Count ScrapedTender entries grouped by tender_id_str
        duplicates = db.query(
            ScrapedTender.tender_id_str, 
            func.count(ScrapedTender.id)
        ).group_by(ScrapedTender.tender_id_str).having(func.count(ScrapedTender.id) > 1).all()
        
        if duplicates:
            print(f"Found {len(duplicates)} tenders with multiple ScrapedTender entries.")
            for tender_id, count in duplicates[:5]:
                print(f"Tender ID: {tender_id}, Count: {count}")
        else:
            print("No duplicates found in ScrapedTender.")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_duplicates()
