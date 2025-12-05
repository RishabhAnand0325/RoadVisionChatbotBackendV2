import json
from time import sleep
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
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
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, 2)
        uuid = "found"
    elif run_id == "last_5_days":
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, 5)
        uuid = "found"
    elif run_id == "last_7_days":
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, 7)
        uuid = "found"
    elif run_id == "last_30_days":
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, 30)
        uuid = "found"
    elif run_id == "last_year":
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, 365)
        uuid = "found"
    elif run_id == "latest":
        upper_limit = 1
        uuid = None # Use default logic for latest (first run)
    else:
        upper_limit = 1
        if run_id is not None:
            # Check if run_id is a valid UUID
            try:
                UUID(run_id)
                uuid = run_id
            except ValueError:
                # Not a UUID, assume it's a date string (YYYY-MM-DD or DD-MM-YYYY)
                # Try to find scrape run by date_str
                # We need a new repo method or reuse existing logic
                # For now, let's try to find a run where date_str matches or tender_release_date matches
                # But tenderiq_repo doesn't have a simple "get by date string" that returns a single run ID
                # Let's use get_scrape_runs_by_specific_date from tenderiq_repository (which is different from repository.py)
                # Wait, we are using 'tenderiq_repo' which is 'app.modules.tenderiq.repositories.repository'
                # It doesn't have get_scrape_runs_by_specific_date.
                # We should add it or implement logic here.
                
                # Let's try to match date_str in all runs (inefficient but safe for now)
                all_runs = tenderiq_repo.get_scrape_runs(db)
                found_run = None
                for r in all_runs:
                    # Check date_str (e.g. "Sunday, Nov 02, 2025") or tender_release_date (Date object)
                    if str(r.tender_release_date) == run_id:
                         found_run = r
                         break
                    # Also check if run_id matches date_str format if needed, but usually it's YYYY-MM-DD from frontend
                
                if found_run:
                    uuid = str(found_run.id)
                else:
                    # Fallback or error? If we can't find it, maybe return empty?
                    # If we leave uuid as None, it returns latest. That might be confusing.
                    # Let's return empty list if not found
                    sliced_scrape_runs = []
                    uuid = "not_found" # Sentinel

    if uuid == "not_found":
         sliced_scrape_runs = []
    elif uuid == "found":
         pass # sliced_scrape_runs already set
    else:
        sliced_scrape_runs = scrape_runs[0:upper_limit] if uuid is None else [tenderiq_repo.get_scrape_run_by_id(db, uuid)]

    # Check if there are any scrape runs
    if not sliced_scrape_runs:
        yield ServerSentEvent(
            data=json.dumps({"queries": [], "message": "No scrape runs available"}),
            event='initial_data'
        )
        return

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

    yield ServerSentEvent(
        data=to_return.model_dump_json(),
        event='initial_data'
    )

    seen_tender_ids = set()
    
    # Calculate min publish date for filtering when date_range is used
    min_publish_date = None
    if run_id in ("last_2_days", "last_5_days", "last_7_days", "last_30_days", "last_year"):
        from datetime import datetime, timedelta
        days_map = {
            "last_2_days": 2,
            "last_5_days": 5,
            "last_7_days": 7,
            "last_30_days": 30,
            "last_year": 365,
        }
        days = days_map.get(run_id, 1)
        min_publish_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    for category in categories_of_current_day:
        start = 0
        batch = 100
        while True:
            tenders = tenderiq_repo.get_tenders_from_category(db, category, start, batch)
            if len(tenders) == 0:
                break

            unique_tenders = []
            for t in tenders:
                if t.tender_id_str not in seen_tender_ids:
                    # Filter by publish_date if date_range is specified
                    if min_publish_date:
                        try:
                            publish_date_str = t.publish_date
                            if not publish_date_str or publish_date_str == "None":
                                continue
                            
                            if not isinstance(publish_date_str, str):
                                publish_date_str = str(publish_date_str)
                            
                            # Parse DD-MM-YYYY format to YYYY-MM-DD for comparison
                            if len(publish_date_str) >= 10:
                                if publish_date_str[2] == '-' and publish_date_str[5] == '-':
                                    parts = publish_date_str[:10].split('-')
                                    day, month, year = parts
                                    comparable_date = f"{year}-{month}-{day}"
                                    if comparable_date < min_publish_date:
                                        continue
                        except (ValueError, TypeError, AttributeError, IndexError):
                            continue
                    
                    seen_tender_ids.add(t.tender_id_str)
                    unique_tenders.append(t)
            
            if unique_tenders:
                pydantic_tenders = [Tender.model_validate(t).model_dump(mode='json') for t in unique_tenders]
                yield ServerSentEvent(
                    data=json.dumps({
                        'query_id': str(category.id),
                        'data': pydantic_tenders
                    }),
                    event='batch'
                )
            start += batch
            sleep(0.5)
    yield ServerSentEvent(event='complete')

def _safe_int(value, default: int = 0) -> int:
    """
    Safely convert a value to int.
    Falls back to `default` for None, 'None', empty strings, or other invalid values.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_scraped_dates(db: Session) -> ScrapedDatesResponse:
    scrape_runs = tenderiq_repo.get_scrape_runs(db)
    
    # Filter out runs with invalid dates
    valid_runs = [s for s in scrape_runs if s.date_str and s.date_str != "N/A"]
    
    dates_list = []
    if valid_runs:
        latest_valid_id = valid_runs[0].id
        dates_list = []
        for s in valid_runs:
            tender_count = _safe_int(s.no_of_new_tenders, default=0)

            dates_list.append(
                ScrapedDate(
                    id=str(s.id),
                    date=str(s.date_str),
                    run_at=str(s.run_at),
                    tender_count=tender_count,
                    is_latest=bool(s.id == latest_valid_id),
                )
            )

    return ScrapedDatesResponse(dates=dates_list)
