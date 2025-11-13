import json
from time import sleep
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app.modules.scraper.db.schema import ScrapeRun
from app.modules.tenderiq.models.pydantic_models import DailyTendersResponse, ScrapedDate, ScrapedDatesResponse, Tender
from app.modules.tenderiq.repositories import repository as tenderiq_repo

def get_daily_tenders_limited(db: Session, start: int, end: int):
    scrape_runs = tenderiq_repo.get_scrape_runs(db)
    latest_scrape_run = scrape_runs[-1]
    categories_of_current_day = tenderiq_repo.get_all_categories(db, latest_scrape_run)

    to_return = DailyTendersResponse(
        id = latest_scrape_run.id,
        run_at = latest_scrape_run.run_at,
        date_str = latest_scrape_run.date_str,
        name = latest_scrape_run.name,
        contact = latest_scrape_run.contact,
        no_of_new_tenders = latest_scrape_run.no_of_new_tenders,
        company = latest_scrape_run.company,
        queries = []
    )

    for category in categories_of_current_day:
        tenders = tenderiq_repo.get_tenders_from_category(db, category, start, end)
        pydantic_tenders = [Tender.model_validate(t).model_dump(mode='json') for t in tenders]
        category.tenders = pydantic_tenders
        to_return.queries.append(category)

    return to_return

def get_daily_tenders_sse(db: Session, start: Optional[int] = 0, end: Optional[int] = 1000, run_id: Optional[str] = None):
    scrape_runs = tenderiq_repo.get_scrape_runs(db)
    latest_scrape_run = scrape_runs[0]
    categories_of_current_day = tenderiq_repo.get_all_categories(db, latest_scrape_run)

    to_return = DailyTendersResponse(
        id = latest_scrape_run.id,
        run_at = latest_scrape_run.run_at,
        date_str = latest_scrape_run.date_str,
        name = latest_scrape_run.name,
        contact = latest_scrape_run.contact,
        no_of_new_tenders = latest_scrape_run.no_of_new_tenders,
        company = latest_scrape_run.company,
        queries = categories_of_current_day
    )

    yield {
        'event': 'initial_data',
        'data': to_return.model_dump_json()
    }

    for category in categories_of_current_day:
        batch = 100
        while True:
            tenders = tenderiq_repo.get_tenders_from_category(db, category, start, batch)
            if len(tenders) == 0:
                break

            pydantic_tenders = [Tender.model_validate(t).model_dump(mode='json') for t in tenders]
            yield {
                'event': 'batch',
                'data': json.dumps({
                    'query_id': str(category.id),
                    'data': pydantic_tenders
                })
            }
            start += batch
            sleep(0.5)
    yield {
        'event': 'complete',
    }

def get_scraped_dates(db: Session) -> ScrapedDatesResponse:
    scrape_runs = tenderiq_repo.get_scrape_runs(db)
    scrape_runs_response: ScrapedDatesResponse = ScrapedDatesResponse(
        dates = [
            ScrapedDate(
                id=str(s.id),
                date=str(s.date_str),
                run_at=str(s.run_at),
                tender_count=int(str(s.no_of_new_tenders)),
                is_latest=bool(s.id == scrape_runs[0].id)
            ) for s in scrape_runs
        ]
    )

    return scrape_runs_response
