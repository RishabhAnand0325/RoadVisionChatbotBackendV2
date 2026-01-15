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
    TenderDetailPageFile,
    TenderDocumentChanges,
    TenderHistoryItem,
    TenderActionsHistory,
    TenderActionHistoryItem
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

def scrape_document_changes(soup: BeautifulSoup) -> Optional[TenderDocumentChanges]:
    """
    Scrape the "Document Changes & Corrigendums" section from the tender detail page.
    Looks for tables or sections with titles like "Document Changes", "Corrigendums", etc.
    """
    try:
        items: List[TenderHistoryItem] = []
        
        # Look for section with document changes/corrigendums
        # Try multiple possible selectors
        possible_selectors = [
            {'class': 'document-changes'},
            {'class': 'corrigendums'},
            {'class': 'tender-history'},
            {'id': 'document-changes'},
            {'id': 'corrigendums'},
            {'id': 'tender-history'},
        ]
        
        changes_section = None
        for selector in possible_selectors:
            changes_section = soup.find('div', selector) or soup.find('section', selector) or soup.find('table', selector)
            if changes_section:
                break
        
        # Also try finding by text content - search more broadly
        # IMPORTANT: Exclude the main tender notice/details tables (first 5 tables)
        if not changes_section:
            # Get all tables, but skip the first 5 (they are: Notice, Details, Key Dates, Contact, Other)
            all_tables = soup.find_all('table')
            # Start from table index 5 onwards (6th table and beyond)
            for table in all_tables[5:]:
                table_text = table.text.lower()
                # Look for headings that specifically indicate corrigendum/changes section
                # Must have keywords AND not be one of the main tender info tables
                header_text = ""
                header_row = table.find('tr')
                if header_row:
                    header_text = header_row.text.lower()
                
                # Check if this is a corrigendum/changes table (not the main tender tables)
                is_corrigendum_table = (
                    any(keyword in header_text for keyword in ['corrigendum', 'amendment', 'change', 'modification', 'history']) or
                    any(keyword in table_text[:300] for keyword in ['document changes', 'corrigendum', 'amendment', 'tender history'])
                ) and not any(keyword in header_text for keyword in ['tender notice', 'tender details', 'key dates', 'contact information', 'other detail'])
                
                if is_corrigendum_table:
                    rows_in_table = table.find_all('tr')
                    if len(rows_in_table) > 1:  # Has data rows
                        changes_section = table
                        logger.debug(f"Found corrigendum section: table with {len(rows_in_table)} rows")
                        break
        
        # Also search divs/sections (but exclude tender-details-home children)
        if not changes_section:
            tender_details_home = soup.find('div', attrs={'class': 'tender-details-home'})
            if tender_details_home:
                # Look for sections AFTER the main tender details
                all_divs = soup.find_all(['div', 'section'])
                for div in all_divs:
                    # Skip if it's inside tender-details-home (those are the main tables)
                    if tender_details_home in div.parents if hasattr(div, 'parents') else False:
                        continue
                    
                    div_text = div.text.lower()
                    # Look for corrigendum-specific headings
                    if any(keyword in div_text[:200] for keyword in ['document changes', 'corrigendum', 'amendment', 'change history']):
                        # Check if it has actual content (not just a heading)
                        if len(div.find_all('tr')) > 1 or len(div.find_all('div', class_=lambda x: x and 'item' in str(x).lower())) > 0:
                            changes_section = div
                            break
        
        if not changes_section:
            logger.debug("Document changes section not found on page")
            return TenderDocumentChanges(items=[])
        
        # Parse the table/section to extract history items
        if changes_section.name == 'table':
            rows = changes_section.find_all('tr')[1:]  # Skip header row
        else:
            # For divs/sections, try multiple selectors
            rows = (changes_section.find_all('div', class_='history-item') or 
                   changes_section.find_all('div', class_='change-item') or
                   changes_section.find_all('div', class_='corrigendum-item') or
                   changes_section.find_all('tr') or
                   [changes_section])  # Fallback to the section itself
        
        for row in rows:
            try:
                cells = row.find_all(['td', 'div'])
                if len(cells) < 2:
                    continue
                
                # Try to extract information from cells
                # Common structure: Date | Type | Note | Files
                item_type = "corrigendum"  # Default
                note = ""
                update_date = ""
                files_changed: List[TenderDetailPageFile] = []
                date_change_from = None
                date_change_to = None
                
                # Skip header rows - check if first cell looks like a header
                first_cell_text = cells[0].text.strip().lower() if len(cells) > 0 else ""
                if first_cell_text in ['tdr', 'tender no', 'tendering authority', 'tender id', 'tender brief', 
                                       'city', 'state', 'document fees', 'emd', 'tender value', 'tender type',
                                       'bidding type', 'competition type', 'date', 'type', 'note', 'description',
                                       'action', 'timestamp', 'user']:
                    continue  # Skip header row
                
                # Extract date (usually first column)
                date_text = cells[0].text.strip() if len(cells) > 0 else ""
                # Validate it looks like a date (not a field name)
                if date_text and not any(keyword in date_text.lower() for keyword in ['tdr', 'tender', 'authority', 'city', 'state', 'emd', 'value']):
                    # Try to parse as date
                    try:
                        from dateutil import parser as date_parser
                        date_parser.parse(date_text)  # Validate it's a date
                        update_date = date_text
                    except:
                        pass  # Not a valid date, skip
                
                # Extract type (corrigendum, amendment, etc.)
                if len(cells) > 1:
                    type_text = cells[1].text.strip().lower()
                    if 'corrigendum' in type_text:
                        item_type = "corrigendum"
                    elif 'amendment' in type_text:
                        item_type = "amendment"
                    elif 'extension' in type_text or 'deadline' in type_text:
                        item_type = "bid_deadline_extension"
                    elif 'date' in type_text and 'extension' in type_text:
                        item_type = "due_date_extension"
                
                # Extract note/description (usually last column or second-to-last)
                if len(cells) > 2:
                    note = cells[2].text.strip()
                elif len(cells) > 1:
                    note = cells[1].text.strip()
                
                # Validate note doesn't look like a field name
                if note and any(keyword in note.lower() for keyword in ['tdr', 'tender no', 'tendering authority', 'city', 'state']):
                    note = ""  # Probably a field name, not a note
                
                # Look for date changes in the note
                if 'from' in note.lower() and 'to' in note.lower():
                    # Try to extract date change
                    import re
                    date_pattern = r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})'
                    dates = re.findall(date_pattern, note)
                    if len(dates) >= 2:
                        date_change_from = dates[0]
                        date_change_to = dates[1]
                
                # Extract file links if present
                links = row.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    if href and ('download' in href.lower() or '.pdf' in href.lower() or '.doc' in href.lower()):
                        files_changed.append(TenderDetailPageFile(
                            file_name=link.text.strip() or href.split('/')[-1],
                            file_url=str(href),
                            file_description="Document",
                            file_size="Unknown"
                        ))
                
                if update_date or note:
                    items.append(TenderHistoryItem(
                        id=None,
                        type=item_type,
                        note=note or "No description available",
                        update_date=update_date or "N/A",
                        files_changed=files_changed,
                        date_change_from=date_change_from,
                        date_change_to=date_change_to
                    ))
            except Exception as e:
                logger.debug(f"Error parsing history row: {e}")
                continue
        
        return TenderDocumentChanges(items=items)
    except Exception as e:
        logger.warning(f"Error scraping document changes: {e}")
        return TenderDocumentChanges(items=[])

def scrape_actions_history(soup: BeautifulSoup) -> Optional[TenderActionsHistory]:
    """
    Scrape the "Actions History" section from the tender detail page.
    Looks for tables or sections showing user actions on the tender.
    """
    try:
        items: List[TenderActionHistoryItem] = []
        
        # Look for actions history section
        possible_selectors = [
            {'class': 'actions-history'},
            {'class': 'action-history'},
            {'class': 'tender-actions'},
            {'id': 'actions-history'},
            {'id': 'action-history'},
        ]
        
        actions_section = None
        for selector in possible_selectors:
            actions_section = soup.find('div', selector) or soup.find('section', selector) or soup.find('table', selector)
            if actions_section:
                break
        
        # Also try finding by text content
        if not actions_section:
            all_tables = soup.find_all('table')
            for table in all_tables:
                table_text = table.text.lower()
                if any(keyword in table_text for keyword in ['actions history', 'action history', 'activity log', 'user actions']):
                    header_row = table.find('tr')
                    if header_row and any(keyword in header_row.text.lower() for keyword in ['action', 'timestamp', 'date', 'user', 'time']):
                        actions_section = table
                        break
        
        if not actions_section:
            return TenderActionsHistory(items=[])
        
        # Parse the table/section to extract action items
        rows = actions_section.find_all('tr')[1:] if actions_section.name == 'table' else actions_section.find_all('div', class_='action-item')
        
        for row in rows:
            try:
                cells = row.find_all(['td', 'div'])
                if len(cells) < 1:
                    continue
                
                # Common structure: Action | Timestamp | User | Notes
                action = ""
                timestamp = ""
                user = None
                notes = None
                
                # Extract action (usually first column)
                if len(cells) > 0:
                    action = cells[0].text.strip()
                
                # Extract timestamp
                if len(cells) > 1:
                    timestamp = cells[1].text.strip()
                
                # Extract user
                if len(cells) > 2:
                    user = cells[2].text.strip() or None
                
                # Extract notes
                if len(cells) > 3:
                    notes = cells[3].text.strip() or None
                
                if action or timestamp:
                    items.append(TenderActionHistoryItem(
                        action=action or "Unknown action",
                        timestamp=timestamp or "N/A",
                        user=user,
                        notes=notes
                    ))
            except Exception as e:
                logger.debug(f"Error parsing action row: {e}")
                continue
        
        return TenderActionsHistory(items=items)
    except Exception as e:
        logger.warning(f"Error scraping actions history: {e}")
        return TenderActionsHistory(items=[])

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

        # Scrape document changes and actions history sections
        document_changes = scrape_document_changes(soup)
        actions_history = scrape_actions_history(soup)
        
        return TenderDetailPage(
            notice=scrape_notice_table(tables['notice']),
            details=scrape_details(tables['details']),
            key_dates=scrape_key_dates(tables['dates']),
            contact_information=scrape_contact_information(tables['contact']),
            other_detail=scrape_other_details(tables['other']),
            document_changes=document_changes,
            actions_history=actions_history
        )

    except Exception as e:
        logger.error(f"Error scraping {tender_link}: {str(e)}")
        return None