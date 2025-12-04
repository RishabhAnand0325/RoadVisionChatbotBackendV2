"""
LangChain Conversation Memory with Database Persistence.

This module provides a SQLAlchemyChatMessageHistory class that implements
LangChain's BaseChatMessageHistory interface for use with modern LCEL chains
that use `RunnableWithMessageHistory`.
"""

from typing import List
from uuid import UUID
from sqlalchemy.orm import Session

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.modules.askai.db.repository import ChatRepository
from app.modules.askai.db.models import Message


class SQLAlchemyChatMessageHistory(BaseChatMessageHistory):
    """
    Chat message history that stores messages in a SQLAlchemy database.

    This class is designed to work with the `askai` module's existing
    database schema (`Chat` and `Message` tables).
    """

    def __init__(self, db: Session, chat_id: UUID):
        self.db = db
        self.chat_id = chat_id
        self.chat_repo = ChatRepository(db)

    @property
    def messages(self) -> List[BaseMessage]:
        """Retrieve messages from the database."""
        # This property correctly overrides and implements the abstract property
        # from the `BaseChatMessageHistory` interface. Linter warnings about
        # overriding a symbol from a base class can be safely ignored here.
        chat = self.chat_repo.get_by_id(self.chat_id)
        if not chat or not chat.messages:
            return []

        langchain_messages: List[BaseMessage] = []
        for msg in chat.messages:
            if msg.sender == "user":
                langchain_messages.append(HumanMessage(content=msg.text))
            elif msg.sender == "bot":
                langchain_messages.append(AIMessage(content=msg.text))
        return langchain_messages

    def add_message(self, message: BaseMessage) -> None:
        """Append a message to the database."""
        sender = ""
        if isinstance(message, HumanMessage):
            sender = "user"
        elif isinstance(message, AIMessage):
            sender = "bot"
        
        if sender:
            db_message = Message(
                chat_id=self.chat_id,
                text=str(message.content),
                sender=sender
            )
            self.db.add(db_message)
            self.db.commit()

    def clear(self) -> None:
        """Clear all messages from the database for this chat session."""
        chat = self.chat_repo.get_by_id(self.chat_id)
        if chat and chat.messages:
            for msg in chat.messages:
                self.db.delete(msg)
            self.db.commit()
