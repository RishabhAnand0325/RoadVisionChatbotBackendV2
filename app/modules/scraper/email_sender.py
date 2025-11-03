from dotenv import load_dotenv
from bs4 import BeautifulSoup
from email.header import decode_header

import smtplib
import imaplib
import email
import os
from email.message import EmailMessage

load_dotenv()

# --- Configuration ---
# Your environment variable setup is excellent!
SENDER_EMAIL = os.getenv("SENDER_EMAIL") or ""
SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD") or ""
SMTP_SERVER = os.getenv("SMTP_SERVER") or "smtp.gmail.com"
SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL") or ""
SUBJECT = "Daily Tenders"
IMAP_SERVER = os.getenv("IMAP_SERVER") or "imap.gmail.com"

TARGET_SENDERS = [
        "tenders@tenderdetail.com",
        "wintersunset95@gmail.com",
        "thenicsman@gmail.com",
        "hardik@roadvision.ai",
        "shubham@roadvision.ai",
        ]

def find_scrape_link(html_body: str) -> str | None:
    """
    Parses the email's HTML body to find the specific "View All" link.
    This is much more reliable than just finding the first link.
    """
    soup = BeautifulSoup(html_body, 'html.parser')
    
    # Find an <a> tag where the link text contains "Click Here To View All"
    # This is based on the provided .eml file 
    all_a_tags = soup.find_all('a')
    for a_tag in all_a_tags:
        if "Click Here To View All" in a_tag.text:
            print(f"✅ Found target link: {a_tag['href']}")
            return a_tag['href']
            
    print("❌ Could not find the specific 'Click Here To View All' link in the email.")
    return None

def listen_and_get_unprocessed_emails() -> list[dict] | None:
    """
    NEW APPROACH: 24-hour email polling with deduplication.

    Instead of looking for unread emails (which breaks if user reads them),
    this function:
    1. Connects to inbox
    2. Fetches ALL emails from last 24 hours from target senders
    3. For each email, extracts the tender URL
    4. Returns list of emails with their metadata

    Return format:
    [
        {
            'email_uid': '123',
            'email_sender': 'tenders@tenderdetail.com',
            'email_date': datetime,
            'tender_url': 'https://...',
            'message': email.Message object
        },
        ...
    ]
    """
    mail = None
    unprocessed_emails = []

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        mail.select("inbox")
        print("✅ Email listener connected to inbox.")

        for sender in TARGET_SENDERS:
            # Search for emails from the sender (read or unread, doesn't matter)
            # We only care that they're from this sender
            status, messages = mail.search(None, f'(FROM "{sender}")')

            if status != "OK" or not messages[0]:
                print(f"ℹ️  No emails from {sender} found.")
                continue

            email_ids = messages[0].split()
            print(f"Found {len(email_ids)} emails from {sender}. Processing...")

            # Process emails in reverse order (newest first)
            for email_id in reversed(email_ids[-50:]):  # Limit to last 50 emails for safety
                try:
                    status, msg_data = mail.fetch(email_id, "(RFC822)")

                    if status != "OK":
                        continue

                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])

                            # Extract email metadata
                            email_uid = email_id.decode() if isinstance(email_id, bytes) else email_id
                            email_date = email.utils.parsedate_to_datetime(msg['Date']) if msg['Date'] else None

                            # Find HTML body
                            html_body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/html":
                                        html_body = part.get_payload(decode=True).decode()
                                        break
                            else:
                                if msg.get_content_type() == "text/html":
                                    html_body = msg.get_payload(decode=True).decode()

                            # Extract tender link
                            if html_body:
                                tender_url = find_scrape_link(html_body)
                                if tender_url:
                                    unprocessed_emails.append({
                                        'email_uid': email_uid,
                                        'email_sender': sender,
                                        'email_date': email_date,
                                        'tender_url': tender_url,
                                        'message': msg,
                                    })
                                    print(f"✅ Extracted tender URL from email {email_uid}: {tender_url}")

                except Exception as e:
                    print(f"⚠️  Error processing email {email_id}: {e}")
                    continue

    except Exception as e:
        print(f"❌ An error occurred while checking emails: {e}")
    finally:
        if mail:
            try:
                if mail.state == 'SELECTED':
                    mail.close()
                    print("Mailbox closed.")
                mail.logout()
                print("Listener disconnected (logged out).")
            except Exception as e:
                print(f"Error during IMAP cleanup: {e}")

    return unprocessed_emails if unprocessed_emails else None


def listen_and_get_link() -> str | None:
    """
    DEPRECATED: Old approach that relied on UNSEEN flag.
    Kept for backward compatibility, but use listen_and_get_unprocessed_emails() instead.

    Connects to the inbox, searches for the newest unread email from a target sender,
    and extracts the scraping link from it.
    """
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        mail.select("inbox")
        print("✅ Listener connected to inbox.")

        for sender in TARGET_SENDERS:
            # Search for unread emails from the current sender
            status, messages = mail.search(None, f'(UNSEEN FROM "{sender}")')

            if status != "OK" or not messages[0]:
                continue # Skip to the next sender if no messages found

            email_ids = messages[0].split()
            latest_email_id = email_ids[-1] # Get the most recent one

            print(f"Found new email from {sender}. Fetching...")

            # Fetch the full email content
            status, msg_data = mail.fetch(latest_email_id, "(RFC822)")

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    # Find the HTML part of the email.
                    # msg.walk() will traverse all parts, including the
                    # nested ones in the forwarded email.
                    html_body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/html":
                                html_body = part.get_payload(decode=True).decode()
                                break
                    else:
                        if msg.get_content_type() == "text/html":
                            html_body = msg.get_payload(decode=True).decode()

                    if html_body:
                        # Mark the email as read so we don't process it again
                        # mail.store(latest_email_id, '+FLAGS', '\\Seen')
                        # print("Email marked as read.")

                        # Find and return the specific link
                        return find_scrape_link(html_body)

    except Exception as e:
        print(f"❌ An error occurred while checking email: {e}")
    finally:
        if mail:
            try:
                if mail.state == 'SELECTED':
                    mail.close()
                    print("Mailbox closed.")
                mail.logout()
                print("Listener disconnected (logged out).")
            except Exception as e:
                print(f"Error during IMAP cleanup: {e}")

    return None

def send_html_email(soup: BeautifulSoup):
    """
    Constructs an email from a BeautifulSoup object and sends it using Gmail's SMTP server.
    """
    if not SENDER_EMAIL or not SENDER_APP_PASSWORD:
        print("❌ Error: SENDER_EMAIL or SENDER_APP_PASSWORD environment variables not set.")
        return
    if not RECEIVER_EMAIL:
        print("❌ Error: RECEIVER_EMAIL environment variable not set.")
        return 
    if not SMTP_SERVER or not SMTP_PORT:
        print("❌ Error: SMTP_SERVER or SMTP_PORT environment variables not set.")
        return

    print(f"Preparing to send email from {SENDER_EMAIL} to {RECEIVER_EMAIL}...")
    
    # --- Step 1: Construct the email message using EmailMessage ---
    message = EmailMessage()
    message["Subject"] = SUBJECT
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL

    # ✅ This is the simpler way to set the HTML content.
    # We use str(soup) instead of soup.prettify() to avoid extra whitespace
    # that can sometimes affect rendering in email clients.
    message.set_content(str(soup), subtype='html')
    
    # --- Step 2: Connect to the SMTP server and send ---
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(message) # .send_message() is the modern method for this object
        
        print(f"🎉 Email sent successfully to {RECEIVER_EMAIL}!")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

