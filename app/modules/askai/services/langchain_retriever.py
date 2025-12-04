"""
LangChain-compatible Weaviate Retriever

Phase 2.2: Document retrieval integration with LangChain.

This module provides a WeaviateRetriever that wraps the existing
Weaviate vector store and exposes it through LangChain's retriever interface.
"""

from typing import List, Dict, Any
from uuid import UUID

from pydantic import ConfigDict
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from app.db.vector_store import VectorStoreManager
from app.config import settings


class WeaviateRetriever(BaseRetriever):
    """
    LangChain retriever for Weaviate vector store.

    This retriever:
    - Wraps the existing Weaviate VectorStoreManager
    - Converts results to LangChain Document objects
    - Preserves metadata from Weaviate
    - Supports configurable top-k results

    Args:
        vector_store: VectorStoreManager instance
        collection: Weaviate collection object
        top_k: Number of top results to retrieve (default: RAG_TOP_K from config)
    """

    vector_store: VectorStoreManager
    collection: Any  # Weaviate collection type
    top_k: int = settings.RAG_TOP_K

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
        **kwargs: Any
    ) -> List[Document]:
        """
        Retrieve documents from Weaviate.

        Args:
            query: The query string
            run_manager: Callback manager for tracking retrieval
            **kwargs: Additional arguments

        Returns:
            List of LangChain Document objects with metadata
        """
        if not self.vector_store or not self.collection:
            print("⚠️  Vector store or collection not initialized")
            return []

        try:
            # Query Weaviate using existing method
            results = self.vector_store.query(
                self.collection,
                query,
                n_results=self.top_k
            )

            if not results:
                print(f"📭 No documents found for query: {query}")
                return []

            # Convert results to LangChain Document objects
            documents = []
            for idx, (doc_content, metadata, score) in enumerate(results):
                # Parse metadata from Weaviate
                source = metadata.get("source", "Unknown")
                page = metadata.get("page", "0")
                doc_id = metadata.get("doc_id", "unknown")
                doc_type = metadata.get("doc_type", "unknown")
                content_type = metadata.get("type", "text")

                # Create Document with preserved metadata
                document = Document(
                    page_content=doc_content,
                    metadata={
                        "source": source,
                        "page": page,
                        "doc_id": doc_id,
                        "doc_type": doc_type,
                        "content_type": content_type,
                        "relevance_score": float(score),
                        "result_index": idx + 1,  # 1-indexed for prompts
                    }
                )
                documents.append(document)

            print(f"✅ Retrieved {len(documents)} documents for query: {query}")
            return documents

        except Exception as e:
            print(f"❌ Error retrieving documents: {e}")
            return []

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
        **kwargs: Any
    ) -> List[Document]:
        """
        Async retrieval from Weaviate.

        Currently delegates to sync implementation.

        Args:
            query: The query string
            run_manager: Callback manager
            **kwargs: Additional arguments

        Returns:
            List of LangChain Document objects
        """
        # For now, use sync implementation
        # TODO: Implement true async Weaviate queries in Phase 3
        return self._get_relevant_documents(query, run_manager=run_manager, **kwargs)

    def get_retriever_info(self) -> Dict[str, Any]:
        """
        Get information about the retriever.

        Returns:
            Dictionary with retriever configuration
        """
        return {
            "name": "WeaviateRetriever",
            "type": "vector_store",
            "vector_store": "Weaviate",
            "collection": self.collection.name if hasattr(self.collection, "name") else "unknown",
            "top_k": self.top_k,
            "model": "all-MiniLM-L6-v2",
        }


def create_weaviate_retriever(
    vector_store: VectorStoreManager,
    chat_id: UUID,
    top_k: int = settings.RAG_TOP_K,
) -> WeaviateRetriever:
    """
    Factory function to create a WeaviateRetriever for a chat.

    Args:
        vector_store: VectorStoreManager instance
        chat_id: UUID of the chat session
        top_k: Number of top results (default: RAG_TOP_K)

    Returns:
        Configured WeaviateRetriever instance

    Raises:
        RuntimeError: If vector store not initialized
    """
    if not vector_store:
        raise RuntimeError("Vector store not initialized")

    # Get or create collection for this chat
    collection = vector_store.get_or_create_collection(str(chat_id))

    retriever = WeaviateRetriever(
        vector_store=vector_store,
        collection=collection,
        top_k=top_k,
    )

    print(f"✅ Created WeaviateRetriever for chat {chat_id}")
    return retriever
