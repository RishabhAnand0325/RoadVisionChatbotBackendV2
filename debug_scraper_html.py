
import sys
import os
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Setup session like in the main code
session = requests.Session()
retry = Retry(total=3, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
session.mount('http://', adapter)
session.mount('https://', adapter)

def debug_html():
    url = "https://delivery.tenderdetail.com/ANFUXESBC?id=146143=Ik0BB1IABwUGHgMBVAJeUF1WAlACVgJTAAFXUw4KC1RSUgBSBQBTUgwGB1IOVlQDBgdIRV4QUVlYWyEWV1JdEAhCWFkIGFdYSVNWAgAHVAZWVQACA1cKBggAHQxMR0kVWx4eUgNaX0dQEBgaQ1UIVgEXUFNCBFpdF1UOCRdydyA0aXRlJHUJWFEeFwc=&fl=CUVFRhUMGR5CFRYaQ1UIVgEXUFNCBFpdF1UOCRdXWA8NSEVTCFJTQ0ZNVQwBB1AFVFYbAwNdBAJfU1RJCgENVkwFBlBUG1cHAQNMDQJUAgtTXAcPA1UB"
    print(f"Fetching URL: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    
    response = session.get(url, headers=headers, timeout=60)
    print(f"Status Code: {response.status_code}")
    print(f"Final URL: {response.url}")
    
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
    print("Saved HTML to debug_page.html")
    
    soup = BeautifulSoup(response.content, 'html.parser')
    tender_details = soup.find('div', attrs={'class': 'tender-details-home'})
    print(f"Found 'tender-details-home': {tender_details is not None}")
    
    if not tender_details:
        print("Page Title:", soup.title.string if soup.title else "No Title")
        # Print some body classes or ids to guess structure
        body = soup.find('body')
        if body:
            print("Body classes:", body.get('class'))
            print("Body id:", body.get('id'))
            
            # Look for any tables
            tables = soup.find_all('table')
            print(f"Found {len(tables)} tables")

if __name__ == "__main__":
    debug_html()
