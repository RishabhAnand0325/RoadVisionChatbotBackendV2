from typing import Optional
from google import genai 
from google.genai.errors import APIError
import tiktoken
import weaviate
from weaviate.client import WeaviateClient

from app.config import settings
from app.modules.askai.models.document import UploadJob
from app.db.vector_store import VectorStoreManager

print("--- Initializing Core Services ---")

# Lazy-loaded globals
_embedding_model = None
_pdf_processor = None
_excel_processor = None
llm_client: Optional[genai.Client] = None
llm_model = None # The GenerativeModel object instance

def get_embedding_model():
    """Lazy-load the embedding model only when needed"""
    global _embedding_model
    if _embedding_model is None:
        print("Loading SentenceTransformer model...")
        from sentence_transformers import SentenceTransformer
        # Note: If 'all-MiniLM-L6-v2' is too large, consider a smaller one or
        # using Google's embeddings API via the 'google-genai' client.
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2", cache_folder="./model_cache")
        print("✅ SentenceTransformer loaded")
    return _embedding_model

def get_vector_store():
    """Lazy-load the vector store"""
    global vector_store
    if vector_store is None and weaviate_client is not None:
        # Assumes VectorStoreManager accepts the embedding model directly
        vector_store = VectorStoreManager(weaviate_client, get_embedding_model())
    return vector_store

def get_pdf_processor():
    """Lazy-load the PDF processor"""
    global _pdf_processor
    if _pdf_processor is None:
        from app.modules.askai.services.document_service import PDFProcessor
        _pdf_processor = PDFProcessor(get_embedding_model(), tokenizer)
    return _pdf_processor

GEMINI_MODEL_NAME = "gemini-2.0-flash-exp"

def get_excel_processor():
    """Lazy-load the Excel processor"""
    global _excel_processor
    if _excel_processor is None:
        from app.modules.askai.services.document_service import ExcelProcessor
        _excel_processor = ExcelProcessor(get_embedding_model(), tokenizer)
    return _excel_processor

def get_llm_client():
    """Get the initialized Gemini client"""
    if llm_client is None:
        raise RuntimeError("Gemini client not initialized")
    return llm_client

try:
    # --- New Google GenAI SDK initialization ---
    # The new SDK uses Client initialization instead of configure()
    llm_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    # You don't initialize a separate GenerativeModel object directly; 
    # you often reference the model string via the client or integration.
    # However, if you need a persistent model instance, you can use a placeholder
    # or rely on the integration to handle the model name.
    
    # FIX: Replaced llm_client.models.get(...) with llm_client.models.list() 
    # This is a safer way to confirm connectivity as it takes no explicit arguments.
    # We iterate once to ensure the call succeeds.
    list(llm_client.models.list())
    print("✅ Gemini 2.0 Flash client configured and connected")

    # embedding_model will be loaded lazily when first needed
    embedding_model = None  # Placeholder for backward compatibility

    # This will be initialized in the startup event.
    weaviate_client: Optional[WeaviateClient] = None
    vector_store: Optional[VectorStoreManager] = None

    try:
        # Ensure weaviate connection is set up correctly (e.g., local or remote)
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
    
    print("--- Core Services Initialized Successfully (AI models will load on first use) ---")

# We specifically catch the new API error class if the key or model fails
except APIError as e:
    print(f"❌ Gemini API Error: Check GOOGLE_API_KEY and model availability. Details: {e}")
    exit(1)
except ImportError as e:
    print(f"❌ Missing package: {e}")
    exit(1)
    print(f"❌ Failed to initialize core services: {e}")
    exit(1)

class GenerativeModelWrapper:
    """Wrapper for Google GenAI Client to mimic legacy GenerativeModel interface"""
    def __init__(self, client: genai.Client, model_name: str):
        self.client = client
        self.model_name = model_name

    def generate_content(self, prompt: str):
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        return response

def get_llm_model():
    """Get the initialized LLM model wrapper"""
    if llm_client is None:
        raise RuntimeError("LLM client not initialized")
    return GenerativeModelWrapper(llm_client, GEMINI_MODEL_NAME)