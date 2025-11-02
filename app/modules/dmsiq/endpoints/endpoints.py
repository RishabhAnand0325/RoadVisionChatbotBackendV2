"""
DMS API Endpoints
Implements all document management system endpoints following OpenAPI specification.
"""

from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db_session
from app.modules.dmsiq.dependencies import get_dms_service
from app.modules.dmsiq.services.dms_service import DmsService
from app.modules.dmsiq.models.pydantic_models import (
    Folder, FolderCreate, FolderUpdate, FolderMove,
    Document, DocumentCreate, DocumentUpdate,
    DocumentCategory, DocumentSummary, DocumentListResponse,
    FolderPermission, DocumentPermission,
    FolderPermissionGrant, DocumentPermissionGrant,
    UploadURLRequest, UploadURLResponse, ConfirmUploadRequest,
    DownloadURLResponse
)

router = APIRouter()

# ==================== SUMMARY & CATEGORIES ====================

@router.get("/summary", response_model=DocumentSummary, tags=["DMS - Summary"])
def get_dms_summary(service: DmsService = Depends(get_dms_service)):
    """Get DMS summary statistics including total documents, storage used, etc."""
    return service.get_summary()


@router.get("/categories", response_model=List[DocumentCategory], tags=["DMS - Categories"])
def list_categories(service: DmsService = Depends(get_dms_service)):
    """List all available document categories."""
    return service.list_categories()


# ==================== FOLDER ENDPOINTS ====================

@router.get("/folders", response_model=List[Folder], tags=["DMS - Folders"])
def list_folders(
    parent_id: Optional[UUID] = Query(None, description="Filter by parent folder (null for root)"),
    department: Optional[str] = Query(None, description="Filter by department"),
    search: Optional[str] = Query(None, description="Search folder name"),
    service: DmsService = Depends(get_dms_service)
):
    """
    List accessible folders with optional filtering.
    Returns hierarchical folder structure with subfolders.
    """
    if parent_id:
        return service.list_subfolders(parent_id)
    return service.list_root_folders(department=department, search=search)


@router.post("/folders", response_model=Folder, status_code=status.HTTP_201_CREATED, tags=["DMS - Folders"])
def create_folder(
    data: FolderCreate,
    db: Session = Depends(get_db_session),
    service: DmsService = Depends(get_dms_service)
):
    """
    Create a new folder.
    Requires write permission on parent folder if specified.
    """
    # TODO: Add authentication and permission check
    # For now, using a placeholder user ID
    from uuid import uuid4
    created_by = uuid4()

    return service.create_folder(data, created_by=created_by)


@router.get("/folders/{folder_id}", response_model=Folder, tags=["DMS - Folders"])
def get_folder(
    folder_id: UUID,
    service: DmsService = Depends(get_dms_service)
):
    """Get folder details including document count and subfolders."""
    return service.get_folder(folder_id)


@router.patch("/folders/{folder_id}", response_model=Folder, tags=["DMS - Folders"])
def update_folder(
    folder_id: UUID,
    data: FolderUpdate,
    service: DmsService = Depends(get_dms_service)
):
    """
    Update folder metadata (name, description, confidentiality level).
    Requires admin permission on folder.
    """
    return service.update_folder(folder_id, data)


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["DMS - Folders"])
def delete_folder(
    folder_id: UUID,
    service: DmsService = Depends(get_dms_service)
):
    """
    Soft delete folder (must be empty).
    Requires admin permission on folder.
    """
    service.delete_folder(folder_id)


@router.post("/folders/{folder_id}/move", response_model=Folder, tags=["DMS - Folders"])
def move_folder(
    folder_id: UUID,
    data: FolderMove,
    service: DmsService = Depends(get_dms_service)
):
    """
    Move folder to new parent and update materialized paths.
    Requires admin permission on both source and destination.
    """
    return service.move_folder(folder_id, data)


@router.get("/folders/{folder_id}/permissions", response_model=List[FolderPermission], tags=["DMS - Folders"])
def list_folder_permissions(
    folder_id: UUID,
    service: DmsService = Depends(get_dms_service)
):
    """
    Get all permissions for a folder.
    Requires admin permission on folder.
    """
    return service.list_folder_permissions(folder_id)


@router.post("/folders/{folder_id}/permissions", response_model=FolderPermission, status_code=status.HTTP_201_CREATED, tags=["DMS - Folders"])
def grant_folder_permission(
    folder_id: UUID,
    data: FolderPermissionGrant,
    db: Session = Depends(get_db_session),
    service: DmsService = Depends(get_dms_service)
):
    """
    Grant permission to user or department on folder.
    Department admins can only grant permissions on their department's folders.
    """
    # TODO: Add authentication and permission check
    from uuid import uuid4
    granted_by = uuid4()

    return service.grant_folder_permission(
        folder_id=folder_id,
        permission_level=data.permission_level,
        granted_by=granted_by,
        user_id=data.user_id,
        department=data.department,
        inherit_to_subfolders=data.inherit_to_subfolders,
        valid_until=data.valid_until
    )


@router.delete("/folders/{folder_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["DMS - Folders"])
def revoke_folder_permission(
    folder_id: UUID,
    permission_id: UUID,
    service: DmsService = Depends(get_dms_service)
):
    """
    Revoke folder permission.
    Requires admin permission on folder.
    """
    service.revoke_folder_permission(folder_id, permission_id)


# ==================== DOCUMENT ENDPOINTS ====================

@router.post("/file-upload", response_model=Document, tags=["DMS - Documents"])
async def upload_file(
    folder_id: UUID = Form(...),
    file: UploadFile = File(...),
    tags: Optional[List[str]] = Form(None),
    category_id: Optional[UUID] = Form(None),
    confidentiality_level: str = Form("internal"),
    service: DmsService = Depends(get_dms_service)
):
    """
    Directly upload a file to the DMS.
    This endpoint is for Phase 1 (local storage) and bypasses the presigned URL flow.
    """
    # TODO: Add authentication and permission check
    from uuid import uuid4
    uploaded_by = uuid4()
    
    document = await service.upload_document(
        file=file,
        folder_id=folder_id,
        uploaded_by=uploaded_by,
        category_id=category_id,
        tags=tags or [],
        confidentiality_level=confidentiality_level
    )
    return document


@router.post("/upload-url", response_model=UploadURLResponse, tags=["DMS - Documents"])
def generate_upload_url(
    data: UploadURLRequest,
    db: Session = Depends(get_db_session),
    service: DmsService = Depends(get_dms_service)
):
    """
    Generate presigned upload URL for direct file upload from frontend.
    Creates document record in 'pending' status.
    Returns upload URL, document ID, and expiration time.
    """
    # TODO: Add authentication and permission check
    from uuid import uuid4
    uploaded_by = uuid4()

    return service.generate_upload_url(
        filename=data.filename,
        file_size=data.file_size,
        mime_type=data.mime_type,
        folder_id=data.folder_id,
        uploaded_by=uploaded_by,
        category_id=data.category_id,
        tags=data.tags,
        confidentiality_level=data.confidentiality_level
    )


@router.post("/documents/{document_id}/confirm-upload", response_model=Document, tags=["DMS - Documents"])
def confirm_upload(
    document_id: UUID,
    data: ConfirmUploadRequest,
    service: DmsService = Depends(get_dms_service)
):
    """
    Confirm S3/local upload completion.
    Changes document status from 'pending' to 'active'.
    Triggers document processing if needed.
    """
    return service.confirm_upload(
        document_id=document_id,
        s3_etag=data.s3_etag,
        s3_version_id=data.s3_version_id
    )


@router.get("/documents", response_model=DocumentListResponse, tags=["DMS - Documents"])
def list_documents(
    folder_id: Optional[UUID] = Query(None, description="Filter by folder"),
    category_id: Optional[UUID] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Full-text search on name and content"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags (all must match)"),
    status: Optional[str] = Query(None, enum=["active", "archived", "pending", "processing"]),
    limit: int = Query(50, ge=1, le=500, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    service: DmsService = Depends(get_dms_service)
):
    """
    List accessible documents with filtering and pagination.
    Returns documents filtered by user permissions and folder access.
    """
    return service.list_documents(
        folder_id=folder_id,
        category_id=category_id,
        search=search,
        tags=tags,
        status=status,
        limit=limit,
        offset=offset
    )


@router.get("/documents/{document_id}", response_model=Document, tags=["DMS - Documents"])
def get_document(
    document_id: UUID,
    service: DmsService = Depends(get_dms_service)
):
    """Get document details including metadata, versions, and permissions."""
    return service.get_document(document_id)


@router.patch("/documents/{document_id}", response_model=Document, tags=["DMS - Documents"])
def update_document(
    document_id: UUID,
    data: DocumentUpdate,
    service: DmsService = Depends(get_dms_service)
):
    """
    Update document metadata (name, tags, folder, status).
    Requires write permission on document.
    """
    return service.update_document(document_id, data)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["DMS - Documents"])
def delete_document(
    document_id: UUID,
    service: DmsService = Depends(get_dms_service)
):
    """
    Soft delete document (can be recovered).
    Requires write permission on document.
    """
    service.delete_document(document_id)


@router.get("/documents/{document_id}/download", response_class=FileResponse, tags=["DMS - Documents"])
def download_file(
    document_id: UUID,
    service: DmsService = Depends(get_dms_service)
):
    """
    Directly download a file from the DMS.
    """
    full_path, filename = service.get_document_for_download(document_id)

    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on storage."
        )

    return FileResponse(path=full_path, filename=filename)


@router.get("/documents/{document_id}/download-url", response_model=DownloadURLResponse, tags=["DMS - Documents"])
def get_download_url(
    document_id: UUID,
    version_number: Optional[int] = Query(None, description="Specific version to download (defaults to latest)"),
    service: DmsService = Depends(get_dms_service)
):
    """
    Generate presigned S3/local download URL.
    Includes permission check and audit logging.
    """
    return service.generate_download_url(document_id, version_number)


@router.get("/documents/{document_id}/versions", tags=["DMS - Documents"])
def get_document_versions(
    document_id: UUID,
    service: DmsService = Depends(get_dms_service)
):
    """
    Get document version history.
    Returns all versions with metadata (size, uploaded by, timestamp, etc.).
    """
    versions = service.repo.get_document_versions(document_id)
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "size_bytes": v.size_bytes,
            "uploaded_by": v.uploaded_by,
            "change_summary": v.change_summary,
            "created_at": v.created_at
        }
        for v in versions
    ]


@router.get("/documents/{document_id}/permissions", response_model=List[DocumentPermission], tags=["DMS - Documents"])
def list_document_permissions(
    document_id: UUID,
    service: DmsService = Depends(get_dms_service)
):
    """
    Get explicit document-level permissions.
    Requires admin permission on document.
    """
    return service.list_document_permissions(document_id)


@router.post("/documents/{document_id}/permissions", response_model=DocumentPermission, status_code=status.HTTP_201_CREATED, tags=["DMS - Documents"])
def grant_document_permission(
    document_id: UUID,
    data: DocumentPermissionGrant,
    db: Session = Depends(get_db_session),
    service: DmsService = Depends(get_dms_service)
):
    """
    Grant explicit permission to user on document.
    Requires admin permission on document.
    """
    # TODO: Add authentication and permission check
    from uuid import uuid4
    granted_by = uuid4()

    return service.grant_document_permission(
        document_id=document_id,
        user_id=data.user_id,
        permission_level=data.permission_level,
        granted_by=granted_by,
        valid_until=data.valid_until
    )


@router.delete("/documents/{document_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["DMS - Documents"])
def revoke_document_permission(
    document_id: UUID,
    permission_id: UUID,
    service: DmsService = Depends(get_dms_service)
):
    """
    Revoke explicit document permission.
    Requires admin permission on document.
    """
    service.revoke_document_permission(document_id, permission_id)
