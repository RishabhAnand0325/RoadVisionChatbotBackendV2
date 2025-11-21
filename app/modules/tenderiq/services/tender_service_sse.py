import json
from time import sleep
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app.modules.tenderiq.models.pydantic_models import DailyTendersResponse, ScrapedDate, ScrapedDatesResponse, Tender, ScrapedTenderQuery
from app.modules.tenderiq.repositories import repository as tenderiq_repo
from app.modules.tenderiq.db.tenderiq_repository import TenderIQRepository

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
    """
    run_id here could be a UUID mapping to a ScrapeRun
    OR it could be one of the following strings:
        "latest"
        "last_2_days"
        "last_5_days"
        "last_7_days"
        "last_30_days"
    """

    scrape_runs = tenderiq_repo.get_scrape_runs(db)
    upper_limit = 1
    uuid = None

    if run_id == "last_2_days":
        upper_limit = min(2, len(scrape_runs))
    elif run_id == "last_5_days":
        upper_limit = min(5, len(scrape_runs))
    elif run_id == "last_7_days":
        upper_limit = min(7, len(scrape_runs))
    elif run_id == "last_30_days":
        upper_limit = min(30, len(scrape_runs))
    elif run_id == "latest":
        upper_limit = 1
    else:
        upper_limit = 1
        uuid = run_id if run_id is not None else None

    sliced_scrape_runs = scrape_runs[0:upper_limit] if uuid is None else [tenderiq_repo.get_scrape_run_by_id(db, uuid)]
    categories_of_current_day: list[ScrapedTenderQuery] = []
    for run in sliced_scrape_runs:
        queries_of_this_run = tenderiq_repo.get_all_categories(db, run)
        categories_of_current_day.extend(queries_of_this_run)

    to_return = DailyTendersResponse(
        id = UUID(str(sliced_scrape_runs[0].id)),
        run_at = sliced_scrape_runs[0].run_at,
        date_str = str(sliced_scrape_runs[0].date_str),
        name = str(sliced_scrape_runs[0].name),
        contact = str(sliced_scrape_runs[0].contact),
        no_of_new_tenders = str(sliced_scrape_runs[0].no_of_new_tenders),
        company = str(sliced_scrape_runs[0].company),
        queries = categories_of_current_day
    )

    yield {
        'event': 'initial_data',
        'data': to_return.model_dump_json()
    }

    for category in categories_of_current_day:
        start = 0
        batch = 100
        while True:
            tenders = tenderiq_repo.get_tenders_from_category(db, category, start, batch)
            if len(tenders) == 0:
                break

            # Enrich tenders with action flags before converting to Pydantic
            tenderiq_repository = TenderIQRepository(db)
            enriched_tenders = tenderiq_repository.enrich_scraped_tenders_with_flags(tenders)
            pydantic_tenders = [Tender.model_validate(t).model_dump(mode='json') for t in enriched_tenders]
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
