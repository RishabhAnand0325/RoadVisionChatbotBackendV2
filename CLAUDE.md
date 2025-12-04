# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 🏗️ Architecture Overview

This is a **FastAPI-based RAG (Retrieval Augmented Generation) Chatbot Backend** with a modular architecture. The application integrates multiple services:

### Core Architecture

```
FastAPI Application (app/main.py)
    ↓
API V1 Router (app/api/v1/router.py)
    ├─ Aggregates all module routers
    └─ Registers each module at a specific prefix
        ↓
Module Layer (app/modules/[module_name]/)
    ├─ endpoints/ - FastAPI route handlers
    ├─ services/ - Business logic and external service integration
    ├─ db/ - Database models (SQLAlchemy ORM) and repository layer
    ├─ models/ - Pydantic validation models
    └─ router.py / route.py - Module route aggregation
        ↓
Data Access (Repository Pattern)
    ├─ SQLAlchemy ORM for PostgreSQL
    └─ Vector stores (Weaviate, Chroma)
        ↓
PostgreSQL Database
```

### Module Structure

Each module follows this standard structure:

```
app/modules/[module_name]/
├── db/
│   ├── __init__.py
│   ├── schema.py           # SQLAlchemy ORM models
│   └── repository.py       # Data access methods (Repository pattern)
├── models/
│   └── pydantic_models.py  # Request/response validation models
├── services/
│   ├── __init__.py
│   └── [service_name].py   # Business logic
├── endpoints/
│   ├── __init__.py
│   └── endpoints.py        # FastAPI route handlers
├── dependencies.py         # FastAPI dependency injection
├── router.py / route.py    # Module route aggregation
└── README.md               # Module documentation
```

### Current Modules

| Module | Purpose | Status | Key Feature |
|--------|---------|--------|-------------|
| **askai** | AI/RAG services | Complete | Handles document Q&A via embeddings |
| **auth** | Authentication & authorization | Complete | JWT tokens, user management |
| **tenderiq** | Tender management UI backend | Complete | Tender data visualization |
| **dmsiq** | Document Management System | Complete | Hierarchical folders, versioning, permissions |
| **scraper** | Web scraping for tenders | Active | Now with 24-hour email polling + deduplication |
| **dashboard** | Analytics & reporting | In progress | Future analytics backend |
| **designiq** | Design management | Stub | Placeholder for future features |
| **legaliq** | Legal document management | Stub | Placeholder for future features |
| **health** | Application health checks | Complete | Liveness/readiness probes |

---

## 🗄️ Database Architecture

### PostgreSQL Setup

- **Host**: `localhost:5432` (configurable via `POSTGRES_*` env vars)
- **ORM**: SQLAlchemy with async support
- **Migrations**: Alembic (version control for schema changes)
- **Vector Extension**: pgvector for embedding storage

### Database Layers

1. **ORM Models** (e.g., `app/modules/scraper/db/schema.py`)
   - SQLAlchemy declarative models
   - Define tables, relationships, constraints
   - Use `UUID` for primary keys (PostgreSQL native)

2. **Repository Pattern** (e.g., `app/modules/scraper/db/repository.py`)
   - All database queries go through repository methods
   - Encapsulates query logic
   - Handles session management
   - Example: `ScraperRepository.create_scrape_run()`

3. **Pydantic Models** (e.g., `app/modules/dmsiq/models/pydantic_models.py`)
   - API request/response validation
   - Separate from ORM models
   - Used by FastAPI for automatic OpenAPI schema generation

### Recent Changes: Email Deduplication (Scraper Module)

The scraper now uses **24-hour email polling** instead of relying on the UNSEEN flag:

**Problem Solved**:
- User reads email → email marked as read → listener couldn't find it anymore

**Solution**:
- New `ScrapedEmailLog` table tracks all processed emails
- Composite key: `(email_uid, tender_url)`
- Two deduplication checks:
  1. Email+tender combination already processed?
  2. Tender URL processed from ANY email?
- Daily email cleanup to prevent table bloat

**Files Changed**:
- `app/modules/scraper/db/schema.py` - New `ScrapedEmailLog` model
- `app/modules/scraper/db/repository.py` - 6 new email logging methods
- `app/modules/scraper/email_sender.py` - New `listen_and_get_unprocessed_emails()`
- `app/modules/scraper/main.py` - Redesigned `listen_email()` with polling logic

---

## 📊 Development Commands

### Environment Setup

```bash
# Create virtual environment
python3 -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows)
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Database Migrations (Alembic)

```bash
# Generate new migration (auto-detects schema changes)
alembic revision --autogenerate -m "Description of changes"

# Run all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Check migration status
alembic current

# View migration history
alembic history
```

### Running the Application

```bash
# Development server (auto-reloads on changes)
python app.py

# Production server (requires Gunicorn)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

### Testing

```bash
# Run all tests
pytest

# Run tests in a specific file
pytest tests/test_auth.py

# Run with verbose output
pytest -v

# Run specific test function
pytest tests/test_auth.py::test_login
```

### Code Quality

```bash
# Format code (Black)
black app/

# Check types (Mypy)
mypy app/

# Lint code (Flake8)
flake8 app/
```

---

## 🔑 Key Technologies & Patterns

### FastAPI

- **Router Pattern**: Modular endpoint registration using `include_router()`
- **Dependency Injection**: `Depends()` for service injection, database sessions
- **Validation**: Pydantic models for automatic request/response validation
- **OpenAPI**: Auto-generated documentation at `/docs` and `/redoc`

### SQLAlchemy & Alembic

- **ORM Pattern**: Define tables as Python classes
- **Relationships**: Foreign keys, one-to-many, many-to-many
- **Eager Loading**: Use `joinedload()` to prevent N+1 queries
- **Session Management**: Always use context managers or explicit close

### Repository Pattern

- **Purpose**: Abstract data access layer from business logic
- **Method Naming**: `get_*()`, `list_*()`, `create_*()`, `update_*()`, `delete_*()`, `check_*_permission()`
- **Error Handling**: Raise `HTTPException` for validation errors
- **Transactions**: Explicit `commit()` and `rollback()` for multi-operation safety

### Common Patterns

#### Adding a New Module

1. Create `app/modules/[module_name]/` directory
2. Implement structure:
   ```bash
   mkdir -p app/modules/newmodule/{db,services,endpoints,models}
   touch app/modules/newmodule/{db,services,endpoints,models}/__init__.py
   touch app/modules/newmodule/{dependencies.py,router.py,route.py}
   ```
3. Define ORM models in `db/schema.py`
4. Create repository in `db/repository.py`
5. Implement service in `services/[service_name].py`
6. Create endpoints in `endpoints/endpoints.py`
7. Register in `app/api/v1/router.py`:
   ```python
   from app.modules.newmodule.route import router as newmodule_router
   api_v1_router.include_router(newmodule_router, prefix="/newmodule")
   ```

#### Adding a Database Table

1. Create ORM model in `app/modules/[module]/db/schema.py`
2. Make sure `alembic/env.py` imports the schema:
   ```python
   from app.modules.mymodule.db import schema as mymodule_schema
   ```
3. Generate migration:
   ```bash
   alembic revision --autogenerate -m "Add MyTable"
   ```
4. Review the generated migration file in `alembic/versions/`
5. Run migration:
   ```bash
   alembic upgrade head
   ```

#### Adding a New Endpoint

1. Create function in `app/modules/[module]/endpoints/endpoints.py`:
   ```python
   @router.get("/items/{item_id}", response_model=Item)
   def get_item(item_id: UUID, service: MyService = Depends(get_my_service)):
       return service.get_item(item_id)
   ```
2. Use `Depends()` for:
   - `get_db_session` - Database session (imported from `app.db.database`)
   - `get_my_service()` - Service instance (defined in `dependencies.py`)
   - `get_current_active_user()` - Current user (from auth module)
3. Specify `response_model` for automatic validation and OpenAPI docs
4. Use `status_code` parameter for non-200 responses
5. Add docstring for OpenAPI documentation

#### Permission Checking Pattern

Used heavily in DMS module. Two approaches:

**Option 1: Check in Endpoint**
```python
def delete_document(doc_id: UUID, current_user = Depends(get_current_active_user), ...):
    if not service.check_permission(doc_id, current_user.id, "write"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    service.delete_document(doc_id)
```

**Option 2: Create Permission Dependency**
```python
def require_write_access(doc_id: UUID, current_user = Depends(...)):
    if not service.check_permission(doc_id, current_user.id, "write"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return doc_id

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: UUID = Depends(require_write_access), ...):
    service.delete_document(doc_id)
```

---

## 📝 Important Files & Their Roles

| File | Purpose | Key Concepts |
|------|---------|--------------|
| `app/main.py` | FastAPI app initialization | Middleware setup, router registration |
| `app/config.py` | Configuration management | Environment variables, settings |
| `app/api/v1/router.py` | API v1 route aggregator | Includes all module routers |
| `app/db/database.py` | Database connection setup | SQLAlchemy engine, session factory |
| `alembic/env.py` | Migration environment config | Schema imports, connection details |
| `app/modules/*/db/schema.py` | ORM models | Table definitions |
| `app/modules/*/db/repository.py` | Data access layer | Query methods |
| `app/modules/*/services/*.py` | Business logic | Validation, external API calls |
| `app/modules/*/endpoints/endpoints.py` | API routes | HTTP handlers |

---

## 🔐 Environment Variables

All must be set in `.env` (or environment):

### Essential
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`
- `GOOGLE_API_KEY` - For Google APIs
- `LLAMA_CLOUD_API_KEY` - For PDF parsing
- `WEAVIATE_URL`, `WEAVIATE_API_KEY` - For vector database

### Email (Scraper)
- `SENDER_EMAIL` - Account to receive tender emails
- `SENDER_APP_PASSWORD` - App password (not regular password)
- `RECEIVER_EMAIL` - Where to send processed tenders
- `SMTP_SERVER`, `SMTP_PORT` - Gmail: smtp.gmail.com:587
- `IMAP_SERVER` - Gmail: imap.gmail.com

### JWT (Auth)
- `JWT_SECRET_KEY` - Secret for signing tokens
- `ALGORITHM` - HS256 (default)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token lifetime

---

## 🐛 Debugging Tips

### Database Queries

```python
# Enable SQLAlchemy SQL logging (add to config.py or main.py)
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Check Recent Migrations

```bash
# See migration file contents
cat alembic/versions/[migration_hash].py

# Check what's in database vs what's defined in models
python -c "from app.db.database import Base; print([t.name for t in Base.metadata.tables.values()])"
```

### API Documentation

- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc (ReDoc)
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 404 on new endpoint | Router not registered | Add to `api_v1_router.include_router()` |
| Migration conflicts | Multiple unrelated migrations | Manually edit migration dependencies |
| Permission denied | Missing permission check | Add `check_permission()` call |
| N+1 query problem | Missing eager loading | Add `joinedload()` in query |
| Token validation fails | Wrong secret key | Check `JWT_SECRET_KEY` env var |

---

## 📚 Module-Specific Notes

### Scraper Module (Recent Changes)

**Email Listener Redesign**:
- Old approach: Looked for unread (UNSEEN) emails
- Bug: If user read the email, it disappeared from listener
- New approach: 24-hour polling of ALL emails from sender
- Deduplication: Track by email UID + tender URL
- Database: `ScrapedEmailLog` table with composite unique index

**Key Methods**:
- `listen_and_get_unprocessed_emails()` - Fetch all emails from last 24h
- `has_email_been_processed()` - Check email+tender combo
- `has_tender_url_been_processed()` - Check tender URL from any email
- `log_email_processing()` - Record processing result

**Processing Flow**:
1. Fetch emails every 5 minutes
2. Extract tender URL from each email
3. Check if already processed (2 levels of deduplication)
4. If new → scrape and save to database
5. If duplicate → skip but log

### DMS Module (Document Management)

**Architecture**: 3-layer (Endpoints → Service → Repository)

**Key Features**:
- Hierarchical folders with materialized paths
- Document versioning
- Fine-grained permissions (user/department-based)
- Permission inheritance to subfolders
- Soft deletes with recovery

**Key Methods**: 40+ repository methods, 25+ service methods, 19 API endpoints

**Permission Types**:
- Folder permissions: user OR department, with inherit flag
- Document permissions: user only, fallback to folder permissions
- Levels: read < write < admin
- Expiration: optional `valid_until` timestamp

### Auth Module

**Provides**:
- JWT token generation
- User authentication
- `get_current_active_user()` dependency for endpoint protection

**Usage in Other Modules**:
```python
from app.modules.auth.services.auth_service import get_current_active_user

def protected_endpoint(current_user = Depends(get_current_active_user)):
    return {"user_id": current_user.id}
```

### AskAI Module (RAG)

**Purpose**: Document question-answering

**Flow**:
1. User uploads PDF/Excel → Chunked and embedded
2. User asks question → Semantic search for relevant chunks
3. Chunks + question → LLM for answer generation
4. Answer returned with source documents

**Vector Stores**: Weaviate (primary), Chroma (local fallback)

---

## 🔄 Git Workflow

### Branch Naming

- `main` - Production ready (stable)
- `master` - Development main branch
- `develop/[feature]` - Feature branches
- `fix/[issue]` - Bug fix branches

### Commit Messages

Follow conventional commits:
```
feat: Add new feature
fix: Fix a bug
chore: Maintenance or tooling
docs: Documentation changes
refactor: Code refactoring without feature changes
```

Example:
```
feat: Add 24-hour email polling with deduplication

- Replace UNSEEN flag approach
- Add ScrapedEmailLog table
- Implement composite key deduplication
- Create 6 new repository methods
```

### Before Committing

1. Run tests: `pytest`
2. Check types: `mypy app/`
3. Format code: `black app/`
4. No secrets in commit!

---

## 🎯 Next Steps / TODO

### High Priority
- [ ] Add integration tests for all 19 DMS endpoints
- [ ] Implement real authentication in DMS endpoints (replace uuid4() placeholders)
- [ ] Add audit logging for DMS operations
- [ ] Implement S3 storage backend for DMS

### Medium Priority
- [ ] Add rate limiting to API endpoints
- [ ] Implement request/response caching
- [ ] Add comprehensive error logging
- [ ] Create admin dashboard for monitoring

### Low Priority
- [ ] Complete Dashboard module
- [ ] Implement DesignIQ module
- [ ] Implement LegalIQ module
- [ ] Add WebSocket support for real-time updates

---

## 📖 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM Guide](https://docs.sqlalchemy.org/en/20/orm/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

---

**Last Updated**: November 3, 2024
**Current Version**: 1.0.0
**Maintained By**: Development Team
