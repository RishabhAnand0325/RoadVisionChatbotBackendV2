import mimetypes
from uuid import uuid4

import requests
from dateutil import parser
from sqlalchemy.orm import Session

from app.modules.dmsiq.services.dms_service import DmsService
from app.modules.scraper.data_models import HomePageData


def _parse_date(date_string: str) -> str:
    """
    Parses a date string in a flexible format and converts it to 'YYYY-MM-DD'.
    """
    if not date_string:
        return "unknown-date"
    try:
        # Let dateutil parse the string into a datetime object.
        date_object = parser.parse(date_string)
        # Format the object into the desired "YYYY-MM-DD" string.
        return date_object.strftime("%Y-%m-%d")
    except parser.ParserError:
        print(f"⚠️  Warning: Could not parse the date string '{date_string}'.")
        return "unknown-date"


def process_tenders_for_dms(db: Session, homepage_data: HomePageData) -> HomePageData:
    """
    Processes scraped tender data to create folders and upload files to DMS.
    Updates the tender objects with their new DMS folder IDs.
    """
    print("\n🔄 Starting DMS integration process...")
    dms_service = DmsService(db)
    system_user_id = uuid4()  # Placeholder for a system user

    # Get or create the root folder for daily tenders
    root_folder_path = "/Daily Tenders/"
    dms_service.get_or_create_folder_by_path(root_folder_path, system_user_id)

    date_str = _parse_date(homepage_data.header.date)
    date_folder_path = f"{root_folder_path}{date_str}/"
    dms_service.get_or_create_folder_by_path(date_folder_path, system_user_id)

    for query in homepage_data.query_table:
        for tender in query.tenders:
            if not tender.details:
                print(f"⚠️ Skipping tender {tender.tender_id} as it has no details/files.")
                continue

            try:
                # 1. Create the tender-specific folder in DMS
                tender_folder_path = f"{date_folder_path}{tender.tender_id}/"
                tender_folder = dms_service.get_or_create_folder_by_path(tender_folder_path, system_user_id)
                tender.dms_folder_id = tender_folder.id
                print(f"  - Ensured DMS folder exists for tender {tender.tender_id} (ID: {tender.dms_folder_id})")

                # 2. Download and upload each associated file
                for file_data in tender.details.other_detail.files:
                    print(f"    - Processing file: {file_data.file_name}")
                    # Download file content
                    response = requests.get(file_data.file_url)
                    response.raise_for_status()  # Raise an exception for bad status codes
                    file_content = response.content
                    
                    # Guess MIME type
                    mime_type, _ = mimetypes.guess_type(file_data.file_name)
                    if mime_type is None:
                        mime_type = 'application/octet-stream'

                    # Upload to DMS
                    dms_service.upload_document_from_bytes(
                        file_content=file_content,
                        filename=file_data.file_name,
                        mime_type=mime_type,
                        folder_id=tender.dms_folder_id,
                        uploaded_by=system_user_id
                    )
                    print(f"      ✅ Uploaded to DMS: {file_data.file_name}")

            except requests.RequestException as e:
                print(f"    ❌ Failed to download file for tender {tender.tender_id}: {e}")
            except Exception as e:
                print(f"    ❌ An error occurred processing tender {tender.tender_id} for DMS: {e}")

    print("✅ DMS integration process complete.")
    return homepage_data
