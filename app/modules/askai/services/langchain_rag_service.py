"""
LangChain-based RAG Service

Phase 2.3: Core RAG implementation using LangChain LCEL.

This service provides a cleaner, more maintainable RAG pipeline compared to
the manual implementation, using LangChain's declarative chains (LCEL).
"""

from uuid import UUID
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.core.langchain_config import get_langchain_llm, get_langchain_embeddings, RAG_PROMPT
from app.db.vector_store import VectorStoreManager
from app.modules.askai.db.repository import ChatRepository
from app.modules.askai.services.langchain_memory import DatabaseConversationMemory
from app.modules.askai.services.langchain_retriever import create_weaviate_retriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


class LangChainRAGService:
    """
    RAG service using LangChain chains (Phase 2.3).

    Implements the full RAG pipeline:
    - Memory: Loads chat history from database
    - Retrieval: Uses Weaviate semantic search via WeaviateRetriever
    - Generation: Uses Gemini 2.0 Flash with LCEL chains
    - Persistence: Saves responses back to database

    Architecture:
    ```
    User Message
        ↓
    Memory (load chat history)
        ↓
    Retriever (semantic search)
        ↓
    RAG Chain (prompt → LLM)
        ↓
    Response Parsing
        ↓
    Database Save
        ↓
    Return Response + Sources
    ```
    """

    def __init__(self, vector_store: VectorStoreManager, db: Session):
        """
        Initialize LangChain RAG service.

        Args:
            vector_store: VectorStoreManager instance for document retrieval
            db: SQLAlchemy database session
        """
        self.vector_store = vector_store
        self.db = db
        self.chat_repo = ChatRepository(db)

        # Lazily initialize LLM and embeddings
        self._llm = None
        self._embeddings = None

        # Cache chains per chat session
        self._chains = {}
        self._retrievers = {}
        self._memories = {}

    @property
    def llm(self):
        """Lazy-load LLM."""
        if self._llm is None:
            self._llm = get_langchain_llm()
        return self._llm

    @property
    def embeddings(self):
        """Lazy-load embeddings."""
        if self._embeddings is None:
            self._embeddings = get_langchain_embeddings()
        return self._embeddings

    def send_message(self, chat_id: UUID, user_message: str) -> Dict[str, Any]:
        """
        Process message through RAG pipeline.

        Phase 2.3: Full implementation with retrieval and generation.

        Args:
            chat_id: UUID of the chat session
            user_message: User's question/message

        Returns:
            Dict with 'response' and 'sources' keys

        Raises:
            ValueError: If chat not found
        """
        try:
            # Verify chat exists
            chat = self.chat_repo.get_by_id(chat_id)
            if not chat:
                raise ValueError(f"Chat {chat_id} not found")

            print(f"✅ Processing message for chat {chat_id}")

            # Get or create memory for this chat
            memory = self._get_or_create_memory(chat_id)

            # Get or create RAG chain for this chat
            chain = self._get_or_create_chain(chat_id)

            # Invoke the chain with the user message
            print(f"📝 User message: {user_message}")
            response_text = chain.invoke({"question": user_message})
            print(f"✅ Generated response: {response_text[:100]}...")

            # Retrieve sources for this query
            retriever = self._get_or_create_retriever(chat_id)
            retrieved_docs = retriever.invoke(user_message)

            sources = [
                {
                    "source": doc.metadata.get("source", "Unknown"),
                    "page": doc.metadata.get("page", "0"),
                    "relevance": doc.metadata.get("relevance_score", 0.0),
                }
                for doc in retrieved_docs
            ]
            print(f"📚 Retrieved {len(sources)} source documents")

            # Save messages to database
            self.chat_repo.add_message(chat, sender="user", text=user_message)
            self.chat_repo.add_message(chat, sender="bot", text=response_text)
            self.db.commit()

            # Update memory
            memory.add_user_message(user_message)
            memory.add_ai_message(response_text)

            print(f"✅ Message saved to database")

            return {
                "response": response_text,
                "sources": sources,
            }

        except Exception as e:
            print(f"❌ Error in RAG pipeline: {e}")
            raise

    def _get_or_create_memory(self, chat_id: UUID) -> DatabaseConversationMemory:
        """
        Get or create conversation memory for a chat.

        Args:
            chat_id: Chat session ID

        Returns:
            DatabaseConversationMemory instance
        """
        if chat_id not in self._memories:
            print(f"📝 Creating memory for chat {chat_id}")
            self._memories[chat_id] = DatabaseConversationMemory(
                chat_repo=self.chat_repo,
                chat_id=chat_id,
                max_history=settings.RAG_MEMORY_SIZE,
            )
        return self._memories[chat_id]

    def _get_or_create_retriever(self, chat_id: UUID):
        """
        Get or create retriever for a chat.

        Args:
            chat_id: Chat session ID

        Returns:
            WeaviateRetriever instance
        """
        if chat_id not in self._retrievers:
            print(f"🔍 Creating retriever for chat {chat_id}")
            self._retrievers[chat_id] = create_weaviate_retriever(
                vector_store=self.vector_store,
                chat_id=chat_id,
                top_k=settings.RAG_TOP_K,
            )
        return self._retrievers[chat_id]

    def _get_or_create_chain(self, chat_id: UUID):
        """
        Get or create RAG chain for a chat.

        Args:
            chat_id: Chat session ID

        Returns:
            Callable LCEL chain
        """
        if chat_id not in self._chains:
            print(f"🔗 Building RAG chain for chat {chat_id}")
            self._chains[chat_id] = self._build_chain(chat_id)
        return self._chains[chat_id]

    def _build_chain(self, chat_id: UUID):
        """
        Build RAG chain using LCEL.

        Creates a declarative chain that:
        1. Takes user question as input
        2. Retrieves relevant documents
        3. Formats context from documents
        4. Passes through RAG prompt template
        5. Invokes LLM
        6. Parses string output

        Architecture:
        ```
        {
            "context": retriever | _format_docs,
            "question": RunnablePassthrough(),
        }
        | RAG_PROMPT
        | llm
        | StrOutputParser()
        ```

        Args:
            chat_id: Chat session ID

        Returns:
            Callable chain for processing queries
        """
        retriever = self._get_or_create_retriever(chat_id)

        # Create the RAG chain using LCEL
        chain = (
            {
                "context": retriever | self._format_docs,
                "question": RunnablePassthrough(),
            }
            | RAG_PROMPT
            | self.llm
            | StrOutputParser()
        )

        print(f"✅ RAG chain built for chat {chat_id}")
        return chain

    def _format_docs(self, docs: List) -> str:
        """
        Format retrieved documents for prompt context.

        Converts LangChain Document objects to formatted context string.

        Args:
            docs: List of LangChain Document objects

        Returns:
            Formatted context string for prompt
        """
        if not docs:
            return "No relevant documents found."

        context_parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "")
            content = doc.page_content

            if page and page != "0":
                source_str = f"{source} (Page {page})"
            else:
                source_str = source

            context_parts.append(f"[Source {i}: {source_str}]\n{content}")

        return "\n\n".join(context_parts)

    def _retrieve_documents(self, chat_id: UUID, query: str) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents from vector store.

        Helper method for manual retrieval if needed outside of chain.

        Args:
            chat_id: Chat session ID
            query: User query

        Returns:
            List of documents with metadata
        """
        retriever = self._get_or_create_retriever(chat_id)
        docs = retriever.invoke(query)

        return [
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", "Unknown"),
                "page": doc.metadata.get("page", "0"),
                "relevance": doc.metadata.get("relevance_score", 0.0),
            }
            for doc in docs
        ]
