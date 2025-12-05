from uuid import uuid4
from datetime import date as date_type

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


def _parse_date_to_date_object(date_string: str) -> date_type:
    """
    Parses a date string and returns a date object.
    Used for setting tender_release_date in ScrapeRun.
    """
    if not date_string:
        return None
    try:
        date_object = parser.parse(date_string)
        return date_object.date()
    except (parser.ParserError, ValueError):
        print(f"⚠️  Warning: Could not parse date string '{date_string}', returning None.")
        return None


def process_tenders_for_dms(db: Session, homepage_data: HomePageData) -> tuple[HomePageData, date_type]:
    """
    Processes scraped tender data for DMS integration WITHOUT downloading files.

    New Strategy (Hybrid Remote + Local Caching):
    1. Parse tender release date from website header
    2. Create folder structure in DMS: /tenders/YYYY/MM/DD/[tender_id]/files/
    3. Register file references (with URLs) but DON'T download
    4. DMS Module handles remote vs local file logic transparently
    5. Background job can cache files later on-demand

    This eliminates 12-hour download time and massive storage requirements.

    Returns:
        tuple: (updated_homepage_data, tender_release_date)
        where tender_release_date is parsed from the website header
    """
    print("\n🔄 Starting DMS integration process (NO FILE DOWNLOADS)...")
    dms_service = DmsService(db)
    system_user_id = uuid4()  # Placeholder for a system user

    # Parse the tender release date from website header
    tender_release_date = _parse_date_to_date_object(homepage_data.header.date)
    date_str = _parse_date(homepage_data.header.date)

    # Get or create the root folder for tenders by date
    try:
        root_folder_path = "/tenders/"
        dms_service.get_or_create_folder_by_path(root_folder_path, system_user_id)

        # Create date-based folder structure: YYYY/MM/DD
        year, month, day = date_str.split('-')
        date_folder_path = f"{root_folder_path}{year}/{month}/{day}/"
        dms_service.get_or_create_folder_by_path(date_folder_path, system_user_id)
    except Exception as e:
        print(f"❌ CRITICAL: Could not create base DMS directories. Aborting DMS processing. Error: {e}")
        return homepage_data, tender_release_date

    for query in homepage_data.query_table:
        for tender in query.tenders:
            if not tender.details:
                print(f"⚠️ Skipping tender {tender.tender_id} as it has no details/files.")
                continue

            try:
                # 1. Create the tender-specific folder in DMS
                # Path: /tenders/YYYY/MM/DD/[tender_id]/files/
                tender_folder_path = f"{date_folder_path}{tender.tender_id}/files/"
                tender_folder = dms_service.get_or_create_folder_by_path(tender_folder_path, system_user_id)
                tender.dms_folder_id = tender_folder.id
                print(f"  ✅ DMS folder ready for tender {tender.tender_id}")
                print(f"     Path: {tender_folder_path}")

                # 2. Register file references (WITHOUT downloading)
                # Files remain on their original internet locations
                # DMS will handle fetching them when needed
                file_count = len(tender.details.other_detail.files) if tender.details.other_detail.files else 0
                print(f"     Registering {file_count} remote file references...")

                for file_data in tender.details.other_detail.files:
                    # Create DMS document for each tender file
                    # This makes the file appear as a native DMS document
                    try:
                        dms_doc = dms_service.create_tender_document(
                            filename=file_data.file_name,
                            source_url=file_data.file_url,
                            folder_id=tender_folder.id,
                            uploaded_by=system_user_id,
                            file_size=int(file_data.file_size) if file_data.file_size else None,
                            confidentiality_level='internal'
                        )
                        print(f"    📄 Created DMS document: {file_data.file_name}")
                        print(f"       Document ID: {dms_doc.id}")
                    except Exception as e:
                        print(f"    ⚠️  Failed to create DMS document for {file_data.file_name}: {e}")

            except Exception as e:
                print(f"    ❌ An error occurred processing tender {tender.tender_id} for DMS: {e}")

    print("✅ DMS integration process complete (no files downloaded).")
    print("   Files remain on original internet locations.")
    print("   DMS Module will handle caching on-demand.")
    return homepage_data, tender_release_date
