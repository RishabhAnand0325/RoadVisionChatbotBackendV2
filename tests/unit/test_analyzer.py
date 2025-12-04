
from app.db.database import SessionLocal
from app.modules.analyze.scripts import analyze_tender


db = SessionLocal()

analyze_tender.analyze_tender(db, "51184451")
