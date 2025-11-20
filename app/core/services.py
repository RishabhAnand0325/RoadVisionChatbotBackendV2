from typing import Optional
from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel
import tiktoken
import weaviate
import google.generativeai as genai
from weaviate.client import WeaviateClient

from app.config import settings
from app.modules.askai.models.document import UploadJob
from app.db.vector_store import VectorStoreManager

print("--- Initializing Core Services ---")

# Lazy-loaded globals
_embedding_model = None
_pdf_processor = None
_excel_processor = None

def get_embedding_model():
    """Lazy-load the embedding model only when needed"""
    global _embedding_model
    if _embedding_model is None:
        print("Loading SentenceTransformer model...")
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2", cache_folder="./model_cache")
        print("✅ SentenceTransformer loaded")
    return _embedding_model

def get_vector_store():
    """Lazy-load the vector store"""
    global vector_store
    if vector_store is None and weaviate_client is not None:
        vector_store = VectorStoreManager(weaviate_client, get_embedding_model())
    return vector_store

def get_pdf_processor():
    """Lazy-load the PDF processor"""
    global _pdf_processor
    if _pdf_processor is None:
        from app.modules.askai.services.document_service import PDFProcessor
        _pdf_processor = PDFProcessor(get_embedding_model(), tokenizer)
    return _pdf_processor

def get_excel_processor():
    """Lazy-load the Excel processor"""
    global _excel_processor
    if _excel_processor is None:
        from app.modules.askai.services.document_service import ExcelProcessor
        _excel_processor = ExcelProcessor(get_embedding_model(), tokenizer)
    return _excel_processor

try:
    configure(api_key=settings.GOOGLE_API_KEY)
    llm_model = GenerativeModel("gemini-2.0-flash-exp")
    print("✅ Gemini 2.0 Flash configured")

    # embedding_model will be loaded lazily when first needed
    embedding_model = None  # Placeholder for backward compatibility

    # This will be initialized in the startup event.
    weaviate_client: Optional[WeaviateClient] = None
    vector_store: Optional[VectorStoreManager] = None

    try:
        weaviate_client = weaviate.connect_to_local()
        if not weaviate_client.is_ready():
            raise Exception("Weaviate is not ready")
        print("✅ Weaviate client connected")
        # vector_store will be initialized lazily when embedding model is loaded
        vector_store = None
    except Exception as e:
        print(f"❌ Could not connect to Weaviate: {e}")
        weaviate_client = None
        vector_store = None
    
    tokenizer = tiktoken.get_encoding("cl100k_base")

    # pdf_processor and excel_processor will be loaded lazily
    pdf_processor = None  # Use get_pdf_processor() instead
    excel_processor = None  # Use get_excel_processor() instead
    
    # This mimics the legacy global state for now. Will be replaced in Phase 3 with Redis.
    # active_conversations and document_store are now handled by the database.

    print("--- Core Services Initialized Successfully (AI models will load on first use) ---")

except ImportError as e:
    print(f"❌ Missing package: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Failed to initialize core services: {e}")
    exit(1)
