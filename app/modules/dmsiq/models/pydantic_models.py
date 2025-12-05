from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum

# ==================== Enums ====================
class ConfidentialityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    ACTIVE = "active"
    ARCHIVED = "archived"

class PermissionLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

# ==================== Document Category ====================
class DocumentCategoryBase(BaseModel):
    name: str
    color: Optional[str] = None
    icon: Optional[str] = None

class DocumentCategoryCreate(DocumentCategoryBase):
    pass

class DocumentCategory(DocumentCategoryBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

# ==================== Document ====================
class DocumentBase(BaseModel):
    name: str
    original_filename: str
    mime_type: str
    size_bytes: Optional[int] = None
    folder_id: Optional[UUID] = None
    tags: List[str] = []
    confidentiality_level: ConfidentialityLevel = ConfidentialityLevel.INTERNAL
    doc_metadata: Optional[Dict[str, Any]] = None

class DocumentCreate(BaseModel):
    filename: str
    file_size: int
    mime_type: str
    folder_id: UUID
    category_id: Optional[UUID] = None
    tags: List[str] = []
    confidentiality_level: ConfidentialityLevel = ConfidentialityLevel.INTERNAL

class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    folder_id: Optional[UUID] = None
    tags: Optional[List[str]] = None
    status: Optional[DocumentStatus] = None
    confidentiality_level: Optional[ConfidentialityLevel] = None

class DocumentVersion(BaseModel):
    id: UUID
    version_number: int
    size_bytes: Optional[int] = None
    uploaded_by: UUID
    change_summary: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class Document(DocumentBase):
    id: UUID
    status: DocumentStatus = DocumentStatus.PENDING
    version: int = 1
    uploaded_by: UUID
    created_at: datetime
    updated_at: datetime
    storage_provider: str = "local"
    storage_path: str
    folder_path: Optional[str] = None
    category_ids: List[UUID] = []
    s3_bucket: Optional[str] = None
    s3_etag: Optional[str] = None
    s3_version_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# ==================== Folder ====================
class FolderBase(BaseModel):
    name: str
    parent_folder_id: Optional[UUID] = None
    department: Optional[str] = None
    confidentiality_level: ConfidentialityLevel = ConfidentialityLevel.INTERNAL
    description: Optional[str] = None

class FolderCreate(FolderBase):
    pass

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    confidentiality_level: Optional[ConfidentialityLevel] = None

class FolderMove(BaseModel):
    new_parent_id: Optional[UUID] = None

class Folder(FolderBase):
    id: UUID
    path: str
    document_count: int = 0
    is_system_folder: bool = False
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    subfolders: List['Folder'] = []
    model_config = ConfigDict(from_attributes=True)

Folder.model_rebuild()

# ==================== Folder Permissions ====================
class FolderPermissionBase(BaseModel):
    permission_level: PermissionLevel
    inherit_to_subfolders: bool = True
    valid_until: Optional[datetime] = None

class FolderPermissionGrant(FolderPermissionBase):
    user_id: Optional[UUID] = None
    department: Optional[str] = None

class FolderPermission(FolderPermissionBase):
    id: UUID
    folder_id: UUID
    user_id: Optional[UUID] = None
    department: Optional[str] = None
    granted_by: UUID
    granted_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ==================== Document Permissions ====================
class DocumentPermissionBase(BaseModel):
    user_id: UUID
    permission_level: PermissionLevel
    valid_until: Optional[datetime] = None

class DocumentPermissionGrant(DocumentPermissionBase):
    pass

class DocumentPermission(DocumentPermissionBase):
    id: UUID
    granted_by: UUID
    granted_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ==================== Upload/Download URLs ====================
class UploadURLRequest(BaseModel):
    filename: str
    file_size: int
    mime_type: str
    folder_id: UUID
    category_id: Optional[UUID] = None
    tags: List[str] = []
    confidentiality_level: ConfidentialityLevel = ConfidentialityLevel.INTERNAL

class UploadURLResponse(BaseModel):
    upload_url: str
    document_id: UUID
    storage_path: str
    expires_in: int

class ConfirmUploadRequest(BaseModel):
    s3_etag: str
    s3_version_id: Optional[str] = None

class DownloadURLResponse(BaseModel):
    download_url: str
    filename: str
    expires_in: int

# ==================== Document Summary ====================
class DocumentSummary(BaseModel):
    total_documents: int
    recent_uploads: int
    storage_used: str
    shared_documents: int

# ==================== List Responses ====================
class DocumentListResponse(BaseModel):
    documents: List[Document]
    total: int
    limit: int
    offset: int
