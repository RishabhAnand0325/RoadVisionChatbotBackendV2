
from app.db.database import SessionLocal
from app.modules.tenderiq.repositories import repository as repo

from app.modules.tenderiq.services import tender_service_sse as service
import json

db = SessionLocal()

scrape_runs = repo.get_scrape_runs(db)
latest_scrape_run = scrape_runs[0]
categories_of_current_day = repo.get_all_categories(db, latest_scrape_run)

for category in categories_of_current_day:
    # tenders = repo.get_tenders_from_category(db, category, 0, 100)
    tenders = repo.get_all_tenders_from_category(db, category)
    for tender in tenders:
        print(f"{tender.id}, {tender.tender_name}, {tender.tender_value}")
    print(len(tenders))
