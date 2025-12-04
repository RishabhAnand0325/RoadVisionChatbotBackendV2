import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, JSON, Boolean, Table, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship, backref

from app.db.database import Base

# Association table for many-to-many relationship between documents and categories
document_category_association = Table(
    'document_category_association',
    Base.metadata,
    Column('document_id', UUID(as_uuid=True), ForeignKey('dms_documents.id'), primary_key=True),
    Column('category_id', UUID(as_uuid=True), ForeignKey('dms_categories.id'), primary_key=True)
)

class DmsFolder(Base):
    __tablename__ = 'dms_folders'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    parent_folder_id = Column(UUID(as_uuid=True), ForeignKey('dms_folders.id'), nullable=True)
    path = Column(String, nullable=False)  # Materialized path like /Legal/Cases/2025/
    document_count = Column(Integer, default=0)
    department = Column(String)
    confidentiality_level = Column(String, default='internal', nullable=False)  # public, internal, confidential, restricted
    description = Column(String)
    is_system_folder = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), nullable=False)  # User ID
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)  # For soft delete

    # Relationships
    documents = relationship("DmsDocument", back_populates="folder", cascade="all, delete-orphan")
    parent_folder = relationship(
        "DmsFolder",
        remote_side=[id],
        backref=backref("subfolders", cascade="all, delete-orphan")
    )
    permissions = relationship("DmsFolderPermission", back_populates="folder", cascade="all, delete-orphan")

class DmsDocument(Base):
    __tablename__ = 'dms_documents'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer)
    storage_provider = Column(String, default='local', nullable=False)  # 's3' or 'local' or 'remote'
    storage_path = Column(String, nullable=False)  # Relative path from dms root
    s3_bucket = Column(String)
    s3_etag = Column(String)
    s3_version_id = Column(String)
    folder_id = Column(UUID(as_uuid=True), ForeignKey('dms_folders.id'), nullable=True)
    folder_path = Column(String)  # Denormalized path for quick access
    status = Column(String, default='pending', nullable=False)  # pending, processing, active, archived
    confidentiality_level = Column(String, default='internal', nullable=False)  # public, internal, confidential, restricted
    tags = Column(ARRAY(String), default=[])
    doc_metadata = Column(JSON)
    version = Column(Integer, default=1)
    uploaded_by = Column(UUID(as_uuid=True), nullable=False)  # User ID
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)  # For soft delete

    # Remote/Tender File Support
    source_url = Column(String, nullable=True)  # Original internet URL for tender files
    is_tender_file = Column(Boolean, default=False)  # Whether this is from a tender scrape
    is_cached = Column(Boolean, default=False)  # Whether remote file has been cached locally
    cache_status = Column(String, default='pending', nullable=True)  # pending, cached, failed (for remote files)
    cache_error = Column(Text, nullable=True)  # Error message if caching failed
    scraped_tender_file_id = Column(UUID(as_uuid=True), nullable=True)  # Reference to ScrapedTenderFile

    # Relationships
    folder = relationship("DmsFolder", back_populates="documents")
    categories = relationship(
        "DmsCategory",
        secondary=document_category_association,
        back_populates="documents"
    )
    permissions = relationship("DmsDocumentPermission", back_populates="document", cascade="all, delete-orphan")
    versions = relationship("DmsDocumentVersion", back_populates="document", cascade="all, delete-orphan")

class DmsCategory(Base):
    __tablename__ = 'dms_categories'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    color = Column(String)  # Hex color code
    icon = Column(String)  # Icon name or emoji

    # Relationships
    documents = relationship(
        "DmsDocument",
        secondary=document_category_association,
        back_populates="categories"
    )

class DmsFolderPermission(Base):
    __tablename__ = 'dms_folder_permissions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder_id = Column(UUID(as_uuid=True), ForeignKey('dms_folders.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)  # Either user_id or department, not both
    department = Column(String, nullable=True)
    permission_level = Column(String, nullable=False)  # read, write, admin
    inherit_to_subfolders = Column(Boolean, default=False)
    granted_by = Column(UUID(as_uuid=True), nullable=False)  # User ID
    granted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    valid_until = Column(DateTime, nullable=True)

    # Relationships
    folder = relationship("DmsFolder", back_populates="permissions")

class DmsDocumentPermission(Base):
    __tablename__ = 'dms_document_permissions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('dms_documents.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    permission_level = Column(String, nullable=False)  # read, write, admin
    granted_by = Column(UUID(as_uuid=True), nullable=False)  # User ID
    granted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    valid_until = Column(DateTime, nullable=True)

    # Relationships
    document = relationship("DmsDocument", back_populates="permissions")

class DmsDocumentVersion(Base):
    __tablename__ = 'dms_document_versions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('dms_documents.id'), nullable=False)
    version_number = Column(Integer, nullable=False)
    size_bytes = Column(Integer)
    storage_path = Column(String, nullable=False)
    s3_etag = Column(String)
    s3_version_id = Column(String)
    uploaded_by = Column(UUID(as_uuid=True), nullable=False)  # User ID
    change_summary = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    document = relationship("DmsDocument", back_populates="versions")
