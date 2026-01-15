import os
import warnings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.api.v1.router import api_v1_router
from app.config import settings
from app.utils import ensure_directory_exists

# --- STABILITY FIXES ---
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GRPC_CPP_VERBOSITY"] = "NONE"
os.environ["GLOG_minloglevel"] = "3"
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="PyPDF2")
warnings.filterwarnings("ignore", message="datetime.datetime.utcfromtimestamp()")

# --- APP SETUP ---

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="RAG Chatbot API",
        description="API for the production RAG chatbot backend.",
        version="1.0.0",
    )

    # --- MIDDLEWARE ---
    # Add GZip compression for faster response times
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # In production, restrict this to your frontend's domain
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- EVENT HANDLERS (STARTUP/SHUTDOWN) ---
    @app.on_event("startup")
    async def startup_event():
        print("--- Application Startup ---")
        
        # Initialize database clients within the startup event
        from app.core import services
        
        # Table creation is now managed by Alembic migrations.
        # The create_db_and_tables() function is no longer called on startup.
        
        # Pre-warm tender cache for instant loads
        import threading
        def warm_cache():
            try:
                print("Loading tender cache...")
                from app.db.database import SessionLocal
                from app.modules.tenderiq.services.tender_service_sse import _prewarm_cache
                db = SessionLocal()
                _prewarm_cache(db)
                db.close()
                print("✅ Tender cache warmed successfully")
            except Exception as e:
                print(f"⚠️ Cache warming failed: {e}")
        
        # Run in background thread to not block startup
        threading.Thread(target=warm_cache, daemon=True).start()
        
        print("--- Startup Complete ---")

    @app.on_event("shutdown")
    async def shutdown_event():
        print("--- Application Shutdown ---")
        from app.core.services import weaviate_client
        if weaviate_client:
            weaviate_client.close()
            print("Weaviate client closed.")
        print("--- Shutdown Complete ---")

    app.include_router(api_v1_router, prefix="/api/v1")

    return app

app = create_app()
