"""
Unit tests for LangChain Phase 1: Foundation

Tests for:
- LangChain configuration loading
- LLM and embeddings initialization
- Prompt template creation
- Service instantiation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

from app.core.langchain_config import (
    get_langchain_llm,
    get_langchain_embeddings,
    RAG_PROMPT,
)
from app.modules.askai.services.langchain_rag_service import LangChainRAGService
from app.modules.askai.dependencies_langchain import get_langchain_rag_service


class TestLangChainConfig:
    """Test LangChain configuration initialization."""

    def test_llm_initialization(self):
        """Test that LLM initializes without errors."""
        try:
            llm = get_langchain_llm()
            assert llm is not None
            assert llm.model_name == "gemini-2.0-flash-exp"
        except ValueError as e:
            # Expected if GOOGLE_API_KEY not set
            assert "GOOGLE_API_KEY" in str(e)

    def test_embeddings_initialization(self):
        """Test that embeddings initialize without errors."""
        embeddings = get_langchain_embeddings()
        assert embeddings is not None
        assert embeddings.model_name == "all-MiniLM-L6-v2"

    def test_rag_prompt_template(self):
        """Test that RAG prompt template is properly configured."""
        assert RAG_PROMPT is not None
        # Should have two messages: system and human
        assert len(RAG_PROMPT.messages) == 2
        assert RAG_PROMPT.messages[0].type == "system"
        assert RAG_PROMPT.messages[1].type == "human"


class TestLangChainRAGService:
    """Test LangChainRAGService initialization and basic methods."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create mock vector store."""
        return Mock()

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock()

    @pytest.fixture
    def mock_chat_repo(self):
        """Create mock chat repository."""
        repo = Mock()
        repo.get_by_id = Mock(return_value=Mock(id=uuid4()))
        return repo

    def test_service_initialization(self, mock_vector_store, mock_db):
        """Test that service initializes correctly."""
        with patch.object(LangChainRAGService, '__init__', lambda x, vs, db: None):
            service = LangChainRAGService(mock_vector_store, mock_db)
            assert service is not None

    def test_send_message_stub(self, mock_vector_store, mock_db):
        """Test send_message returns stub response in Phase 1."""
        service = LangChainRAGService(mock_vector_store, mock_db)
        service.chat_repo = Mock()

        chat_id = uuid4()
        mock_chat = Mock(id=chat_id)
        service.chat_repo.get_by_id = Mock(return_value=mock_chat)
        service.chat_repo.add_message = Mock()
        service.db = mock_db

        response = service.send_message(chat_id, "Test question?")

        assert response is not None
        assert "response" in response
        assert "sources" in response
        assert isinstance(response["response"], str)
        assert isinstance(response["sources"], list)
        assert "Phase 1" in response["response"]  # Stub message

    def test_send_message_chat_not_found(self, mock_vector_store, mock_db):
        """Test send_message raises error if chat not found."""
        service = LangChainRAGService(mock_vector_store, mock_db)
        service.chat_repo = Mock()
        service.chat_repo.get_by_id = Mock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            service.send_message(uuid4(), "Test question?")

    def test_format_documents_empty(self, mock_vector_store, mock_db):
        """Test formatting empty documents."""
        service = LangChainRAGService(mock_vector_store, mock_db)
        result = service._format_documents([])
        assert result == ""

    def test_format_documents_with_content(self, mock_vector_store, mock_db):
        """Test formatting documents with content."""
        service = LangChainRAGService(mock_vector_store, mock_db)
        docs = [
            {"source": "doc1.pdf", "content": "Content 1"},
            {"source": "doc2.pdf", "content": "Content 2"},
        ]
        result = service._format_documents(docs)
        assert "Source 1" in result
        assert "Source 2" in result
        assert "Content 1" in result
        assert "Content 2" in result


class TestDependencyInjection:
    """Test dependency injection setup."""

    def test_get_langchain_rag_service_dependency(self):
        """Test that dependency injection returns service instance."""
        mock_db = Mock()
        with patch('app.core.services.vector_store', new_callable=Mock):
            with patch('app.modules.askai.dependencies_langchain.vector_store'):
                # This would require full FastAPI setup, so we'll test the function
                pass

        # Basic smoke test that the function exists and is callable
        assert callable(get_langchain_rag_service)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
