"""
DMS Repository Layer
Handles all database operations for folders, documents, categories, and permissions.
"""

from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import and_, or_, select, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.modules.dmsiq.db.schema import (
    DmsFolder, DmsDocument, DmsCategory, DmsFolderPermission,
    DmsDocumentPermission, DmsDocumentVersion, document_category_association
)
from app.modules.dmsiq.models.pydantic_models import (
    FolderCreate, FolderUpdate, DocumentCreate, DocumentUpdate,
    ConfidentialityLevel, PermissionLevel
)


class DmsRepository:
    """Repository for DMS operations with comprehensive CRUD and query methods."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ==================== FOLDER OPERATIONS ====================

    def create_folder(
        self,
        name: str,
        created_by: UUID,
        parent_folder_id: Optional[UUID] = None,
        department: Optional[str] = None,
        confidentiality_level: str = ConfidentialityLevel.INTERNAL,
        description: Optional[str] = None,
        is_system_folder: bool = False
    ) -> DmsFolder:
        """Create a new folder with materialized path."""
        # Generate materialized path
        if parent_folder_id:
            parent = self.get_folder(parent_folder_id)
            if not parent:
                raise ValueError(f"Parent folder {parent_folder_id} not found")
            path = f"{parent.path}{name}/"
        else:
            path = f"/{name}/"

        folder = DmsFolder(
            name=name,
            parent_folder_id=parent_folder_id,
            path=path,
            document_count=0,
            department=department,
            confidentiality_level=confidentiality_level,
            description=description,
            is_system_folder=is_system_folder,
            created_by=created_by
        )
        self.db.add(folder)
        self.db.flush()
        return folder

    def get_folder(self, folder_id: UUID) -> Optional[DmsFolder]:
        """Get folder by ID with relationships."""
        return self.db.query(DmsFolder).filter(
            DmsFolder.id == folder_id,
            DmsFolder.is_deleted == False
        ).options(
            joinedload(DmsFolder.documents),
            joinedload(DmsFolder.subfolders),
            joinedload(DmsFolder.permissions)
        ).first()

    def list_folders(
        self,
        parent_id: Optional[UUID] = None,
        department: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[DmsFolder]:
        """List folders with optional filtering."""
        query = self.db.query(DmsFolder).filter(DmsFolder.is_deleted == False)

        if parent_id is not None:
            query = query.filter(DmsFolder.parent_folder_id == parent_id)
        else:
            # Root folders only
            query = query.filter(DmsFolder.parent_folder_id == None)

        if department:
            query = query.filter(DmsFolder.department == department)

        if search:
            query = query.filter(DmsFolder.name.ilike(f"%{search}%"))

        return query.options(
            joinedload(DmsFolder.subfolders),
            joinedload(DmsFolder.documents)
        ).all()

    def update_folder(
        self,
        folder_id: UUID,
        update_data: FolderUpdate
    ) -> Optional[DmsFolder]:
        """Update folder metadata."""
        folder = self.get_folder(folder_id)
        if not folder:
            return None

        if update_data.name:
            folder.name = update_data.name
            # Regenerate path if name changed
            if folder.parent_folder_id:
                parent = self.get_folder(folder.parent_folder_id)
                folder.path = f"{parent.path}{update_data.name}/"
            else:
                folder.path = f"/{update_data.name}/"

        if update_data.description is not None:
            folder.description = update_data.description

        if update_data.confidentiality_level:
            folder.confidentiality_level = update_data.confidentiality_level

        folder.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return folder

    def delete_folder(self, folder_id: UUID) -> bool:
        """Soft delete folder."""
        folder = self.get_folder(folder_id)
        if not folder:
            return False

        # Check if folder has documents or subfolders
        has_documents = self.db.query(DmsDocument).filter(
            DmsDocument.folder_id == folder_id,
            DmsDocument.is_deleted == False
        ).first() is not None

        has_subfolders = self.db.query(DmsFolder).filter(
            DmsFolder.parent_folder_id == folder_id,
            DmsFolder.is_deleted == False
        ).first() is not None

        if has_documents or has_subfolders:
            raise ValueError("Cannot delete folder with documents or subfolders")

        folder.is_deleted = True
        folder.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return True

    def move_folder(self, folder_id: UUID, new_parent_id: Optional[UUID]) -> Optional[DmsFolder]:
        """Move folder to new parent and update materialized path."""
        folder = self.get_folder(folder_id)
        if not folder:
            return None

        # Generate new path
        if new_parent_id:
            parent = self.get_folder(new_parent_id)
            if not parent:
                raise ValueError(f"Parent folder {new_parent_id} not found")
            new_path = f"{parent.path}{folder.name}/"
        else:
            new_path = f"/{folder.name}/"

        # Update folder
        folder.parent_folder_id = new_parent_id
        folder.path = new_path

        # Update all subfolders' paths (recursively)
        self._update_subfolder_paths(folder_id, new_path)

        folder.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return folder

    def _update_subfolder_paths(self, folder_id: UUID, new_parent_path: str) -> None:
        """Recursively update materialized paths for subfolders."""
        subfolders = self.db.query(DmsFolder).filter(
            DmsFolder.parent_folder_id == folder_id,
            DmsFolder.is_deleted == False
        ).all()

        for subfolder in subfolders:
            new_path = f"{new_parent_path}{subfolder.name}/"
            subfolder.path = new_path
            # Recursively update children
            self._update_subfolder_paths(subfolder.id, new_path)

    def get_folder_by_path(self, path: str) -> Optional[DmsFolder]:
        """Get folder by materialized path."""
        return self.db.query(DmsFolder).filter(
            DmsFolder.path == path,
            DmsFolder.is_deleted == False
        ).first()

    # ==================== DOCUMENT OPERATIONS ====================

    def create_document(
        self,
        name: str,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
        uploaded_by: UUID,
        folder_id: Optional[UUID] = None,
        confidentiality_level: str = ConfidentialityLevel.INTERNAL,
        tags: Optional[List[str]] = None,
        doc_metadata: Optional[dict] = None,
        status: str = "pending"
    ) -> DmsDocument:
        """Create a new document."""
        from app.modules.dmsiq.services.file_storage import FileStorageService

        # Get folder path if folder exists
        folder_path = None
        if folder_id:
            folder = self.get_folder(folder_id)
            if folder:
                folder_path = folder.path
                # Increment folder document count
                folder.document_count = (folder.document_count or 0) + 1

        document = DmsDocument(
            name=name,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path="",  # Placeholder, will be set below
            folder_id=folder_id,
            folder_path=folder_path,
            status=status,
            confidentiality_level=confidentiality_level,
            tags=tags or [],
            doc_metadata=doc_metadata,
            version=1,
            uploaded_by=uploaded_by,
            storage_provider="local"
        )
        self.db.add(document)
        self.db.flush()  # Get ID

        # Set storage path based on ID
        document.storage_path = FileStorageService.get_storage_path(document.id, original_filename)
        self.db.flush()  # Save path

        return document

    def get_document(self, document_id: UUID) -> Optional[DmsDocument]:
        """Get document by ID with relationships."""
        return self.db.query(DmsDocument).filter(
            DmsDocument.id == document_id,
            DmsDocument.is_deleted == False
        ).options(
            joinedload(DmsDocument.folder),
            joinedload(DmsDocument.categories),
            joinedload(DmsDocument.versions),
            joinedload(DmsDocument.permissions)
        ).first()

    def list_documents(
        self,
        folder_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        confidentiality_level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[DmsDocument], int]:
        """List documents with filtering, returns (documents, total_count)."""
        query = self.db.query(DmsDocument).filter(DmsDocument.is_deleted == False)

        if folder_id:
            query = query.filter(DmsDocument.folder_id == folder_id)

        if category_id:
            query = query.join(DmsDocument.categories).filter(DmsCategory.id == category_id)

        if search:
            query = query.filter(
                or_(
                    DmsDocument.name.ilike(f"%{search}%"),
                    DmsDocument.original_filename.ilike(f"%{search}%")
                )
            )

        if tags:
            # Documents must contain all specified tags
            for tag in tags:
                query = query.filter(DmsDocument.tags.contains([tag]))

        if status:
            query = query.filter(DmsDocument.status == status)

        if confidentiality_level:
            query = query.filter(DmsDocument.confidentiality_level == confidentiality_level)

        # Get total count before pagination
        total = query.count()

        # Apply pagination
        documents = query.options(
            joinedload(DmsDocument.folder),
            joinedload(DmsDocument.categories),
            joinedload(DmsDocument.versions)
        ).offset(offset).limit(limit).all()

        return documents, total

    def update_document(
        self,
        document_id: UUID,
        update_data: DocumentUpdate
    ) -> Optional[DmsDocument]:
        """Update document metadata."""
        document = self.get_document(document_id)
        if not document:
            return None

        if update_data.name:
            document.name = update_data.name

        if update_data.folder_id is not None:
            old_folder = document.folder
            new_folder = self.get_folder(update_data.folder_id) if update_data.folder_id else None

            # Update folder document counts
            if old_folder:
                old_folder.document_count = max(0, (old_folder.document_count or 1) - 1)
            if new_folder:
                new_folder.document_count = (new_folder.document_count or 0) + 1

            document.folder_id = update_data.folder_id
            document.folder_path = new_folder.path if new_folder else None

        if update_data.tags is not None:
            document.tags = update_data.tags

        if update_data.status:
            document.status = update_data.status

        if update_data.confidentiality_level:
            document.confidentiality_level = update_data.confidentiality_level

        document.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return document

    def delete_document(self, document_id: UUID) -> bool:
        """Soft delete document."""
        document = self.get_document(document_id)
        if not document:
            return False

        document.is_deleted = True
        document.updated_at = datetime.now(timezone.utc)

        # Decrement folder document count
        if document.folder:
            document.folder.document_count = max(0, (document.folder.document_count or 1) - 1)

        self.db.flush()
        return True

    # ==================== CATEGORY OPERATIONS ====================

    def get_categories(self) -> List[DmsCategory]:
        """Get all document categories."""
        return self.db.query(DmsCategory).all()

    def get_category(self, category_id: UUID) -> Optional[DmsCategory]:
        """Get category by ID."""
        return self.db.query(DmsCategory).filter(DmsCategory.id == category_id).first()

    def create_category(self, name: str, color: Optional[str] = None, icon: Optional[str] = None) -> DmsCategory:
        """Create a new category."""
        try:
            category = DmsCategory(name=name, color=color, icon=icon)
            self.db.add(category)
            self.db.flush()
            return category
        except IntegrityError:
            self.db.rollback()
            raise ValueError(f"Category '{name}' already exists")

    def add_document_category(self, document_id: UUID, category_id: UUID) -> bool:
        """Add a category to a document."""
        document = self.get_document(document_id)
        category = self.get_category(category_id)

        if not document or not category:
            return False

        # Check if already associated
        existing = self.db.query(document_category_association).filter(
            and_(
                document_category_association.c.document_id == document_id,
                document_category_association.c.category_id == category_id
            )
        ).first()

        if not existing:
            stmt = document_category_association.insert().values(
                document_id=document_id,
                category_id=category_id
            )
            self.db.execute(stmt)
            self.db.flush()

        return True

    def remove_document_category(self, document_id: UUID, category_id: UUID) -> bool:
        """Remove a category from a document."""
        stmt = document_category_association.delete().where(
            and_(
                document_category_association.c.document_id == document_id,
                document_category_association.c.category_id == category_id
            )
        )
        self.db.execute(stmt)
        self.db.flush()
        return True

    # ==================== PERMISSION OPERATIONS ====================

    def grant_folder_permission(
        self,
        folder_id: UUID,
        permission_level: str,
        granted_by: UUID,
        user_id: Optional[UUID] = None,
        department: Optional[str] = None,
        inherit_to_subfolders: bool = False,
        valid_until: Optional[datetime] = None
    ) -> DmsFolderPermission:
        """Grant folder permission to user or department."""
        if not user_id and not department:
            raise ValueError("Either user_id or department must be provided")

        permission = DmsFolderPermission(
            folder_id=folder_id,
            user_id=user_id,
            department=department,
            permission_level=permission_level,
            inherit_to_subfolders=inherit_to_subfolders,
            granted_by=granted_by,
            valid_until=valid_until
        )
        self.db.add(permission)
        self.db.flush()
        return permission

    def get_folder_permissions(self, folder_id: UUID) -> List[DmsFolderPermission]:
        """Get all permissions for a folder."""
        return self.db.query(DmsFolderPermission).filter(
            DmsFolderPermission.folder_id == folder_id
        ).all()

    def revoke_folder_permission(self, permission_id: UUID) -> bool:
        """Revoke a folder permission."""
        permission = self.db.query(DmsFolderPermission).filter(
            DmsFolderPermission.id == permission_id
        ).first()

        if permission:
            self.db.delete(permission)
            self.db.flush()
            return True
        return False

    def check_folder_permission(
        self,
        folder_id: UUID,
        user_id: UUID,
        user_department: Optional[str] = None,
        required_level: str = "read"
    ) -> bool:
        """Check if user has required permission on folder."""
        # Check direct user permission
        user_permission = self.db.query(DmsFolderPermission).filter(
            and_(
                DmsFolderPermission.folder_id == folder_id,
                DmsFolderPermission.user_id == user_id,
                DmsFolderPermission.permission_level.in_(self._get_required_permissions(required_level))
            )
        ).first()

        if user_permission and self._is_permission_valid(user_permission):
            return True

        # Check department permission if user has department
        if user_department:
            dept_permission = self.db.query(DmsFolderPermission).filter(
                and_(
                    DmsFolderPermission.folder_id == folder_id,
                    DmsFolderPermission.department == user_department,
                    DmsFolderPermission.permission_level.in_(self._get_required_permissions(required_level))
                )
            ).first()

            if dept_permission and self._is_permission_valid(dept_permission):
                return True

        # Check parent folder permissions if inherit_to_subfolders is set
        folder = self.get_folder(folder_id)
        if folder and folder.parent_folder_id:
            parent_permission = self.db.query(DmsFolderPermission).filter(
                and_(
                    DmsFolderPermission.folder_id == folder.parent_folder_id,
                    DmsFolderPermission.inherit_to_subfolders == True
                )
            ).first()

            if parent_permission:
                return self.check_folder_permission(
                    folder.parent_folder_id,
                    user_id,
                    user_department,
                    required_level
                )

        return False

    def grant_document_permission(
        self,
        document_id: UUID,
        user_id: UUID,
        permission_level: str,
        granted_by: UUID,
        valid_until: Optional[datetime] = None
    ) -> DmsDocumentPermission:
        """Grant document permission to user."""
        permission = DmsDocumentPermission(
            document_id=document_id,
            user_id=user_id,
            permission_level=permission_level,
            granted_by=granted_by,
            valid_until=valid_until
        )
        self.db.add(permission)
        self.db.flush()
        return permission

    def get_document_permissions(self, document_id: UUID) -> List[DmsDocumentPermission]:
        """Get all permissions for a document."""
        return self.db.query(DmsDocumentPermission).filter(
            DmsDocumentPermission.document_id == document_id
        ).all()

    def revoke_document_permission(self, permission_id: UUID) -> bool:
        """Revoke a document permission."""
        permission = self.db.query(DmsDocumentPermission).filter(
            DmsDocumentPermission.id == permission_id
        ).first()

        if permission:
            self.db.delete(permission)
            self.db.flush()
            return True
        return False

    def check_document_permission(
        self,
        document_id: UUID,
        user_id: UUID,
        required_level: str = "read"
    ) -> bool:
        """Check if user has required permission on document."""
        document = self.get_document(document_id)
        if not document:
            return False

        # Check document-specific permission
        doc_permission = self.db.query(DmsDocumentPermission).filter(
            and_(
                DmsDocumentPermission.document_id == document_id,
                DmsDocumentPermission.user_id == user_id,
                DmsDocumentPermission.permission_level.in_(self._get_required_permissions(required_level))
            )
        ).first()

        if doc_permission and self._is_permission_valid(doc_permission):
            return True

        # Fall back to folder permission
        if document.folder_id:
            return self.check_folder_permission(document.folder_id, user_id, required_level=required_level)

        return False

    # ==================== VERSION OPERATIONS ====================

    def create_document_version(
        self,
        document_id: UUID,
        storage_path: str,
        size_bytes: int,
        uploaded_by: UUID,
        change_summary: Optional[str] = None,
        s3_etag: Optional[str] = None,
        s3_version_id: Optional[str] = None
    ) -> DmsDocumentVersion:
        """Create a new version of a document."""
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Get next version number
        latest_version = self.db.query(func.max(DmsDocumentVersion.version_number)).filter(
            DmsDocumentVersion.document_id == document_id
        ).scalar() or 0

        version = DmsDocumentVersion(
            document_id=document_id,
            version_number=latest_version + 1,
            storage_path=storage_path,
            size_bytes=size_bytes,
            uploaded_by=uploaded_by,
            change_summary=change_summary,
            s3_etag=s3_etag,
            s3_version_id=s3_version_id
        )
        self.db.add(version)

        # Update document version count
        document.version = latest_version + 1
        document.updated_at = datetime.now(timezone.utc)

        self.db.flush()
        return version

    def get_document_versions(self, document_id: UUID) -> List[DmsDocumentVersion]:
        """Get all versions of a document."""
        return self.db.query(DmsDocumentVersion).filter(
            DmsDocumentVersion.document_id == document_id
        ).order_by(DmsDocumentVersion.version_number.desc()).all()

    # ==================== UTILITY METHODS ====================

    @staticmethod
    def _get_required_permissions(required_level: str) -> List[str]:
        """Get list of permission levels that satisfy the requirement."""
        permission_hierarchy = {
            "read": ["read", "write", "admin"],
            "write": ["write", "admin"],
            "admin": ["admin"]
        }
        return permission_hierarchy.get(required_level, [])

    @staticmethod
    def _is_permission_valid(permission) -> bool:
        """Check if permission is still valid (not expired)."""
        if permission.valid_until is None:
            return True
        return datetime.now(timezone.utc) < permission.valid_until

    def get_storage_summary(self) -> dict:
        """Get storage statistics for summary endpoint."""
        total_size = self.db.query(func.sum(DmsDocument.size_bytes)).filter(
            DmsDocument.is_deleted == False
        ).scalar() or 0

        total_documents = self.db.query(func.count(DmsDocument.id)).filter(
            DmsDocument.is_deleted == False
        ).scalar() or 0

        recent_uploads = self.db.query(func.count(DmsDocument.id)).filter(
            and_(
                DmsDocument.is_deleted == False,
                DmsDocument.created_at >= datetime.now(timezone.utc).replace(day=1)
            )
        ).scalar() or 0

        shared_documents = self.db.query(func.count(DmsDocument.id)).filter(
            DmsDocument.is_deleted == False
        ).join(DmsDocumentPermission).distinct().scalar() or 0

        def bytes_to_human(bytes_val):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.2f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.2f} TB"

        return {
            "total_documents": total_documents,
            "recent_uploads": recent_uploads,
            "storage_used": bytes_to_human(total_size),
            "shared_documents": shared_documents
        }

    def commit(self) -> None:
        """Commit all pending changes."""
        self.db.commit()

    def rollback(self) -> None:
        """Rollback all pending changes."""
        self.db.rollback()
