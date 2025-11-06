"""
Celery tasks for the TenderIQ analysis module.
"""
import asyncio
import uuid
from app.celery_app import celery_app
from app.db.database import SessionLocal
from .db.repository import AnalyzeRepository
from .events import publish_update
from .schema import AnalysisStatusEnum
from .services.document_parsing_service import DocumentParsingService

async def _run_analysis_async(analysis_id: uuid.UUID):
    """Asynchronous wrapper for the analysis process."""
    db = SessionLocal()
    repo = AnalyzeRepository(db)
    analysis = repo.get_by_id(analysis_id)
    if not analysis:
        return

    try:
        # 1. Parsing Phase
        repo.update(analysis, {"status": AnalysisStatusEnum.parsing, "progress": 10, "status_message": "Initializing document parsing..."})
        publish_update(analysis_id, "status", {"status": "parsing", "progress": 10, "message": "Initializing document parsing..."})
        
        parsing_service = DocumentParsingService(db)
        await parsing_service.parse_documents_for_analysis(analysis_id)
        
        repo.update(analysis, {"progress": 30, "status_message": "Document parsing complete."})
        publish_update(analysis_id, "status", {"progress": 30, "message": "Document parsing complete."})

        # 2. Analysis Phase
        repo.update(analysis, {"status": AnalysisStatusEnum.analyzing, "progress": 40, "status_message": "Extracting key information..."})
        publish_update(analysis_id, "status", {"status": "analyzing", "progress": 40, "message": "Extracting key information..."})

        # TODO: Call One-Pager, Scope of Work, etc. services here.
        # Each service will be responsible for updating the DB and publishing its own results.
        await asyncio.sleep(5) # Placeholder for real work

        # 3. Finalization
        repo.update(analysis, {"status": AnalysisStatusEnum.completed, "progress": 100, "status_message": "Analysis complete."})
        publish_update(analysis_id, "status", {"status": "completed", "progress": 100, "message": "Analysis complete."})
        publish_update(analysis_id, "control", "close", event_type="control")

    except Exception as e:
        repo.update(analysis, {"status": AnalysisStatusEnum.failed, "error_message": str(e)})
        publish_update(analysis_id, "error", {"message": str(e)}, event_type="error")
        publish_update(analysis_id, "control", "close", event_type="control")
    finally:
        db.close()

@celery_app.task
def run_tender_analysis(analysis_id: str):
    """
    The main Celery task to perform a full tender analysis.
    This synchronous task runs the main async analysis function.
    """
    asyncio.run(_run_analysis_async(uuid.UUID(analysis_id)))
