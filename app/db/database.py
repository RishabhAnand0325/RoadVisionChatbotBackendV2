from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Create the SQLAlchemy engine
engine = create_engine(settings.DATABASE_URL)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a base class for declarative models
Base = declarative_base()

def create_db_and_tables():
    """
    Creates the database and all tables defined across all modules.
    This function discovers models that inherit from the Base class.
    """
    # Import all modules that contain SQLAlchemy models here
    # so that they are registered with the Base metadata.
    from app.modules.askai.db import models
    
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")

# FastAPI dependency to get a DB session for a single request
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
