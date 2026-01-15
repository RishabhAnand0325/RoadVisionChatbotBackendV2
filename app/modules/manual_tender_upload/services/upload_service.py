"""
Service for handling manual tender uploads and PDF processing.
Manages file storage, validation, and parsing.
"""
import os
import uuid
import logging
from typing import Optional, Tuple
from datetime import datetime
from pathlib import Path
import mimetypes

logger = logging.getLogger(__name__)

# Configuration
UPLOAD_BASE_DIR = os.getenv("UPLOAD_BASE_DIR", "/uploads/manual_tenders")
ALLOWED_MIME_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


class ManualTenderUploadService:
    """Service for managing manual tender uploads."""
    
    @staticmethod
    def ensure_upload_directory() -> str:
        """Ensure upload directory exists."""
        os.makedirs(UPLOAD_BASE_DIR, exist_ok=True)
        return UPLOAD_BASE_DIR
    
    @staticmethod
    def generate_upload_reference() -> str:
        """Generate a unique upload reference."""
        return f"MTU_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8].upper()}"
    
    @staticmethod
    def validate_file(filename: str, file_size: int, mime_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate file for upload.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        # Check file size
        if file_size > MAX_FILE_SIZE:
            return False, f"File size exceeds maximum limit of {MAX_FILE_SIZE // (1024*1024)}MB"
        
        # Check file extension
        allowed_extensions = {'.pdf', '.docx', '.doc'}
        file_ext = Path(filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return False, f"File type not allowed. Supported: {', '.join(allowed_extensions)}"
        
        # Check MIME type (basic validation)
        if mime_type not in ALLOWED_MIME_TYPES and not mime_type.startswith('application/'):
            return False, "Invalid MIME type for tender document"
        
        return True, None
    
    @staticmethod
    def save_uploaded_file(
        file_content: bytes,
        filename: str,
        upload_reference: str,
        user_id: uuid.UUID
    ) -> Tuple[str, str]:
        """
        Save uploaded file to disk.
        
        Returns:
            Tuple[str, str]: (file_path, relative_path)
        """
        ManualTenderUploadService.ensure_upload_directory()
        
        # Create user-specific subdirectory
        user_dir = os.path.join(UPLOAD_BASE_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        # Generate safe filename
        file_ext = Path(filename).suffix
        safe_filename = f"{upload_reference}{file_ext}"
        
        # Full file path
        file_path = os.path.join(user_dir, safe_filename)
        
        # Write file
        try:
            with open(file_path, 'wb') as f:
                f.write(file_content)
            logger.info(f"File saved: {file_path}")
        except IOError as e:
            logger.error(f"Failed to save file: {e}")
            raise
        
        # Return both absolute and relative paths
        relative_path = f"manual_tenders/{user_id}/{safe_filename}"
        return file_path, relative_path
    
    @staticmethod
    def delete_uploaded_file(file_path: str) -> bool:
        """Delete an uploaded file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"File deleted: {file_path}")
                return True
            return False
        except OSError as e:
            logger.error(f"Failed to delete file: {e}")
            return False
    
    @staticmethod
    def get_file_content(file_path: str) -> Optional[bytes]:
        """Read file content from disk."""
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except IOError as e:
            logger.error(f"Failed to read file: {e}")
            return None
    
    @staticmethod
    def get_file_mime_type(filename: str) -> str:
        """Get MIME type for a file."""
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type and mime_type in ALLOWED_MIME_TYPES:
            return mime_type
        # Default to PDF if uncertain
        return "application/pdf"


class PDFProcessingService:
    """Service for processing PDF content and extracting metadata."""
    
    @staticmethod
    def extract_text_from_pdf(file_path: str, max_pages: Optional[int] = None) -> Optional[str]:
        """
        Extract text content from PDF file.
        Uses PyPDF2 or pypdf library.
        """
        try:
            import pypdf
            
            text_content = []
            with open(file_path, 'rb') as pdf_file:
                reader = pypdf.PdfReader(pdf_file)
                pages_to_process = min(len(reader.pages), max_pages) if max_pages else len(reader.pages)
                
                for page_num in range(pages_to_process):
                    page = reader.pages[page_num]
                    text_content.append(page.extract_text())
            
            return "\n".join(text_content)
        except ImportError:
            logger.warning("pypdf not installed. Cannot extract PDF text.")
            return None
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return None
    
    @staticmethod
    def extract_first_n_pages_text(file_path: str, num_pages: int = 10) -> Optional[str]:
        """Extract text from first N pages of PDF for preview."""
        return PDFProcessingService.extract_text_from_pdf(file_path, max_pages=num_pages)
    
    @staticmethod
    def get_pdf_metadata(file_path: str) -> dict:
        """Extract metadata from PDF (page count, creation date, etc)."""
        try:
            import pypdf
            
            with open(file_path, 'rb') as pdf_file:
                reader = pypdf.PdfReader(pdf_file)
                return {
                    "page_count": len(reader.pages),
                    "metadata": dict(reader.metadata) if reader.metadata else {}
                }
        except Exception as e:
            logger.error(f"Error extracting PDF metadata: {e}")
            return {"page_count": 0, "metadata": {}}
