from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import Field, BaseModel, ConfigDict
from .document import DriveFolder, DocumentMetadata

# --- API Models ---

class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    """Model for API responses for a single chat's messages."""
    id: UUID
    text: str
    sender: str
    timestamp: datetime

class ChatMetadata(BaseModel):
    """Model for the list of chats API response."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    created_at: str
    updated_at: str
    message_count: int
    pdf_count: int
    pdf_list: List[DocumentMetadata] = []

class NewMessageRequest(BaseModel):
    message: str

class Source(BaseModel):
    id: int
    source: str
    location: str
    doc_type: str
    content_type: str
    content: str
    full_content: str
    page: Optional[str] = None

class NewMessageResponse(BaseModel):
    reply: str
    sources: List[Source]
    message_count: int

class RenameChatRequest(BaseModel):
    title: str

class CreateNewChatRequest(BaseModel):
    driveUrl: Optional[str]
