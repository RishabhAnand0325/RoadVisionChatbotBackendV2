
import os
from .drive import authenticate_google_drive, get_shareable_link, upload_folder_to_drive


def test_google_drive():
    service = authenticate_google_drive()
    if not service:
        raise Exception("Google Drive authentication failed.")

    # Upload a folder to Google Drive
    # Make a dummy folder
    os.system("mkdir -p dummy_folder")
    # Upload the folder to Google Drive
    folder_id = upload_folder_to_drive(service, "dummy_folder")
    # Get the shareable link for the folder
    shareable_link = get_shareable_link(service, folder_id)
    print("Shareable link:", shareable_link)

def test_upload_folder_to_drive():
    service = authenticate_google_drive()
    if not service:
        raise Exception("Google Drive authentication failed.")

    # Upload a folder to Google Drive
    folder_id = upload_folder_to_drive(service, "tenders/2025-10-12/51172462", "1Ndc4cCJyQqgeJBBXAJ80pdSvITiQBDul")
    shareable_link = get_shareable_link(service, folder_id)
    print("Folder uploaded to Google Drive with ID:", shareable_link)

def main():
    print("Choose an option to test:")
    print("1. Upload a folder to Google Drive")
    print("2. Upload a folder to Google Drive v2")
    choice = input("Enter your choice: ")
    if choice == "1":
        test_google_drive()
    elif choice == "2":
        test_upload_folder_to_drive()
    else:
        print("Invalid choice.")

if __name__ == '__main__':
    main()
