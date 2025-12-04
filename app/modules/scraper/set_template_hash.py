"""
Utility script to set the email template hash from a known-good email.

Usage:
    python -m app.modules.scraper.set_template_hash <email_sender> <html_file_path> [description]

Example:
    python -m app.modules.scraper.set_template_hash tenders@tenderdetail.com sample_email.html "Initial template from 2025-11-29"
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

from app.modules.scraper.email_template_validator import set_template_hash


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m app.modules.scraper.set_template_hash <email_sender> <html_file_path> [description]")
        print("\nExample:")
        print("  python -m app.modules.scraper.set_template_hash tenders@tenderdetail.com sample_email.html")
        sys.exit(1)
    
    email_sender = sys.argv[1]
    html_file_path = sys.argv[2]
    description = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not os.path.exists(html_file_path):
        print(f"Error: File not found: {html_file_path}")
        sys.exit(1)
    
    # Read HTML file
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_body = f.read()
    
    # Set template hash
    try:
        template_hash_record = set_template_hash(html_body, email_sender, description)
        print(f"✅ Template hash set successfully!")
        print(f"   Sender: {email_sender}")
        print(f"   Hash: {template_hash_record.template_hash}")
        print(f"   ID: {template_hash_record.id}")
        if description:
            print(f"   Description: {description}")
    except Exception as e:
        print(f"❌ Error setting template hash: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


