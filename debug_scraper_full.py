
import sys
import os
import logging
from app.modules.scraper.main import scrape_link

# Setup logging
logging.basicConfig(level=logging.DEBUG)

def test_scrape_link():
    url = "https://delivery.tenderdetail.com/ANFUXESBC?id=146143=Ik0BB1IABwUGHgMBVAJeUF1WAlACVgJTAAFXUw4KC1RSUgBSBQBTUgwGB1IOVlQDBgdIRV4QUVlYWyEWV1JdEAhCWFkIGFdYSVNWAgAHVAZWVQACA1cKBggAHQxMR0kVWx4eUgNaX0dQEBgaQ1UIVgEXUFNCBFpdF1UOCRdydyA0aXRlJHUJWFEeFwc=&fl=CUVFRhUMGR5CFRYaQ1UIVgEXUFNCBFpdF1UOCRdXWA8NSEVTCFJTQ0ZNVQwBB1AFVFYbAwNdBAJfU1RJCgENVkwFBlBUG1cHAQNMDQJUAgtTXAcPA1UB"
    print(f"Testing scrape_link for URL: {url}")
    try:
        # Use skip_dedup_check=True so we don't rely on DB state or get skipped
        result = scrape_link(link=url, skip_dedup_check=True, source_priority="high")
        print("scrape_link result:", result)
    except Exception as e:
        print(f"scrape_link failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scrape_link()
