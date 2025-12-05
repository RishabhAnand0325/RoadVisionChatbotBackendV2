from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from dateutil import parser
import io
import os
import re
import tempfile
import uuid
from typing import List
import re
import tempfile
import uuid
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session

from app.config import settings
from app.core.global_stores import upload_jobs
from app.modules.askai.models.document import ProcessingJob, ProcessingStage, ProcessingStatus, UploadJob, DriveFile, DriveFolder
from app.modules.askai.db.repository import ChatRepository
from app.modules.askai.services.document_processing_service import process_uploaded_pdf


# Google drive setup
SCOPES = ['https://www.googleapis.com/auth/drive']
creds = None

def authenticate_google_drive():
    """Authenticates with the Google Drive API and returns a service object."""
    creds = None
    token_path = os.path.join(settings.ROOT_DIR, 'token.json')
    creds_path = os.path.join(settings.ROOT_DIR, 'credentials.json')
    
    # The file token.json stores the user's access and refresh tokens.
    # It's created automatically when the authorization flow completes for the first time.
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                print(f"❌ 'credentials.json' not found in root directory: {settings.ROOT_DIR}")
                return None
            # This will open a browser window for you to log in and authorize the app.
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            
    try:
        service = build('drive', 'v3', credentials=creds)
        print("✅ Google Drive API Authentication Successful!")
        return service
    except HttpError as error:
        print(f"An error occurred during authentication: {error}")
        return None

def _scan_folder_recursively(service, folder_id: str) -> DriveFolder:
    """Helper to recursively scan a Google Drive folder."""
    try:
        # List files and folders in the current folder
        query = f"'{folder_id}' in parents and trashed=false"
        # Request all fields needed for DriveFile model
        fields = "files(id, name, mimeType, size)"
        results = service.files().list(q=query, fields=fields).execute()
        items = results.get('files', [])

        files: List[DriveFile] = []
        subfolders: List[DriveFolder] = []
        for item in items:
            if item.get('mimeType') == 'application/vnd.google-apps.folder':
                subfolders.append(_scan_folder_recursively(service, item['id']))
            else:
                # The 'size' field might be missing for certain Google Docs formats
                if 'size' not in item:
                    item['size'] = "0"
                files.append(DriveFile.model_validate(item))

        return DriveFolder(
            id=folder_id,
            files=files,
            subfolders=subfolders
        )
    except HttpError as error:
        print(f"An error occurred while scanning folder {folder_id}: {error}")
        raise Exception(f"Failed to access Google Drive folder. Please check permissions and URL.") from error

def add_drive_folder_to_chat(db: Session, chat_id: UUID, drive_url: str) -> DriveFolder:
    """Scans a Google Drive folder and adds its structure to a chat document."""
    service = authenticate_google_drive()
    if not service:
        raise Exception("Could not authenticate with Google Drive.")

    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', drive_url)
    if not match:
        raise ValueError("Invalid Google Drive folder URL provided.")
    folder_id = match.group(1)

    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(chat_id)
    if not chat:
        raise ValueError("Chat not found")

    # Check if this folder is already associated with the chat
    if any(folder['id'] == folder_id for folder in chat.drive_folders):
        raise ValueError(f"Drive folder {folder_id} is already added to this chat.")

    folder_structure = _scan_folder_recursively(service, folder_id)

    chat_repo.add_drive_folder(chat, folder_structure.model_dump())
    
    print(f"✅ Added Drive folder '{folder_id}' to chat '{chat_id}'")
    return folder_structure

def download_files_from_drive(drive_url: str, conversation_id: str):
    """
    Downloads all files from a Google Drive folder and processes them.
    This function is intended to be run in a background task.
    """
    service = authenticate_google_drive()
    if not service:
        print("❌ Could not authenticate with Google Drive. Aborting download.")
        return

    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', drive_url)
    if not match:
        print(f"❌ Invalid Google Drive folder URL: {drive_url}")
        return
    folder_id = match.group(1)

    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name)"
        ).execute()
        items = results.get('files', [])

        if not items:
            print(f"No files found in the folder: {drive_url}")
            return

        for item in items:
            file_id = item['id']
            file_name = item['name']
            print(f"⬇️ Downloading {file_name} ({file_id})")

            job_id = str(uuid.uuid4())
            upload_jobs[job_id] = UploadJob(
                job_id=job_id,
                filename=file_name,
                chat_id=conversation_id,
                status=ProcessingStatus.DOWNLOADING,
                stage=ProcessingStage.NOT_PROCESSING,
                progress=0,
                finished_at="",
                chunks_added=0,
                error=None
            )
            new_upload_job = upload_jobs[job_id]

            request = service.files().get_media(fileId=file_id)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as tmp_file:
                downloader = MediaIoBaseDownload(tmp_file, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    print(f"Download {int(status.progress() * 100)}%.")
                    new_upload_job.progress = int(status.progress() * 100)

                temp_path = tmp_file.name

            print(f"📂 File saved to temporary path: {temp_path}")
            
            new_upload_job.status = ProcessingStatus.QUEUED
            process_uploaded_pdf(temp_path, conversation_id, file_name, job_id)

    except HttpError as error:
        print(f'An error occurred: {error}')
