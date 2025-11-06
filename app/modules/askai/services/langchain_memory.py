"""
LangChain Conversation Memory with Database Persistence

Phase 2.1: Memory management for chat history.

This module provides a DatabaseConversationMemory class that:
- Loads chat history from PostgreSQL on initialization
- Keeps recent messages in memory for the current session
- Is compatible with LangChain's memory interface
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory

from app.modules.askai.db.repository import ChatRepository


class DatabaseConversationMemory:
    """
    LangChain-compatible conversation memory backed by PostgreSQL.

    Features:
    - Loads recent chat history from database on initialization
    - Keeps last N messages in memory for current session
    - Compatible with LangChain chat models
    - Tracks conversation in both memory and database

    Args:
        chat_repo: ChatRepository instance for database access
        chat_id: UUID of the chat session
        max_history: Maximum number of messages to keep in memory (default: 10)
    """

    def __init__(
        self,
        chat_repo: ChatRepository,
        chat_id: UUID,
        max_history: int = 10,
    ):
        """Initialize memory with chat history from database."""
        self.chat_repo = chat_repo
        self.chat_id = chat_id
        self.max_history = max_history

        # Use ConversationBufferMemory as internal buffer
        self.chat_memory = ConversationBufferMemory(
            return_messages=True,
            human_prefix="User",
            ai_prefix="Assistant",
        )

        # Load existing chat history from database
        self._load_history_from_db()

        msg_count = len(self.chat_memory.chat_memory.messages) if hasattr(self.chat_memory, 'chat_memory') else 0
        print(f"✅ Memory initialized for chat {chat_id} with {msg_count} messages")

    def _load_history_from_db(self) -> None:
        """
        Load recent chat messages from database into memory.

        Loads the last `max_history` messages and converts them to
        LangChain message objects.
        """
        try:
            # Get the chat object with its messages
            chat = self.chat_repo.get_by_id(self.chat_id)
            if not chat:
                print(f"⚠️  Chat {self.chat_id} not found")
                return

            # Get the last max_history messages
            messages = chat.messages[-self.max_history:] if chat.messages else []

            # Convert to LangChain message objects
            for msg in messages:
                if msg.sender == "user":
                    self.chat_memory.chat_memory.add_user_message(msg.text)
                elif msg.sender == "bot":
                    self.chat_memory.chat_memory.add_ai_message(msg.text)

            if messages:
                print(f"📝 Loaded {len(messages)} messages from database for chat {self.chat_id}")

        except Exception as e:
            print(f"❌ Error loading chat history: {e}")

    def get_history_for_langchain(self) -> List[BaseMessage]:
        """
        Get conversation history in LangChain format.

        Returns:
            List of LangChain message objects
        """
        return self.chat_memory.chat_memory.messages

    def add_user_message(self, message: str) -> None:
        """
        Add a user message to memory.

        Args:
            message: User's message text
        """
        self.chat_memory.chat_memory.add_user_message(message)

    def add_ai_message(self, message: str) -> None:
        """
        Add an AI message to memory.

        Args:
            message: AI's response text
        """
        self.chat_memory.chat_memory.add_ai_message(message)

    def clear(self) -> None:
        """Clear conversation memory (keeps database history intact)."""
        self.chat_memory.clear()

    def get_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get memory variables for LangChain chains.

        Required by ConversationMemory interface.

        Args:
            inputs: Input variables from the chain

        Returns:
            Dictionary with chat_history key
        """
        messages = self.get_history_for_langchain()

        # Format as string for simple prompts
        history_lines = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "USER"
            elif isinstance(msg, AIMessage):
                role = "ASSISTANT"
            else:
                role = "UNKNOWN"
            history_lines.append(f"{role}: {msg.content}")
        history_str = "\n".join(history_lines)

        return {
            "chat_history": history_str,
            "messages": messages,  # Also provide raw messages
        }

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """
        Save context after chain execution.

        This is called automatically by LangChain chains.
        Note: Messages are saved to database by the service layer,
        not by memory itself.

        Args:
            inputs: Input to the chain
            outputs: Output from the chain
        """
        # Messages are saved to database by the service layer
        # This method is called for compatibility with ConversationMemory
        pass

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load memory variables from the system.

        Required by ConversationMemory interface.

        Args:
            inputs: Input variables

        Returns:
            Memory variables dictionary
        """
        return self.get_memory_variables(inputs)

    @property
    def memory_variables(self) -> List[str]:
        """
        Return list of memory variable names.

        Required by ConversationMemory interface.

        Returns:
            List of memory variable names
        """
        return ["chat_history", "messages"]

    def get_context_for_prompt(self) -> str:
        """
        Get formatted context string for embedding in prompts.

        Returns:
            Formatted chat history as string
        """
        messages = self.get_history_for_langchain()
        if not messages:
            return "No previous conversation history."

        context_lines = []
        for msg in messages:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            context_lines.append(f"{role}: {msg.content}")

        return "\n".join(context_lines)
