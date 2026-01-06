# from typing import List, Optional
# from bs4 import BeautifulSoup
# from bs4.element import Tag
# import requests

# from app.core.helpers import get_number_from_currency_string

# from .data_models import TenderDetailContactInformation, TenderDetailDetails, TenderDetailKeyDates, TenderDetailNotice, TenderDetailOtherDetail, TenderDetailPage, TenderDetailPageFile

# def notice_table_helper(search: str, rows: List[Tag]) -> str:
#     for row in rows:
#         if search in row.text:
#             return row.find_all('td')[1].text.strip()

#     return "N/A"


# def scrape_notice_table(table: Tag) -> TenderDetailNotice:
#     # up to 14 rows in the notice table
#     # Row one is table name, Ignore
#     # Remaining rows are as follows:
#     # 1. TDR
#     # 2. Tendering Authority
#     # 3. Tender No
#     # 4. Tender ID
#     # 5. Tender Brief
#     # 6. City
#     # 7. State
#     # 8. Document Fees
#     # 9. EMD
#     # 10. Tender Value
#     # 11. Tender Type
#     # 12. Bidding Type
#     # 13. Competition Type
#     # Note that some of these will not exist. 
#     # we have to smartly find the ones that do exist
#     rows = table.find_all('tr')
#     rows = rows[1:]

#     return TenderDetailNotice(
#         tdr=notice_table_helper('TDR', rows),
#         tendering_authority=notice_table_helper('Tendering Authority', rows),
#         tender_no=notice_table_helper('Tender No', rows),
#         tender_id=notice_table_helper('Tender ID', rows),
#         tender_brief=notice_table_helper('Tender Brief', rows),
#         city=notice_table_helper('City', rows),
#         state=notice_table_helper('State', rows),
#         document_fees=notice_table_helper('Document Fees', rows),
#         emd=notice_table_helper('EMD', rows),
#         tender_value=get_number_from_currency_string(notice_table_helper('Tender Value', rows)),
#         tender_type=notice_table_helper('Tender Type', rows),
#         bidding_type=notice_table_helper('Bidding Type', rows),
#         competition_type=notice_table_helper('Competition Type', rows)
#     )

# def scrape_details(table: Tag) -> TenderDetailDetails:
#     # This table will have a paragraph that contains all the details
#     p = table.find('p')
#     if not p:
#         raise Exception("Tender details table does not have a paragraph")
#     return TenderDetailDetails(tender_details=p.text.strip())

# def key_dates_helper(search: str, rows: List[Tag]) -> str:
#     for row in rows:
#         if search in row.text:
#             return row.find_all('td')[1].text.strip()

#     return "N/A"

# def scrape_key_dates(table: Tag) -> TenderDetailKeyDates:
#     # This table has upto 4 rows:
#     # 1. Table name
#     # 2. Publish Date
#     # 3. Last Date of Bid Submission
#     # 4. Tender Opening Date
#     # Note that some of these will not exist.
#     rows = table.find_all('tr')
#     rows = rows[1:]

#     return TenderDetailKeyDates(
#         publish_date=key_dates_helper('Publish Date', rows),
#         last_date_of_bid_submission=key_dates_helper('Last Date of Bid Submission', rows),
#         tender_opening_date=key_dates_helper('Tender Opening Date', rows)
#     )

# def contact_information_helper(search: str, rows: List[Tag]) -> str:
#     for row in rows:
#         if search in row.text:
#             return row.find_all('td')[1].text.strip()

#     return "N/A"

# def scrape_contact_information(table: Tag) -> TenderDetailContactInformation:
#     # This table has upto 4 rows:
#     # 1. Table name
#     # 2. Company Name
#     # 3. Contact Person
#     # 4. Address
#     # Note that some of these will not exist.
#     rows = table.find_all('tr')
#     rows = rows[1:]

#     return TenderDetailContactInformation(
#         company_name=contact_information_helper('Company Name', rows),
#         contact_person=contact_information_helper('Contact Person', rows),
#         address=contact_information_helper('Address', rows)
#     )

# def scrape_other_details(table: Tag) -> TenderDetailOtherDetail:
#     # This table has 4 rows:
#     # 1. Table name
#     # 2. Information source
#     # 3. Another sub-table with variable number of rows containing the following columns:
#     #     1. File name
#     #     2. File type
#     #     3. File size
#     #     4. File link
#     #   The first row is the column names and should be ignored
#     # 4. Empty row
#     rows = table.find_all('tr', recursive=False)
#     if not len(rows) == 4:
#         raise Exception("Tender other details table has incorrect number of rows")

#     # Information source
#     information_source = rows[1].find_all('td')[1].text.strip()

#     # Another sub-table
#     sub_table = rows[2]
#     if not sub_table:
#         raise Exception("Tender other details table does not have a sub-table")
#     sub_table_rows = sub_table.find_all('tr')
#     if not len(sub_table_rows) > 0:
#         raise Exception("Tender other details table sub-table has incorrect number of rows")

#     # Ignoring the first row, iterate through the remaining rows
#     files: List[TenderDetailPageFile] = []
#     for i in range(1, len(sub_table_rows)):
#         file_row = sub_table_rows[i]
#         url_element = file_row.find('a')
#         if not url_element:
#             raise Exception("Tender other details table sub-table does not have a link")
#         file_link = url_element.attrs['href']
#         file_name = file_row.find_all('td')[1].text.strip()
#         file_type = file_row.find_all('td')[2].text.strip()
#         file_size = file_row.find_all('td')[3].text.strip()
#         files.append(TenderDetailPageFile(
#             file_name=file_name,
#             file_url=str(file_link),
#             file_description=file_type,
#             file_size=file_size
#         ))

#     return TenderDetailOtherDetail(
#         information_source=information_source,
#         files=files
#     )


# def scrape_tender(tender_link) -> TenderDetailPage:
#     # print("Scraping tender: " + tender_link)
#     page = requests.get(tender_link)
#     soup = BeautifulSoup(page.content, 'html.parser')

#     # Every tender page will have a tender-details-home class that contains all the content
#     tender_details_home = soup.find('div', attrs={'class': 'tender-details-home'})
#     if not tender_details_home:
#         raise Exception("Tender details home not found")

#     # Tender details home will have 5 tables in the order:
#     # 1. Tender Notice
#     # 2. Tender Details
#     # 3. Key Dates
#     # 4. Contact Information
#     # 5. Other Detail
#     tender_details_tables = tender_details_home.find_all('table', recursive=False)
#     if not tender_details_tables:
#         raise Exception("Tender details tables not found")
#     if not len(tender_details_tables) == 5:
#         raise Exception("Tender details tables not found")


#     # Tender notice table
#     tender_notice_table = tender_details_tables[0]
#     if not tender_notice_table:
#         raise Exception("Tender notice table not found")

#     # Tender details table
#     tender_details_table = tender_details_tables[1]
#     if not tender_details_table:
#         raise Exception("Tender details table not found")

#     # Key dates table
#     key_dates_table = tender_details_tables[2]
#     if not key_dates_table:
#         raise Exception("Key dates table not found")

#     # Contact information table
#     contact_information_table = tender_details_tables[3]
#     if not contact_information_table:
#         raise Exception("Contact information table not found")

#     # Other details table
#     other_details_table = tender_details_tables[4]
#     if not other_details_table:
#         raise Exception("Other details table not found")

#     notice = scrape_notice_table(tender_notice_table)
#     details = scrape_details(tender_details_table)
#     key_dates = scrape_key_dates(key_dates_table)
#     contact_information = scrape_contact_information(contact_information_table)
#     other_detail = scrape_other_details(other_details_table)

#     return TenderDetailPage(
#         notice=notice,
#         details=details,
#         key_dates=key_dates,
#         contact_information=contact_information,
#         other_detail=other_detail
#     )


from typing import List, Optional
import logging
from bs4 import BeautifulSoup
from bs4.element import Tag
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.helpers import get_number_from_currency_string
from .data_models import (
    TenderDetailContactInformation, 
    TenderDetailDetails, 
    TenderDetailKeyDates, 
    TenderDetailNotice, 
    TenderDetailOtherDetail, 
    TenderDetailPage, 
    TenderDetailPageFile
)

# Configure logger
logger = logging.getLogger(__name__)

# --- SPEED OPTIMIZATION: Global Session with Pooling ---
# This keeps 50 connections open so threads don't wait for handshakes
session = requests.Session()
retry = Retry(total=3, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
session.mount('http://', adapter)
session.mount('https://', adapter)
# -------------------------------------------------------

def notice_table_helper(search: str, rows: List[Tag]) -> str:
    if not rows: return "N/A"
    for row in rows:
        if search in row.text:
            cells = row.find_all('td')
            if len(cells) > 1: return cells[1].text.strip()
    return "N/A"

def scrape_notice_table(table: Optional[Tag]) -> TenderDetailNotice:
    if not table:
        return TenderDetailNotice(
            tdr="N/A", tendering_authority="N/A", tender_no="N/A", tender_id="N/A",
            tender_brief="N/A", city="N/A", state="N/A", document_fees="N/A",
            emd="N/A", tender_value=0, tender_type="N/A", bidding_type="N/A",
            competition_type="N/A"
        )
    rows = table.find_all('tr')
    rows = rows[1:] if len(rows) > 0 else []

    return TenderDetailNotice(
        tdr=notice_table_helper('TDR', rows),
        tendering_authority=notice_table_helper('Tendering Authority', rows),
        tender_no=notice_table_helper('Tender No', rows),
        tender_id=notice_table_helper('Tender ID', rows),
        tender_brief=notice_table_helper('Tender Brief', rows),
        city=notice_table_helper('City', rows),
        state=notice_table_helper('State', rows),
        document_fees=notice_table_helper('Document Fees', rows),
        emd=notice_table_helper('EMD', rows),
        tender_value=get_number_from_currency_string(notice_table_helper('Tender Value', rows)),
        tender_type=notice_table_helper('Tender Type', rows),
        bidding_type=notice_table_helper('Bidding Type', rows),
        competition_type=notice_table_helper('Competition Type', rows)
    )

def scrape_details(table: Optional[Tag]) -> TenderDetailDetails:
    if not table: return TenderDetailDetails(tender_details="N/A")
    p = table.find('p')
    return TenderDetailDetails(tender_details=p.text.strip()) if p else TenderDetailDetails(tender_details=table.text.strip())

def key_dates_helper(search: str, rows: List[Tag]) -> str:
    if not rows: return "N/A"
    for row in rows:
        if search in row.text:
            cells = row.find_all('td')
            if len(cells) > 1: return cells[1].text.strip()
    return "N/A"

def scrape_key_dates(table: Optional[Tag]) -> TenderDetailKeyDates:
    if not table: return TenderDetailKeyDates(publish_date="N/A", last_date_of_bid_submission="N/A", tender_opening_date="N/A")
    rows = table.find_all('tr')[1:]
    return TenderDetailKeyDates(
        publish_date=key_dates_helper('Publish Date', rows),
        last_date_of_bid_submission=key_dates_helper('Last Date of Bid Submission', rows),
        tender_opening_date=key_dates_helper('Tender Opening Date', rows)
    )

def contact_information_helper(search: str, rows: List[Tag]) -> str:
    if not rows: return "N/A"
    for row in rows:
        if search in row.text:
            cells = row.find_all('td')
            if len(cells) > 1: return cells[1].text.strip()
    return "N/A"

def scrape_contact_information(table: Optional[Tag]) -> TenderDetailContactInformation:
    if not table: return TenderDetailContactInformation(company_name="N/A", contact_person="N/A", address="N/A")
    rows = table.find_all('tr')[1:]
    return TenderDetailContactInformation(
        company_name=contact_information_helper('Company Name', rows),
        contact_person=contact_information_helper('Contact Person', rows),
        address=contact_information_helper('Address', rows)
    )

def scrape_other_details(table: Optional[Tag]) -> TenderDetailOtherDetail:
    default_obj = TenderDetailOtherDetail(information_source="N/A", files=[])
    if not table: return default_obj
    rows = table.find_all('tr', recursive=False)
    if not rows: return default_obj

    information_source = "N/A"
    try:
        # Fast scan for source
        for row in rows:
            if "Information Source" in row.text:
                cells = row.find_all('td')
                if len(cells) > 1:
                    information_source = cells[1].text.strip()
                break
    except: pass

    files: List[TenderDetailPageFile] = []
    try:
        # Try multiple approaches to find the files table
        sub_table = table.find('table')
        
        # If no nested table, the files might be in the main table rows
        if not sub_table:
            # Look for rows with download links directly
            all_rows = table.find_all('tr')
            for row in all_rows:
                url_element = row.find('a', href=True)
                if url_element and 'href' in url_element.attrs:
                    href = url_element.attrs['href']
                    # Check if it looks like a file download link
                    if href and ('download' in href.lower() or '.pdf' in href.lower() or 
                                 '.doc' in href.lower() or '.xls' in href.lower() or
                                 'file' in href.lower() or 'attachment' in href.lower()):
                        cells = row.find_all('td')
                        if len(cells) >= 2:
                            files.append(TenderDetailPageFile(
                                file_name=cells[1].text.strip() if len(cells) > 1 else url_element.text.strip(),
                                file_url=str(href),
                                file_description=cells[2].text.strip() if len(cells) > 2 else "Document",
                                file_size=cells[3].text.strip() if len(cells) > 3 else "Unknown"
                            ))
        else:
            sub_table_rows = sub_table.find_all('tr')[1:] # Skip header
            for row in sub_table_rows:
                url_element = row.find('a', href=True)
                cells = row.find_all('td')
                if url_element and len(cells) >= 2:
                    files.append(TenderDetailPageFile(
                        file_name=cells[1].text.strip() if len(cells) > 1 else url_element.text.strip(),
                        file_url=str(url_element.attrs.get('href', '')),
                        file_description=cells[2].text.strip() if len(cells) > 2 else "Document",
                        file_size=cells[3].text.strip() if len(cells) > 3 else "Unknown"
                    ))
    except Exception as e:
        logger.warning(f"Error parsing files: {e}")

    return TenderDetailOtherDetail(information_source=information_source, files=files)

def scrape_tender(tender_link: str) -> Optional[TenderDetailPage]:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Connection': 'keep-alive'
        }
        
        # --- OPTIMIZATION 1: Use Session with Pooling ---
        page = session.get(tender_link, headers=headers, timeout=60)
        if page.status_code != 200: return None

        # --- OPTIMIZATION 2: LXML Parser (Install with: pip install lxml) ---
        try:
            soup = BeautifulSoup(page.content, 'lxml')
        except:
            soup = BeautifulSoup(page.content, 'html.parser')

        tender_details_home = soup.find('div', attrs={'class': 'tender-details-home'})
        if not tender_details_home:
            # logger.warning(f"Container not found: {tender_link}")
            return None

        # --- OPTIMIZATION 3: Dynamic & Safe Table Finding ---
        all_tables = tender_details_home.find_all('table', recursive=False)
        tables = {'notice': None, 'details': None, 'dates': None, 'contact': None, 'other': None}
        
        for tbl in all_tables:
            txt = tbl.text.lower()[:100] # Check start of text only
            if "tender notice" in txt: tables['notice'] = tbl
            elif "tender details" in txt: tables['details'] = tbl
            elif "key dates" in txt: tables['dates'] = tbl
            elif "contact information" in txt: tables['contact'] = tbl
            elif "other detail" in txt: tables['other'] = tbl

        return TenderDetailPage(
            notice=scrape_notice_table(tables['notice']),
            details=scrape_details(tables['details']),
            key_dates=scrape_key_dates(tables['dates']),
            contact_information=scrape_contact_information(tables['contact']),
            other_detail=scrape_other_details(tables['other'])
        )

    except Exception as e:
        logger.error(f"Error scraping {tender_link}: {str(e)}")
        return None