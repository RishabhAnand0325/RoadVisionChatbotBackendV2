"""
LangChain-based RAG Service

Phase 2.3: Core RAG implementation using LangChain LCEL.

This service provides a cleaner, more maintainable RAG pipeline compared to
the manual implementation, using LangChain's declarative chains (LCEL).
"""

from uuid import UUID
from typing import Dict, List, Any
from uuid import UUID
from sqlalchemy.orm import Session
from operator import itemgetter

from app.config import settings
from app.core.langchain_config import get_langchain_llm, get_langchain_embeddings, RAG_PROMPT
from app.db.vector_store import VectorStoreManager
from app.modules.askai.db.repository import ChatRepository
from app.modules.askai.services.langchain_memory import SQLAlchemyChatMessageHistory
from app.modules.askai.services.langchain_retriever import create_weaviate_retriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate


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
        Process a message through the RAG pipeline using RunnableWithMessageHistory.
        """
        try:
            chat = self.chat_repo.get_by_id(chat_id)
            if not chat:
                raise ValueError(f"Chat {chat_id} not found")

            print(f"✅ Processing message for chat {chat_id}")

            chain_with_history = self._get_or_create_chain(chat_id)

            # Invoke the chain. History is managed automatically.
            response = chain_with_history.invoke(
                {"question": user_message},
                config={"configurable": {"session_id": str(chat_id)}}
            )
            response_text = response.content
            print(f"✅ Generated response: {response_text[:100]}...")

            # Retrieve sources separately for the response payload
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

            return {
                "response": response_text,
                "sources": sources,
            }
        except Exception as e:
            print(f"❌ Error in RAG pipeline: {e}")
            raise

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

    def _get_or_create_chain(self, chat_id: UUID) -> RunnableWithMessageHistory:
        """
        Get or create a history-aware RAG chain for a chat session.
        """
        if chat_id not in self._chains:
            print(f"🔗 Building RAG chain with history for chat {chat_id}")
            
            base_chain = self._build_base_chain(chat_id)
            
            chain_with_history = RunnableWithMessageHistory(
                runnable=base_chain,
                get_session_history=lambda session_id: SQLAlchemyChatMessageHistory(
                    db=self.db,
                    chat_id=UUID(session_id)
                ),
                input_messages_key="question",
                history_messages_key="chat_history",
            )
            self._chains[chat_id] = chain_with_history
            
        return self._chains[chat_id]

    def _build_base_chain(self, chat_id: UUID):
        """
        Builds the core RAG chain that expects history.
        """
        retriever = self._get_or_create_retriever(chat_id)

        # Dynamically insert a placeholder for chat history into the RAG_PROMPT
        prompt_messages = list(RAG_PROMPT.messages)
        prompt_messages.insert(1, MessagesPlaceholder(variable_name="chat_history"))
        prompt_with_history = ChatPromptTemplate.from_messages(prompt_messages)

        # This part of the chain is responsible for generating the context
        context_chain = itemgetter("question") | retriever | self._format_docs
        
        # The main chain for processing the request
        conversational_rag_chain = (
            {
                "context": context_chain,
                "question": itemgetter("question"),
                "chat_history": itemgetter("chat_history"),
            }
            | prompt_with_history
            | self.llm
            | StrOutputParser()
        )
        return conversational_rag_chain

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
