from uuid import UUID
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime

from .models import Chat, Message, Document

class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> List[Chat]:
        return self.db.query(Chat).order_by(desc(Chat.updated_at)).all()

    def get_by_id(self, chat_id: UUID) -> Optional[Chat]:
        return self.db.get(Chat, chat_id)

    def create(self, title: str) -> Chat:
        now = datetime.now()
        new_chat = Chat(
            title=title,
            created_at=now,
            updated_at=now,
        )
        self.db.add(new_chat)
        self.db.commit()
        self.db.refresh(new_chat)
        return new_chat
    
    def count(self) -> int:
        return self.db.query(Chat).count()

    def delete(self, chat: Chat) -> None:
        self.db.delete(chat)
        self.db.commit()

    def rename(self, chat: Chat, new_title: str) -> Chat:
        chat.title = new_title
        chat.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(chat)
        return chat

    def add_message(self, chat: Chat, sender: str, text: str):
        now = datetime.now()
        new_message = Message(chat_id=chat.id, sender=sender, text=text, timestamp=now)
        self.db.add(new_message)
        chat.updated_at = now
        # The commit will be handled by the service layer after all messages are added
    
    def add_drive_folder(self, chat: Chat, folder_data: dict) -> Chat:
        # The JSON column needs to be mutated in place for SQLAlchemy to detect the change.
        chat.drive_folders.append(folder_data)
        self.db.commit()
        self.db.refresh(chat)
        return chat

class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_document_to_chat(self, chat: Chat, document: Document):
        chat.documents.append(document)
        chat.updated_at = datetime.now()
        self.db.commit()

    def find_by_filename_for_chat(self, chat_id: UUID, filename: str) -> Optional[Document]:
        return self.db.query(Document).filter(Document.filename == filename, Document.chats.any(id=chat_id)).first()

    def remove_document_from_chat(self, chat: Chat, document: Document):
        chat.documents.remove(document)
        self.db.commit()

        # If this document is not associated with any other chat, delete it entirely.
        if not document.chats:
            self.db.delete(document)
        
        self.db.commit()

    def get_by_hash(self, file_hash: str) -> Optional[Document]:
        return self.db.query(Document).filter(Document.file_hash == file_hash).first()
