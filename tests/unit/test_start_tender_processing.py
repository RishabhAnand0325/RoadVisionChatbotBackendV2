
import argparse
from app.modules.scraper import detail_page_scrape
from app.modules.scraper.process_tender import start_tender_processing
from app.db.database import SessionLocal
from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository


def test_tender_processing(tender_url: str):
    """
    Runs the full end-to-end processing and analysis for a single tender URL.
    """
    print(f"--- 🧪 Starting Test for Tender Processing ---")
    print(f"URL: {tender_url}")

    # 1. Scrape the tender detail page to get the data model
    print("\n[Step 1/3] Scraping tender detail page...")
    try:
        detail_page_data = detail_page_scrape.scrape_tender(tender_url)
        print("✅ Detail page scraped successfully.")
    except Exception as e:
        print(f"❌ Failed to scrape detail page: {e}")
        return

    # 2. Run the processing function
    print("\n[Step 2/3] Starting tender processing and analysis...")
    start_tender_processing(detail_page_data)
    print("✅ Tender processing function finished.")

    # 3. Verify the result in the database
    print("\n[Step 3/3] Verifying results in the database...")
    db = SessionLocal()
    try:
        analyze_repo = AnalyzeRepository(db)
        tender_id_str = detail_page_data.notice.tender_id
        
        from app.modules.scraper.db.schema import ScrapedTender
        
        scraped_tender = db.query(ScrapedTender).filter(ScrapedTender.tender_id_str == tender_id_str).first()
        if not scraped_tender:
            print(f"❌ Verification failed: ScrapedTender with id '{tender_id_str}' not found in 'scraped_tenders' table.")
            return

        analysis = analyze_repo.get_by_tender_id(tender_id_str)
        
        if analysis:
            print("✅ Verification successful! Found analysis record in the database.")
            print(f"   - Analysis ID: {analysis.id}")
            print(f"   - Status: {analysis.status}")
            if analysis.one_pager_json:
                print("   - One-Pager data is present.")
            else:
                print("   - ⚠️ One-Pager data is NOT present.")
        else:
            print("❌ Verification failed: No analysis record found for this tender.")

    finally:
        db.close()
    
    print(f"\n--- ✅ Test Finished ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the tender processing pipeline.")
    parser.add_argument(
        "url",
        nargs="?",
        default="https://www.tenderdetail.com/Indian-Tenders/TenderNotice/51690490/E748B155-1BBE-47B5-B962-10CF50EB85DD/147107/47136136/7c7651b5-98f3-4956-9404-913de95abb79",
        help="The URL of the tender detail page to process."
    )
    args = parser.parse_args()

    test_tender_processing(args.url)
