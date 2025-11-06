"""
Celery tasks for the TenderIQ analysis module.
"""
from app.celery_app import celery_app
from app.db.database import SessionLocal
from .db.repository import AnalyzeRepository
from .events import publish_update
from .schema import AnalysisStatusEnum

@celery_app.task
def run_tender_analysis(analysis_id: str):
    """
    The main Celery task to perform a full tender analysis.
    This task orchestrates all sub-services for parsing, analysis, and data extraction.
    """
    db = SessionLocal()
    try:
        repo = AnalyzeRepository(db)
        analysis = repo.get_by_id(analysis_id)
        if not analysis:
            # Analysis record was deleted after task was queued.
            return

        # 1. Update status to 'parsing' and notify
        repo.update(analysis, {"status": AnalysisStatusEnum.parsing, "progress": 10, "status_message": "Parsing documents..."})
        publish_update(analysis_id, "status", {"status": "parsing", "progress": 10, "message": "Parsing documents..."})
        
        # TODO: Call Document Parsing Service here

        # 2. Update status to 'analyzing' and notify
        repo.update(analysis, {"status": AnalysisStatusEnum.analyzing, "progress": 30, "status_message": "Extracting key information..."})
        publish_update(analysis_id, "status", {"status": "analyzing", "progress": 30, "message": "Extracting key information..."})

        # TODO: Call One-Pager, Scope of Work, and other analysis services here
        # Each service will update the DB and publish its own results.

        # 3. Finalize and mark as complete
        repo.update(analysis, {"status": AnalysisStatusEnum.completed, "progress": 100, "status_message": "Analysis complete."})
        publish_update(analysis_id, "status", {"status": "completed", "progress": 100, "message": "Analysis complete."})
        publish_update(analysis_id, "control", "close", event_type="control")

    except Exception as e:
        # Handle errors
        repo = AnalyzeRepository(db)
        repo.update(analysis, {"status": AnalysisStatusEnum.failed, "error_message": str(e)})
        publish_update(analysis_id, "error", {"message": str(e)}, event_type="error")
        publish_update(analysis_id, "control", "close", event_type="control")
    
    finally:
        db.close()
