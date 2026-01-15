from uuid import UUID
from typing import List, Optional, Tuple
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.services import get_vector_store
from app.modules.askai.models.chat import ChatMetadata, Message, CreateNewChatRequest, DocumentMetadata
from app.modules.askai.db.repository import ChatRepository, DocumentRepository
from app.modules.askai.services.drive_service import download_files_from_drive

def get_all_chats(db: Session) -> List[ChatMetadata]:
    """Get all chats from PostgreSQL."""
    chat_repo = ChatRepository(db)
    chats = chat_repo.get_all()
    response_chats = []
    for chat in chats:
        pdf_list = [
            DocumentMetadata(
                name=doc.filename,
                chunks=len(doc.chunks),
                status=doc.status
            ) for doc in chat.documents
        ]
        response_chats.append(
            ChatMetadata(
                id=chat.id,
                title=chat.title,
                created_at=chat.created_at.isoformat(),
                updated_at=chat.updated_at.isoformat(),
                message_count=len(chat.messages),
                pdf_count=len(chat.documents),
                pdf_list=pdf_list,
            )
        )
    return response_chats

def create_new_chat(db: Session, payload: Optional[CreateNewChatRequest], background_tasks: BackgroundTasks) -> ChatMetadata:
    """Create a new chat session in PostgreSQL."""
    chat_repo = ChatRepository(db)
    chat_count = chat_repo.count()
    new_chat = chat_repo.create(title=f"New Chat {chat_count + 1}")

    if payload and payload.driveUrl:
        background_tasks.add_task(download_files_from_drive, payload.driveUrl, str(new_chat.id))

    return ChatMetadata(
        id=new_chat.id,
        title=new_chat.title,
        created_at=new_chat.created_at.isoformat(),
        updated_at=new_chat.updated_at.isoformat(),
        message_count=0,
        pdf_count=0,
        pdf_list=[],
    )

def get_chat_messages(db: Session, chat_id: UUID) -> List[Message]:
    """Get all messages for a specific chat from PostgreSQL."""
    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(chat_id)
    if not chat:
        return []
    
    return [Message.model_validate(msg) for msg in chat.messages]

def delete_chat_by_id(db: Session, chat_id: UUID) -> bool:
    """Delete a chat session and its associated data from PostgreSQL."""
    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(chat_id)
    if not chat:
        return False
    
    chat_repo.delete(chat)
    
    # Try to delete from vector store if it's available
    vs = get_vector_store()
    if vs is not None:
        try:
            vs.delete_collection(str(chat_id))
        except Exception as e:
            print(f"Warning: Failed to delete vector store collection for chat {chat_id}: {e}")
    
    return True

def rename_chat_by_id(db: Session, chat_id: UUID, new_title: str) -> bool:
    """Rename a chat session in PostgreSQL."""
    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(chat_id)
    if not chat:
        return False
    
    chat_repo.rename(chat, new_title)
    return True

def remove_document_from_chat(db: Session, chat_id: UUID, pdf_name: str) -> Tuple[bool, str]:
    """Remove a document from a chat and handle cleanup."""
    chat_repo = ChatRepository(db)
    doc_repo = DocumentRepository(db)

    chat = chat_repo.get_by_id(chat_id)
    if not chat:
        return False, "Chat not found"

    doc_to_delete = doc_repo.find_by_filename_for_chat(chat_id, pdf_name)
    if not doc_to_delete:
        return False, f"PDF '{pdf_name}' not found in this chat"

    doc_repo.remove_document_from_chat(chat, doc_to_delete)
    
    # After commit, the session is expired, so we need to check the updated state.
    # A simple way is to check the length of the relationship.
    if len(chat.documents) == 0:
        vector_store.delete_collection(str(chat_id))
    
    return True, "PDF removed successfully"
