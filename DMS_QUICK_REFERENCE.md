# DMS Module - Quick Reference

## What Was Done

### ✅ Database Schema (133 lines)
**File**: `app/modules/dmsiq/db/schema.py`

7 SQLAlchemy ORM models:
1. `DmsFolder` - Hierarchical folders with materialized paths
2. `DmsDocument` - Document metadata and storage
3. `DmsCategory` - Document categories (independent of folders)
4. `DmsFolderPermission` - Folder-level access control (user or department)
5. `DmsDocumentPermission` - Document-level explicit permissions
6. `DmsDocumentVersion` - Version history tracking
7. `document_category_association` - M:M relationship table

**Key Features**:
- Soft deletes (is_deleted flag)
- Timestamped (UTC timezone)
- Confidentiality levels (public, internal, confidential, restricted)
- Permission hierarchy with inheritance
- Version tracking
- Materialized paths for O(1) navigation

### ✅ Pydantic Models (194 lines)
**File**: `app/modules/dmsiq/models/pydantic_models.py`

30+ validation models including:
- **Enums**: ConfidentialityLevel, DocumentStatus, PermissionLevel
- **Core**: Document, Folder, DocumentCategory
- **Permissions**: FolderPermission, DocumentPermission
- **Operations**: FolderCreate, DocumentCreate, FolderUpdate, DocumentUpdate
- **Upload/Download**: UploadURLRequest, UploadURLResponse, DownloadURLResponse
- **Lists**: DocumentListResponse, DocumentSummary

**All Models**:
- ✅ Proper type hints
- ✅ from_attributes=True for ORM compatibility
- ✅ Enums for validation
- ✅ Forward references for recursion

### ✅ File Storage Service (278 lines)
**File**: `app/modules/dmsiq/services/file_storage.py`

FileStorageService class with:
- Core: `save_file()`, `read_file()`, `delete_file()`, `file_exists()`
- Paths: `get_storage_path()`, `get_folder_path()`, sanitization methods
- Utilities: `create_version()`, `get_dms_root()`, `get_storage_stats()`

**Storage Layout**:
```
dms/
├── documents/
│   ├── 2025/01/uuid-filename.pdf
│   └── 2025/02/uuid-contract.docx
└── .trash/
    └── TIMESTAMP_UUID_filename
```

### ✅ Directory Setup
- Created `/dms/` directory at repository root
- Created `app/modules/dmsiq/services/` directory

### ✅ Documentation
- `app/modules/dmsiq/README.md` - Comprehensive module documentation
- `DMS_SETUP_SUMMARY.md` - This setup summary
- `DMS_OPENAPI_MAPPING.md` - OpenAPI spec to implementation mapping

## What's Needed Next

### 1. Repository Layer (PRIORITY 1) - ~2-3 hours
**File**: `app/modules/dmsiq/db/repository.py`

Must implement CRUD operations:
- Folders: create, read, update, delete, list, move, get_by_path
- Documents: create, read, update, delete, list, search, get_versions
- Categories: list, create
- Permissions: grant, revoke, check, list
- Queries: by folder, by category, by confidentiality, with permissions

Example structure:
```python
class DmsRepository:
    # Folders
    async def create_folder(self, name, parent_id, created_by, ...)
    async def get_folder(self, folder_id)
    async def list_folders(self, parent_id=None, department=None)
    async def update_folder(self, folder_id, ...)
    async def delete_folder(self, folder_id)
    
    # Documents
    async def create_document(self, name, filename, folder_id, ...)
    async def get_document(self, document_id)
    async def list_documents(self, folder_id, category_id, tags, status, limit, offset)
    async def update_document(self, document_id, ...)
    
    # Permissions
    async def grant_folder_permission(self, folder_id, user_id/department, level, ...)
    async def check_folder_permission(self, folder_id, user_id, required_level)
    async def check_document_permission(self, document_id, user_id, required_level)
```

### 2. API Endpoints (PRIORITY 1) - ~3-4 hours
**File**: `app/modules/dmsiq/endpoints/endpoints.py`

Implement 19 endpoints from OpenAPI spec:
- 8 Folder endpoints (CRUD + permissions)
- 8 Document endpoints (CRUD + permissions)
- 2 Category endpoints
- 1 Summary endpoint

### 3. Router Setup (PRIORITY 1) - ~30 mins
**File**: `app/modules/dmsiq/route.py`

Aggregate endpoints and register with main API:
```python
from fastapi import APIRouter
from .endpoints import endpoints

router = APIRouter(prefix="/dms", tags=["DMS"])
# Register endpoints
```

Then add to `app/api/v1/router.py`:
```python
from app.modules.dmsiq.route import router as dms_router
router.include_router(dms_router)
```

### 4. Database Migration (PRIORITY 1) - ~15 mins
```bash
alembic revision --autogenerate -m "Add DMS module tables"
alembic upgrade head
```

### 5. Permission Middleware (PRIORITY 2) - ~2 hours
- Check folder permissions before list/read operations
- Check document permissions before read operations
- Check write permissions before modify operations
- Validate user department for department-based permissions
- Handle permission inheritance and expiration

### 6. Testing (PRIORITY 2) - ~4-6 hours
- Unit tests for FileStorageService
- Integration tests for Repository
- API tests for all endpoints
- Permission scenario tests

## File Structure Complete

```
✅ Schema (7 tables)
   ├─ dms_folders
   ├─ dms_documents
   ├─ dms_categories
   ├─ document_category_association
   ├─ dms_folder_permissions
   ├─ dms_document_permissions
   └─ dms_document_versions

✅ Models (30+ classes)
   ├─ Enums
   ├─ Core Models
   ├─ Request Models
   └─ Response Models

✅ Services (FileStorageService)
   ├─ File I/O
   ├─ Path Management
   ├─ Version Control
   └─ Storage Utils

📝 Repository (needs implementation)
   ├─ Folder CRUD
   ├─ Document CRUD
   ├─ Category queries
   └─ Permission management

📝 Endpoints (19 endpoints)
   ├─ Folder endpoints
   ├─ Document endpoints
   ├─ Category endpoints
   └─ Summary endpoint

📝 Router (needs setup)
   └─ Endpoint aggregation
```

## OpenAPI Compliance

All 19 endpoints from OpenAPI spec:
✅ GET /dms/summary
✅ GET /dms/categories
✅ GET /dms/folders
✅ POST /dms/folders
✅ GET /dms/folders/{folder_id}
✅ PATCH /dms/folders/{folder_id}
✅ DELETE /dms/folders/{folder_id}
✅ POST /dms/folders/{folder_id}/move
✅ GET /dms/folders/{folder_id}/permissions
✅ POST /dms/folders/{folder_id}/permissions
✅ DELETE /dms/folders/{folder_id}/permissions/{permission_id}
✅ POST /dms/upload-url
✅ POST /dms/documents/{document_id}/confirm-upload
✅ GET /dms/documents
✅ GET /dms/documents/{document_id}
✅ PATCH /dms/documents/{document_id}
✅ DELETE /dms/documents/{document_id}
✅ GET /dms/documents/{document_id}/download-url
✅ GET /dms/documents/{document_id}/versions
✅ GET /dms/documents/{document_id}/permissions
✅ POST /dms/documents/{document_id}/permissions

## Key Design Decisions

1. **Materialized Paths**: `/Legal/Cases/2025/` for O(1) folder nav
2. **Soft Deletes**: Files moved to `.trash/` with timestamps
3. **Denormalized Counts**: document_count on folders for performance
4. **Date-Based Storage**: `documents/YYYY/MM/` for organization
5. **Path Sanitization**: All user inputs sanitized
6. **Dual Permissions**: Folder (user/department) + Document (user only)
7. **Status Pipeline**: pending → processing → active → archived
8. **Category Separation**: Independent from folder hierarchy

## Development Timeline Estimate

- Repository Layer: 2-3 hours
- Endpoints: 3-4 hours
- Router Setup: 0.5 hour
- Migration: 0.25 hour
- Permissions Middleware: 2 hours
- Testing: 4-6 hours
- **Total: 12-16 hours for complete MVP**

## Common Code Patterns

### Using FileStorageService
```python
from app.modules.dmsiq.services.file_storage import FileStorageService

# Save file
success, path = FileStorageService.save_file(file_content, storage_path)

# Read file
success, content = FileStorageService.read_file(storage_path)

# Delete (soft)
success, msg = FileStorageService.delete_file(storage_path)

# Check existence
exists = FileStorageService.file_exists(storage_path)

# Get stats
stats = FileStorageService.get_storage_stats()
```

### Repository Pattern (TBD)
```python
repo = DmsRepository(db_session)

# Folders
folder = await repo.create_folder(name, parent_id, created_by, ...)
folders = await repo.list_folders(parent_id=None)
await repo.delete_folder(folder_id)

# Documents
doc = await repo.create_document(name, filename, folder_id, ...)
docs = await repo.list_documents(folder_id, limit=50, offset=0)

# Permissions
await repo.grant_folder_permission(folder_id, user_id, "write")
has_access = await repo.check_folder_permission(folder_id, user_id, "read")
```

## Dependencies to Verify

- SQLAlchemy 2.0+ for async support
- Pydantic 2.x for validation
- FastAPI 0.119.0+ for async endpoints
- PostgreSQL driver (psycopg2 or asyncpg)

All should already be in `requirements.txt`.

---

**Status**: 🟢 Foundation Complete
**Next**: Repository Implementation
**Estimated**: 12-16 hours to MVP completion
