
from app.modules.scraper import detail_page_scrape, home_page_scrape
from app.modules.scraper.process_tender import start_tender_processing


detail_page_data = detail_page_scrape.scrape_tender("https://www.tenderdetail.com/Indian-Tenders/TenderNotice/51690490/E748B155-1BBE-47B5-B962-10CF50EB85DD/147107/47136136/7c7651b5-98f3-4956-9404-913de95abb79")
start_tender_processing(detail_page_data)
