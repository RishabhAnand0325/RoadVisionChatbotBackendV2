from typing import List, Tuple
from bs4 import BeautifulSoup

import requests

from .data_models import HomePageData, HomePageHeader, Tender, TenderQuery

def scrape_page(url) -> HomePageData:
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')

    # There are two p-mr-date classes in the page. The first one contains the date, second one contains contact info
    date_elem = soup.find('p', attrs={'class': 'm-r-date'})
    if not date_elem:
        raise Exception("Date not found")
    date = date_elem.text
    contact = "For customer support: (+91) 8115366981"
    name = "Shubham Kanojia"
    company = "RoadVision AI Pvt. Ltd."

    # For finding the number of new tenders, we need to find the m-main-count element.
    # This element will contain a string like "{{integer}} New Tenders Related to Your Business
    # We need to extract the integer from this string.
    main_count_elem = soup.find('p', attrs={'class': 'm-main-count'})
    if not main_count_elem:
        raise Exception("Main count not found")
    main_count = main_count_elem.text
    no_of_new_tenders = main_count.split(' ')[0]

    header = HomePageHeader(
            date=date,
            name=name,
            contact=contact,
            no_of_new_tenders=no_of_new_tenders,
            company=company
        )

    # The body contains a div of class container-fluid
    container = soup.find('div', attrs={'class': 'container-fluid'})
    if not container:
        raise Exception("Container not found")

    # There are 5 row elements (direct children) in the page.
    row_elements = container.find_all('div', attrs={'class': 'row'}, recursive=False)
    if not len(row_elements) == 5:
        raise Exception("Row elements not found")

    # The 4th one contains a table with query names and number of tenders.
    query_names_and_tenders_table = row_elements[3]
    # Get the table body
    query_names_and_tenders_table_body = query_names_and_tenders_table.find('tbody')
    if not query_names_and_tenders_table_body:
        raise Exception("Table body not found")
    # There will be a variable numnber of tr elements in this table.
    table_body_rows = query_names_and_tenders_table_body.find_all('tr', recursive=False)
    queries_and_numbers: List[Tuple[str, str]] = []
    for row in table_body_rows:
        # Each tr element contains 3 td elements.
        # The first one is query name.
        # The second one is number of tenders.
        # Ignore the third one
        td_elements = row.find_all('td')
        query_name = td_elements[0].text
        no_of_tenders = td_elements[1].text
        queries_and_numbers.append((query_name, no_of_tenders))
        print(row)

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

    tenders_list_list: List[List[Tender]] = []

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
            title = title_elem.text

            state_elem = mainTR.find('p', attrs={'class': 'm-td-state'})
            if not state_elem:
                raise Exception("Date not found")
            state = state_elem.text

            m_td_brief_elements = mainTR.find_all('p', attrs={'class': 'm-td-brief'})
            if not len(m_td_brief_elements) == 3:
                raise Exception("m-td-brief elements not found")

            summary_elem = m_td_brief_elements[0]
            tender_id_elem = summary_elem.find('strong')
            if not tender_id_elem:
                raise Exception("Tender ID not found")
            tender_id = tender_id_elem.text.split(':')[1]

            tender_value = m_td_brief_elements[1].text.split(':')[1]
            due_date = m_td_brief_elements[2].text.split(':')[1]

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
        query_table.append(TenderQuery(
            query_name=query_name,
            number_of_tenders=no_of_tenders,
            tenders=tenders_list
        ))


    return HomePageData(header=header, query_table=query_table)

