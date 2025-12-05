# DMS (Document Management System) Module

## Overview

The DMS module provides comprehensive document and folder management capabilities for the Ceigall Suite platform. It implements a hierarchical folder structure with fine-grained permission controls and supports document categorization.

## Architecture

### Database Schema

The DMS module uses the following database tables:

#### `dms_folders`
- **Purpose**: Hierarchical folder structure with materialized paths
- **Key Fields**:
  - `id`: UUID primary key
  - `parent_folder_id`: Self-referencing foreign key for hierarchy
  - `path`: Materialized path (e.g., `/Legal/Cases/2025/`) for O(1) navigation
  - `document_count`: Denormalized count of documents in folder
  - `confidentiality_level`: Access control level (public, internal, confidential, restricted)
  - `created_by`: UUID of user who created the folder
  - `is_deleted`: Boolean flag for soft delete

#### `dms_documents`
- **Purpose**: Document metadata and storage information
- **Key Fields**:
  - `id`: UUID primary key
  - `original_filename`: Original filename as uploaded
  - `mime_type`: File MIME type
  - `size_bytes`: File size in bytes
  - `storage_provider`: Storage backend ('local' for MVP, 's3' for future)
  - `storage_path`: Relative path to file on disk/S3
  - `status`: Document lifecycle (pending, processing, active, archived)
  - `confidentiality_level`: Access control level
  - `tags`: Array of string tags for categorization
  - `version`: Current version number (for versioning support)
  - `uploaded_by`: UUID of user who uploaded

#### `dms_categories`
- **Purpose**: Document categories (separate from folders)
- **Key Fields**:
  - `id`: UUID primary key
  - `name`: Category name (unique)
  - `color`: Hex color code for UI
  - `icon`: Icon identifier
- **Note**: Categories are independent of folders and a document can have multiple categories

#### `document_category_association`
- **Purpose**: Many-to-many relationship between documents and categories

#### `dms_folder_permissions`
- **Purpose**: Fine-grained access control for folders
- **Key Fields**:
  - `user_id`: Target user (OR department, mutually exclusive)
  - `department`: Target department
  - `permission_level`: 'read', 'write', or 'admin'
  - `inherit_to_subfolders`: Boolean flag to cascade permissions
  - `valid_until`: Optional expiration date for time-limited permissions

#### `dms_document_permissions`
- **Purpose**: Explicit document-level permissions
- **Key Fields**:
  - `user_id`: Target user (required)
  - `permission_level`: 'read', 'write', or 'admin'
  - `valid_until`: Optional expiration date

#### `dms_document_versions`
- **Purpose**: Document version history
- **Key Fields**:
  - `version_number`: Sequential version number
  - `storage_path`: Storage location of this version
  - `change_summary`: Description of changes in this version
  - `uploaded_by`: User who uploaded this version

### File Storage (Local Disk MVP)

Files are stored in the `dms/` directory at the repository root with the following structure:

```
dms/
├── documents/
│   ├── 2025/
│   │   ├── 01/
│   │   │   ├── {document_id}-filename.pdf
│   │   │   └── {document_id}-contract.docx
│   │   └── 02/
│   │       └── {document_id}-report.xlsx
│   └── 2024/
└── .trash/  # Soft-deleted files (timestamped for recovery)
```

**Storage Path Format**: `documents/YYYY/MM/{UUID}-{sanitized_filename}`

### Pydantic Models

All models are defined in `models/pydantic_models.py`:

#### Enums
- `ConfidentialityLevel`: public, internal, confidential, restricted
- `DocumentStatus`: pending, processing, active, archived
- `PermissionLevel`: read, write, admin

#### Core Models
- `DocumentCategory`: Category definition with color and icon
- `Document`: Full document with metadata and relationships
- `Folder`: Hierarchical folder with subfolders and document count
- `FolderPermission`: Folder-level access control
- `DocumentPermission`: Document-level access control
- `DocumentVersion`: Version history entry

#### Request/Response Models
- `FolderCreate`, `FolderUpdate`, `FolderMove`: Folder operations
- `DocumentCreate`, `DocumentUpdate`: Document operations
- `UploadURLRequest`, `UploadURLResponse`: Upload workflow
- `ConfirmUploadRequest`: Upload completion confirmation
- `DownloadURLResponse`: Download URL generation
- `DocumentSummary`: Statistics endpoint
- `DocumentListResponse`: Paginated document listing

### File Storage Service

The `FileStorageService` class in `services/file_storage.py` provides:

**Core Operations**:
- `save_file()`: Write file to disk with automatic directory creation
- `read_file()`: Read file from disk
- `delete_file()`: Soft delete with trash functionality
- `file_exists()`: Check file existence
- `get_file_size()`: Get file size without loading content

**Path Operations**:
- `get_storage_path()`: Generate storage path with date-based organization
- `get_folder_path()`: Generate hierarchical folder path
- `_sanitize_filename()`: Remove dangerous characters while preserving extension
- `_sanitize_path_component()`: Sanitize folder names

**Utilities**:
- `create_version()`: Create version copy of existing file
- `get_dms_root()`: Get root directory path
- `get_storage_stats()`: Get storage usage statistics
- `_cleanup_empty_dirs()`: Recursive cleanup of empty directories

## API Endpoints

### Summary & Categories
- `GET /dms/summary` - Get storage statistics
- `GET /dms/categories` - List all document categories

### Folder Management
- `GET /dms/folders` - List folders (hierarchical)
- `POST /dms/folders` - Create folder
- `GET /dms/folders/{folder_id}` - Get folder details
- `PATCH /dms/folders/{folder_id}` - Update folder metadata
- `DELETE /dms/folders/{folder_id}` - Soft delete folder
- `POST /dms/folders/{folder_id}/move` - Move folder to new parent
- `GET /dms/folders/{folder_id}/permissions` - List folder permissions
- `POST /dms/folders/{folder_id}/permissions` - Grant permission
- `DELETE /dms/folders/{folder_id}/permissions/{permission_id}` - Revoke permission

### Document Upload
- `POST /dms/upload-url` - Get presigned upload URL
- `POST /dms/documents/{document_id}/confirm-upload` - Confirm upload completion

### Document Management
- `GET /dms/documents` - List documents (paginated, filtered)
- `GET /dms/documents/{document_id}` - Get document details
- `PATCH /dms/documents/{document_id}` - Update document metadata
- `DELETE /dms/documents/{document_id}` - Soft delete document
- `GET /dms/documents/{document_id}/download-url` - Get download URL
- `GET /dms/documents/{document_id}/versions` - Get version history
- `GET /dms/documents/{document_id}/permissions` - List document permissions
- `POST /dms/documents/{document_id}/permissions` - Grant permission

## MVP Implementation Notes

### Phase 1 (Current)
- ✅ Database schemas defined
- ✅ Pydantic models defined
- ✅ Local file storage service implemented
- ⏳ Repository layer (CRUD operations) - Next
- ⏳ API endpoints - Next
- ⏳ Permission checking middleware - Next

### Phase 2 (Future)
- S3 storage provider support
- Presigned URLs (for S3 upload/download)
- Celery tasks for document processing
- Full-text search on document content
- Document preview generation
- Audit logging

### Key Design Decisions

1. **Materialized Paths**: Folders use materialized paths (e.g., `/Legal/Cases/2025/`) instead of recursive queries for O(1) navigation performance

2. **Soft Deletes**: Both folders and documents use soft delete flags to maintain referential integrity and allow recovery

3. **Document vs. Folder Permissions**:
   - Folder permissions: Can target users or departments, support inheritance
   - Document permissions: Direct user access only

4. **Categories vs. Folders**:
   - Folders: Hierarchical structure for organization
   - Categories: Flat, multi-assignable tags for document classification

5. **Local Storage MVP**: Files stored on disk with date-based organization (`documents/YYYY/MM/`) for easy backup and migration

## Configuration

Add to `.env`:
```bash
DMS_ROOT_PATH=/path/to/dms  # Optional, defaults to ./dms
DMS_MAX_FILE_SIZE=104857600  # 100MB in bytes
```

## Database Migration

A migration file will need to be created to set up all DMS tables:

```bash
cd chatbot-backend
alembic revision --autogenerate -m "Add DMS module tables"
alembic upgrade head
```

## Security Considerations

1. **File Path Traversal**: All paths are sanitized to prevent directory traversal attacks
2. **Permission Checks**: All operations require permission validation against folder/document permissions
3. **Soft Delete**: Deletes are reversible; files move to `.trash/` directory with timestamps
4. **MIME Type Validation**: Upload endpoints validate against allowed MIME types
5. **Confidentiality Levels**: Enforced at both folder and document level

## Future Enhancements

1. **Document Processing Pipeline**: Celery tasks for:
   - PDF text extraction for full-text search
   - Document classification using ML
   - OCR for scanned documents
   - Thumbnail generation

2. **Search**: Full-text search across document content and metadata

3. **Sharing**: Share documents with external parties via secure links

4. **Audit Trail**: Log all access and modifications with user tracking

5. **Storage Analytics**: Dashboard showing storage usage trends
