import time
from typing import Optional
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from premailer import transform
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from datetime import datetime

import requests
import re
import json
import os

# Local modules
from app.db.database import SessionLocal
from app.modules.scraper.db.repository import ScraperRepository
from app.modules.tenderiq.db.repository import TenderRepository
from .detail_page_scrape import scrape_tender
from .process_tender import start_tender_processing
# from .drive import authenticate_google_drive, download_folders, get_shareable_link, upload_folder_to_drive
from .email_sender import listen_and_get_link, listen_and_get_unprocessed_emails, send_html_email
from .home_page_scrape import scrape_page
from .services.dms_integration_service import process_tenders_for_dms
from .templater import generate_email, reformat_page
from .progress_tracker import ProgressTracker, ScrapeSection, logger

load_dotenv()

GOOGLE_DRIVE_PARENT_FOLDER = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER")
base_url = "https://www.tenderdetail.com"
tdr_xpath = "/html/body/div/div[1]/section[2]/div[1]/div/div/table[1]/tbody/tr[2]/td[2]"

def clean_project():
    # First lets clear the tenders/ directory
    os.system("rm -rf tenders/")
    # Create the tenders/ directory
    os.mkdir("tenders/")

def insert_drive_links(soup: BeautifulSoup):
    soup2 = BeautifulSoup(open("./final.html"), 'html.parser')
    soup1_tenders_links = soup.find_all('a', attrs={'class': 'tender_table_view_tender_link'})
    soup2_tenders_links = soup2.find_all('p', attrs={'class': 'm-td-brief-link'})

    # Replace the links in soup1 with the google drive links in soup2
    # Iterate through both lists at the same time
    for tender1, tender2 in zip(soup1_tenders_links, soup2_tenders_links):
        tender1['href'] = tender2.find_all('a')[0]['href']

def scrape_link(link: str, source_priority: str = "normal", skip_dedup_check: bool = False, email_info: Optional[dict] = None):
    """
    Main scraping function with comprehensive progress tracking and logging.
    Supports both manual link pasting and email-based scraping with unified deduplication.

    Flow:
    1. Check for duplicates (with priority-based conflict resolution)
    2. Scrape home page
    3. Scrape detail pages for each tender
    4. DMS integration
    5. Save to database
    6. Log processing and generate/send email

    Args:
        link: The tender URL to scrape
        source_priority: "low", "normal", or "high" - used for conflict resolution when same tender from multiple sources
        skip_dedup_check: If True, skip deduplication check (use with caution, mainly for testing)
    """
    tracker = ProgressTracker(verbose=True)
    start_time = datetime.now()

    try:
        # Initialize database connection for deduplication check
        db = SessionLocal()
        scraper_repo = ScraperRepository(db)

        # Step 0: Deduplication Check (before any scraping)
        if not skip_dedup_check:
            with ScrapeSection(tracker, "Deduplication Check"):
                is_duplicate, existing_log = scraper_repo.check_tender_duplicate_with_priority(link, source_priority)

                if is_duplicate:
                    logger.info(f"⏭️  DUPLICATE TENDER DETECTED: {link}")
                    logger.info(f"   Previously processed by: {existing_log.email_sender} on {existing_log.processed_at}")

                    priority_order = {"low": 0, "normal": 1, "high": 2}
                    source_level = priority_order.get(source_priority, 1)
                    existing_level = priority_order.get(existing_log.priority, 1)

                    if source_level > existing_level:
                        logger.info(f"   ✅ Higher priority detected! Re-processing tender...")
                        # Mark old one as superseded
                        scraper_repo.mark_superseded(
                            str(existing_log.id),
                            f"Reprocessed with higher priority ({source_priority})"
                        )
                        logger.info(f"   Marked previous entry as superseded")
                    else:
                        logger.warning(f"   ⚠️  Same or lower priority. Skipping scrape.")
                        logger.info(f"   To re-scrape, use source_priority='high'")

                        # Log this as skipped
                        if email_info:
                             scraper_repo.log_email_processing(
                                email_uid=email_info['email_uid'],
                                email_sender=email_info['email_sender'],
                                email_received_at=email_info['email_date'],
                                tender_url=link,
                                processing_status="skipped",
                                error_message=f"Duplicate tender (existing priority: {existing_log.priority}, new: {source_priority})",
                                priority=source_priority
                            )
                        else:
                            scraper_repo.log_email_processing(
                                email_uid="manual",
                                email_sender="manual_input",
                                email_received_at=datetime.utcnow(),
                                tender_url=link,
                                processing_status="skipped",
                                error_message=f"Duplicate tender (existing priority: {existing_log.priority}, new: {source_priority})",
                                priority=source_priority
                            )
                        db.close()
                        tracker.close_all_progress_bars()
                        return "skipped"
                else:
                    logger.info(f"✅ No duplicates found. Proceeding with scrape...")
        db.close()

        with ScrapeSection(tracker, "Homepage Scraping"):
            logger.info(f"📍 Starting scrape of: {link}")
            homepage = scrape_page(link)
            total_tenders = sum(len(q.tenders) for q in homepage.query_table)
            logger.info(f"📊 Found {total_tenders} tenders across {len(homepage.query_table)} categories")

            for query in homepage.query_table:
                logger.info(f"   📋 {query.query_name}: {len(query.tenders)} tenders")

        removed_tenders = {}
        db = SessionLocal()
        try:
            scraper_repo = ScraperRepository(db)
            tender_repo = TenderRepository(db)
            
            # DMS Integration is done first to prepare folders and get the canonical release date
            with ScrapeSection(tracker, "DMS Integration"):
                logger.info("🔄 Processing tenders for DMS integration...")
                homepage, tender_release_date = process_tenders_for_dms(db, homepage)
                logger.info("✅ DMS integration completed.")

            # Create the main ScrapeRun and empty query records
            with ScrapeSection(tracker, "Initialize Scrape Run"):
                scrape_run, query_map = scraper_repo.create_scrape_run_shell(homepage, tender_release_date)
                logger.info(f"✅ ScrapeRun created with ID: {scrape_run.id}")

            # --- STAGE 1: Scrape Details & Populate Database ---
            total_tenders = sum(len(q.tenders) for q in homepage.query_table)
            scrape_progress = tracker.create_detail_scrape_progress_bar(total_tenders)

            with ScrapeSection(tracker, "Detail Page Scraping & DB Save"):
                for query_data in homepage.query_table:
                    query_orm = query_map[query_data.query_name]
                    query_progress = tracker.create_query_progress_bar(f"Scraping {query_data.query_name}", len(query_data.tenders))

                    tenders_to_remove = []
                    for tender_data in query_data.tenders:
                        try:
                            # 1. Scrape detail page
                            logger.debug(f"🎯 Scraping detail page for: {tender_data.tender_name}")
                            tender_data.details = scrape_tender(tender_data.tender_url)
                            logger.debug(f"✅ Detail page scraped.")

                            # 2. Populate scraped_tenders table
                            logger.debug(f"💾 Saving to 'scraped_tenders': {tender_data.tender_name}")
                            scraped_tender_orm = scraper_repo.add_scraped_tender_details(query_orm, tender_data, tender_release_date)
                            logger.debug(f"✅ Saved to 'scraped_tenders'.")

                            # 3. Populate main tenders table
                            logger.debug(f"💾 Saving to 'tenders': {tender_data.tender_name}")
                            tender_repo.get_or_create_by_id(scraped_tender_orm)
                            logger.debug(f"✅ Saved to 'tenders'.")

                        except Exception as e:
                            logger.warning(f"⚠️  Failed to scrape or save tender {tender_data.tender_name}: {str(e)}")
                            tenders_to_remove.append(tender_data)
                            removed_tenders[tender_data.tender_id] = json.loads(
                                tender_data.model_dump_json(indent=2)
                            )
                        
                        if query_progress: query_progress.update(1)
                        if scrape_progress: scrape_progress.update(1)

                    # Remove tenders that failed to scrape/save, so they aren't processed for analysis
                    for tender in tenders_to_remove:
                        query_data.tenders.remove(tender)
                    
                    if query_progress: query_progress.close()
            
            if scrape_progress:
                scrape_progress.close()

            # --- STAGE 2: Process Tender Files for Analysis ---
            total_tenders_to_analyze = sum(len(q.tenders) for q in homepage.query_table)
            analysis_progress = tracker.create_analysis_progress_bar(total_tenders_to_analyze)

            with ScrapeSection(tracker, "Tender File Analysis"):
                for query_data in homepage.query_table:
                    query_progress = tracker.create_query_progress_bar(f"Analyzing {query_data.query_name}", len(query_data.tenders))
                    
                    for tender_data in query_data.tenders:
                        try:
                            if tender_data.details:
                                logger.debug(f"🔬 Starting analysis for: {tender_data.tender_name}")
                                # start_tender_processing(tender_data.details)
                                logger.debug(f"✅ Analysis complete for: {tender_data.tender_name}")
                            else:
                                logger.warning(f"⚠️  Skipping analysis for {tender_data.tender_name}: No details available.")
                        except Exception as e:
                            logger.error(f"❌ Analysis failed for tender {tender_data.tender_name}: {str(e)}")

                        if query_progress: query_progress.update(1)
                        if analysis_progress: analysis_progress.update(1)

                    if query_progress: query_progress.close()

            if analysis_progress:
                analysis_progress.close()

            if removed_tenders:
                logger.warning(f"⚠️  Removed {len(removed_tenders)} tenders due to processing errors")
            logger.info(f"✅ Tender processing completed for {total_tenders - len(removed_tenders)} tenders")

            # Log successful processing
            if email_info:
                scraper_repo.log_email_processing(
                    email_uid=email_info['email_uid'],
                    email_sender=email_info['email_sender'],
                    email_received_at=email_info['email_date'],
                    tender_url=link,
                    processing_status="success",
                    scrape_run_id=str(scrape_run.id),
                    priority=source_priority
                )
            else: # Manual run success
                scraper_repo.log_email_processing(
                    email_uid="manual",
                    email_sender="manual_input",
                    email_received_at=datetime.utcnow(),
                    tender_url=link,
                    processing_status="success",
                    scrape_run_id=str(scrape_run.id),
                    priority=source_priority
                )

        except Exception as e:
            logger.error(f"❌ Critical error during main processing loop", e)
            db.rollback()
            tracker.log_error("Processing loop failed", e)
            raise
        finally:
            db.close()
            logger.info("🔒 Database session closed")

        # Email generation and sending
        with ScrapeSection(tracker, "Email Generation & Sending"):
            logger.info("📧 Generating email template...")
            generated_template = generate_email(homepage)

            logger.info("💾 Writing HTML files...")
            with open("email.html", "w") as f:
                f.write(generated_template.prettify())

            if removed_tenders:
                with open("removed_tenders.json", "w") as f:
                    f.write(json.dumps(removed_tenders))
                logger.info(f"📝 Wrote removed_tenders.json with {len(removed_tenders)} entries")

            logger.info("📤 Sending email...")
            send_html_email(generated_template)
            logger.info("✅ Email sent successfully")

        # Log final statistics
        duration = (datetime.now() - start_time).total_seconds()
        final_tender_count = sum(len(q.tenders) for q in homepage.query_table)

        tracker.log_summary({
            "Total Tenders Processed": final_tender_count,
            "Tenders Removed (Errors)": len(removed_tenders),
            "Duration": f"{duration:.2f}s",
            "Status": "✅ SUCCESS"
        })
        return "success"

    except Exception as e:
        tracker.log_error("❌ Fatal error in scrape_link", e)
        # Log failure if it's from an email or manual run
        try:
            db = SessionLocal()
            scraper_repo = ScraperRepository(db)
            if email_info:
                scraper_repo.log_email_processing(
                    email_uid=email_info['email_uid'],
                    email_sender=email_info['email_sender'],
                    email_received_at=email_info['email_date'],
                    tender_url=link,
                    processing_status="failed",
                    error_message=str(e),
                    priority=source_priority
                )
            else: # Manual run failure
                scraper_repo.log_email_processing(
                    email_uid="manual",
                    email_sender="manual_input",
                    email_received_at=datetime.utcnow(),
                    tender_url=link,
                    processing_status="failed",
                    error_message=str(e),
                    priority=source_priority
                )
            db.close()
        except Exception as log_e:
            logger.error(f"Additionally, failed to log the error to database: {log_e}")
        raise
    finally:
        tracker.close_all_progress_bars()

def listen_email():
    """
    Email listening loop with progress tracking and comprehensive logging.

    Flow:
    1. Fetch ALL emails from tenders@tenderdetail.com (read or unread)
    2. For each email, extract the tender URL
    3. Check if email+tender has been processed before (deduplication)
    4. Check if tender URL has been processed from ANY email
    5. If not processed, scrape it and log in database
    6. Wait 5 minutes and repeat

    This avoids the "user reads email → listener can't find it" bug.
    """
    tracker = ProgressTracker(verbose=True)
    cycle_number = 0

    while True:
        cycle_number += 1
        cycle_start = datetime.now()

        with ScrapeSection(tracker, f"Email Polling Cycle #{cycle_number}"):
            db = SessionLocal()
            try:
                scraper_repo = ScraperRepository(db)

                # 1. Get all emails from last 24 hours
                logger.info("📧 Fetching unprocessed emails...")
                emails_data = listen_and_get_unprocessed_emails()

                if not emails_data:
                    logger.info("ℹ️  No emails from target senders found.")
                    db.close()
                    continue  # Skip to sleep and retry in next cycle

                logger.info(f"📊 Found {len(emails_data)} emails with tender URLs")

                # Create progress bar for email processing
                email_progress = tracker.create_email_progress_bar(len(emails_data))

                # 2. Process each email
                processed_count = 0
                skipped_count = 0
                failed_count = 0

                # Create deduplication progress bar
                dedup_progress = tracker.create_deduplication_progress_bar(len(emails_data))

                for email_info in emails_data:
                    tender_url = email_info['tender_url']
                    logger.info(f"🚀 Processing potential new tender from email: {tender_url}")

                    try:
                        # Close the session from this loop before calling scrape_link
                        # scrape_link manages its own db sessions internally
                        db.close()

                        # Call the unified scraping function
                        # It will handle deduplication, scraping, DMS, db saving, and logging
                        status = scrape_link(link=tender_url, email_info=email_info)

                        if status == "success":
                            processed_count += 1
                        elif status == "skipped":
                            skipped_count += 1

                    except Exception as e:
                        # scrape_link now handles its own error logging, so we just note it here
                        logger.error(f"❌ Scrape for {tender_url} failed. See logs above for details.")
                        failed_count += 1
                    finally:
                        # Re-open session for the next iteration of the loop
                        db = SessionLocal()
                        scraper_repo = ScraperRepository(db)

                    if dedup_progress:
                        dedup_progress.update(1)
                    if email_progress:
                        email_progress.update(1)

                # Close progress bars
                if dedup_progress:
                    dedup_progress.close()
                if email_progress:
                    email_progress.close()

                # Log cycle summary
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                tracker.log_stats({
                    "Total Emails": len(emails_data),
                    "Processed (New)": processed_count,
                    "Skipped (Duplicates)": skipped_count,
                    "Failed": failed_count,
                    "Cycle Duration": f"{cycle_duration:.2f}s"
                })

            except Exception as e:
                logger.error(f"❌ Critical error in listen_email cycle", e)
                db.rollback()
            finally:
                db.close()

        # 7. Wait for 5 minutes before checking again
        sleep_duration_seconds = 300
        logger.info(f"\n{'='*60}")
        logger.info(f"⏳ Next check in {sleep_duration_seconds / 60} minutes...")
        logger.info(f"{'='*60}\n")
        time.sleep(sleep_duration_seconds)


def listen_email_old():
    """
    DEPRECATED: Old implementation using UNSEEN flag.
    Kept for reference but use listen_email() instead.
    """
    while True:
        print("\n--- Starting new cycle: Listening for trigger email ---")

        # 1. Call the listener to get a link
        link_to_scrape = listen_and_get_link()

        # 2. If a link is found, run the scraper
        if link_to_scrape:
            print(f"🚀 Link found! Starting scrape for: {link_to_scrape}")
            try:
                scrape_link(link_to_scrape) # Your existing scraping function
                print("✅ Scraping and email sending process completed successfully.")
            except Exception as e:
                print(f"❌ An error occurred during the scrape/send process: {e}")
        else:
            print("No new trigger email found.")

        # 3. Wait for 5 minutes before checking again
        sleep_duration_seconds = 300
        print(f"--- Cycle complete. Waiting for {sleep_duration_seconds / 60} minutes... ---")
        time.sleep(sleep_duration_seconds)
    
if __name__ == "__main__":
    """
    Main workflow: Continuously listens for emails, and when a valid link is
    found, triggers the scraping and sending process.
    """
    print("Select a start mode: ")
    print("1. Paste a link")
    print("2. Listen for emails")

    choice = input("Enter your choice (1/2): ")

    if choice == '1':
        link_to_scrape = input("Enter the link to scrape: ")
        if link_to_scrape == "":
            link_to_scrape = "https://www.tenderdetail.com/dailytenders/47136136/7c7651b5-98f3-4956-9404-913de95abb79"
        scrape_link(link_to_scrape)
        print("✅ Scraping and email sending process completed successfully.")

    elif choice == '2':
        listen_email()

    else:
        print("Invalid choice. Please select 1 or 2.")
