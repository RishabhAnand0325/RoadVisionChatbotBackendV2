"""
Corrigendum and Tender Change Tracking Service

This service tracks changes to tenders over time, particularly when corrigendums
are issued. It compares tender versions and highlights what changed.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.modules.tenderiq.db.schema import Tender, TenderActionHistory, TenderActionEnum
from app.modules.tenderiq.db.repository import TenderRepository
from app.modules.scraper.db.schema import ScrapedTender


class TenderChange:
    """Represents a single change in a tender field"""
    def __init__(self, field: str, old_value: Any, new_value: Any, change_type: str = "updated"):
        self.field = field
        self.old_value = old_value
        self.new_value = new_value
        self.change_type = change_type  # updated, added, removed
        self.timestamp = datetime.now(timezone.utc)


class CorrigendumTrackingService:
    """Service for tracking and displaying tender changes from corrigendums"""
    
    # Fields to track for changes
    TRACKED_FIELDS = [
        'tender_value', 'estimated_cost', 'emd', 'document_fees',
        'submission_deadline', 'due_date', 'last_date_of_bid_submission',
        'prebid_meeting_date', 'site_visit_deadline',
        'tender_brief', 'scope_of_work', 'product_category',
        'eligibility_criteria', 'technical_requirements',
        'tendering_authority', 'issuing_authority',
        'city', 'state', 'location'
    ]
    
    # Human-readable field names
    FIELD_LABELS = {
        'tender_value': 'Tender Value',
        'estimated_cost': 'Estimated Cost',
        'emd': 'EMD Amount',
        'document_fees': 'Document Fees',
        'submission_deadline': 'Submission Deadline',
        'due_date': 'Due Date',
        'last_date_of_bid_submission': 'Last Date of Bid Submission',
        'prebid_meeting_date': 'Pre-bid Meeting Date',
        'site_visit_deadline': 'Site Visit Deadline',
        'tender_brief': 'Tender Brief',
        'scope_of_work': 'Scope of Work',
        'product_category': 'Product Category',
        'eligibility_criteria': 'Eligibility Criteria',
        'technical_requirements': 'Technical Requirements',
        'tendering_authority': 'Tendering Authority',
        'issuing_authority': 'Issuing Authority',
        'city': 'City',
        'state': 'State',
        'location': 'Location',
    }
    
    def __init__(self, db: Session):
        self.db = db
        self.repo = TenderRepository(db)
    
    def detect_changes(
        self,
        tender_id: str,
        new_scraped_data: ScrapedTender
    ) -> List[TenderChange]:
        """
        Compare current tender data with new scraped data to detect changes.
        
        Args:
            tender_id: The tender reference number
            new_scraped_data: New scraped data from the portal
            
        Returns:
            List of TenderChange objects representing detected changes
        """
        # Get existing tender
        tender = self.db.query(Tender).filter(Tender.tender_ref_number == tender_id).first()
        if not tender:
            return []
        
        # Get previous scraped data
        old_scraped = self.db.query(ScrapedTender).filter(
            ScrapedTender.tender_id_str == tender_id
        ).order_by(ScrapedTender.id.desc()).first()
        
        if not old_scraped:
            return []
        
        changes = []
        
        # Compare each tracked field
        for field in self.TRACKED_FIELDS:
            old_value = getattr(old_scraped, field, None) if hasattr(old_scraped, field) else getattr(tender, field, None)
            new_value = getattr(new_scraped_data, field, None)
            
            # Detect change
            if self._values_different(old_value, new_value):
                changes.append(TenderChange(
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                    change_type="updated"
                ))
        
        return changes
    
    def apply_corrigendum(
        self,
        tender_id: str,
        new_scraped_data: ScrapedTender,
        user_id: UUID,
        corrigendum_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply corrigendum changes to a tender and log them.
        
        Args:
            tender_id: The tender reference number
            new_scraped_data: New scraped data with corrigendum changes
            user_id: User applying the corrigendum
            corrigendum_note: Optional note about the corrigendum
            
        Returns:
            Dictionary with summary of changes
        """
        # Detect changes
        changes = self.detect_changes(tender_id, new_scraped_data)
        
        if not changes:
            return {
                "status": "no_changes",
                "message": "No changes detected in corrigendum",
                "changes": []
            }
        
        # Get tender
        tender = self.db.query(Tender).filter(Tender.tender_ref_number == tender_id).first()
        
        if not tender:
            return {
                "status": "error",
                "message": "Tender not found",
                "changes": []
            }
        
        # Apply changes to tender
        updates = {}
        for change in changes:
            # Map scraped fields to tender fields if needed
            tender_field = self._map_to_tender_field(change.field)
            if hasattr(tender, tender_field):
                updates[tender_field] = change.new_value
        
        # Update tender
        if updates:
            for key, value in updates.items():
                setattr(tender, key, value)
            self.db.commit()
            self.db.refresh(tender)
        
        # Log corrigendum action
        action_log = TenderActionHistory(
            tender_id=tender.id,
            user_id=user_id,
            action=TenderActionEnum.corrigendum_updated,
            notes=self._format_changes_note(changes, corrigendum_note)
        )
        self.db.add(action_log)
        self.db.commit()
        self.db.refresh(action_log)
        
        return {
            "status": "success",
            "message": f"{len(changes)} changes applied from corrigendum",
            "changes": [self._format_change(change) for change in changes],
            "action_log_id": str(action_log.id)
        }
    
    def get_tender_change_history(
        self,
        tender_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get the complete change history for a tender in frontend-compatible format.
        
        Args:
            tender_id: The tender reference number or UUID
            
        Returns:
            List of TenderHistoryItem-compatible dictionaries
        """
        try:
            # Try to parse as UUID first and query directly
            try:
                tender_uuid = UUID(tender_id)
                tender = self.db.query(Tender).filter(Tender.id == tender_uuid).first()
            except (ValueError, AttributeError):
                # Treat as tender reference number
                tender = self.db.query(Tender).filter(Tender.tender_ref_number == tender_id).first()
            
            if not tender:
                return []
            
            # Get all corrigendum actions from history
            corrigendum_actions = self.db.query(TenderActionHistory).filter(
                and_(
                    TenderActionHistory.tender_id == tender.id,
                    TenderActionHistory.action == TenderActionEnum.corrigendum_updated
                )
            ).order_by(TenderActionHistory.timestamp.desc()).all()
            
            history = []
            for action in corrigendum_actions:
                try:
                    # Parse changes from notes to determine type and date changes
                    changes = self._parse_changes_from_note(action.notes or "")
                    history_type, date_change = self._determine_history_type_and_dates(changes)
                    
                    # Ensure date_change always has the required structure
                    if date_change is None:
                        date_change = {
                            "from_date": None,
                            "to_date": None
                        }
                    
                    history_item = {
                        "id": str(action.id),
                        "tender_id": str(tender.id),
                        "user_id": str(action.user_id) if action.user_id else None,
                        "tdr": tender.tender_ref_number or "",  # Add tender reference number
                        "type": history_type,
                        "note": action.notes or "",
                        "update_date": action.timestamp.isoformat() if action.timestamp else datetime.now(timezone.utc).isoformat(),
                        "files_changed": [],  # TODO: Link to actual file changes
                        "date_change": date_change
                    }
                    history.append(history_item)
                except Exception as e:
                    # Skip this history item if there's an error parsing it
                    continue
            
            return history
            
        except Exception as e:
            print(f"Error fetching corrigendum history for tender {tender_id}: {str(e)}")
            return []
    
    def _values_different(self, old_value: Any, new_value: Any) -> bool:
        """Check if two values are different, handling None and type conversions"""
        # Both None or empty
        if (old_value is None or str(old_value).strip() == "") and \
           (new_value is None or str(new_value).strip() == ""):
            return False
        
        # One is None/empty, other isn't
        if (old_value is None or str(old_value).strip() == "") or \
           (new_value is None or str(new_value).strip() == ""):
            return True
        
        # For dates, compare as strings
        if isinstance(old_value, datetime) or isinstance(new_value, datetime):
            old_str = old_value.isoformat() if isinstance(old_value, datetime) else str(old_value)
            new_str = new_value.isoformat() if isinstance(new_value, datetime) else str(new_value)
            return old_str != new_str
        
        # For numbers, compare as floats
        try:
            return float(old_value) != float(new_value)
        except (ValueError, TypeError):
            pass
        
        # Default: compare as strings
        return str(old_value) != str(new_value)
    
    def _map_to_tender_field(self, scraped_field: str) -> str:
        """Map scraped tender field names to Tender model field names"""
        field_mapping = {
            'tender_value': 'estimated_cost',
            'last_date_of_bid_submission': 'submission_deadline',
            'due_date': 'submission_deadline',
            # Add more mappings as needed
        }
        return field_mapping.get(scraped_field, scraped_field)
    
    def _format_change(self, change: TenderChange) -> Dict[str, Any]:
        """Format a TenderChange object for API response"""
        field_label = self.FIELD_LABELS.get(change.field, change.field)
        
        return {
            "field": change.field,
            "field_label": field_label,
            "old_value": str(change.old_value) if change.old_value else None,
            "new_value": str(change.new_value) if change.new_value else None,
            "change_type": change.change_type,
            "timestamp": change.timestamp.isoformat()
        }
    
    def _format_changes_note(
        self,
        changes: List[TenderChange],
        additional_note: Optional[str] = None
    ) -> str:
        """Format changes into a readable note for the action log"""
        note_parts = []
        
        if additional_note:
            note_parts.append(f"Corrigendum: {additional_note}")
        else:
            note_parts.append("Corrigendum applied")
        
        note_parts.append(f"\n\nChanges ({len(changes)}):")
        
        for change in changes:
            field_label = self.FIELD_LABELS.get(change.field, change.field)
            old_val = str(change.old_value) if change.old_value else "Not set"
            new_val = str(change.new_value) if change.new_value else "Removed"
            note_parts.append(f"• {field_label}: {old_val} → {new_val}")
        
        return "\n".join(note_parts)
    
    def _parse_changes_from_note(self, note: str) -> List[Dict[str, str]]:
        """Parse changes from a formatted note"""
        if not note or "Changes" not in note:
            return []
        
        changes = []
        lines = note.split('\n')
        
        for line in lines:
            if line.startswith('•'):
                # Parse format: "• Field Label: old_value → new_value"
                try:
                    # Split only on the FIRST colon to get field label
                    parts = line[2:].split(':', 1)  # Split on first : only
                    field_label = parts[0].strip()
                    # Now split the value part on the arrow
                    value_parts = parts[1].split('→')
                    old_value = value_parts[0].strip()
                    new_value = value_parts[1].strip() if len(value_parts) > 1 else None
                    
                    change = {
                        "field": field_label,
                        "old_value": old_value,
                        "new_value": new_value
                    }
                    changes.append(change)
                except (IndexError, AttributeError):
                    continue
        
        return changes
    
    def _determine_history_type_and_dates(
        self, 
        changes: List[Dict[str, str]]
    ) -> tuple[str, Optional[Dict[str, str]]]:
        """
        Determine the history type and extract date changes from parsed changes.
        
        Returns:
            Tuple of (history_type, date_change_dict or None)
        """
        if not changes:
            return "corrigendum", None
            
        # Date-related fields that indicate extensions
        date_fields = {
            'Submission Deadline': 'bid_deadline_extension',
            'Due Date': 'due_date_extension',
            'Last Date of Bid Submission': 'bid_deadline_extension',
        }
        
        # Check if any changes are date-related
        date_change = None
        history_type = "corrigendum"  # Default
        
        for change in changes:
            field = change.get("field", "")
            
            if field in date_fields:
                history_type = date_fields[field]
                old_val = change.get("old_value", "")
                new_val = change.get("new_value", "")
                if old_val and new_val:
                    # Parse datetime strings to ISO format if needed
                    from_date = self._normalize_date_string(old_val)
                    to_date = self._normalize_date_string(new_val)
                    date_change = {
                        "from_date": from_date,
                        "to_date": to_date
                    }
                break  # Use first date change found
            elif field in ['Tender Value', 'Estimated Cost', 'EMD Amount']:
                history_type = "amendment"
        
        return history_type, date_change
    
    def _normalize_date_string(self, date_str: str) -> str:
        """Convert various date formats to ISO format string"""
        if not date_str or date_str == "Not set" or date_str == "Removed":
            return datetime.min.replace(tzinfo=timezone.utc).isoformat()
        
        # Try to parse common date formats
        from dateutil import parser
        try:
            # Try parsing with dateutil (handles most formats)
            dt = parser.parse(date_str)
            # Ensure timezone awareness
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except:
            # If parsing fails, return the original string
            return date_str
