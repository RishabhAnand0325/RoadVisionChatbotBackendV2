"""
DMS Business Logic Service Layer
Handles business logic, validation, and orchestration of DMS operations.
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timezone
from fastapi import HTTPException, status, UploadFile
from pathlib import Path

from sqlalchemy.orm import Session

from app.modules.dmsiq.db.repository import DmsRepository
from app.modules.dmsiq.services.file_storage import FileStorageService
from app.modules.dmsiq.models.pydantic_models import (
    Folder, FolderCreate, FolderUpdate, FolderMove,
    Document, DocumentCreate, DocumentUpdate,
    DocumentCategory, FolderPermission, DocumentPermission,
    UploadURLResponse, DownloadURLResponse, DocumentSummary,
    DocumentListResponse, PermissionLevel, ConfidentialityLevel
)


class DmsService:
    """Business logic service for DMS operations."""

    def __init__(self, db: Session):
        """Initialize service with database session and repository."""
        self.db = db
        self.repo = DmsRepository(db)

    # ==================== FOLDER SERVICES ====================

    def list_root_folders(
        self,
        department: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Folder]:
        """List root folders (parent_id is None)."""
        try:
            folders = self.repo.list_folders(parent_id=None, department=department, search=search)
            return [self._folder_to_response(f) for f in folders]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing folders: {str(e)}")

    def list_subfolders(self, parent_id: UUID) -> List[Folder]:
        """List subfolders of a given folder."""
        try:
            parent = self.repo.get_folder(parent_id)
            if not parent:
                raise HTTPException(status_code=404, detail="Parent folder not found")

            subfolders = self.repo.list_folders(parent_id=parent_id)
            return [self._folder_to_response(f) for f in subfolders]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing subfolders: {str(e)}")

    def create_folder(
        self,
        data: FolderCreate,
        created_by: UUID
    ) -> Folder:
        """Create a new folder."""
        try:
            # Validate parent folder exists if specified
            if data.parent_folder_id:
                parent = self.repo.get_folder(data.parent_folder_id)
                if not parent:
                    raise HTTPException(status_code=404, detail="Parent folder not found")

            folder = self.repo.create_folder(
                name=data.name,
                created_by=created_by,
                parent_folder_id=data.parent_folder_id,
                department=data.department,
                confidentiality_level=data.confidentiality_level,
                description=data.description,
                is_system_folder=False
            )
            self.repo.commit()
            return self._folder_to_response(folder)
        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error creating folder: {str(e)}")

    def get_folder(self, folder_id: UUID) -> Folder:
        """Get folder details."""
        try:
            folder = self.repo.get_folder(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")
            return self._folder_to_response(folder)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting folder: {str(e)}")

    def update_folder(
        self,
        folder_id: UUID,
        data: FolderUpdate
    ) -> Folder:
        """Update folder metadata."""
        try:
            folder = self.repo.update_folder(folder_id, data)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")
            self.repo.commit()
            return self._folder_to_response(folder)
        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error updating folder: {str(e)}")

    def delete_folder(self, folder_id: UUID) -> None:
        """Delete folder (must be empty)."""
        try:
            success = self.repo.delete_folder(folder_id)
            if not success:
                raise HTTPException(status_code=404, detail="Folder not found")
            self.repo.commit()
        except HTTPException:
            self.repo.rollback()
            raise
        except ValueError as e:
            self.repo.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error deleting folder: {str(e)}")

    def move_folder(
        self,
        folder_id: UUID,
        data: FolderMove
    ) -> Folder:
        """Move folder to new parent."""
        try:
            folder = self.repo.move_folder(folder_id, data.new_parent_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")
            self.repo.commit()
            return self._folder_to_response(folder)
        except HTTPException:
            self.repo.rollback()
            raise
        except ValueError as e:
            self.repo.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error moving folder: {str(e)}")

    def get_or_create_folder_by_path(self, path: str, created_by: UUID) -> Folder:
        """
        Retrieves a folder by its materialized path. If the folder (or any of its parents)
        does not exist, they will be created.
        """
        try:
            folder = self.repo.get_folder_by_path(path)
            if folder:
                return self._folder_to_response(folder)

            # Folder doesn't exist, create it and parents if necessary
            path_parts = [part for part in path.strip('/').split('/') if part]
            current_path_segment = "/"
            parent_id = None
            target_folder = None

            for part in path_parts:
                current_path_segment += f"{part}/"
                folder_in_path = self.repo.get_folder_by_path(current_path_segment)
                if not folder_in_path:
                    folder_in_path = self.repo.create_folder(
                        name=part,
                        created_by=created_by,
                        parent_folder_id=parent_id
                    )
                parent_id = folder_in_path.id
                target_folder = folder_in_path
            
            self.repo.commit()

            if not target_folder:
                raise HTTPException(status_code=500, detail="Failed to create folder hierarchy")

            return self._folder_to_response(target_folder)
        except Exception as e:
            self.repo.rollback()
            print(f"ERROR in get_or_create_folder_by_path for path '{path}': {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error getting or creating folder by path: {str(e)}")

    # ==================== DOCUMENT SERVICES ====================

    def list_documents(
        self,
        folder_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> DocumentListResponse:
        """List documents with filtering."""
        try:
            # Validate limits
            if limit > 500:
                limit = 500
            if offset < 0:
                offset = 0

            documents, total = self.repo.list_documents(
                folder_id=folder_id,
                category_id=category_id,
                search=search,
                tags=tags,
                status=status,
                limit=limit,
                offset=offset
            )

            doc_responses = [self._document_to_response(d) for d in documents]
            return DocumentListResponse(
                documents=doc_responses,
                total=total,
                limit=limit,
                offset=offset
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

    def get_document(self, document_id: UUID) -> Document:
        """Get document details."""
        try:
            document = self.repo.get_document(document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            return self._document_to_response(document)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting document: {str(e)}")

    def create_document(
        self,
        name: str,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
        folder_id: UUID,
        uploaded_by: UUID,
        tags: Optional[List[str]] = None,
        confidentiality_level: str = ConfidentialityLevel.INTERNAL,
        doc_metadata: Optional[dict] = None
    ) -> Document:
        """Create a new document in pending status."""
        try:
            # Validate folder exists
            folder = self.repo.get_folder(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")

            document = self.repo.create_document(
                name=name,
                original_filename=original_filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                uploaded_by=uploaded_by,
                folder_id=folder_id,
                confidentiality_level=confidentiality_level,
                tags=tags,
                doc_metadata=doc_metadata,
                status="pending"
            )

            self.repo.commit()
            return self._document_to_response(document)
        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error creating document: {str(e)}")

    def update_document(
        self,
        document_id: UUID,
        data: DocumentUpdate
    ) -> Document:
        """Update document metadata."""
        try:
            document = self.repo.update_document(document_id, data)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            self.repo.commit()
            return self._document_to_response(document)
        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error updating document: {str(e)}")

    def delete_document(self, document_id: UUID) -> None:
        """Soft delete document."""
        try:
            success = self.repo.delete_document(document_id)
            if not success:
                raise HTTPException(status_code=404, detail="Document not found")
            self.repo.commit()
        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

    async def upload_document(
        self,
        file: UploadFile,
        folder_id: UUID,
        uploaded_by: UUID,
        category_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        confidentiality_level: str = ConfidentialityLevel.INTERNAL
    ) -> Document:
        """Handle direct file upload."""
        try:
            folder = self.repo.get_folder(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")

            file_content = await file.read()
            file_size = len(file_content)

            # Create document record. storage_path will be set by the repo.
            document = self.repo.create_document(
                name=file.filename,
                original_filename=file.filename,
                mime_type=file.content_type,
                size_bytes=file_size,
                uploaded_by=uploaded_by,
                folder_id=folder_id,
                confidentiality_level=confidentiality_level,
                tags=tags,
                status="active"
            )
            
            # Now save the file using the path from the document object
            success, full_path_or_error = FileStorageService.save_file(file_content, document.storage_path)
            if not success:
                self.repo.rollback() # Important!
                raise HTTPException(status_code=500, detail=f"Failed to save file: {full_path_or_error}")
            
            if category_id:
                self.repo.add_document_category(document.id, category_id)
            
            self.repo.commit()
            return self._document_to_response(document)

        except Exception as e:
            self.repo.rollback()
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

    def upload_document_from_bytes(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        folder_id: UUID,
        uploaded_by: UUID,
        category_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        confidentiality_level: str = ConfidentialityLevel.INTERNAL
    ) -> Document:
        """Handle synchronous file upload from bytes, for internal service use."""
        try:
            folder = self.repo.get_folder(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")

            file_size = len(file_content)

            document = self.repo.create_document(
                name=filename,
                original_filename=filename,
                mime_type=mime_type,
                size_bytes=file_size,
                uploaded_by=uploaded_by,
                folder_id=folder_id,
                confidentiality_level=confidentiality_level,
                tags=tags,
                status="active"
            )
            
            success, full_path_or_error = FileStorageService.save_file(file_content, document.storage_path)
            if not success:
                self.repo.rollback()
                raise HTTPException(status_code=500, detail=f"Failed to save file: {full_path_or_error}")
            
            if category_id:
                self.repo.add_document_category(document.id, category_id)
            
            self.repo.commit()
            return self._document_to_response(document)

        except Exception as e:
            self.repo.rollback()
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

    def confirm_upload(
        self,
        document_id: UUID,
        s3_etag: str,
        s3_version_id: Optional[str] = None
    ) -> Document:
        """Confirm document upload completion."""
        try:
            document = self.repo.get_document(document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")

            # Update document status to active
            from app.modules.dmsiq.models.pydantic_models import DocumentUpdate as DocUpdate
            update_data = DocUpdate(status="active")
            document = self.repo.update_document(document_id, update_data)

            # Store S3 metadata if provided
            if s3_etag:
                document.s3_etag = s3_etag
            if s3_version_id:
                document.s3_version_id = s3_version_id

            self.repo.commit()
            return self._document_to_response(document)
        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error confirming upload: {str(e)}")

    # ==================== TENDER FILE SERVICES ====================

    def create_tender_document(
        self,
        filename: str,
        source_url: str,
        folder_id: UUID,
        uploaded_by: UUID,
        scraped_tender_file_id: Optional[UUID] = None,
        file_size: Optional[int] = None,
        confidentiality_level: str = ConfidentialityLevel.INTERNAL
    ) -> Document:
        """
        Create a DMS document from a remote tender file.

        This creates a document that references an internet URL instead of storing
        the file locally. The document appears in the DMS hierarchy like any other document.

        Args:
            filename: Name of the file (displayed in DMS)
            source_url: Original internet URL to the tender file
            folder_id: DMS folder to place the document in
            uploaded_by: User ID creating the document
            scraped_tender_file_id: Reference to ScrapedTenderFile record (for tracking)
            file_size: File size in bytes (optional, can be determined later)
            confidentiality_level: DMS confidentiality level

        Returns:
            Document: The created DMS document record
        """
        try:
            # Validate folder exists
            folder = self.repo.get_folder(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")

            # Guess MIME type from filename
            import mimetypes
            mime_type, _ = mimetypes.guess_type(filename)
            if mime_type is None:
                mime_type = 'application/octet-stream'

            # Create document with remote source information
            document = self.repo.create_document(
                name=filename,
                original_filename=filename,
                mime_type=mime_type,
                size_bytes=file_size,
                uploaded_by=uploaded_by,
                folder_id=folder_id,
                confidentiality_level=confidentiality_level,
                status="active",  # Already available (remote URL)
                storage_provider="remote"  # Mark as remote file
            )

            # Set tender file specific fields
            document.source_url = source_url
            document.is_tender_file = True
            document.is_cached = False
            document.cache_status = "pending"
            document.scraped_tender_file_id = scraped_tender_file_id

            self.repo.commit()
            return self._document_to_response(document)

        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error creating tender document: {str(e)}")

    # ==================== CATEGORY SERVICES ====================

    def list_categories(self) -> List[DocumentCategory]:
        """List all document categories."""
        try:
            categories = self.repo.get_categories()
            return [
                DocumentCategory(id=c.id, name=c.name, color=c.color, icon=c.icon)
                for c in categories
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing categories: {str(e)}")

    def create_category(
        self,
        name: str,
        color: Optional[str] = None,
        icon: Optional[str] = None
    ) -> DocumentCategory:
        """Create a new category."""
        try:
            category = self.repo.create_category(name=name, color=color, icon=icon)
            self.repo.commit()
            return DocumentCategory(id=category.id, name=category.name, color=category.color, icon=category.icon)
        except ValueError as e:
            self.repo.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error creating category: {str(e)}")

    def add_document_category(self, document_id: UUID, category_id: UUID) -> Document:
        """Add a category to a document."""
        try:
            success = self.repo.add_document_category(document_id, category_id)
            if not success:
                raise HTTPException(status_code=404, detail="Document or category not found")
            self.repo.commit()

            document = self.repo.get_document(document_id)
            return self._document_to_response(document)
        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error adding category: {str(e)}")

    # ==================== PERMISSION SERVICES ====================

    def list_folder_permissions(self, folder_id: UUID) -> List[FolderPermission]:
        """List all permissions for a folder."""
        try:
            folder = self.repo.get_folder(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")

            permissions = self.repo.get_folder_permissions(folder_id)
            return [self._folder_permission_to_response(p) for p in permissions]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing permissions: {str(e)}")

    def grant_folder_permission(
        self,
        folder_id: UUID,
        permission_level: str,
        granted_by: UUID,
        user_id: Optional[UUID] = None,
        department: Optional[str] = None,
        inherit_to_subfolders: bool = True,
        valid_until: Optional[datetime] = None
    ) -> FolderPermission:
        """Grant permission on a folder."""
        try:
            folder = self.repo.get_folder(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")

            permission = self.repo.grant_folder_permission(
                folder_id=folder_id,
                permission_level=permission_level,
                granted_by=granted_by,
                user_id=user_id,
                department=department,
                inherit_to_subfolders=inherit_to_subfolders,
                valid_until=valid_until
            )
            self.repo.commit()
            return self._folder_permission_to_response(permission)
        except HTTPException:
            self.repo.rollback()
            raise
        except ValueError as e:
            self.repo.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error granting permission: {str(e)}")

    def revoke_folder_permission(self, folder_id: UUID, permission_id: UUID) -> None:
        """Revoke folder permission."""
        try:
            folder = self.repo.get_folder(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")

            success = self.repo.revoke_folder_permission(permission_id)
            if not success:
                raise HTTPException(status_code=404, detail="Permission not found")

            self.repo.commit()
        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error revoking permission: {str(e)}")

    def list_document_permissions(self, document_id: UUID) -> List[DocumentPermission]:
        """List all permissions for a document."""
        try:
            document = self.repo.get_document(document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")

            permissions = self.repo.get_document_permissions(document_id)
            return [self._document_permission_to_response(p) for p in permissions]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing permissions: {str(e)}")

    def grant_document_permission(
        self,
        document_id: UUID,
        user_id: UUID,
        permission_level: str,
        granted_by: UUID,
        valid_until: Optional[datetime] = None
    ) -> DocumentPermission:
        """Grant permission on a document."""
        try:
            document = self.repo.get_document(document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")

            permission = self.repo.grant_document_permission(
                document_id=document_id,
                user_id=user_id,
                permission_level=permission_level,
                granted_by=granted_by,
                valid_until=valid_until
            )
            self.repo.commit()
            return self._document_permission_to_response(permission)
        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error granting permission: {str(e)}")

    def revoke_document_permission(self, document_id: UUID, permission_id: UUID) -> None:
        """Revoke document permission."""
        try:
            document = self.repo.get_document(document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")

            success = self.repo.revoke_document_permission(permission_id)
            if not success:
                raise HTTPException(status_code=404, detail="Permission not found")

            self.repo.commit()
        except HTTPException:
            self.repo.rollback()
            raise
        except Exception as e:
            self.repo.rollback()
            raise HTTPException(status_code=500, detail=f"Error revoking permission: {str(e)}")

    # ==================== UPLOAD/DOWNLOAD SERVICES ====================

    def generate_upload_url(
        self,
        filename: str,
        file_size: int,
        mime_type: str,
        folder_id: UUID,
        uploaded_by: UUID,
        category_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        confidentiality_level: str = ConfidentialityLevel.INTERNAL
    ) -> UploadURLResponse:
        """Generate upload URL for direct file upload."""
        try:
            # Validate folder exists
            folder = self.repo.get_folder(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")

            # Create document in pending status
            document = self.create_document(
                name=filename,
                original_filename=filename,
                mime_type=mime_type,
                size_bytes=file_size,
                folder_id=folder_id,
                uploaded_by=uploaded_by,
                tags=tags,
                confidentiality_level=confidentiality_level
            )

            # Add category if specified
            if category_id:
                self.repo.add_document_category(document.id, category_id)
                self.repo.commit()

            # Return upload URL response
            # For local storage MVP, we return file path
            # In production with S3, this would be presigned URL
            return UploadURLResponse(
                upload_url=f"/api/v1/dms/documents/{document.id}/upload",  # Placeholder
                document_id=document.id,
                storage_path=document.storage_path,
                expires_in=3600  # 1 hour
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating upload URL: {str(e)}")

    def generate_download_url(
        self,
        document_id: UUID,
        version_number: Optional[int] = None
    ) -> DownloadURLResponse:
        """Generate download URL for direct file download."""
        try:
            document = self.repo.get_document(document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")

            # Determine storage path
            storage_path = document.storage_path
            if version_number:
                versions = self.repo.get_document_versions(document_id)
                version = next((v for v in versions if v.version_number == version_number), None)
                if not version:
                    raise HTTPException(status_code=404, detail="Version not found")
                storage_path = version.storage_path

            return DownloadURLResponse(
                download_url=f"/api/v1/dms/documents/{document_id}/download",  # Placeholder
                filename=document.original_filename,
                expires_in=300  # 5 minutes
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating download URL: {str(e)}")

    def get_document_for_download(self, document_id: UUID) -> Tuple[Path, str]:
        """
        Get full file path and name for download.

        Supports both local and remote tender files:
        - Local: Returns path to local file
        - Remote tender file: Downloads from source URL and caches, returns cached path
        """
        try:
            document = self.repo.get_document(document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")

            # Handle remote tender files with smart caching
            if document.is_tender_file and document.storage_provider == "remote":
                return self._handle_tender_file_download(document)

            # Standard local file handling
            full_path = FileStorageService.get_full_path(document.storage_path)
            return full_path, document.original_filename
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error preparing file for download: {str(e)}")

    def _handle_tender_file_download(self, document) -> Tuple[Path, str]:
        """
        Handle download of a tender file.

        Smart caching logic:
        1. If file is cached locally → return cached path
        2. If not cached → download from source URL → cache → return cached path
        """
        import requests
        from app.modules.dmsiq.services.file_storage import FileStorageService

        # Check if already cached
        if document.is_cached:
            cached_path = FileStorageService.get_full_path(document.storage_path)
            if cached_path.exists():
                return cached_path, document.original_filename

        # File not cached, need to download
        if not document.source_url:
            raise HTTPException(
                status_code=400,
                detail="Remote file has no source URL"
            )

        try:
            # Download from remote URL
            response = requests.get(document.source_url, timeout=60)
            response.raise_for_status()
            file_content = response.content

            # Cache the file
            success, result = FileStorageService.save_file(
                file_content,
                document.storage_path
            )

            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to cache tender file: {result}"
                )

            # Update document cache status
            document.is_cached = True
            document.cache_status = "cached"
            document.cache_error = None
            self.repo.commit()

            cached_path = FileStorageService.get_full_path(document.storage_path)
            return cached_path, document.original_filename

        except requests.RequestException as e:
            # Update document with error
            document.cache_status = "failed"
            document.cache_error = f"Failed to download: {str(e)}"
            self.repo.commit()

            raise HTTPException(
                status_code=500,
                detail=f"Failed to download tender file: {str(e)}"
            )

    def get_summary(self) -> DocumentSummary:
        """Get DMS summary statistics."""
        try:
            stats = self.repo.get_storage_summary()
            return DocumentSummary(**stats)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting summary: {str(e)}")

    # ==================== HELPER METHODS ====================

    def _folder_to_response(self, folder) -> Folder:
        """Convert folder ORM model to Pydantic response."""
        return Folder(
            id=folder.id,
            name=folder.name,
            parent_folder_id=folder.parent_folder_id,
            path=folder.path,
            document_count=folder.document_count or 0,
            subfolders=[self._folder_to_response(sf) for sf in (folder.subfolders or [])],
            department=folder.department,
            confidentiality_level=folder.confidentiality_level,
            description=folder.description,
            is_system_folder=folder.is_system_folder,
            created_by=folder.created_by,
            created_at=folder.created_at,
            updated_at=folder.updated_at
        )

    def _document_to_response(self, document) -> Document:
        """Convert document ORM model to Pydantic response."""
        return Document(
            id=document.id,
            name=document.name,
            original_filename=document.original_filename,
            mime_type=document.mime_type,
            size_bytes=document.size_bytes,
            storage_provider=document.storage_provider,
            storage_path=document.storage_path,
            s3_bucket=document.s3_bucket,
            s3_etag=document.s3_etag,
            s3_version_id=document.s3_version_id,
            category_ids=[c.id for c in (document.categories or [])],
            folder_id=document.folder_id,
            folder_path=document.folder_path,
            status=document.status,
            confidentiality_level=document.confidentiality_level,
            tags=document.tags or [],
            doc_metadata=document.doc_metadata,
            version=document.version,
            uploaded_by=document.uploaded_by,
            created_at=document.created_at,
            updated_at=document.updated_at
        )

    def _folder_permission_to_response(self, permission) -> FolderPermission:
        """Convert folder permission ORM model to Pydantic response."""
        return FolderPermission(
            id=permission.id,
            folder_id=permission.folder_id,
            user_id=permission.user_id,
            department=permission.department,
            permission_level=permission.permission_level,
            inherit_to_subfolders=permission.inherit_to_subfolders,
            granted_by=permission.granted_by,
            granted_at=permission.granted_at,
            valid_until=permission.valid_until
        )

    def _document_permission_to_response(self, permission) -> DocumentPermission:
        """Convert document permission ORM model to Pydantic response."""
        return DocumentPermission(
            id=permission.id,
            user_id=permission.user_id,
            permission_level=permission.permission_level,
            granted_by=permission.granted_by,
            granted_at=permission.granted_at,
            valid_until=permission.valid_until
        )
