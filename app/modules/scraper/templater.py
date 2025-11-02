from bs4 import BeautifulSoup
import copy
import premailer

from .data_models import HomePageData

p = premailer.Premailer(
        allow_loading_external_files=True
    )

def apply_multi_column_table_layout(soup, container_element, align_last_right=False):
    """
    Takes a container element and rearranges its direct children into a table
    with evenly spaced columns. This is the email-safe way to create a
    multi-item, evenly-spaced layout.

    Args:
        soup (BeautifulSoup): The main soup object.
        container_element (Tag): The parent element whose children will be arranged.
        align_last_right (bool): If True, aligns the last item to the right, mimicking
                                space-between for 2+ items.
    """
    # Find all direct children to be arranged. 'recursive=False' is key here.
    children = container_element.find_all(recursive=False)
    
    # If there's nothing to do, just exit.
    if not children:
        return

    num_children = len(children)
    # Calculate the percentage width for each column.
    col_width = int(100 / num_children)

    # --- Create the new table structure ---
    table = soup.new_tag('table', width="100%", border="0", cellpadding="0", cellspacing="0")
    tr = soup.new_tag('tr')
    table.append(tr)

    print(f"Applying {num_children}-column table layout...")

    # --- Loop through each child and create a cell for it ---
    for i, child in enumerate(children):
        # Base style for all cells
        style = f"width: {col_width}%; vertical-align: top;"

        # Add specific text alignment
        if align_last_right and num_children > 1:
            if i == 0:
                style += " text-align: left;"  # First item
            elif i == num_children - 1:
                style += " text-align: right;" # Last item
            else:
                style += " text-align: center;" # Middle items
        else:
            style += " text-align: left;" # Default alignment for all

        # Create the table cell (td) with the calculated style
        td = soup.new_tag('td', style=style)
        
        # .extract() removes the child from its original location
        td.append(child.extract())
        
        # Add the new cell to our table row
        tr.append(td)

    # --- Finalize the container ---
    # Clear out any old inline styles (like display:flex)
    container_element.attrs.pop('style', None)
    
    # Add the newly created table into the now-empty container
    container_element.append(table)


def reformat_page(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Refactors an entire HTML page (as a BeautifulSoup object) to use email-safe
    table layouts instead of CSS Flexbox.
    """
    print("🚀 Starting HTML reformatting for email compatibility...")

    # --- Section 1: Image Header ---
    img_element = soup.find('img')
    if img_element:
        # Set email-safe image styles
        img_element.attrs['style'] = "width:100px; height:auto; display:block;"
        # The container is two levels above the image
        img_parent_container = img_element.parent.parent
        if img_parent_container:
            print("Applying table layout to image header...")
            apply_multi_column_table_layout(soup, img_parent_container, align_last_right=True)

    # --- Section 2: Owner Name ---
    owner = soup.find('p', attrs={'class': 'm-owner-name'})
    if owner:
        # The container is two levels above the owner p tag
        owner_parent_container = owner.parent.parent
        if owner_parent_container:
            print("Applying table layout to owner section...")
            apply_multi_column_table_layout(soup, owner_parent_container, align_last_right=True)

    # --- Section 3: Main Transaction Rows ---
    mainTR_list = soup.find_all('div', attrs={'class': 'm-mainTR'})
    for mainTR in mainTR_list:
        rows = mainTR.find_all('div', attrs={'class': 'row'})
        
        # Handle the specific case for company and place in the first row
        if len(rows) >= 1:
            row1 = rows[0]
            company = row1.find('div', attrs={'class': 'col-md-8'})
            place = row1.find('div', attrs={'class': 'col-md-4'})

            if company and place:
                print("Applying specific 2-column table to company/place row...")
                # This logic is already a perfect 2-column table, so we keep it.
                table = soup.new_tag('table', width="100%", border="0", cellpadding="0", cellspacing="0", role="presentation")
                tr = soup.new_tag('tr')
                table.append(tr)
                td_left = soup.new_tag('td', style="width: 50%; text-align: left; vertical-align: top;")
                td_left.append(company.extract())
                tr.append(td_left)
                td_right = soup.new_tag('td', style="width: 50%; text-align: right; vertical-align: top;")
                td_right.append(place.extract())
                tr.append(td_right)
                row1.insert(0, table)

        # Handle any other rows that need a general multi-column layout
        if len(rows) >= 2:
            row2 = rows[1]
            print("Applying table layout to the second row...")
            apply_multi_column_table_layout(soup, row2, align_last_right=True)
            
    print("✅ HTML reformatting complete.")
    return soup


def generate_email(data: HomePageData) -> BeautifulSoup:
    """
    Generates an email HTML string from a HomePageData object.
    """
    # Import the exsiting HTML template
    with open('./template.html', 'r') as f:
        template_html = f.read()

    # Create a new BeautifulSoup object from the template HTML
    soup = BeautifulSoup(template_html, 'html.parser')

    # Get the elements
    ## Header section
    date_elem = soup.find('td', attrs={'id': 'date'})
    if not date_elem:
        raise Exception("Date element not found")
    contact_elem = soup.find('td', attrs={'id': 'contact'})
    if not contact_elem:
        raise Exception("Contact element not found")
    name_elem = soup.find('h4', attrs={'id': 'name'})
    if not name_elem:
        raise Exception("Name element not found")
    company_elem = soup.find('td', attrs={'id': 'company'})
    if not company_elem:
        raise Exception("Company element not found")
    no_of_new_tenders_elem = soup.find('span', attrs={'id': 'no_of_new_tenders'})
    if not no_of_new_tenders_elem:
        raise Exception("No of new tenders element not found")

    # Set the values
    date_elem.string = data.header.date
    contact_elem.string = data.header.contact
    name_elem.string = data.header.name
    company_elem.string = data.header.company
    no_of_new_tenders_elem.string = data.header.no_of_new_tenders

    # The queries table
    queries_table_elem = soup.find('table', attrs={'id': 'queries'})
    if not queries_table_elem:
        raise Exception("Queries table not found")
    queries_table_body = queries_table_elem.find('tbody')
    if not queries_table_body:
        raise Exception("Queries table body not found")

    # Inside queries_table_body, there will be a class query_tender_row.
    # Grab the element, save it in memory for appending, decompose the original one
    query_tender_row_elem = queries_table_body.find('tr', attrs={'class': 'query_tender_row'})
    if not query_tender_row_elem:
        raise Exception("Query tender row not found")
    # query_tender_row_elem.decompose()
    # Now we can append the new tender rows to the table body
    for tender in data.query_table:
        new_query_tender_row = copy.copy(query_tender_row_elem)
        # Classes available in new_query_tender_row:
        #   query_tender_row_query
        #   query_tender_row_no_of_tenders_found
        query_tender_row_query = new_query_tender_row.find('td', attrs={'class': 'query_tender_row_query'})
        if query_tender_row_query:
            query_tender_row_query.string = tender.query_name
        query_tender_row_no_of_tenders_found = new_query_tender_row.find('td', attrs={'class': 'query_tender_row_no_of_tenders_found'})
        if query_tender_row_no_of_tenders_found:
            query_tender_row_no_of_tenders_found.string = tender.number_of_tenders
        queries_table_body.append(new_query_tender_row)
    query_tender_row_elem.decompose()

    # The tenders div
    tenders_div_elem = soup.find('div', attrs={'id': 'tenders'})
    if not tenders_div_elem:
        raise Exception("Tenders div not found")

    # Inside tenders_div_elem, there will be a table
    # Grab the element, save it in memory for appending, decompose the original one
    tenders_table_elem = tenders_div_elem.find('table')
    if not tenders_table_elem:
        raise Exception("Tenders table not found")

    for query in data.query_table:
        new_query_table = copy.copy(tenders_table_elem)
        # Classes available in new_tender_table:
        #   tender_query_table_tender_name
        #   tender_table
        tender_query_table_tender_name = new_query_table.find('td', attrs={'class': 'tender_query_table_tender_name'})
        if not tender_query_table_tender_name:
            raise Exception("Tender query table tender name not found")
        tender_query_table_tender_name.string = query.query_name

        tender_query_table_body = new_query_table.find('tbody')
        if not tender_query_table_body:
            raise Exception("Tender query table body not found")
        tender_table = tender_query_table_body.find('tr')
        if not tender_table:
            raise Exception("Tender table not found")
        for tender_data in query.tenders:
            new_tender_table = copy.copy(tender_table)
            if not new_tender_table:
                raise Exception("New tender table not found")
            # Classes available in new_tender_table:
            #   tender_table_tender_name_and_number
            #   tender_table_tender_city
            #   tender_table_tender_summary
            #   tender_table_tender_value
            #   tender_table_tender_due_date
            #   tender_table_view_tender_link
            tender_table_tender_name_and_number = new_tender_table.find('td', attrs={'class': 'tender_table_tender_name_and_number'})
            if not tender_table_tender_name_and_number:
                raise Exception("Tender table tender name and number not found")
            tender_table_tender_name_and_number.string = tender_data.tender_name
            tender_table_tender_city = new_tender_table.find('td', attrs={'class': 'tender_table_tender_city'})
            if not tender_table_tender_city:
                raise Exception("Tender table tender city not found")
            tender_table_tender_city.string = tender_data.city
            tender_table_tender_summary = new_tender_table.find('td', attrs={'class': 'tender_table_tender_summary'})
            if not tender_table_tender_summary:
                raise Exception("Tender table tender summary not found")
            tender_table_tender_summary.string = tender_data.summary
            tender_table_tender_value = new_tender_table.find('span', attrs={'class': 'tender_table_tender_value'})
            if not tender_table_tender_value:
                raise Exception("Tender table tender value not found")
            tender_table_tender_value.string = tender_data.value
            tender_table_tender_due_date = new_tender_table.find('span', attrs={'class': 'tender_table_tender_due_date'})
            if not tender_table_tender_due_date:
                raise Exception("Tender table tender due date not found")
            tender_table_tender_due_date.string = tender_data.due_date
            tender_table_view_tender_link = new_tender_table.find('a', attrs={'class': 'tender_table_view_tender_link'})
            if not tender_table_view_tender_link:
                raise Exception("Tender table view tender link not found")
            tender_table_view_tender_link['href'] = tender_data.tender_url
            tender_table_redirect_to_website = new_tender_table.find('a', attrs={'class': 'tender_table_redirect_to_website'})
            if not tender_table_redirect_to_website:
                raise Exception("Tender table redirect to website not found")
            # TODO: Update this link to point to the DMSIQ frontend when available
            tender_table_redirect_to_website['href'] = tender_data.tender_url

            tender_query_table_body.append(new_tender_table)

        tender_table.decompose()

        tenders_div_elem.append(new_query_table)

    tenders_table_elem.decompose()

    transformed = p.transform(soup.prettify())

    return BeautifulSoup(transformed, 'html.parser')
