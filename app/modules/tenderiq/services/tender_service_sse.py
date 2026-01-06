import json
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from app.modules.tenderiq.models.pydantic_models import DailyTendersResponse, ScrapedDate, ScrapedDatesResponse, Tender
from app.modules.tenderiq.repositories import repository as tenderiq_repo
from datetime import datetime, timedelta
import threading

# Simple in-memory cache for instant first load
_tender_cache = {
    'last_30_days': None,
    'last_7_days': None,
    'last_5_days': None,
    'timestamp': None
}
_cache_lock = threading.Lock()

def _get_from_cache(date_range: str):
    """Get cached tender data if available and recent (< 5 minutes old)"""
    with _cache_lock:
        if date_range in _tender_cache and _tender_cache[date_range] and _tender_cache['timestamp']:
            age = datetime.now() - _tender_cache['timestamp']
            if age < timedelta(minutes=5):
                return _tender_cache[date_range]
    return None

def _update_cache(date_range: str, data: dict):
    """Update cache with new data"""
    with _cache_lock:
        _tender_cache[date_range] = data
        _tender_cache['timestamp'] = datetime.now()

def _prewarm_cache(db: Session):
    """Pre-warm the cache on server startup - filter by actual publish dates"""
    from datetime import datetime, timedelta
    print("🔥 Warming tender cache for all date ranges...")
    
    # Define date ranges with proper date filtering
    date_configs = [
        {'range': 'last_2_days', 'days': 2},
        {'range': 'last_5_days', 'days': 5},
        {'range': 'last_7_days', 'days': 7},
        {'range': 'last_30_days', 'days': 30}
    ]
    
    scrape_runs = tenderiq_repo.get_scrape_runs(db)
    if not scrape_runs:
        return
    
    # Cache each date range with proper date filtering
    for config in date_configs:
        date_range = config['range']
        days = config['days']
        
        # Calculate min_publish_date for this range
        min_publish_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Get scrape runs for this specific date range
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, days)
        
        if not sliced_scrape_runs:
            print(f"  ⊘ {date_range}: No scrape runs found")
            continue
        
        # Get categories from these runs only
        categories_of_range = []
        for run in sliced_scrape_runs:
            queries_of_this_run = tenderiq_repo.get_all_categories(db, run)
            categories_of_range.extend(queries_of_this_run)
        
        if not categories_of_range:
            print(f"  ⊘ {date_range}: No categories found")
            continue
        
        # Collect tenders WITH DATE FILTERING (up to 300 for better UX)
        all_tenders = []
        seen_ids = set()
        max_for_startup = 300
        
        for category in categories_of_range[:5]:  # First 5 categories for more coverage
            # CRITICAL: Pass min_publish_date to filter by actual tender dates
            tenders = tenderiq_repo.get_tenders_from_category(
                db, category, 0, max_for_startup,
                min_publish_date=min_publish_date
            )
            for t in tenders:
                # Only include tenders with valid data and matching date range
                if t.tender_id_str not in seen_ids and t.tender_name and t.due_date:
                    seen_ids.add(t.tender_id_str)
                    all_tenders.append(t)
                    if len(all_tenders) >= max_for_startup:
                        break
            if len(all_tenders) >= max_for_startup:
                break
        
        if all_tenders:
            # Convert to pydantic
            pydantic_tenders = [Tender.model_validate(t).model_dump(mode='json') for t in all_tenders]
            
            cache_data = {
                'id': str(sliced_scrape_runs[0].id),
                'run_at': str(sliced_scrape_runs[0].run_at),
                'date_str': str(sliced_scrape_runs[0].date_str),
                'name': str(sliced_scrape_runs[0].name),
                'contact': str(sliced_scrape_runs[0].contact),
                'no_of_new_tenders': str(sliced_scrape_runs[0].no_of_new_tenders),
                'company': str(sliced_scrape_runs[0].company),
                'queries': [{
                    'id': str(categories_of_range[0].id),
                    'query_name': categories_of_range[0].query_name,
                    'tenders': pydantic_tenders
                }]
            }
            
            _update_cache(date_range, cache_data)
            print(f"  ✓ {date_range}: Cached {len(pydantic_tenders)} tenders (filtered by date)")
        else:
            print(f"  ⊘ {date_range}: No valid tenders in date range")


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

    # Check cache and send cached data immediately for instant load
    cached_data = _get_from_cache(run_id if run_id else 'default')
    seen_tender_ids = set()
    
    if cached_data:
        print(f"[CACHE HIT] Sending {len([t for q in cached_data.get('queries', []) for t in q.get('tenders', [])])} cached tenders immediately")
        yield ServerSentEvent(
            data=json.dumps(cached_data),
            event='initial_data'
        )
        # Populate seen_tender_ids from cache to avoid duplicates
        if 'queries' in cached_data:
            for query in cached_data['queries']:
                if 'tenders' in query:
                    for tender in query['tenders']:
                        if 'tender_id_str' in tender:
                            seen_tender_ids.add(tender['tender_id_str'])
        print(f"[CACHE] Will stream any new tenders beyond the {len(seen_tender_ids)} cached ones")
    else:
        print(f"[NO CACHE] Streaming all tenders fresh")
        # No cache, send minimal initial data
        yield ServerSentEvent(
            data=to_return.model_dump_json(),
            event='initial_data'
        )

    total_tenders_in_run = 0
    
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
    
    # Stream tenders in batches - fast batches, no sleep delay
    # Accumulate validated tenders before sending to avoid tiny batches
    accumulated_tenders = []
    first_batch_sent = False
    batches_sent = 0
    
    print(f"[STREAM] Processing {len(categories_of_current_day)} categories, already seen {len(seen_tender_ids)} tenders")
    
    for category in categories_of_current_day:
        start = 0
        batch_size = 500  # Very large batches for snappy loading
        category_tender_count = 0
        while True:
            tenders = tenderiq_repo.get_tenders_from_category(
                db, category, start, batch_size, 
                min_publish_date=min_publish_date if min_publish_date else None
            )
            if len(tenders) == 0:
                break

            unique_tenders = []
            for t in tenders:
                if t.tender_id_str not in seen_tender_ids:
                    seen_tender_ids.add(t.tender_id_str)
                    unique_tenders.append(t)
            
            if unique_tenders:
                # For demo purpose: Filter out tenders with missing essential data
                for t in unique_tenders:
                    # A tender must have a name and a due date to be shown
                    if t.tender_name and t.due_date:
                        accumulated_tenders.append(t)
                        category_tender_count += 1
                
                # Send batches immediately once we have at least 1 tender, then every 50 tenders
                if len(accumulated_tenders) >= 50 or (not first_batch_sent and len(accumulated_tenders) >= 1):
                    pydantic_tenders = [Tender.model_validate(t).model_dump(mode='json') for t in accumulated_tenders]
                    total_tenders_in_run += len(pydantic_tenders)
                    batches_sent += 1
                    first_batch_sent = True
                    
                    print(f"[BATCH #{batches_sent}] Sending {len(pydantic_tenders)} tenders")
                    
                    yield ServerSentEvent(
                        data=json.dumps({
                            'query_id': str(category.id),
                            'data': pydantic_tenders
                        }),
                        event='batch'
                    )
                    accumulated_tenders = []  # Clear after sending
            
            start += batch_size
            # Stop if we got less than batch size (no more data)
            if len(tenders) < batch_size:
                break
        
        if category_tender_count > 0:
            print(f"  ✓ Category {category.query_name}: {category_tender_count} new tenders")
    
    # Send any remaining tenders
    if accumulated_tenders:
        pydantic_tenders = [Tender.model_validate(t).model_dump(mode='json') for t in accumulated_tenders]
        total_tenders_in_run += len(pydantic_tenders)
        batches_sent += 1
        
        print(f"[FINAL BATCH] Sending remaining {len(pydantic_tenders)} tenders")
        
        yield ServerSentEvent(
            data=json.dumps({
                'query_id': str(categories_of_current_day[0].id) if categories_of_current_day else '',
                'data': pydantic_tenders
            }),
            event='batch'
        )
    
    print(f"[STREAM COMPLETE] Total new tenders streamed: {total_tenders_in_run}, batches sent: {batches_sent}")
    
    # Update cache with complete data for next request
    cache_key = run_id if run_id else 'default'
    if cache_key in ['last_30_days', 'last_7_days', 'last_5_days', 'last_2_days']:
        # Build complete response for cache
        cache_data = {
            'id': str(to_return.id),
            'run_at': str(to_return.run_at),
            'date_str': to_return.date_str,
            'name': to_return.name,
            'contact': to_return.contact,
            'no_of_new_tenders': to_return.no_of_new_tenders,
            'company': to_return.company,
            'queries': [{'id': str(q.id), 'name': q.query_name, 'tenders': []} for q in categories_of_current_day]
        }
        _update_cache(cache_key, cache_data)
        print(f"[CACHE UPDATE] Cached {total_tenders_in_run} tenders for {cache_key}")
    
    yield ServerSentEvent(event='complete')

def get_daily_tenders_bulk(db: Session, run_id: Optional[str] = None):
    """
    Non-streaming version that returns all tenders at once.
    Much faster than SSE streaming for quick loads.
    """
    from datetime import datetime, timedelta
    
    scrape_runs = tenderiq_repo.get_scrape_runs(db)
    uuid = None

    if run_id == "last_2_days":
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, 2)
    elif run_id == "last_5_days":
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, 5)
    elif run_id == "last_7_days":
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, 7)
    elif run_id == "last_30_days":
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, 30)
    elif run_id == "last_year":
        sliced_scrape_runs = tenderiq_repo.get_scrape_runs_by_date_range(db, 365)
    elif run_id == "latest" or run_id is None:
        sliced_scrape_runs = scrape_runs[0:1]
    else:
        try:
            from uuid import UUID
            UUID(run_id)
            sliced_scrape_runs = [tenderiq_repo.get_scrape_run_by_id(db, run_id)]
        except ValueError:
            sliced_scrape_runs = scrape_runs[0:1]

    if not sliced_scrape_runs:
        return DailyTendersResponse(
            id=UUID('00000000-0000-0000-0000-000000000000'),
            run_at='',
            date_str='',
            name='',
            contact='',
            no_of_new_tenders='0',
            company='',
            queries=[]
        )

    # Calculate min publish date for filtering
    min_publish_date = None
    if run_id in ("last_2_days", "last_5_days", "last_7_days", "last_30_days", "last_year"):
        days_map = {
            "last_2_days": 2,
            "last_5_days": 5,
            "last_7_days": 7,
            "last_30_days": 30,
            "last_year": 365,
        }
        days = days_map.get(run_id, 1)
        min_publish_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    categories_of_current_day = []
    for run in sliced_scrape_runs:
        queries_of_this_run = tenderiq_repo.get_all_categories(db, run)
        categories_of_current_day.extend(queries_of_this_run)

    # Collect ALL tenders at once (no batching)
    seen_tender_ids = set()
    all_tenders = []
    
    for category in categories_of_current_day:
        # Get all tenders for this category at once (no pagination)
        tenders = tenderiq_repo.get_tenders_from_category(
            db, category, 0, 100000,  # Large limit to get all
            min_publish_date=min_publish_date if min_publish_date else None
        )
        
        for t in tenders:
            if t.tender_id_str not in seen_tender_ids:
                # For demo purpose: Filter out tenders with missing essential data
                if t.tender_name and t.due_date:
                    seen_tender_ids.add(t.tender_id_str)
                    all_tenders.append(t)

    # Convert to pydantic models
    pydantic_tenders = [Tender.model_validate(t).model_dump(mode='json') for t in all_tenders]
    
    # Put all tenders in the first query
    if categories_of_current_day:
        categories_of_current_day[0].tenders = pydantic_tenders
        for cat in categories_of_current_day[1:]:
            cat.tenders = []

    to_return = DailyTendersResponse(
        id=UUID(str(sliced_scrape_runs[0].id)),
        run_at=sliced_scrape_runs[0].run_at,
        date_str=str(sliced_scrape_runs[0].date_str),
        name=str(sliced_scrape_runs[0].name),
        contact=str(sliced_scrape_runs[0].contact),
        no_of_new_tenders=str(len(pydantic_tenders)),
        company=str(sliced_scrape_runs[0].company),
        queries=categories_of_current_day
    )

    return to_return

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
