from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from dateutil import parser

import os
import mimetypes
import requests

from .data_models import HomePageData
from .detail_page_scrape import scrape_tender

# Google drive setup
SCOPES = ['https://www.googleapis.com/auth/drive']
creds = None

def parse_date(date_string: str) -> str:
    """
    Parses a date string in a flexible format and converts it to 'YYYY-MM-DD'.

    Args:
        date_string: The date string to parse (e.g., "Sunday, Oct 12,2025").

    Returns:
        The formatted date string 'YYYY-MM-DD', or None if parsing fails.
    """
    if not date_string:
        return "unknown-date"

    try:
        # 1. Let dateutil parse the string into a datetime object.
        # It handles missing spaces and other variations automatically.
        date_object = parser.parse(date_string)

        # 2. Format the object into the desired "YYYY-MM-DD" string.
        formatted_string = date_object.strftime("%Y-%m-%d")
        return formatted_string

    except parser.ParserError:
        print(f"⚠️  Warning: Could not parse the date string '{date_string}'.")
        return "unknown-date"

def find_folder(service, folder_name, parent_folder_id=None):
    """Finds a folder by name and optional parent ID."""
    try:
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"

        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        existing_folders = response.get('files', [])

        if existing_folders:
            return existing_folders[0]
        return None
    except HttpError as error:
        print(f"An error occurred finding a folder: {error}")
        return None

def is_folder_empty(service, folder_id):
    """Checks if a Google Drive folder is empty."""
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        response = service.files().list(q=query, spaces='drive', fields='files(id)', pageSize=1).execute()
        items = response.get('files', [])
        return len(items) == 0
    except HttpError as error:
        print(f"An error occurred checking if folder is empty: {error}")
        return False # Assume not empty on error

def download_folders(data: HomePageData):
    date = parse_date(data.header.date)
    os.system("rm -rf tenders/" + date)
    os.system("mkdir -p tenders/" + date)

    service = authenticate_google_drive()
    if not service:
        return

    # Check if the date folder exists
    date_folder = find_folder(service, date)
    if date_folder:
        date_folder_id = date_folder.get('id')
        if not is_folder_empty(service, date_folder_id):
            print(f"Folder '{date}' already exists and is not empty.")
        else:
            print(f"Folder '{date}' already exists and is empty.")
    else:
        # Upload the "date" folder to Google Drive and get the folder id
        date_folder_id = upload_folder_to_drive(service, "tenders/" + date)

    for query_table in data.query_table:
        for tender in query_table.tenders:
            try:
                tender_folder = find_folder(service, tender.tender_id, date_folder_id)
                if tender_folder:
                    tender_folder_id = tender_folder.get('id')
                    if not is_folder_empty(service, tender_folder_id):
                        print(f"Folder '{tender.tender_id}' already exists and is not empty. Skipping download.")
                        tender.drive_url = get_shareable_link(service, tender_folder_id)
                        continue

                if not tender.details:
                    tender.details = scrape_tender(tender.tender_url)
                    raise Exception("Tender details not found")
                # Create a folder for each tender
                folder_path = "tenders/" + date + "/" + tender.tender_id
                os.system("mkdir -p " + folder_path)
                for file in tender.details.other_detail.files:
                    file_path = folder_path + "/" + file.file_name
                    if not os.path.exists(file_path):
                        # Download the file
                        print("Downloading file " + file.file_name + " to " + file_path)
                        with open(file_path, 'wb') as f:
                            f.write(requests.get(file.file_url).content)

                # Upload the tender folder to Google Drive and get the folder id
                tender_folder_id = upload_folder_to_drive(service, folder_path, date_folder_id)
                # Get the shareable link for the tender folder
                tender.drive_url = get_shareable_link(service, tender_folder_id)
            except Exception as e:
                print("Error: " + str(e))
                query_table.tenders.remove(tender)

def authenticate_google_drive():
    """Authenticates with the Google Drive API and returns a service object."""
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    # It's created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # This will open a browser window for you to log in and authorize the app.
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    try:
        service = build('drive', 'v3', credentials=creds)
        print("✅ Google Drive API Authentication Successful!")
        return service
    except HttpError as error:
        print(f"An error occurred during authentication: {error}")
        return None

def upload_folder_to_drive(service, local_folder_path, parent_folder_id=None) -> Optional[str]:
    """Uploads a local folder and its contents to Google Drive.
    Checks if the folder already exists before uploading."""
    folder_name = os.path.basename(local_folder_path)

    try:
        # Check if folder already exists
        existing_folder = find_folder(service, folder_name, parent_folder_id)
        if existing_folder:
            folder_id = existing_folder.get('id')
            print(f"\nFolder '{folder_name}' already exists with ID: {folder_id}. Skipping upload.")
            return folder_id

        print(f"\nUploading folder '{folder_name}' to Google Drive...")

        # 1. Create the folder on Google Drive
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        gdrive_folder = service.files().create(body=file_metadata, fields='id').execute()
        gdrive_folder_id = gdrive_folder.get('id')
        print(f"  - Created Google Drive folder with ID: {gdrive_folder_id}")

        # 2. Upload files into the created folder
        for item in os.listdir(local_folder_path):
            item_path = os.path.join(local_folder_path, item)
            if os.path.isfile(item_path):
                # Guess the MIME type of the file
                mimetype, _ = mimetypes.guess_type(item_path)
                file_metadata = {
                    'name': item,
                    'parents': [gdrive_folder_id]
                }
                media = MediaFileUpload(item_path, mimetype=mimetype)
                service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                print(f"    - Uploaded file: {item}")
        
        return gdrive_folder_id
    except HttpError as error:
        print(f"An error occurred uploading the folder: {error}")
        return None

def get_shareable_link(service, folder_id):
    """Makes a folder public and returns its shareable link."""
    try:
        # Create a permission for anyone with the link to view
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        service.permissions().create(fileId=folder_id, body=permission).execute()
        
        # Get the webViewLink from the file's metadata
        result = service.files().get(fileId=folder_id, fields='webViewLink').execute()
        link = result.get('webViewLink')
        print(f"  - Generated shareable link: {link}")
        return link
    except HttpError as error:
        print(f"An error occurred while getting the shareable link: {error}")
        return None

