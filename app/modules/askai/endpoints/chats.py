from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Body, status, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.modules.askai.models.chat import ChatMetadata, Message, NewMessageRequest, NewMessageResponse, RenameChatRequest, CreateNewChatRequest
from app.modules.askai.services import chat_service, rag_service
from app.db.database import get_db_session
from app.config import settings
from app.modules.askai.dependencies_langchain import get_langchain_rag_service

router = APIRouter()

@router.get("/chats", response_model=List[ChatMetadata], tags=["AskAI - Chats"])
def get_chats(db: Session = Depends(get_db_session)):
    """Get all chats, sorted by last updated"""
    return chat_service.get_all_chats(db)

@router.post("/chats", response_model=ChatMetadata, status_code=status.HTTP_201_CREATED, tags=["AskAI - Chats"])
def create_chat(
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db_session),
        payload: Optional[CreateNewChatRequest] = None,
    ):
    """Create a new chat session and start importing documents from Google Drive"""
    return chat_service.create_new_chat(db, payload, background_tasks)

@router.get("/chats/{chat_id}", response_model=List[Message], tags=["AskAI - Chats"])
def get_chat(chat_id: UUID, db: Session = Depends(get_db_session)):
    """Get all messages for a specific chat"""
    return chat_service.get_chat_messages(db, chat_id)

@router.delete("/chats/{chat_id}", status_code=status.HTTP_200_OK, tags=["AskAI - Chats"])
def delete_chat(chat_id: UUID, db: Session = Depends(get_db_session)):
    """Delete a chat session and its associated data"""
    success = chat_service.delete_chat_by_id(db, chat_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return {"message": "Chat deleted successfully"}

@router.put("/chats/{chat_id}/rename", status_code=status.HTTP_200_OK, tags=["AskAI - Chats"])
def rename_chat(
    chat_id: UUID,
    payload: RenameChatRequest = Body(...),
    db: Session = Depends(get_db_session)
):
    """Rename a chat session"""
    if not payload.title or not payload.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title cannot be empty")
    
    success = chat_service.rename_chat_by_id(db, chat_id, payload.title.strip())
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return {"message": "Chat renamed successfully"}

@router.post("/chats/{chat_id}/messages", response_model=NewMessageResponse, tags=["AskAI - Chats"])
def send_message(
    chat_id: UUID,
    payload: NewMessageRequest = Body(...),
    db: Session = Depends(get_db_session),
    langchain_service = Depends(get_langchain_rag_service),
):
    """Send a message to a chat and get a RAG-based response"""
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")

    try:
        # Feature flag: Use LangChain RAG if enabled, otherwise use old implementation
        if settings.USE_LANGCHAIN_RAG:
            response = langchain_service.send_message(chat_id, payload.message.strip())
            return NewMessageResponse(
                user_message=payload.message.strip(),
                bot_response=response["response"],
                sources=response["sources"]
            )
        else:
            return rag_service.send_message_to_chat(db, chat_id, payload.message.strip())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
