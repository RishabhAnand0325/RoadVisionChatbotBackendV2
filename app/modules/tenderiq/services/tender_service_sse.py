import json
from time import sleep
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app.modules.tenderiq.models.pydantic_models import DailyTendersResponse, Tender
from app.modules.tenderiq.repositories import repository as tenderiq_repo

def get_daily_tenders_sse(db: Session):

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
