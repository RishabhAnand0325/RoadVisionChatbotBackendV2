import os
import shutil
from typing import Tuple
from fastapi import UploadFile, HTTPException
import PyPDF2
from datetime import datetime
from pathlib import Path
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module="PyPDF2")


class DocumentService:
    """Service for handling document operations"""
    
    def __init__(self, storage_path: str = "Case-traker-data"):
        """
        Initialize document service
        
        Args:
            storage_path: Path to store uploaded documents (relative to backend root)
        """
        # Get the backend root directory
        backend_root = Path(__file__).parent.parent.parent.parent.parent
        self.storage_path = backend_root / storage_path
        
        # Create directory if it doesn't exist
        self.storage_path.mkdir(exist_ok=True)
    
    async def save_document(self, file: UploadFile) -> Tuple[str, str]:
        """
        Save uploaded document to storage
        
        Args:
            file: Uploaded file
            
        Returns:
            Tuple of (filename, file_path)
            
        Raises:
            HTTPException: If file is invalid or save fails
        """
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed"
            )
        
        # Check file size (50MB limit)
        file_content = await file.read()
        file_size_mb = len(file_content) / (1024 * 1024)
        
        if file_size_mb > 50:
            raise HTTPException(
                status_code=400,
                detail=f"File size ({file_size_mb:.2f}MB) exceeds 50MB limit"
            )
        
        # Generate filename (keep original name)
        filename = file.filename
        file_path = self.storage_path / filename
        
        # If file exists, add timestamp to make it unique
        if file_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{timestamp}{ext}"
            file_path = self.storage_path / filename
        
        try:
            # Save file
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            return filename, str(file_path)
        
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save document: {str(e)}"
            )
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text content from PDF file
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text content
            
        Raises:
            HTTPException: If extraction fails
        """
        try:
            text_content = ""
            
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                # Extract text from all pages
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
            
            if not text_content.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Could not extract text from PDF. The document may be scanned or image-based."
                )
            
            return text_content
        
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to extract text from PDF: {str(e)}"
            )
    
    def delete_document(self, filename: str) -> bool:
        """
        Delete a document from storage
        
        Args:
            filename: Name of file to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            file_path = self.storage_path / filename
            if file_path.exists():
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting document: {e}")
            return False
