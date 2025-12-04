import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.db.database import SessionLocal
from app.modules.analyze.scripts.analyze_tender import analyze_tender

def main():
    db = SessionLocal()
    try:
        # tdr_id = "51184451"
        tdr_id = "51702878"
        print(f"🔍 Running analysis for tender {tdr_id}...")
        analyze_tender(db, tdr_id)
        print("✅ Analysis complete")
    finally:
        db.close()

if __name__ == "__main__":
    main()
