from typing import List, Optional, Tuple
from bs4 import BeautifulSoup

import requests
from selenium.webdriver.chrome.webdriver import WebDriver

from app.core.helpers import remove_starting_numbers
from app.modules.scraper.helpers import clean_text

from .data_models import HomePageData, HomePageHeader, Tender, TenderQuery

def scrape_page(url, driver: WebDriver) -> Optional[HomePageData]:
    driver.get(url)
    
    # page = requests.get(url)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Get the date
    date_elem = soup.select("body > table:nth-child(1) > tbody > tr > td > table > tbody > tr:nth-child(1) > td > table > tbody > tr > td:nth-child(2) > span:nth-child(2) > span")[0]
    if not date_elem:
        raise Exception("Date not found")
    date = clean_text(date_elem.text)
    contact = "For customer support: (+91) 8115366981"
    name = "Shubham Kanojia"
    company = "RoadVision AI Pvt. Ltd."

    # Get the tender count
    main_count_elem = soup.select("body > table:nth-child(1) > tbody > tr > td > table > tbody > tr:nth-child(3) > td > table > tbody > tr > td:nth-child(2) > strong > span")[0]
    if not main_count_elem:
        raise Exception("Main count not found")
    main_count = clean_text(main_count_elem.text)
    no_of_new_tenders = main_count.split(' ')[0]

    header = HomePageHeader(
        date=date,
        name=name,
        contact=contact,
        no_of_new_tenders=no_of_new_tenders,
        company=company
    )

    # From the query table, get the query name and number of tenders found
    query_table_rows = soup.select("body > table:nth-child(1) > tbody > tr > td > table > tbody > tr:nth-child(5) > td > table > tbody > tr")
    # Remove the first row, which is the header row
    row_elements = query_table_rows[1:]
    if not len(row_elements) > 0:
        raise Exception("Row elements not found")
    # Now each row element has three td's
    # The first td is the query name
    # The second td is the number of tenders
    queries_and_numbers: List[Tuple[str, int]] = []
    for row in row_elements:
        row_tds = row.select("td")
        query_name = clean_text(row_tds[0].text)
        no_of_tenders = int(clean_text(row_tds[1].text))
        queries_and_numbers.append((query_name, no_of_tenders))

    # This next table contains a list of tr's
    # A tr can be of mainTR class or autority-list/authority-list class
    # Each autority-list item marks the start of a query
    tenders_list_list: List[List[Tender]] = []
    main_table = soup.select("body > table:nth-child(2) > tbody > tr > td > table > tbody > tr:nth-child(2) > td > table")
    if not len(main_table) == 1:
        raise Exception("Main table not found")
    main_table_rows = main_table[0].find_all('tr')
    # Remove the first row, which is the header row
    maintr_count = 0
    curr_query: List[Tender] = []
    for row in main_table_rows:
        if row.has_attr('class') and row['class'][0] == 'autority-list':
            maintr_count = 0
            curr_query = []
        elif row.has_attr('class') and row['class'][0] == 'mainTR':
            continue


    # The last one is the list of queries, and their 
    # children tables are tender datas.
    # The last row will have a list of col-md-12 elements.
    col_md_12_elements = row_elements[-1].find_all('div', attrs={'class': 'col-md-12'}, recursive=False)
    if not len(col_md_12_elements) % 2 == 0:
        raise Exception("Col-md-12 elements not found")
    # Every odd numbered col-md-12 element is a query name of the format "{{name}} ({{number of tenders}})"
    # Every even numbered col-md-12 element is a table of tenders.
    # Remove every odd numbered col-md-12 element.
    col_md_12_elements = col_md_12_elements[1::2]

    # Now queries_and_numbers and col_md_12_elements should have the same number of elements corresponding to the same query.
    if not len(queries_and_numbers) == len(col_md_12_elements):
        raise Exception("Queries and col-md-12 elements do not correspond")


    for column in col_md_12_elements:
        tender_query_list: List[Tender] = []
        # each column will contain a m-mainTR element.
        mainTR_elements = column.find_all('div', attrs={'class': 'm-mainTR'}, recursive=False)
        for mainTR in mainTR_elements:
            # each m-mainTR element will contain the following:
            # 1. m-r-td-title
            # 2. m-td-state
            # 3. 3 m-td-brief elements
            #   1. Summary of tender. We need to extract this with the html
            #   2. Tender value. We need to remove the <strong> element from here
            #   3. Due date. We need to remove the <strong> element from here
            # 4. m-td-brief-link
            #   contains an <a> element with the tender link
            title_elem = mainTR.find('p', attrs={'class': 'm-r-td-title'})
            if not title_elem:
                raise Exception("Title not found")
            title = title_elem.text.strip()
            title = remove_starting_numbers(title)

            state_elem = mainTR.find('p', attrs={'class': 'm-td-state'})
            if not state_elem:
                raise Exception("State not found")
            state = state_elem.text.strip()

            m_td_brief_elements = mainTR.find_all('p', attrs={'class': 'm-td-brief'})
            if not len(m_td_brief_elements) == 3:
                raise Exception("m-td-brief elements not found")

            summary_elem = m_td_brief_elements[0]
            tender_id_elem = summary_elem.find('strong')
            if not tender_id_elem:
                raise Exception("Tender ID not found")
            tender_id = tender_id_elem.text.split(':')[1].strip()

            tender_value = m_td_brief_elements[1].text.split(':')[1].strip()
            due_date = m_td_brief_elements[2].text.split(':')[1].strip()

            link_elem = mainTR.find('a')
            if not link_elem:
                raise Exception("Link not found")
            link = link_elem['href']

            tender_query_list.append(Tender(
                tender_id=tender_id,
                tender_name=title,
                tender_url= "https://www.tenderdetail.com" + str(link),
                drive_url=None,
                city=state,
                summary=summary_elem.text,
                value=tender_value,
                due_date=due_date,
                details=None
            ))

        tenders_list_list.append(tender_query_list)

    query_table: List[TenderQuery] = []
    for (query_name, no_of_tenders), tenders_list in zip(queries_and_numbers, tenders_list_list):
        # For now, add only categories that have "Civil" in their name
        if "Civil" not in query_name:
            continue
        query_table.append(TenderQuery(
            query_name=query_name,
            number_of_tenders=no_of_tenders,
            tenders=tenders_list
        ))


    return HomePageData(header=header, query_table=query_table)

