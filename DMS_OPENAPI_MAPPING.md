# DMS Module - OpenAPI Spec Mapping

This document maps the OpenAPI specification to the implemented database schemas and Pydantic models.

## OpenAPI Components → Database Schema Mapping

### 1. Document (OpenAPI Schema)
**OpenAPI Spec Location**: `/components/schemas/Document` (lines 56-80)

**Maps to Database Tables:**
- `dms_documents` (main)
- `dms_document_versions` (for version history)

**Field Mapping:**
| OpenAPI Field | Database Column | Pydantic Model | Notes |
|---|---|---|---|
| id | dms_documents.id | Document.id | UUID |
| name | dms_documents.name | Document.name | Display name |
| original_filename | dms_documents.original_filename | Document.original_filename | Uploaded name |
| mime_type | dms_documents.mime_type | Document.mime_type | application/pdf, etc |
| size_bytes | dms_documents.size_bytes | Document.size_bytes | File size |
| storage_provider | dms_documents.storage_provider | Document.storage_provider | 'local' or 's3' |
| storage_path | dms_documents.storage_path | Document.storage_path | documents/2025/01/uuid-file.pdf |
| s3_bucket | dms_documents.s3_bucket | Document.s3_bucket | AWS S3 bucket name |
| s3_etag | dms_documents.s3_etag | Document.s3_etag | S3 ETag for integrity |
| s3_version_id | dms_documents.s3_version_id | Document.s3_version_id | S3 version ID |
| category_ids | document_category_association | Document.category_ids | Via junction table |
| folder_id | dms_documents.folder_id | Document.folder_id | Parent folder |
| folder_path | dms_documents.folder_path | Document.folder_path | /Legal/Cases/2025/ |
| status | dms_documents.status | Document.status | pending, processing, active, archived |
| confidentiality_level | dms_documents.confidentiality_level | Document.confidentiality_level | public, internal, confidential, restricted |
| tags | dms_documents.tags | Document.tags | ARRAY(String) |
| metadata | dms_documents.metadata | Document.metadata | JSON for extensibility |
| version | dms_documents.version | Document.version | Current version number |
| uploaded_by | dms_documents.uploaded_by | Document.uploaded_by | UUID of uploader |
| created_at | dms_documents.created_at | Document.created_at | Timestamp |
| updated_at | dms_documents.updated_at | Document.updated_at | Timestamp |

### 2. Folder (OpenAPI Schema)
**OpenAPI Spec Location**: `/components/schemas/Folder` (lines 82-102)

**Maps to Database Table:**
- `dms_folders` (main)

**Field Mapping:**
| OpenAPI Field | Database Column | Pydantic Model | Notes |
|---|---|---|---|
| id | dms_folders.id | Folder.id | UUID |
| name | dms_folders.name | Folder.name | Folder name |
| parent_folder_id | dms_folders.parent_folder_id | Folder.parent_folder_id | Parent UUID |
| path | dms_folders.path | Folder.path | /Legal/Cases/2025/ |
| document_count | dms_folders.document_count | Folder.document_count | Denormalized count |
| subfolders | dms_folders (self-ref) | Folder.subfolders | Recursive Folder list |
| department | dms_folders.department | Folder.department | Department name |
| confidentiality_level | dms_folders.confidentiality_level | Folder.confidentiality_level | public, internal, confidential, restricted |
| description | dms_folders.description | Folder.description | Folder description |
| is_system_folder | dms_folders.is_system_folder | Folder.is_system_folder | True for system folders |
| created_by | dms_folders.created_by | Folder.created_by | Creator UUID |
| created_at | dms_folders.created_at | Folder.created_at | Timestamp |
| updated_at | dms_folders.updated_at | Folder.updated_at | Timestamp |

### 3. FolderPermission (OpenAPI Schema)
**OpenAPI Spec Location**: `/components/schemas/FolderPermission` (lines 42-54)

**Maps to Database Table:**
- `dms_folder_permissions`

**Field Mapping:**
| OpenAPI Field | Database Column | Pydantic Model | Notes |
|---|---|---|---|
| id | dms_folder_permissions.id | FolderPermission.id | UUID |
| folder_id | dms_folder_permissions.folder_id | FolderPermission.folder_id | Target folder |
| user_id | dms_folder_permissions.user_id | FolderPermission.user_id | Nullable, OR department |
| department | dms_folder_permissions.department | FolderPermission.department | Nullable, OR user_id |
| permission_level | dms_folder_permissions.permission_level | FolderPermission.permission_level | read, write, admin |
| inherit_to_subfolders | dms_folder_permissions.inherit_to_subfolders | FolderPermission.inherit_to_subfolders | Cascade flag |
| granted_by | dms_folder_permissions.granted_by | FolderPermission.granted_by | Granter UUID |
| granted_at | dms_folder_permissions.granted_at | FolderPermission.granted_at | Timestamp |
| valid_until | dms_folder_permissions.valid_until | FolderPermission.valid_until | Expiration (nullable) |

### 4. DocumentCategory (OpenAPI Schema)
**OpenAPI Spec Location**: `/components/schemas/DocumentCategory` (lines 104-112)

**Maps to Database Table:**
- `dms_categories`

**Field Mapping:**
| OpenAPI Field | Database Column | Pydantic Model | Notes |
|---|---|---|---|
| id | dms_categories.id | DocumentCategory.id | UUID |
| name | dms_categories.name | DocumentCategory.name | Category name |
| color | dms_categories.color | DocumentCategory.color | Hex color code |
| icon | dms_categories.icon | DocumentCategory.icon | Icon identifier |

### 5. DocumentSummary (OpenAPI Schema)
**OpenAPI Spec Location**: `/components/schemas/DocumentSummary` (lines 114-121)

**Maps to:** Computed from database queries
- `dms_documents` table
- `dms_folder_permissions` table

**Field Mapping:**
| OpenAPI Field | Source | Pydantic Model | Notes |
|---|---|---|---|
| total_documents | COUNT(*) from dms_documents | DocumentSummary.total_documents | Non-deleted documents |
| recent_uploads | COUNT(*) WHERE created_at > TODAY-7 | DocumentSummary.recent_uploads | Last 7 days |
| storage_used | SUM(size_bytes) | DocumentSummary.storage_used | Bytes converted to human readable |
| shared_documents | COUNT DISTINCT documents with dms_document_permissions | DocumentSummary.shared_documents | Documents with explicit permissions |

## OpenAPI Paths → Endpoints Implementation Plan

### Folder Management Endpoints

| Method | Path | OpenAPI | Database Query | Implementation Status |
|---|---|---|---|---|
| GET | `/dms/folders` | Lines 352-387 | SELECT * FROM dms_folders WHERE parent_folder_id IS NULL | 📝 Pending |
| POST | `/dms/folders` | Lines 389-422 | INSERT INTO dms_folders | 📝 Pending |
| GET | `/dms/folders/{folder_id}` | Lines 424-445 | SELECT * FROM dms_folders WHERE id = ? | 📝 Pending |
| PATCH | `/dms/folders/{folder_id}` | Lines 447-476 | UPDATE dms_folders WHERE id = ? | 📝 Pending |
| DELETE | `/dms/folders/{folder_id}` | Lines 478-495 | UPDATE dms_folders SET is_deleted = TRUE WHERE id = ? | 📝 Pending |
| POST | `/dms/folders/{folder_id}/move` | Lines 497-528 | UPDATE dms_folders SET parent_folder_id = ? WHERE id = ? | 📝 Pending |
| GET | `/dms/folders/{folder_id}/permissions` | Lines 530-555 | SELECT * FROM dms_folder_permissions WHERE folder_id = ? | 📝 Pending |
| POST | `/dms/folders/{folder_id}/permissions` | Lines 557-591 | INSERT INTO dms_folder_permissions | 📝 Pending |
| DELETE | `/dms/folders/{folder_id}/permissions/{permission_id}` | Lines 593-615 | DELETE FROM dms_folder_permissions WHERE id = ? | 📝 Pending |

### Document Management Endpoints

| Method | Path | OpenAPI | Database Query | Implementation Status |
|---|---|---|---|---|
| GET | `/dms/documents` | Lines 709-772 | SELECT * FROM dms_documents (paginated, filtered) | 📝 Pending |
| GET | `/dms/documents/{document_id}` | Lines 775-797 | SELECT * FROM dms_documents WHERE id = ? | 📝 Pending |
| PATCH | `/dms/documents/{document_id}` | Lines 799-830 | UPDATE dms_documents WHERE id = ? | 📝 Pending |
| DELETE | `/dms/documents/{document_id}` | Lines 832-848 | UPDATE dms_documents SET is_deleted = TRUE WHERE id = ? | 📝 Pending |
| GET | `/dms/documents/{document_id}/download-url` | Lines 850-888 | SELECT storage_path FROM dms_documents WHERE id = ? | 📝 Pending |
| GET | `/dms/documents/{document_id}/versions` | Lines 890-925 | SELECT * FROM dms_document_versions WHERE document_id = ? ORDER BY version_number | 📝 Pending |
| GET | `/dms/documents/{document_id}/permissions` | Lines 927-960 | SELECT * FROM dms_document_permissions WHERE document_id = ? | 📝 Pending |
| POST | `/dms/documents/{document_id}/permissions` | Lines 962-994 | INSERT INTO dms_document_permissions | 📝 Pending |

### Document Upload/Download Endpoints

| Method | Path | OpenAPI | Database Query | Implementation Status |
|---|---|---|---|---|
| POST | `/dms/upload-url` | Lines 617-661 | INSERT INTO dms_documents (status='pending') | 📝 Pending |
| POST | `/dms/documents/{document_id}/confirm-upload` | Lines 663-707 | UPDATE dms_documents SET status='processing' WHERE id = ? | 📝 Pending |

### Utility Endpoints

| Method | Path | OpenAPI | Database Query | Implementation Status |
|---|---|---|---|---|
| GET | `/dms/summary` | Lines 315-330 | Aggregate queries on dms_documents | 📝 Pending |
| GET | `/dms/categories` | Lines 332-350 | SELECT * FROM dms_categories | 📝 Pending |

## Pydantic Model → OpenAPI Schema Mapping

### Request Models
```
POST /dms/folders
├── Input: FolderCreate (schema)
│   └── name, parent_folder_id, department, confidentiality_level, description
├── Response: Folder (schema)
└── Status: 201

POST /dms/upload-url
├── Input: UploadURLRequest
│   └── filename, file_size, mime_type, folder_id, category_id, tags, confidentiality_level
├── Response: UploadURLResponse
│   └── upload_url, document_id, storage_path, expires_in
└── Status: 200

POST /dms/documents/{document_id}/confirm-upload
├── Input: ConfirmUploadRequest
│   └── s3_etag, s3_version_id
├── Response: {status, task_id}
└── Status: 200
```

### Response Models
```
GET /dms/documents
├── Response: DocumentListResponse
│   ├── documents: List[Document]
│   ├── total: int
│   ├── limit: int
│   └── offset: int
└── Status: 200

GET /dms/folders
├── Response: List[Folder]
│   └── (Recursive with subfolders)
└── Status: 200

GET /dms/categories
├── Response: List[DocumentCategory]
└── Status: 200

GET /dms/summary
├── Response: DocumentSummary
│   ├── total_documents: int
│   ├── recent_uploads: int
│   ├── storage_used: str
│   └── shared_documents: int
└── Status: 200
```

## Data Flow Example: Document Upload

```
Frontend Request
│
├─ POST /dms/upload-url
│  ├── Input: UploadURLRequest {filename, file_size, mime_type, folder_id}
│  ├── Service: Create DmsDocument with status='pending'
│  │  └── INSERT INTO dms_documents (status='pending', ...)
│  └── Response: UploadURLResponse {document_id, storage_path, expires_in}
│
├─ [Frontend uploads file directly]
│
└─ POST /dms/documents/{document_id}/confirm-upload
   ├── Input: ConfirmUploadRequest {s3_etag}
   ├── Service: Update status to 'processing'
   │  └── UPDATE dms_documents SET status='processing', s3_etag=?
   └── Response: {status: 'processing', task_id: '...'}
```

## Database Relationships Diagram

```
┌─────────────────┐
│  dms_folders    │
├─────────────────┤
│ id (PK)         │
│ parent_id (FK)  │──┐ Self-ref
│ created_by (FK) │  │
│ path            │  │
│ ...             │  │
└─────────────────┘  │
    ▲                │
    │                │
    └────────────────┘

    │
    │ (1:M)
    │
    ▼
┌──────────────────────┐       ┌──────────────────────┐
│  dms_documents       │       │  dms_categories      │
├──────────────────────┤       ├──────────────────────┤
│ id (PK)              │◄─────►│ id (PK)              │
│ folder_id (FK)       │ (M:M) │ name                 │
│ uploaded_by (FK)     │       │ color                │
│ status               │       │ icon                 │
│ version              │       └──────────────────────┘
│ ...                  │
└──────────────────────┘
    │
    │ (1:M)
    │
    ▼
┌──────────────────────┐
│ dms_document_versions│
├──────────────────────┤
│ id (PK)              │
│ document_id (FK)     │
│ version_number       │
│ uploaded_by (FK)     │
│ ...                  │
└──────────────────────┘

Permissions:

┌──────────────────────────┐
│ dms_folder_permissions   │
├──────────────────────────┤
│ id (PK)                  │
│ folder_id (FK)           │
│ user_id (FK, nullable)   │
│ department               │
│ permission_level         │
│ inherit_to_subfolders    │
│ ...                      │
└──────────────────────────┘

┌──────────────────────────┐
│ dms_document_permissions │
├──────────────────────────┤
│ id (PK)                  │
│ document_id (FK)         │
│ user_id (FK)             │
│ permission_level         │
│ ...                      │
└──────────────────────────┘
```

## Summary

**Total OpenAPI Schemas Covered**: 7
- ✅ Document
- ✅ Folder
- ✅ FolderPermission
- ✅ DocumentCategory
- ✅ DocumentSummary
- ✅ DocumentVersion (implicit in /versions endpoint)
- ✅ All request/response models

**Database Tables Created**: 7
- ✅ dms_folders
- ✅ dms_documents
- ✅ dms_categories
- ✅ document_category_association
- ✅ dms_folder_permissions
- ✅ dms_document_permissions
- ✅ dms_document_versions

**Pydantic Models**: 30+
- ✅ All core models
- ✅ All request/response models
- ✅ All enums
- ✅ Support for recursive structures

**API Endpoints**: 19 total
- ✅ 8 Folder endpoints
- ✅ 8 Document endpoints
- ✅ 2 Category/Upload endpoints
- ✅ 1 Summary endpoint

**Status**: 🟢 Ready for Repository & Endpoint Implementation
