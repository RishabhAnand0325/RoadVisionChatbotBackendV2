from typing import List, Tuple
from bs4 import BeautifulSoup
import requests
import re # Added for robust regex matching

from app.core.helpers import remove_starting_numbers
from app.modules.scraper.helpers import clean_text
from .data_models import HomePageData, HomePageHeader, Tender, TenderQuery

def scrape_page(url) -> HomePageData:
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')

    # --- 1. ROBUST HEADER PARSING ---
    # Find date anywhere, don't crash if specific class implies strict position
    date_elem = soup.find('p', attrs={'class': 'm-r-date'})
    date = clean_text(date_elem.text) if date_elem else "Unknown Date"
    
    contact = "For customer support: (+91) 8115366981"
    name = "Shubham Kanojia"
    company = "RoadVision AI Pvt. Ltd."

    # Robust extract of new tender count
    main_count_elem = soup.find('p', attrs={'class': 'm-main-count'})
    if main_count_elem:
        main_count_text = clean_text(main_count_elem.text)
        # Extract first number found in string using regex, safer than split(' ')[0]
        match = re.search(r'\d+', main_count_text)
        no_of_new_tenders = match.group() if match else "0"
    else:
        no_of_new_tenders = "0"

    header = HomePageHeader(
        date=date,
        name=name,
        contact=contact,
        no_of_new_tenders=no_of_new_tenders,
        company=company
    )

    # --- 2. ROBUST BODY PARSING (The Fix) ---
    container = soup.find('div', attrs={'class': 'container-fluid'})
    if not container:
        # If no container, return empty data rather than crashing
        print(f"Warning: No container found for {url}")
        return HomePageData(header=header, query_table=[])

    # Instead of looking for specific rows (row[3], row[5]), we look for 
    # specific CONTENT patterns inside the entire container.
    
    query_table: List[TenderQuery] = []
    
    # We assume the page structure involves sections comprising:
    # 1. A Header div (containing the Query Name)
    # 2. A Content div (containing the Tenders)
    # We iterate through all 'col-md-12' divs as they contain both headers and tables.
    all_cols = container.find_all('div', attrs={'class': 'col-md-12'})

    current_query_name = "Uncategorized"
    current_tender_count = "0"

    for col in all_cols:
        # Check if this column is a Tender List (Has 'm-mainTR' inside)
        tender_rows = col.find_all('div', attrs={'class': 'm-mainTR'})
        
        if tender_rows:
            # === PROCESSING TENDERS ===
            # This column contains tenders. They belong to the 'current_query_name' found previously.
            
            # 1. Apply Filter: Only process if "Civil" (or "Civil Work") is in the category name
            # Matching your script's logic more closely
            if "Civil" not in current_query_name:
                continue

            tender_query_list: List[Tender] = []
            
            for mainTR in tender_rows:
                try:
                    # Title
                    title_elem = mainTR.find('p', attrs={'class': 'm-r-td-title'})
                    title = remove_starting_numbers(title_elem.text.strip()) if title_elem else "Unknown Title"

                    # State / City
                    state_elem = mainTR.find('p', attrs={'class': 'm-td-state'})
                    state = state_elem.text.strip() if state_elem else "Unknown"

                    # Brief Elements (ID, Value, Date)
                    m_td_brief_elements = mainTR.find_all('p', attrs={'class': 'm-td-brief'})
                    
                    summary_text = ""
                    tender_id = ""
                    tender_value = ""
                    due_date = ""

                    if len(m_td_brief_elements) >= 3:
                        # 1. Summary & ID
                        summary_elem = m_td_brief_elements[0]
                        summary_text = summary_elem.text
                        tender_id_elem = summary_elem.find('strong')
                        if tender_id_elem:
                            # Robust split
                            parts = tender_id_elem.text.split(':')
                            tender_id = parts[1].strip() if len(parts) > 1 else parts[0]
                        
                        # 2. Value
                        val_text = m_td_brief_elements[1].text
                        val_parts = val_text.split(':')
                        tender_value = val_parts[1].strip() if len(val_parts) > 1 else val_text

                        # 3. Date
                        date_text = m_td_brief_elements[2].text
                        date_parts = date_text.split(':')
                        due_date = date_parts[1].strip() if len(date_parts) > 1 else date_text

                    # Link
                    link_elem = mainTR.find('a')
                    link = link_elem['href'] if link_elem else ""
                    full_link = "https://www.tenderdetail.com" + str(link) if link else ""

                    tender_obj = Tender(
                        tender_id=tender_id,
                        tender_name=title,
                        tender_url=full_link,
                        drive_url=None,
                        city=state,
                        summary=summary_text,
                        value=tender_value,
                        due_date=due_date,
                        details=None
                    )
                    tender_query_list.append(tender_obj)
                except Exception as e:
                    print(f"Error parsing single tender row: {e}")
                    continue

            # Add to result if we found tenders
            if tender_query_list:
                query_table.append(TenderQuery(
                    query_name=current_query_name,
                    number_of_tenders=str(len(tender_query_list)), # Recalculate actual count found
                    tenders=tender_query_list
                ))

        else:
            # === PROCESSING HEADERS ===
            # If it doesn't have tender rows, it might be a header div.
            # Headers usually look like "Query Name (50)" or just "Query Name"
            text = col.get_text(strip=True)
            if text:
                # Store this as the category for the NEXT iteration
                current_query_name = text
                
                # Optional: Extract count from header string "(123)" if needed, 
                # but relying on actual scraped count (above) is safer.

    return HomePageData(header=header, query_table=query_table)
