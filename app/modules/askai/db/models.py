import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Table, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.config import settings

# Association table for the many-to-many relationship between Chat and Document
chat_document_association = Table('chat_document_association', Base.metadata,
    Column('chat_id', UUID(as_uuid=True), ForeignKey('chats.id')),
    Column('document_id', UUID(as_uuid=True), ForeignKey('documents.id'))
)

class Chat(Base):
    __tablename__ = 'chats'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    drive_folders = Column(JSON, default=[])
    
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    documents = relationship("Document", secondary=chat_document_association, back_populates="chats")

class Message(Base):
    __tablename__ = 'messages'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey('chats.id'), nullable=False)
    sender = Column(String, nullable=False)  # 'user' or 'bot'
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    chat = relationship("Chat", back_populates="messages")

class Document(Base):
    __tablename__ = 'documents'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    doc_type = Column(String, default="pdf")
    file_hash = Column(String, unique=True, nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(String, default="active")
    uploaded_at = Column(DateTime, nullable=False)
    processing_stats = Column(JSON)
    
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    chats = relationship("Chat", secondary=chat_document_association, back_populates="documents")

class DocumentChunk(Base):
    __tablename__ = 'document_chunks'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)
    content = Column(Text, nullable=False)
    chunk_metadata = Column(JSON)
    
    document = relationship("Document", back_populates="chunks")
