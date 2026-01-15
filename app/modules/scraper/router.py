from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, HttpUrl
from typing import Optional
from uuid import UUID
from app.db.database import get_db_session
from app.modules.auth.services.auth_service import get_current_active_user
from app.modules.auth.db.schema import User
from app.modules.scraper.main import scrape_link
from app.modules.scraper.db.repository import ScraperRepository
from app.modules.scraper.db.schema import ScrapeRun

router = APIRouter()


class ScrapeLinkRequest(BaseModel):
    link: HttpUrl
    source_priority: Optional[str] = "normal"
    skip_dedup_check: Optional[bool] = False


class ScrapeStatusResponse(BaseModel):
    status: str
    message: str
    scrape_run_id: Optional[str] = None


@router.post("/scrape/link", response_model=ScrapeStatusResponse, tags=["Scraper"])
async def trigger_scrape(
    request: ScrapeLinkRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Trigger scraping for a tender link.
    This endpoint accepts a link and starts scraping in the background.
    """
    try:
        # Add scraping task to background
        background_tasks.add_task(
            scrape_link,
            str(request.link),
            request.source_priority,
            request.skip_dedup_check
        )
        
        return ScrapeStatusResponse(
            status="started",
            message=f"Scraping started for link: {request.link}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start scraping: {str(e)}"
        )


@router.get("/scrape/runs", tags=["Scraper"])
def get_scrape_runs(
    limit: Optional[int] = 10,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get recent scrape runs.
    """
    try:
        repo = ScraperRepository(db)
        runs = repo.get_available_scrape_runs()
        return {
            "runs": [
                {
                    "id": str(run.id),
                    "run_at": run.run_at.isoformat() if run.run_at else None,
                    "tender_release_date": run.tender_release_date.isoformat() if run.tender_release_date else None,
                    "date_str": run.date_str,
                    "name": run.name,
                    "company": run.company,
                    "no_of_new_tenders": run.no_of_new_tenders,
                }
                for run in runs[:limit]
            ],
            "total": len(runs)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch scrape runs: {str(e)}"
        )


@router.get("/scrape/runs/{run_id}", tags=["Scraper"])
def get_scrape_run_details(
    run_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get details of a specific scrape run.
    """
    try:
        repo = ScraperRepository(db)
        # Query the scrape run with relationships loaded
        run = (
            db.query(ScrapeRun)
            .filter(ScrapeRun.id == UUID(run_id))
            .options(
                joinedload(ScrapeRun.queries)
            )
            .first()
        )
        
        if not run:
            raise HTTPException(status_code=404, detail="Scrape run not found")
        
        return {
            "id": str(run.id),
            "run_at": run.run_at.isoformat() if run.run_at else None,
            "tender_release_date": run.tender_release_date.isoformat() if run.tender_release_date else None,
            "date_str": run.date_str,
            "name": run.name,
            "company": run.company,
            "contact": run.contact,
            "no_of_new_tenders": run.no_of_new_tenders,
            "queries": [
                {
                    "id": str(query.id),
                    "query_name": query.query_name,
                    "number_of_tenders": query.number_of_tenders,
                }
                for query in run.queries
            ]
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch scrape run: {str(e)}"
        )
