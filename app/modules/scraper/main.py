import time
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from premailer import transform
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By

import requests
import re
import json
import os

# Local modules
from app.db.database import SessionLocal
from app.modules.scraper.db.repository import ScraperRepository
from .detail_page_scrape import scrape_tender
# from .drive import authenticate_google_drive, download_folders, get_shareable_link, upload_folder_to_drive
from .email_sender import listen_and_get_link, send_html_email
from .home_page_scrape import scrape_page
from .services.dms_integration_service import process_tenders_for_dms
from .templater import generate_email, reformat_page

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

def scrape_link(link: str):
    homepage = scrape_page(link)
    removed_tenders = {}
    for query_table in homepage.query_table:
        print("Current query: " + query_table.query_name)
        for tender in query_table.tenders:
            try:
                tender.details = scrape_tender(tender.tender_url)
            except Exception as e:
                query_table.tenders.remove(tender)
                removed_tenders[tender.tender_id] = json.loads(tender.model_dump_json(indent=2))
                print("Error: " + str(e))

    # download_folders(homepage) # NOTE: De-activated while switching to DMS

    db = SessionLocal()
    try:
        # --- DMS Integration and Database Save ---
        homepage = process_tenders_for_dms(db, homepage)

        print("\n💾 Saving scraped data to the database...")
        scraper_repo = ScraperRepository(db)
        scraper_repo.create_scrape_run(homepage)
        print("✅ Scraped data saved successfully.")

    except Exception as e:
        print(f"❌ A critical error occurred during DMS integration or database save: {e}")
        db.rollback()
    finally:
        db.close()
        print("🔒 Database session closed.")

    generated_template = generate_email(homepage)
    # insert_drive_links(generated_template)

    with open("email.html", "w") as f:
        f.write(generated_template.prettify())

    with open("removed_tenders.json", "w") as f:
        f.write(json.dumps(removed_tenders))

    send_html_email(generated_template)

def listen_email():
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
