from typing import Optional, Union, List
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
import re
from dateutil import parser as date_parser
# Assume other necessary imports for ScrapedTender, Tender, etc. are here
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.tenderiq.db.schema import Tender, TenderWishlist
from app.modules.tenderiq.models.pydantic_models import DailyTendersResponse, FullTenderDetails, Tender as TenderModel
from app.modules.tenderiq.repositories import repository as tenderiq_repo
# REMOVED: Lazy import corrigendum service only when needed
# from app.modules.tenderiq.services.corrigendum_service import CorrigendumTrackingService


# --- NEW HELPER FUNCTION FOR DATE STANDARDIZATION ---
def normalize_date_format(date_str: Optional[str]) -> str:
    """
    Converts various date formats to a standard ISO-like format (YYYY-MM-DD).
    Handles: DD-MM-YYYY, DD/MM/YYYY, DD-Mon-YYYY, ISO formats, and others.
    Returns empty string if date cannot be parsed.
    """
    if not date_str or not isinstance(date_str, str):
        return ""
    
    date_str = date_str.strip()
    if not date_str:
        return ""
    
    try:
        # First, try explicit DD-MM-YYYY format (most common in India)
        if len(date_str) == 10 and date_str.count('-') == 2:
            parts = date_str.split('-')
            if all(p.isdigit() for p in parts):
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                    from datetime import datetime as dt
                    parsed_date = dt(year, month, day)
                    return parsed_date.strftime("%Y-%m-%d")
        
        # Try dateutil parser for flexible parsing
        parsed_date = date_parser.parse(date_str, dayfirst=True)
        return parsed_date.strftime("%Y-%m-%d")
    except Exception:
        pass
    
    # If all parsing fails, return the original string (frontend will handle it)
    return date_str


# --- NEW HELPER FUNCTION ---
def parse_indian_currency(value: Union[str, int, float, None]) -> Union[int, str]:
    """Cleans an Indian monetary string (including 'Crore') and converts it to an integer.
    Returns the original string if it contains 'Ref Document' or similar non-numeric text."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return 0
    
    # Check if the value contains "Ref Document" or similar text - return as-is
    value_lower = value.lower()
    if any(keyword in value_lower for keyword in ['ref document', 'refer document', 'refer to document', 'see document', 'as per document']):
        return value
    
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

def get_full_tender_details(db: Session, tender_id: UUID, tdr: Optional[str] = None) -> Optional[FullTenderDetails]:
    """
    Get complete tender details with optimized queries and proper eager loading.
    """
    # Import here to avoid circular imports
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        tender_id_str = str(tender_id)
        # logger.info(f"Fetching tender details for ID: {tender_id_str}")
        
        # Step 1: Try ScrapedTender first (most common case)
        scraped_tender = db.query(ScrapedTender).options(
            joinedload(ScrapedTender.files),
            joinedload(ScrapedTender.query)
        ).filter(
            ScrapedTender.id == tender_id
        ).first()

        if scraped_tender is None:
            # Step 2: Try Tender directly
            tender = db.query(Tender).options(
                joinedload(Tender.history)
            ).filter(
                Tender.id == tender_id
            ).first()
            
            if tender is None:
                # Step 3: If tdr provided, lookup by tdr
                if tdr:
                    tender = db.query(Tender).options(
                        joinedload(Tender.history)
                    ).filter(
                        Tender.tender_ref_number == tdr
                    ).first()
                    
                    if tender is not None:
                        # Get most recent ScrapedTender by tdr
                        scraped_tender = db.query(ScrapedTender).options(
                            joinedload(ScrapedTender.files),
                            joinedload(ScrapedTender.query)
                        ).filter(
                            ScrapedTender.tdr == tdr
                        ).order_by(ScrapedTender.id.desc()).first()
                        
                        scraped_dict = orm_to_dict(scraped_tender) if scraped_tender else {}
                        tender_dict = orm_to_dict(tender)
                    else:
                        return None
                else:
                    # Step 4: Try TenderWishlist lookup
                    wishlist_entry = db.query(TenderWishlist).filter(
                        TenderWishlist.id == tender_id_str
                    ).first()
                    
                    if wishlist_entry is not None and wishlist_entry.tender_ref_number:
                        tdr_from_wishlist = wishlist_entry.tender_ref_number
                        
                        tender = db.query(Tender).options(
                            joinedload(Tender.history)
                        ).filter(
                            Tender.tender_ref_number == tdr_from_wishlist
                        ).first()
                        
                        if tender is not None:
                            scraped_tender = db.query(ScrapedTender).options(
                                joinedload(ScrapedTender.files),
                                joinedload(ScrapedTender.query)
                            ).filter(
                                ScrapedTender.tdr == tdr_from_wishlist
                            ).order_by(ScrapedTender.id.desc()).first()
                            
                            scraped_dict = orm_to_dict(scraped_tender) if scraped_tender else {}
                            tender_dict = orm_to_dict(tender)
                        else:
                            return None
                    else:
                        return None
            else:
                # Found Tender, get ScrapedTender by tdr
                scraped_tender = db.query(ScrapedTender).options(
                    joinedload(ScrapedTender.files),
                    joinedload(ScrapedTender.query)
                ).filter(
                    ScrapedTender.tdr == tender.tender_ref_number
                ).first()
                
                if scraped_tender is None:
                    logger.info(f"ScrapedTender not found for tender_ref: {tender.tender_ref_number}. Using Tender data alone.")
                    scraped_dict = {}
                    tender_dict = orm_to_dict(tender)
                else:
                    scraped_dict = orm_to_dict(scraped_tender)
                    tender_dict = orm_to_dict(tender)
        else:
            logger.debug(f"Step 1 success: Found ScrapedTender. Looking for corresponding Tender by tdr: {scraped_tender.tdr}")
            # Found ScrapedTender, now get corresponding Tender
            tender = db.query(Tender).options(
                joinedload(Tender.history)
            ).filter(
                Tender.tender_ref_number == scraped_tender.tdr
            ).first()

            if tender is None:
                # Use ScrapedTender data alone
                logger.info(f"Tender not found for tdr: {scraped_tender.tdr}. Using ScrapedTender data alone.")
                scraped_dict = orm_to_dict(scraped_tender)
                tender_dict = {}
            else:
                scraped_dict = orm_to_dict(scraped_tender)
                tender_dict = orm_to_dict(tender)
    
    except Exception as e:
        logger.error(f"Error loading tender data for ID {tender_id}: {str(e)}", exc_info=True)
        raise

    # --- FIX 1: Convert emd and tender_value from complex strings to integers ---
    # APPLY THE RENAMED FUNCTION: parse_indian_currency
    try:
        if scraped_dict and "emd" in scraped_dict:
            parsed_emd = parse_indian_currency(scraped_dict['emd'])
            # If parsing returns a string (non-numeric), set to None for Optional[int] field
            scraped_dict['emd'] = parsed_emd if isinstance(parsed_emd, int) else None
        if scraped_dict and 'tender_value' in scraped_dict:
            parsed_value = parse_indian_currency(scraped_dict['tender_value'])
            scraped_dict['tender_value'] = parsed_value if isinstance(parsed_value, int) else None
        if tender_dict and 'emd' in tender_dict:
            parsed_emd = parse_indian_currency(tender_dict['emd'])
            tender_dict['emd'] = parsed_emd if isinstance(parsed_emd, int) else None
        if tender_dict and 'tender_value' in tender_dict:
            parsed_value = parse_indian_currency(tender_dict['tender_value'])
            tender_dict['tender_value'] = parsed_value if isinstance(parsed_value, int) else None
    except Exception as e:
        logger.error(f"Error parsing currency values for tender {tender_id}: {str(e)}", exc_info=True)
        # Don't fail completely, just log and continue
        # Set to None if parsing fails
        if scraped_dict and "emd" in scraped_dict:
            scraped_dict['emd'] = None
        if scraped_dict and 'tender_value' in scraped_dict:
            scraped_dict['tender_value'] = None
        if tender_dict and 'emd' in tender_dict:
            tender_dict['emd'] = None
        if tender_dict and 'tender_value' in tender_dict:
            tender_dict['tender_value'] = None

    # Sanitize string fields that can be legitimately None in the database
    string_fields_to_sanitize = [
        "error_message", "query_id", "tendering_authority", "tender_no",
        "tender_id_detail", "tender_brief", "state", "document_fees", 
        "tender_type", "bidding_type", "competition_type", "tender_details", 
        "company_name", "contact_person", "address", "information_source", 
        "portal_source", "portal_url", "document_url", "reviewed_by_id", 
        "employer_address", "mode", "tender_opening_date", "publish_date",
        "last_date_of_bid_submission"
    ]
    for field in string_fields_to_sanitize:
        for d in (scraped_dict, tender_dict):
            if d.get(field) is None:
                d[field] = ""
    

    
    # --- FIX 2: Handle relational object for 'query' (Failing because it's an object/dict) ---
    query_obj = scraped_dict.get("query")
    if isinstance(query_obj, dict):
        # Extract query_name for category field
        query_name = query_obj.get("query_name") or query_obj.get("query_text") or ""
        scraped_dict["query"] = query_obj.get("query_text") or ""
        # Set category from query_name if not already set
        if not scraped_dict.get("category"):
            scraped_dict["category"] = query_name
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
    
    # PRESERVE scraped_dict fields that shouldn't be overridden by empty tender_dict values
    # This is critical for fields like dates and information_source where tender_dict may have empty strings or None
    preserve_from_scraped = [
        "information_source", "publish_date", "tender_opening_date", 
        "last_date_of_bid_submission", "city", "state", "category"
    ]
    for field in preserve_from_scraped:
        # Check if scraped_dict has a non-empty value and combined either doesn't have it or has None/empty
        if scraped_dict.get(field) and (not combined.get(field) or combined.get(field) in [None, "", "None"]):
            combined[field] = scraped_dict[field]
    
    # FIX LOCATION LOGIC: Ensure city, location, and state are properly mapped
    # ScrapedTender has 'city' and 'state', Tender has 'location' and 'state'
    # We need to ensure all three fields are present and consistent
    if not combined.get("city") and combined.get("location"):
        combined["city"] = combined["location"]
    elif not combined.get("location") and combined.get("city"):
        combined["location"] = combined["city"]
    
    # Ensure state is properly set
    if not combined.get("state") and scraped_dict.get("state"):
        combined["state"] = scraped_dict["state"]
    elif not combined.get("state") and tender_dict.get("state"):
        combined["state"] = tender_dict["state"]
    
    # FIX LOCATION FORMATTING: Ensure city and state are properly capitalized (title case)
    if combined.get("city") and isinstance(combined.get("city"), str):
        combined["city"] = combined["city"].title()
    if combined.get("location") and isinstance(combined.get("location"), str):
        combined["location"] = combined["location"].title()
    if combined.get("state") and isinstance(combined.get("state"), str):
        combined["state"] = combined["state"].title()
    
    # FIX CATEGORY LOGIC: Ensure category is properly set from scraped_dict if tender_dict has None/empty
    # Category comes from query.query_name which we extracted earlier
    # This is critical - category must never be empty or None
    if not combined.get("category") or combined.get("category") in [None, "", "None"]:
        if scraped_dict.get("category"):
            combined["category"] = scraped_dict["category"]

    # --- FIX: Ensure nullable string fields are never None ---
    # This must happen after the merge to catch any None values that made it through
    # NOTE: category is NOT in this list because we handle it specially above
    nullable_string_fields = [
        "error_message", "query_id", "tendering_authority", "tender_no",
        "tender_id_detail", "tender_brief", "state", "document_fees", 
        "tender_type", "bidding_type", "competition_type", "tender_details", 
        "company_name", "contact_person", "address", "information_source", 
        "portal_source", "portal_url", "document_url", "reviewed_by_id", 
        "employer_address", "mode", "tender_opening_date", "publish_date",
        "last_date_of_bid_submission", "city", "location"
    ]
    for field in nullable_string_fields:
        if combined.get(field) is None:
            combined[field] = ""
    # --- NORMALIZE ALL DATE FIELDS TO STANDARD FORMAT ---
    date_fields = ["publish_date", "due_date", "last_date_of_bid_submission", "tender_opening_date"]
    for field in date_fields:
        if field in combined and combined[field]:
            combined[field] = normalize_date_format(combined[field])

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
    # Initialize history array if not present
    if "history" not in combined:
        combined["history"] = []
    
    # Add scraped actions history from ScrapedTender if available
    if scraped_dict and scraped_dict.get("actions_history_json"):
        scraped_actions = scraped_dict.get("actions_history_json", {})
        if isinstance(scraped_actions, dict) and scraped_actions.get("items"):
            for action_item in scraped_actions.get("items", []):
                # Convert scraped action to ActionHistoryItem format
                action_history_item = {
                    "id": f"scraped_action_{len(combined.get('history', []))}",
                    "tender_id": str(tender.id) if tender else "",
                    "user_id": None,  # Scraped actions don't have user info
                    "action": action_item.get("action", "viewed"),
                    "notes": action_item.get("notes") or action_item.get("note") or "",
                    "timestamp": action_item.get("timestamp") or datetime.now(timezone.utc),
                    "created_at": action_item.get("timestamp") or datetime.now(timezone.utc),
                }
                combined["history"].append(action_history_item)
    
    # Add default "scraped" action if no history exists and we have scraped data
    # This ensures Actions History section always shows at least one entry
    if not combined.get("history") and scraped_dict:
        # Try to get scraped_at timestamp, fallback to publish_date or current time
        scraped_at = None
        if scraped_dict.get("scraped_at"):
            scraped_at = scraped_dict.get("scraped_at")
        elif scraped_dict.get("publish_date"):
            try:
                from dateutil import parser as date_parser
                scraped_at = date_parser.parse(scraped_dict.get("publish_date"), dayfirst=True)
            except:
                pass
        
        if not scraped_at:
            scraped_at = datetime.now(timezone.utc)
        
        # Ensure scraped_at is a datetime object
        if isinstance(scraped_at, str):
            try:
                from dateutil import parser as date_parser
                scraped_at = date_parser.parse(scraped_at)
            except:
                scraped_at = datetime.now(timezone.utc)
        elif not isinstance(scraped_at, datetime):
            scraped_at = datetime.now(timezone.utc)
        
        default_action = {
            "id": "scraped_default",
            "tender_id": str(tender.id) if tender else "",
            "user_id": None,
            "action": "viewed",  # Use "viewed" as default action type
            "notes": "Tender scraped and added to system",
            "timestamp": scraped_at,
            "created_at": scraped_at,
        }
        combined["history"].append(default_action)
    
    if "history" in combined and combined["history"]:
        new_history = []
        for item in combined["history"]:
            try:
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
                     date_change_value = None
                else:
                    # Only keep date_change if it has actual meaningful dates (not sentinel values)
                    from_date_raw = date_change_value.get("from_date")
                    to_date_raw = date_change_value.get("to_date")
                    
                    # Skip sentinel datetime values (year 1 means no real data)
                    has_valid_from = from_date_raw and not isinstance(from_date_raw, str) or (isinstance(from_date_raw, str) and "0001" not in from_date_raw)
                    has_valid_to = to_date_raw and not isinstance(to_date_raw, str) or (isinstance(to_date_raw, str) and "0001" not in to_date_raw)
                    
                    if not (has_valid_from or has_valid_to):
                        date_change_value = None
                    else:
                        # Convert to ISO strings if we have valid data
                        if isinstance(from_date_raw, datetime):
                            date_change_value["from_date"] = from_date_raw.isoformat()
                        elif isinstance(from_date_raw, str) and from_date_raw and "0001" not in from_date_raw:
                            date_change_value["from_date"] = from_date_raw
                        else:
                            date_change_value["from_date"] = None
                        
                        if isinstance(to_date_raw, datetime):
                            date_change_value["to_date"] = to_date_raw.isoformat()
                        elif isinstance(to_date_raw, str) and to_date_raw and "0001" not in to_date_raw:
                            date_change_value["to_date"] = to_date_raw
                        else:
                            date_change_value["to_date"] = None
                        
                        # If both are now None, don't include date_change
                        if not date_change_value.get("from_date") and not date_change_value.get("to_date"):
                            date_change_value = None

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
                    "tdr": tender.tender_ref_number or "",                # Add tender reference number
                    "type": history_type,
                    "note": item.get("notes") or item.get("note") or "",
                    "update_date": update_date_value,                      # Expected as string
                    "files_changed": files_changed_value,               
                    "date_change": date_change_value,                      # Contains string dates
                }
                new_history.append(history_item_data)
            except Exception as e:
                print(f"Error processing history item: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        combined["history"] = new_history
        combined["tender_history"] = []  # Start with empty, only add corrigendum history
    else:
        combined["tender_history"] = []
        combined["history"] = []
    
    # Add corrigendum history from TenderActionHistory
    try:
        # Lazy import to avoid slowing down startup
        from app.modules.tenderiq.services.corrigendum_service import CorrigendumTrackingService
        
        corrigendum_service = CorrigendumTrackingService(db)
        corrigendum_history = corrigendum_service.get_tender_change_history(str(tender.id))
        
        # Merge corrigendum history with existing tender history
        if corrigendum_history:
            # Remove corrigendum_updated items from tender_history to avoid duplicates
            # (they'll be replaced with properly formatted ones from corrigendum service)
            combined["tender_history"] = [
                h for h in combined["tender_history"] 
                if not (h.get("note", "").startswith("Corrigendum:"))
            ]
            
            # Add to tender_history (shown in frontend)
            combined["tender_history"].extend(corrigendum_history)
        
        # DEDUPLICATE tender_history: Keep only unique entries by type + date + note
        # This prevents the same change from appearing multiple times
        seen_tender_history: dict = {}
        deduplicated_tender_history = []
        
        for item in combined["tender_history"]:
            update_date = item.get("update_date", "")
            history_type = item.get("type", "")
            note = item.get("note", "")
            
            # Create a unique key for this history entry
            key = f"{history_type}|{update_date}|{note}"
            
            if key not in seen_tender_history:
                seen_tender_history[key] = True
                deduplicated_tender_history.append(item)
        
        # Sort by update_date descending (most recent first)
        combined["tender_history"] = sorted(
            deduplicated_tender_history,
            key=lambda x: x.get("update_date", ""),
            reverse=True
        )
        
        # LIMIT to last 10 unique changes to prevent clutter
        combined["tender_history"] = combined["tender_history"][:10]
    except Exception as e:
        # Log error but don't fail the entire request
        pass

    # HACK: Remove the 'history' item if the "action" is empty (only for tender_action_history, not corrigendum)
    combined["history"] = [item for item in combined["history"] if item.get("action") is not None]

    # Sanitize integer fields: ensure they are either int or None (not strings)
    integer_fields = ["emd", "tender_value", "estimated_cost", "bid_security", "length_km", 
                     "per_km_cost", "span_length", "road_work_amount", "structure_work_amount"]
    for field in integer_fields:
        if field in combined:
            value = combined[field]
            if isinstance(value, str):
                # Try to parse as integer, if fails set to None
                try:
                    # Remove common non-numeric text
                    cleaned = value.lower().strip()
                    if any(keyword in cleaned for keyword in ['ref document', 'refer document', 'refer to document', 'see document', 'as per document', 'n/a', 'na', 'not applicable']):
                        combined[field] = None
                    else:
                        # Try to extract number from string
                        numbers = re.findall(r'\d+', value.replace(',', ''))
                        if numbers:
                            combined[field] = int(numbers[0])
                        else:
                            combined[field] = None
                except (ValueError, TypeError):
                    combined[field] = None
            elif value is not None and not isinstance(value, int):
                # If it's a float or Decimal, convert to int
                try:
                    combined[field] = int(value)
                except (ValueError, TypeError):
                    combined[field] = None

    # Validate the modified dictionary
    try:
        return FullTenderDetails.model_validate(combined)
    except Exception as e:
        logger.error(f"Error validating FullTenderDetails for tender {tender_id}: {str(e)}", exc_info=True)
        logger.error(f"Combined dict keys: {list(combined.keys())}")
        raise

def get_daily_tenders(db: Session, start: Optional[int] = 0, end: Optional[int] = 1000, run_id: Optional[str] = None) -> DailyTendersResponse:
    scrape_runs = tenderiq_repo.get_scrape_runs(db)
    latest_scrape_run = scrape_runs[0]
    categories_of_current_day = tenderiq_repo.get_all_categories(db, latest_scrape_run)

    for category in categories_of_current_day:
        tenders = tenderiq_repo.get_tenders_from_category(db, category, start or 0, end or 1000)
        pydantic_tenders = [TenderModel.model_validate(t).model_dump(mode='json') for t in tenders]
        category.tenders = pydantic_tenders

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

    return to_return
