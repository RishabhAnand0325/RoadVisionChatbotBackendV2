from app.modules.scraper.tenderdetails_v2 import home_page_scrape
from app.modules.scraper.service import get_headless_driver

def main():
    driver = get_headless_driver()
    home_page_scrape.scrape_page("https://www.tenderdetail.com/dailytenderresults/255579/03b3ca1e-cbb5-4bfb-b64a-5da085948d21#Civil%20Work", driver)
    pass

if __name__ == "__main__":
    main()
