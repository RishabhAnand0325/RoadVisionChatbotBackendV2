from typing import Optional, Union, List
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
import re
# Assume other necessary imports for ScrapedTender, Tender, etc. are here
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.tenderiq.db.schema import Tender
from app.modules.tenderiq.models.pydantic_models import DailyTendersResponse, FullTenderDetails


# --- NEW HELPER FUNCTION ---
def parse_indian_currency(value: Union[str, int, float, None]) -> int:
    """Cleans an Indian monetary string (including 'Crore') and converts it to an integer."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return 0
    
    # 1. Handle "Crore" conversion (1 Crore = 10,000,000)
    if "crore" in value.lower():
        # Regex to find the number part (including decimals)
        match = re.search(r'[\d,.]+', value.lower().replace('crore', ''))
        if match:
            cleaned_value = match.group(0).replace(',', '')
            try:
                # Multiply by 10,000,000
                return int(float(cleaned_value) * 10000000)
            except ValueError:
                pass # Fall through to general cleaning
            
    # 2. General cleaning: Remove non-numeric, non-dot, non-comma characters
    cleaned_value = re.sub(r'[^\d.]', '', value).replace(',', '') 
    
    try:
        # Convert to float first to handle decimals, then to int
        return int(float(cleaned_value))
    except ValueError:
        return 0 # Return 0 if conversion fails
        
# (Assume get_latest_daily_tenders is here)

def orm_to_dict(obj, visited=None):
    if visited is None:
        visited = set()
    if obj is None:
        return None
    if isinstance(obj, list):
        return [orm_to_dict(o, visited) for o in obj]
    if isinstance(obj, dict):
        return {k: orm_to_dict(v, visited) for k, v in obj.items()}
    obj_id = id(obj)
    if obj_id in visited:
        return None
    visited.add(obj_id)
    if hasattr(obj, "__dict__"):
        data = {}
        for k, v in vars(obj).items():
            if k == "_sa_instance_state" or k == "tender":
                continue
            data[k] = orm_to_dict(v, visited)
        visited.remove(obj_id)
        return data
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        try:
            return int(obj)
        except:
            return float(obj)
    if hasattr(obj, '_value_'):
        return obj._value_
    return obj


def get_full_tender_details(db: Session, tender_id: UUID) -> Optional[FullTenderDetails]:
    # Get ScrapedTender with files and query relationship joined if exists
    scraped_tender = db.query(ScrapedTender).options(
        joinedload(ScrapedTender.files),
        joinedload(ScrapedTender.query)
    ).filter(
        ScrapedTender.id == tender_id
    ).first()

    if scraped_tender is None:
        return None

    tender = db.query(Tender).options(
        joinedload(Tender.history)
    ).filter(
        Tender.tender_ref_number == scraped_tender.tdr
    ).first()

    if tender is None:
        return None

    scraped_dict = orm_to_dict(scraped_tender)
    tender_dict = orm_to_dict(tender)

    # --- FIX 1: Convert emd and tender_value from complex strings to integers ---
    # APPLY THE RENAMED FUNCTION: parse_indian_currency
    if "emd" in scraped_dict:
        scraped_dict['emd'] = parse_indian_currency(scraped_dict['emd'])
    if 'tender_value' in scraped_dict:
        scraped_dict['tender_value'] = parse_indian_currency(scraped_dict['tender_value'])
    if 'emd' in tender_dict:
        tender_dict['emd'] = parse_indian_currency(tender_dict['emd'])
    if 'tender_value' in tender_dict:
        tender_dict['tender_value'] = parse_indian_currency(tender_dict['tender_value'])
        

    # Sanitize string fields that can be legitimately None in the database
    string_fields_to_sanitize = [
        "error_message", "query_id", "tendering_authority", "tender_no",
        "tender_id_detail", "tender_brief", "state", "document_fees", 
        "tender_type", "bidding_type", "competition_type", "tender_details", 
        "company_name", "contact_person", "address", "information_source", 
        "portal_source", "portal_url", "document_url", "reviewed_by_id", 
        "employer_address", "mode"
    ]
    for field in string_fields_to_sanitize:
        for d in (scraped_dict, tender_dict):
            if d.get(field) is None:
                d[field] = ""
    
    # --- FIX 2: Handle relational object for 'query' (Failing because it's an object/dict) ---
    query_obj = scraped_dict.get("query")
    if isinstance(query_obj, dict):
        scraped_dict["query"] = query_obj.get("query_text") or ""
    elif query_obj is None:
        scraped_dict["query"] = ""


    # Convert Decimal (retained)
    for field in [
        "estimated_cost", "bid_security", "length_km", "per_km_cost", "span_length",
        "road_work_amount", "structure_work_amount"
    ]:
        val = tender_dict.get(field)
        if isinstance(val, Decimal):
            tender_dict[field] = int(val)
        elif val is None:
            tender_dict[field] = 0

    # Normalize enums like status (retained)
    tender_dict["status"] = (tender_dict.get("status") or "new").lower()

    # Merge dictionaries, tender fields override scraped fields (retained)
    combined = {**scraped_dict, **tender_dict}

    # --- REMAINING FIXES FOR PYDANTIC ERRORS (retained) ---

    # 1. Fix risk_level (Enum Mismatch)
    if combined.get("risk_level") not in ["low", "medium", "high"]:
        combined["risk_level"] = "low"

    # 2. Handle Boolean fields
    combined["is_favorite"] = combined.get("is_favorite") or False
    combined["is_wishlisted"] = combined.get("is_wishlisted") or False
    combined["is_archived"] = combined.get("is_archived") or False

    if "files" in combined and combined["files"]:
        for file_item in combined["files"]:
            file_item["is_cached"] = file_item.get("is_cached") or False

    # 3. Handle Date fields failing on None by using datetime.min
    date_fields_to_sanitize = [
        "e_published_date", "identification_date", "prebid_meeting_date",
        "site_visit_deadline", "reviewed_at"
    ]
    for field in date_fields_to_sanitize:
        if combined.get(field) is None:
            combined[field] = datetime.min.replace(tzinfo=timezone.utc)
            
    # 4. Process history data: Final fixes for nested types and enums
    if "history" in combined and combined["history"]:
        new_history = []
        for item in combined["history"]:
            
            fallback_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
            
            # FIX: Robustly extract action as a simple string
            action_value = item.get("action")
            
            if isinstance(action_value, dict) and '_value_' in action_value:
                 action_value = action_value['_value_']
            elif hasattr(action_value, '_value_'):
                action_value = action_value._value_
            elif action_value is None or not isinstance(action_value, str):
                action_value = "viewed"
            
            # Fix: tender_history.0.type Enum Mismatch (default to "other")
            history_type = item.get("type")
            if history_type not in ['due_date_extension', 'bid_deadline_extension', 'corrigendum', 'amendment', 'other']:
                 history_type = "other"
            
            # Fix: tender_history.0.update_date requires a string
            update_date_dt = item.get("created_at") or fallback_dt
            update_date_value = update_date_dt.isoformat() if isinstance(update_date_dt, datetime) else str(update_date_dt)


            # Fix: tender_history.0.files_changed requires a list
            files_changed_value = item.get("files_changed")
            if not isinstance(files_changed_value, list):
                files_changed_value = []
                
            # FIX: date_change.from_date/to_date require strings
            date_change_value = item.get("date_change")
            if not isinstance(date_change_value, dict):
                 date_change_value = {}

            # FIX: Convert the sentinel datetime to an ISO string for date_change sub-fields
            sentinel_date_str = datetime.min.replace(tzinfo=timezone.utc).isoformat()
            
            # Ensure the required sub-fields are present and converted to string
            date_change_value["from_date"] = (
                date_change_value.get("from_date").isoformat()
                if isinstance(date_change_value.get("from_date"), datetime)
                else sentinel_date_str
            )
            date_change_value["to_date"] = (
                date_change_value.get("to_date").isoformat()
                if isinstance(date_change_value.get("to_date"), datetime)
                else sentinel_date_str
            )

            history_item_data = {
                # Map standard/simple fields
                "id": str(item.get("id")) if item.get("id") else None,
                "tender_id": str(item.get("tender_id")) if item.get("tender_id") else None,
                "user_id": str(item.get("user_id")) if item.get("user_id") else None,
                "created_at": item.get("created_at") or fallback_dt, 
                
                # Fields required by the TenderHistory Pydantic model
                "action": action_value or "viewed",                                # Uses the string value
                "notes": item.get("notes") or "",                      # 'notes' (plural) field
                "timestamp": item.get("created_at") or fallback_dt,    # Timestamp expected as datetime
                "tdr": item.get("tdr") or "",                       
                "type": history_type,
                "note": item.get("notes") or "",
                "update_date": update_date_value,                      # Expected as string
                "files_changed": files_changed_value,               
                "date_change": date_change_value,                      # Contains string dates
            }
            new_history.append(history_item_data)
        
        combined["history"] = new_history
        combined["tender_history"] = new_history 
    else:
        combined["tender_history"] = []
        combined["history"] = []

    # HACK: Remove the 'history' item if the "action" is empty
    for item in combined["history"]:
        if item["action"] == None:
            combined["history"].remove(item)

    print(combined["history"])

    # Validate the modified dictionary
    return FullTenderDetails.model_validate(combined)
