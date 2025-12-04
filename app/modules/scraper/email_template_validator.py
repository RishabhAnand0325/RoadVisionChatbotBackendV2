"""
Email Template Security Validator

This module provides security checks to ensure incoming emails match the expected template structure.
If an email template has changed, processing is stopped to prevent potential security issues or parsing errors.
"""
import hashlib
import re
from typing import Optional
from bs4 import BeautifulSoup
from datetime import datetime

from app.db.database import SessionLocal
from app.modules.scraper.db.schema import EmailTemplateHash


def extract_template_structure(html_body: str) -> str:
    """
    Extracts the structural signature of an email template by:
    1. Removing all text content (keeping only structure)
    2. Normalizing whitespace
    3. Removing dynamic content (links, dates, etc.)
    4. Keeping only tag structure, classes, and IDs
    
    This creates a fingerprint that identifies the template structure
    regardless of the actual content.
    
    Args:
        html_body: The HTML content of the email
        
    Returns:
        A normalized string representing the template structure
    """
    soup = BeautifulSoup(html_body, 'html.parser')
    
    # Remove all text nodes but keep structure
    for element in soup.find_all(text=True):
        if element.parent and element.parent.name not in ['script', 'style']:
            # Replace text with placeholder, but keep structure
            element.replace_with(' ')
    
    # Remove script and style tags completely
    for tag in soup.find_all(['script', 'style']):
        tag.decompose()
    
    # Normalize attributes - remove dynamic values but keep structure
    for tag in soup.find_all():
        # Keep important structural attributes
        attrs_to_keep = ['class', 'id', 'href', 'src']
        new_attrs = {}
        
        for attr, value in tag.attrs.items():
            if attr in attrs_to_keep:
                # For href and src, normalize URLs to placeholder
                if attr in ['href', 'src']:
                    if isinstance(value, list):
                        new_attrs[attr] = ['URL_PLACEHOLDER']
                    else:
                        new_attrs[attr] = 'URL_PLACEHOLDER'
                else:
                    # Keep class and id as-is (they define structure)
                    new_attrs[attr] = value
        
        tag.attrs = new_attrs
    
    # Get the normalized HTML structure
    normalized_html = str(soup)
    
    # Further normalize: remove extra whitespace
    normalized_html = re.sub(r'\s+', ' ', normalized_html)
    normalized_html = normalized_html.strip()
    
    return normalized_html


def generate_template_hash(html_body: str) -> str:
    """
    Generates a SHA256 hash of the email template structure.
    
    Args:
        html_body: The HTML content of the email
        
    Returns:
        SHA256 hash string of the template structure
    """
    structure = extract_template_structure(html_body)
    return hashlib.sha256(structure.encode('utf-8')).hexdigest()


def validate_email_template(html_body: str, email_sender: str) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Validates that an incoming email's template matches the expected template hash.
    
    Args:
        html_body: The HTML content of the incoming email
        email_sender: The sender email address
        
    Returns:
        Tuple of (is_valid, current_hash, error_message)
        - is_valid: True if template matches, False otherwise
        - current_hash: The hash of the current email template
        - error_message: Error message if validation failed
    """
    db = SessionLocal()
    try:
        # Generate hash of incoming email template
        current_hash = generate_template_hash(html_body)
        
        # Get the active template hash for this sender
        template_hash_record = db.query(EmailTemplateHash).filter(
            EmailTemplateHash.email_sender == email_sender,
            EmailTemplateHash.is_active == True
        ).first()
        
        if not template_hash_record:
            # No template hash stored yet - this is the first email
            # We'll allow it but log a warning
            error_msg = f"No template hash found for sender {email_sender}. First email received - consider setting up template hash."
            return True, current_hash, error_msg  # Allow first email, but warn
        
        # Compare hashes
        if current_hash != template_hash_record.template_hash:
            error_msg = (
                f"Email template structure has changed for {email_sender}. "
                f"Expected hash: {template_hash_record.template_hash[:16]}..., "
                f"Received hash: {current_hash[:16]}.... "
                f"Processing stopped for security."
            )
            return False, current_hash, error_msg
        
        # Template matches - update last_validated_at
        template_hash_record.last_validated_at = datetime.utcnow()
        db.commit()
        
        return True, current_hash, None
        
    except Exception as e:
        error_msg = f"Error validating email template: {str(e)}"
        return False, None, error_msg
    finally:
        db.close()


def set_template_hash(html_body: str, email_sender: str, description: Optional[str] = None) -> EmailTemplateHash:
    """
    Sets or updates the expected template hash for a sender.
    This should be called when you receive a known-good email template.
    
    Args:
        html_body: The HTML content of a known-good email
        email_sender: The sender email address
        description: Optional description of the template
        
    Returns:
        EmailTemplateHash record
    """
    db = SessionLocal()
    try:
        template_hash = generate_template_hash(html_body)
        
        # Check if hash already exists for this sender
        existing = db.query(EmailTemplateHash).filter(
            EmailTemplateHash.email_sender == email_sender,
            EmailTemplateHash.template_hash == template_hash
        ).first()
        
        if existing:
            # Update existing record
            existing.is_active = True
            existing.last_validated_at = datetime.utcnow()
            if description:
                existing.description = description
            db.commit()
            db.refresh(existing)
            return existing
        
        # Deactivate old templates for this sender
        db.query(EmailTemplateHash).filter(
            EmailTemplateHash.email_sender == email_sender
        ).update({'is_active': False})
        
        # Create new template hash record
        new_hash = EmailTemplateHash(
            template_hash=template_hash,
            email_sender=email_sender,
            is_active=True,
            description=description,
            last_validated_at=datetime.utcnow()
        )
        db.add(new_hash)
        db.commit()
        db.refresh(new_hash)
        return new_hash
        
    finally:
        db.close()


