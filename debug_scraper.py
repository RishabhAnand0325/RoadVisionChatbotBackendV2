
import sys
import os
import logging
from app.modules.scraper.detail_page_scrape import scrape_tender

# Setup logging
logging.basicConfig(level=logging.DEBUG)

def test_scrape():
    url = "https://delivery.tenderdetail.com/ANFUXESBC?id=146143=Ik0BB1IABwUGHgMBVAJeUF1WAlACVgJTAAFXUw4KC1RSUgBSBQBTUgwGB1IOVlQDBgdIRV4QUVlYWyEWV1JdEAhCWFkIGFdYSVNWAgAHVAZWVQACA1cKBggAHQxMR0kVWx4eUgNaX0dQEBgaQ1UIVgEXUFNCBFpdF1UOCRdydyA0aXRlJHUJWFEeFwc=&fl=CUVFRhUMGR5CFRYaQ1UIVgEXUFNCBFpdF1UOCRdXWA8NSEVTCFJTQ0ZNVQwBB1AFVFYbAwNdBAJfU1RJCgENVkwFBlBUG1cHAQNMDQJUAgtTXAcPA1UB"
    print(f"Testing scrape for URL: {url}")
    try:
        result = scrape_tender(url)
        print("Scrape result:", result)
    except Exception as e:
        print(f"Scrape failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scrape()
