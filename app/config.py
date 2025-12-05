import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

class Settings:
    # Paths
    ROOT_DIR: Path = Path(__file__).parent.parent.resolve()
    CHROMA_PATH: Path = ROOT_DIR / "chroma_db"
    DATA_DIR: Path = ROOT_DIR / "data"

    # Document Processing
    MAX_CHUNKS_PER_DOCUMENT: int = 2000
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    MAX_PDFS_PER_CHAT: int = 5
    MAX_EXCEL_PER_CHAT: int = 2
    MAX_PDF_SIZE_MB: int = 50
    MAX_EXCEL_SIZE_MB: int = 10

    # Archive Processing
    MAX_ARCHIVE_RECURSION_DEPTH: int = 3  # Max nested archive extraction depth
    MAX_FILES_PER_ARCHIVE: int = 100  # Max files in archive (prevents extraction bombs)
    MAX_EXTRACTED_SIZE_MB: int = 500  # Max total uncompressed archive size

    # RAG
    RAG_TOP_K: int = 15  # Number of documents to retrieve per query
    RAG_MEMORY_SIZE: int = 10  # Number of recent messages to keep in memory (Phase 2+)

    # Feature Flags
    USE_LANGCHAIN_RAG: bool = False  # Toggle for LangChain migration (Phase 1+)

    # API Keys
    GOOGLE_API_KEY: str = ""
    LLAMA_CLOUD_API_KEY: str = ""
    
    # PostgreSQL
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/postgres"

    # Redis for Caching, Pub/Sub, and Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Celery for Background Tasks
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND_URL: str = ""

    # Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_SECRET_KEY: str = "secret"
    ALGORITHM: str = "HS256"
    
    # Environment
    ENV: str = "development"

    def __init__(self):
        self._load_and_validate_env()

    def _load_and_validate_env(self):
        """Load and validate environment variables"""
        print("🔍 Loading environment variables...")
        
        env_path = self.ROOT_DIR / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, verbose=True)
        else:
            load_dotenv(verbose=True)

        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise Exception("❌ GOOGLE_API_KEY not found in environment!")
        self.GOOGLE_API_KEY = google_api_key

        llama_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not llama_api_key:
            raise Exception("❌ LLAMA_CLOUD_API_KEY not found in environment!")
        self.LLAMA_CLOUD_API_KEY = llama_api_key
        
        # Load PostgreSQL settings
        self.POSTGRES_USER = os.getenv("POSTGRES_USER", self.POSTGRES_USER)
        self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self.POSTGRES_DB = os.getenv("POSTGRES_DB", self.POSTGRES_DB)
        self.POSTGRES_HOST = os.getenv("POSTGRES_HOST", self.POSTGRES_HOST)
        self.POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", self.POSTGRES_PORT))

        self.DATABASE_URL = (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
        
        print(f"✅ GOOGLE_API_KEY: configured")
        print(f"✅ LLAMA_CLOUD_API_KEY: {'configured' if self.LLAMA_CLOUD_API_KEY else 'not configured (optional)'}")
        print(f"✅ PostgreSQL: configured at {self.POSTGRES_HOST}:{self.POSTGRES_PORT}")

        # Load Redis settings and configure Celery URLs
        self.REDIS_HOST = os.getenv("REDIS_HOST", self.REDIS_HOST)
        self.REDIS_PORT = int(os.getenv("REDIS_PORT", self.REDIS_PORT))
        self.REDIS_DB = int(os.getenv("REDIS_DB", self.REDIS_DB))
        self.CELERY_BROKER_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        self.CELERY_RESULT_BACKEND_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        print(f"✅ Redis: configured at {self.REDIS_HOST}:{self.REDIS_PORT}")

        # Load security settings
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", self.JWT_SECRET_KEY)
        self.ALGORITHM = os.getenv("JWT_ALGORITHM", self.ALGORITHM)
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", self.ACCESS_TOKEN_EXPIRE_MINUTES))

        # Load feature flags
        self.USE_LANGCHAIN_RAG = os.getenv("USE_LANGCHAIN_RAG", "false").lower() == "true"
        if self.USE_LANGCHAIN_RAG:
            print("⚠️  LANGCHAIN_RAG: enabled (Phase 1+ migration in progress)")

# Singleton instance
settings = Settings()
