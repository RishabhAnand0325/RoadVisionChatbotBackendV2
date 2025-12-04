from uuid import UUID
from app.db.database import SessionLocal
from app.modules.analyze.services import analysis_rfp_service

db = SessionLocal()

def main():
    rfp_sections = analysis_rfp_service.get_rfp_sections(db, UUID("93e4e3c1-a6ed-4da2-9110-80589849e4b8"))
    print(rfp_sections.model_dump_json())

if __name__ == "__main__":
    main()
