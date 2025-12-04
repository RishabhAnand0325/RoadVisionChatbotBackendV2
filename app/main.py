import os
import warnings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_v1_router
from app.config import settings
from app.utils import ensure_directory_exists

# --- STABILITY FIXES ---
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GRPC_CPP_VERBOSITY"] = "NONE"
os.environ["GLOG_minloglevel"] = "3"
warnings.filterwarnings("ignore")

# --- APP SETUP ---

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="RAG Chatbot API",
        description="API for the production RAG chatbot backend.",
        version="1.0.0",
    )

    # --- MIDDLEWARE ---
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
