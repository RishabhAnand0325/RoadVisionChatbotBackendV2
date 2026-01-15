"""
Dependency Injection for LangChain RAG Service

Phase 1: Setup FastAPI dependencies for LangChain components.
"""

from sqlalchemy.orm import Session
from fastapi import Depends

from app.db.database import get_db_session
from app.core.services import get_vector_store
from app.modules.askai.services.langchain_rag_service import LangChainRAGService


def get_langchain_rag_service(db: Session = Depends(get_db_session)) -> LangChainRAGService:
    """
    FastAPI dependency to provide LangChain RAG service instance.

    Args:
        db: Database session (injected by FastAPI)

    Returns:
        LangChainRAGService instance
    """
    vector_store = get_vector_store()
    if not vector_store:
        raise RuntimeError("Vector store not initialized")

    return LangChainRAGService(vector_store, db)
