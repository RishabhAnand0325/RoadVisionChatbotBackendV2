"""
BidSynopsis Business Logic Layer

This module contains the core business logic functions for generating bid synopsis.
Following the project's architectural pattern:

- synopsis_service.py (this file): Core business logic functions 
- services/bid_synopsis_service.py: Service layer that orchestrates operations
- db/repository.py: Data access layer
- endpoints/synopsis.py: API endpoint layer

The main function generate_bid_synopsis() is used by the service layer
to transform tender and scraped_tender data into structured bid synopsis.
"""

from typing import Optional, Union
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
import re

from app.modules.tenderiq.db.schema import Tender
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.analyze.db.schema import TenderAnalysis
from .pydantic_models import (
    BasicInfoItem,
    RequirementItem,
    BidSynopsisResponse,
)


def _extract_from_analysis(analysis: Optional[TenderAnalysis], field_keywords: str, section: str = 'data_sheet') -> str:
    """
    Extract specific field from analysis JSON data.
    Returns the value if found, otherwise 'N/A'.
    """
    if not analysis:
        return "N/A"
    
    try:
        if section == 'data_sheet' and analysis.data_sheet_json:
            data = analysis.data_sheet_json
            # Search in all sections for the field
            for section_name in ['project_information', 'contract_details', 'financial_details']:
                if section_name in data:
                    for item in data[section_name]:
                        if isinstance(item, dict) and item.get('label', ''):
                            label_lower = item.get('label', '').lower()
                            # Check if any keyword matches the label
                            for keyword in field_keywords.split():
                                if keyword.lower() in label_lower:
                                    value = item.get('value', 'N/A')
                                    if value and str(value).strip() and str(value) != 'N/A':
                                        return str(value)
        
        elif section == 'scope' and analysis.scope_of_work_json:
            scope = analysis.scope_of_work_json
            if 'project_details' in scope and scope['project_details']:
                details = scope['project_details']
                # Map common field names
                field_mapping = {
                    'length': 'total_length',
                    'duration': 'duration', 
                    'completion': 'duration',
                    'value': 'contract_value',
                    'cost': 'contract_value'
                }
                
                for keyword in field_keywords.split():
                    for key, mapped_key in field_mapping.items():
                        if keyword.lower() in key and mapped_key in details:
                            value = details[mapped_key]
                            if value and str(value).strip() and str(value) != 'N/A':
                                return str(value)
                        
    except Exception:
        pass
    
    return "N/A"


def parse_indian_currency(value: Union[str, int, float, None]) -> float:
    """
    Converts Indian currency format (with Crores, Lakhs) to a numeric value.
    1 Crore = 10,000,000
    1 Lakh = 100,000
    """
    if value is None:
        return 0.0

    if isinstance(value, str):
        value_lower = value.lower().strip()
        
        # Skip non-numeric indicators
        if any(skip_word in value_lower for skip_word in ["refer document", "refer", "n/a", "na", "not available"]):
            return 0.0
        
        # Handle "INR X Lakhs" format (common in scraped data)
        if "inr" in value_lower and "lakh" in value_lower:
            match = re.search(r'inr\s*([\d,.]+)\s*lakhs?', value_lower)
            if match:
                cleaned_value = match.group(1).replace(',', '')
                try:
                    lakh_value = float(cleaned_value)
                    return lakh_value / 100  # Convert Lakhs to Crores
                except ValueError:
                    pass
        
        # Handle "INR X Crores" format
        if "inr" in value_lower and "crore" in value_lower:
            match = re.search(r'inr\s*([\d,.]+)\s*crores?', value_lower)
            if match:
                cleaned_value = match.group(1).replace(',', '')
                try:
                    return float(cleaned_value)  # Already in Crores
                except ValueError:
                    pass
        
        # Handle "crore" conversion
        if "crore" in value_lower:
            match = re.search(r'([\d,.]+)', value_lower.replace('crore', ''))
            if match:
                cleaned_value = match.group(1).replace(',', '')
                try:
                    return float(cleaned_value)  # Already in Crores
                except ValueError:
                    pass
        
        # Handle "lakh" conversion  
        if "lakh" in value_lower:
            match = re.search(r'([\d,.]+)', value_lower.replace('lakh', ''))
            if match:
                cleaned_value = match.group(1).replace(',', '')
                try:
                    lakh_value = float(cleaned_value)
                    return lakh_value / 100  # Convert Lakhs to Crores
                except ValueError:
                    pass

        # General cleaning: Extract numeric part
        cleaned_value = re.sub(r'[^\d.]', '', value).replace(',', '')
        try:
            numeric_value = float(cleaned_value)
            # If it's a large number (> 1000000), likely in Rs, convert to Crores
            if numeric_value > 1000000:
                return numeric_value / 10000000
            # If it's a medium number (> 1000), likely in thousands, convert appropriately  
            elif numeric_value > 1000:
                return numeric_value / 10000000  # Assume Rs
            else:
                return numeric_value  # Assume already in appropriate unit
        except ValueError:
            return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    return 0.0


def _get_from_analysis_data_sheet(analysis: Optional[TenderAnalysis], field_name: str) -> Optional[str]:
    """
    Extract specific field from analysis data_sheet_json.
    """
    if not analysis or not analysis.data_sheet_json:
        return None
    
    data_sheet = analysis.data_sheet_json
    
    # Search in all sections
    sections = ['project_information', 'contract_details', 'financial_details', 'technical_summary', 'important_dates']
    
    for section_name in sections:
        if section_name in data_sheet:
            items = data_sheet[section_name]
            for item in items:
                if isinstance(item, dict) and 'label' in item and 'value' in item:
                    label = item['label'].lower()
                    if field_name.lower() in label or any(keyword in label for keyword in field_name.lower().split()):
                        value = item['value']
                        if value and value.strip() and value.strip().lower() != 'n/a':
                            return value.strip()
    return None


def _get_from_analysis_scope_of_work(analysis: Optional[TenderAnalysis], field_name: str) -> Optional[str]:
    """
    Extract specific field from analysis scope_of_work_json.
    """
    if not analysis or not analysis.scope_of_work_json:
        return None
        
    scope = analysis.scope_of_work_json
    
    if 'project_details' in scope and scope['project_details']:
        project_details = scope['project_details']
        
        field_mapping = {
            'project_name': 'project_name',
            'location': 'location', 
            'total_length': 'total_length',
            'duration': 'duration',
            'contract_value': 'contract_value'
        }
        
        if field_name in field_mapping:
            value = project_details.get(field_mapping[field_name])
            if value and str(value).strip() and str(value).strip().lower() not in ['n/a', 'none', 'null']:
                return str(value).strip()
    
    return None


def get_estimated_cost_in_crores(tender: Tender, scraped_tender: Optional[ScrapedTender] = None, analysis: Optional[TenderAnalysis] = None) -> float:
    """
    Converts the estimated cost to Crores for display.
    Handles conversion from different units (Rs/Lakhs/Crores).
    Prioritizes analysis data, then tries scraped data, then tender data.
    """
    # First try analysis data (most accurate)
    if analysis:
        # Try contract value from scope of work
        contract_value = _get_from_analysis_scope_of_work(analysis, 'contract_value')
        if contract_value and 'refer document' not in contract_value.lower():
            parsed_value = parse_indian_currency(contract_value)
            if parsed_value > 0:
                return parsed_value
        
        # Try contract value from data sheet
        contract_value = _get_from_analysis_data_sheet(analysis, 'contract value')
        if contract_value and 'refer document' not in contract_value.lower():
            parsed_value = parse_indian_currency(contract_value)
            if parsed_value > 0:
                return parsed_value
    
    # Try tender data first
    if tender.estimated_cost is not None:
        if isinstance(tender.estimated_cost, Decimal):
            value = float(tender.estimated_cost)
        else:
            value = float(tender.estimated_cost)

        # Smart conversion based on value range
        if value > 10000000:  # If > 1 Crore, assume it's in Rs
            return value / 10000000
        elif value > 0:  # If small positive value, assume already in Crores
            return value
    
    # Try scraped tender data if tender data is missing/zero
    if scraped_tender and hasattr(scraped_tender, 'tender_value') and scraped_tender.tender_value:
        tender_value_str = scraped_tender.tender_value
        if tender_value_str and tender_value_str.lower().strip() not in ["refer document", "n/a", "na"]:
            parsed_value = parse_indian_currency(tender_value_str)
            if parsed_value > 0:
                return parsed_value
    
    # Try parsing from tender_details or other fields
    if scraped_tender and scraped_tender.tender_details:
        # Look for currency patterns in tender details
        details = scraped_tender.tender_details.lower()
        
        # Pattern for "Rs. X Crore" or "X Crores"
        crore_match = re.search(r'rs\.?\s*(\d+(?:\.\d+)?)\s*crores?', details)
        if crore_match:
            return float(crore_match.group(1))
            
        # Pattern for "Rs. X Lakh" -> convert to Crores
        lakh_match = re.search(r'rs\.?\s*(\d+(?:\.\d+)?)\s*lakhs?', details)
        if lakh_match:
            return float(lakh_match.group(1)) / 100
    
    return 0.0


def get_bid_security_in_crores(tender: Tender) -> float:
    """
    Extracts and converts bid security (EMD) to Crores.
    """
    if tender.bid_security is None:
        return 0.0

    if isinstance(tender.bid_security, Decimal):
        value = float(tender.bid_security)
    else:
        value = float(tender.bid_security)

    # Smart conversion based on value range
    # EMD is typically 1-5% of tender value, so use that for context
    if value > 10000000:  # If > 1 Crore, assume it's in Rs
        return value / 10000000
    elif value > 10000:  # If > 10K, assume it's in Rs (small EMD)
        return value / 10000000  
    elif value > 100:  # If > 100, likely in Lakhs
        return value / 100
    else:  # Already in Crores or very small value
        return value


def _get_work_name(tender: Tender, scraped_tender: Optional[ScrapedTender], analysis: Optional[TenderAnalysis] = None) -> str:
    """
    Gets the work name prioritizing analysis data, then scraped tender data over tender table.
    """
    # First try analysis data (most accurate)
    if analysis:
        project_name = _get_from_analysis_scope_of_work(analysis, 'project_name')
        if project_name:
            cleaned = _clean_tender_title(project_name, tender.employer_name)
            if cleaned != "N/A":
                return cleaned
        
        # Try from data sheet
        project_name = _get_from_analysis_data_sheet(analysis, 'project name')
        if project_name:
            cleaned = _clean_tender_title(project_name, tender.employer_name) 
            if cleaned != "N/A":
                return cleaned
    
    # Next try scraped tender data (usually more detailed)
    if scraped_tender:
        # Try tender_name from scraped data first
        if scraped_tender.tender_name:
            cleaned = _clean_tender_title(scraped_tender.tender_name, tender.employer_name)
            if cleaned != "N/A" and cleaned != scraped_tender.tender_name:
                return cleaned
        
        # Try tender_brief if tender_name wasn't useful
        if scraped_tender.tender_brief:
            brief = scraped_tender.tender_brief.strip()
            if len(brief) > 10 and brief.lower() != (tender.employer_name or "").lower():
                # Take first sentence or reasonable portion
                sentences = brief.split('.', 1)
                first_part = sentences[0].strip()
                if len(first_part) > 20:
                    return first_part
                return brief[:100] + "..." if len(brief) > 100 else brief
    
    # Fallback to tender table data
    if tender.tender_title:
        cleaned = _clean_tender_title(tender.tender_title, tender.employer_name)
        if cleaned != "N/A":
            return cleaned
    
    # Last fallback
    return "N/A"


def _clean_tender_title(title: str, employer_name: Optional[str]) -> str:
    """
    Cleans tender title by removing employer name and unwanted prefixes.
    Uses actual scraped data only, no artificial categories.
    """
    if not title or title.lower() == "n/a":
        return "N/A"
    
    original_title = title
    
    # Remove leading numbers/punctuation first (like "1.", "2.", etc.)
    title = re.sub(r'^[0-9\s\.\-\:]+', '', title).strip()
    
    # If title is exactly the same as employer name, it's probably not the actual work description
    if employer_name and title.strip().lower() == employer_name.strip().lower():
        return "N/A"  # Let the calling function handle fallback to scraped data
    
    # Remove employer name if present but keep the work description
    if employer_name and employer_name.lower() in title.lower():
        # Try to extract the part that's not the employer name
        title_parts = title.split()
        employer_parts = employer_name.split()
        filtered_parts = [part for part in title_parts if part.lower() not in [ep.lower() for ep in employer_parts]]
        if len(filtered_parts) > 2:  # Only use if we have substantial content left
            title = ' '.join(filtered_parts).strip()
    
    return title if title else "N/A"


def extract_emd_from_scraped(scraped_tender: Optional[ScrapedTender], analysis: Optional[TenderAnalysis] = None) -> float:
    """
    Extracts EMD value from analysis or scraped tender data.
    Returns value in Crores or 0.0 if not found.
    """
    # First try analysis data
    if analysis:
        emd_amount = _get_from_analysis_data_sheet(analysis, 'emd amount')
        if emd_amount:
            parsed_value = parse_indian_currency(emd_amount)
            if parsed_value > 0:
                return parsed_value
    
    # Try scraped data as fallback
    if not scraped_tender:
        return 0.0

    # Try emd field first
    if scraped_tender.emd:
        emd_value = parse_indian_currency(scraped_tender.emd)
        # EMD is typically in Lakhs, so convert appropriately
        if emd_value > 100:  # If > 100, likely in actual currency (Rs)
            return emd_value / 10000000  # Convert Rs to Crores
        elif emd_value > 0.1:  # If between 0.1-100, likely in Lakhs
            return emd_value / 100  # Convert Lakhs to Crores
        return emd_value  # Already in Crores

    return 0.0


def _format_emd_display(emd_crores: float) -> str:
    """
    Formats EMD for display with appropriate units.
    """
    if emd_crores <= 0:
        return "N/A"
    
    if emd_crores >= 1.0:
        return f"Rs. {emd_crores:.2f} Crores in form of Bank Guarantee"
    else:
        # Convert to Lakhs for better readability
        emd_lakhs = emd_crores * 100
        return f"Rs. {emd_lakhs:.2f} Lakhs in form of Bank Guarantee"


def extract_document_cost(scraped_tender: Optional[ScrapedTender]) -> str:
    """
    Extracts document cost from scraped tender data.
    Returns formatted string with Rs. prefix or "N/A" if not available.
    """
    if not scraped_tender:
        return "N/A"

    # Try document_fees field first
    if scraped_tender.document_fees:
        cost_str = scraped_tender.document_fees.strip()
        if cost_str and cost_str.lower() != "n/a" and cost_str != "":
            # Clean and standardize to Rs. format
            # Remove existing currency indicators
            cleaned = re.sub(r'\b(rs\.?|inr|₹)\s*', '', cost_str, flags=re.IGNORECASE).strip()
            # Remove leading/trailing slashes or dashes
            cleaned = re.sub(r'^[-/\s]+|[-/\s]+$', '', cleaned).strip()
            return f"Rs. {cleaned}"

    return "N/A"


def _get_project_length(tender: Tender, scraped_tender: Optional[ScrapedTender] = None, analysis: Optional[TenderAnalysis] = None) -> str:
    """
    Get project length from analysis, tender or scraped data.
    """
    # Try analysis data first (most accurate)
    if analysis:
        length_from_analysis = _extract_from_analysis(analysis, 'length', 'scope')
        if length_from_analysis != "N/A":
            return length_from_analysis
    
    # Try tender data
    if tender.length_km:
        return f"{tender.length_km} km"
    
    # Try scraped data
    if scraped_tender and scraped_tender.tender_details:
        details = scraped_tender.tender_details.lower()
        
        # Look for km patterns
        km_match = re.search(r'(\d+(?:\.\d+)?)\s*km', details)
        if km_match:
            return f"{km_match.group(1)} km"
            
        # Look for length/distance mentions
        length_match = re.search(r'length[:\s]+(\d+(?:\.\d+)?)\s*(?:km|kilometres?)', details)
        if length_match:
            return f"{length_match.group(1)} km"
    
    return "N/A"


def extract_completion_period(scraped_tender: Optional[ScrapedTender], analysis: Optional[TenderAnalysis] = None) -> str:
    """
    Extracts completion period from analysis or scraped tender data.
    Returns formatted string or "N/A" if not available.
    """
    # First try analysis data
    if analysis:
        duration = _get_from_analysis_scope_of_work(analysis, 'duration')
        if duration:
            return duration
        
        duration = _get_from_analysis_data_sheet(analysis, 'contract duration')
        if duration:
            return duration
    
    # Try scraped data as fallback
    if not scraped_tender:
        return "N/A"

    # Try tender_details field (parse for duration/period info)
    if scraped_tender.tender_details:
        details = scraped_tender.tender_details.lower()
        
        # Look for patterns like "X months", "X years", "X days"
        month_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:months?|month|m\.?)', details)
        if month_match:
            months = float(month_match.group(1))
            if months > 12:
                years = months / 12
                return f"{years:.1f} Years ({int(months)} Months)"
            return f"{int(months)} Months"

        year_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:years?|year|y\.?)', details)
        if year_match:
            years = float(year_match.group(1))
            months = int(years * 12)
            return f"{years} Years ({months} Months)"
            
        # Look for "completion period" or "execution period"
        period_match = re.search(r'(?:completion|execution)\s+period[:\s]*([^.\n]+)', details)
        if period_match:
            period_text = period_match.group(1).strip()
            if len(period_text) < 50:  # Reasonable length
                return period_text.title()
    
    # Try other fields if available
    if hasattr(scraped_tender, 'project_duration') and scraped_tender.project_duration:
        return scraped_tender.project_duration
        
    return "N/A"


def extract_pre_bid_meeting_details(scraped_tender: Optional[ScrapedTender], 
                                     tender: Tender) -> str:
    """
    Extracts pre-bid meeting details from scraped tender or uses tender data.
    """
    if tender.prebid_meeting_date:
        return tender.prebid_meeting_date.strftime("%d/%m/%Y at %H%M Hours IST")

    if scraped_tender and scraped_tender.tender_details:
        # Look for pre-bid meeting patterns
        details = scraped_tender.tender_details.lower()
        prebid_match = re.search(
            r'pre[\s-]?bid\s+meeting.*?(\d{1,2})[/-](\d{1,2})[/-](\d{4}).*?(\d{1,2}):(\d{2})',
            details,
            re.IGNORECASE
        )
        if prebid_match:
            day, month, year, hour, minute = prebid_match.groups()
            try:
                date_obj = datetime(int(year), int(month), int(day), int(hour), int(minute))
                return date_obj.strftime("%d/%m/%Y at %H%M Hours IST")
            except ValueError:
                pass

    return "N/A"


def format_bid_due_date(tender: Tender, scraped_tender: Optional[ScrapedTender]) -> str:
    """
    Formats bid due date from tender or scraped data.
    """
    if tender.submission_deadline:
        # Check if it's midnight (00:00) and format accordingly
        if tender.submission_deadline.hour == 0 and tender.submission_deadline.minute == 0:
            return tender.submission_deadline.strftime("%d.%m.%Y, 11:59 PM")
        else:
            return tender.submission_deadline.strftime("%d.%m.%Y, %H:%M %p")

    if scraped_tender and scraped_tender.due_date:
        return scraped_tender.due_date

    return "N/A"


def generate_basic_info(tender: Tender, scraped_tender: Optional[ScrapedTender], analysis: Optional[TenderAnalysis] = None) -> list[BasicInfoItem]:
    """
    Generates the basicInfo array with 10 key fields.
    Dynamically fetches data from analysis, tender and scraped_tender tables.
    """
    # Try analysis data first for most accurate information
    tender_value_crores = 0.0
    if analysis:
        value_from_analysis = _extract_from_analysis(analysis, 'value cost contract', 'scope')
        if value_from_analysis != "N/A":
            tender_value_crores = parse_indian_currency(value_from_analysis)
    
    # Fallback to existing logic if analysis doesn't have the data
    if tender_value_crores == 0.0:
        tender_value_crores = get_estimated_cost_in_crores(tender, scraped_tender)
    
    emd_crores = get_bid_security_in_crores(tender)

    # Extract dynamic data with analysis priority
    document_cost = extract_document_cost(scraped_tender)
    
    # Try completion period from analysis first
    completion_period = "N/A"
    if analysis:
        completion_from_analysis = _extract_from_analysis(analysis, 'duration completion period', 'scope')
        if completion_from_analysis != "N/A":
            completion_period = completion_from_analysis
    if completion_period == "N/A":
        completion_period = extract_completion_period(scraped_tender)
    
    pre_bid_meeting = extract_pre_bid_meeting_details(scraped_tender, tender)
    bid_due_date = format_bid_due_date(tender, scraped_tender)
    
    # Get EMD from either tender or scraped data
    emd_from_scraped = extract_emd_from_scraped(scraped_tender)
    final_emd = emd_crores if emd_crores > 0 else emd_from_scraped

    basic_info = [
        BasicInfoItem(
            sno=1,
            item="Employer",
            description=tender.employer_name or scraped_tender.tendering_authority if scraped_tender else "N/A"
        ),
        BasicInfoItem(
            sno=2,
            item="Name of Work",
            description=_get_work_name(tender, scraped_tender)
        ),
        BasicInfoItem(
            sno=3,
            item="Tender Value",
            description=f"Rs. {tender_value_crores:.2f} Crores (Excluding GST)" if tender_value_crores > 0 else "N/A"
        ),
        BasicInfoItem(
            sno=4,
            item="Project Length",
            description=_get_project_length(tender, scraped_tender, analysis)
        ),
        BasicInfoItem(
            sno=5,
            item="EMD",
            description=_format_emd_display(final_emd)
        ),
        BasicInfoItem(
            sno=6,
            item="Cost of Tender Documents",
            description=document_cost
        ),
        BasicInfoItem(
            sno=7,
            item="Period of Completion",
            description=completion_period
        ),
        BasicInfoItem(
            sno=8,
            item="Pre-Bid Meeting",
            description=pre_bid_meeting
        ),
        BasicInfoItem(
            sno=9,
            item="Bid Due date",
            description=bid_due_date
        ),
        BasicInfoItem(
            sno=10,
            item="Physical Submission",
            description=bid_due_date  # Same as Bid Due date
        ),
    ]

    return basic_info


def generate_all_requirements(tender: Tender, scraped_tender: Optional[ScrapedTender], analysis: Optional[TenderAnalysis] = None) -> list[RequirementItem]:
    """
    Generates the allRequirements array with eligibility criteria.
    Uses tender data for calculations and scraped data for requirement details.
    Enhanced with analysis data for improved accuracy.
    Uses generic requirements suitable for most infrastructure projects.
    """
    tender_value_crores = get_estimated_cost_in_crores(tender, scraped_tender)
    tender_value = tender.estimated_cost or 0

    # Use actual project description from scraped data if available
    project_description = "infrastructure projects"
    if scraped_tender and scraped_tender.tender_brief:
        brief = scraped_tender.tender_brief.lower()
        if any(word in brief for word in ["water", "pipeline", "supply", "treatment"]):
            project_description = "water supply and infrastructure projects"
        elif any(word in brief for word in ["building", "construction", "structure"]):
            project_description = "building and construction projects"
        elif any(word in brief for word in ["road", "highway", "bridge"]):
            project_description = "road and highway projects"

    # Base requirements (common to all categories)
    requirements = [
        RequirementItem(
            description="Site Visit",
            requirement="Bidders shall submit their respective Bids after visiting the Project site and ascertaining for themselves the site conditions, location, surroundings, climate, availability of power, water & other utilities for construction, access to site, handling and storage of materials, weather data, applicable laws and regulations, and any other matter considered relevant by them.",
            extractedValue=_extract_from_analysis(analysis, 'site visit mandatory', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
        RequirementItem(
            description="Technical Capacity",
            requirement=f"For demonstrating technical capacity and experience, the Bidder shall, over the past 7 (Seven) financial years preceding the Bid Due Date, have: (i) paid for, or received payments for, construction of Eligible Project(s); (ii) developed Eligible Project(s) in Category 1 and/or Category 2; (iii) collected and appropriated revenues from Eligible Project(s) such that the sum total is more than Rs. {(tender_value_crores * 2.4 * 1.02):.2f} Crore (the \"Threshold Technical Capability\").",
            extractedValue=_extract_from_analysis(analysis, 'technical capacity turnover experience', 'eligibility') if analysis else "",
            ceigallValue=f"Rs. {(tender_value_crores * 2.4):.2f} Crores" if tender_value_crores > 0 else "N/A"
        ),
        RequirementItem(
            description="Technical Capability Threshold",
            requirement="Provided that at least one fourth of the Threshold Technical Capability shall be from the Eligible Projects in Category 1 and/ or Category 3 specified in tender requirements.",
            extractedValue=_extract_from_analysis(analysis, 'threshold capability category', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
        RequirementItem(
            description="Eligible Project Cost",
            requirement=f"Capital cost of eligible projects should be more than Rs. {tender_value_crores:.2f} Crores." if tender_value_crores > 0 else "Capital cost of eligible projects should be as per tender requirements.",
            extractedValue=_extract_from_analysis(analysis, 'eligible project cost minimum', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
        RequirementItem(
            description="Similar Work (JV Required)",
            requirement=f"Joint Venture requirement for similar work experience: Rs. {(tender_value_crores * 0.25):.2f} Crores" if tender_value_crores > 0 else "Joint Venture requirements as per tender specifications.",
            extractedValue=_extract_from_analysis(analysis, 'joint venture similar work', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
    ]

    # Generic infrastructure work requirements (suitable for all project types)
    requirements.extend([
        RequirementItem(
            description="a) Similar Work Experience",
            requirement=f"One project of {project_description} with completion cost of project equal to or more than Rs. {(tender_value_crores * 0.26):.2f} crores. For this purpose, a project shall be considered to be completed if desired purpose of the project is achieved, and more than 90% of the value of work has been completed.",
            extractedValue=_extract_from_analysis(analysis, 'similar work experience one project', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
        RequirementItem(
            description="b) Technical Capability",
            requirement=f"Experience in executing similar {project_description} with required technical specifications and quality standards as per relevant Indian Standards and project requirements.",
            extractedValue=_extract_from_analysis(analysis, 'technical capability standards', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
    ])

    # Common financial requirements
    requirements.extend([
        RequirementItem(
            description="Credit Rating",
            requirement="The Bidder shall have 'A' and above Credit Rating given by Credit Rating Agencies authorized by SEBI.",
            extractedValue=_extract_from_analysis(analysis, 'credit rating requirement', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
        RequirementItem(
            description="Clause 2.2.2 A - Special Requirement",
            requirement=f"The bidder shall have experience in executing {project_description} with required materials and construction standards as per relevant specifications and quality requirements.",
            extractedValue=_extract_from_analysis(analysis, 'special requirement clause materials', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
        RequirementItem(
            description="2.2.2 B (i) Financial Capacity",
            requirement=f"The Bidder shall have a minimum Financial Capacity of Rs. {(tender_value_crores * 0.2):.2f} Crore at the close of the preceding financial year. Net Worth: Rs. {(tender_value_crores * 0.2):.2f} Crores (Each Member) / Rs. {(tender_value_crores * 0.2):.2f} Crore (JV Total). Provided further that each member of the Consortium shall have a minimum Net Worth of 7.5% of Estimated Project Cost in the immediately preceding financial year.",
            extractedValue=_extract_from_analysis(analysis, 'financial capacity net worth minimum', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
        RequirementItem(
            description="2.2.2 B (ii) Financial Resources",
            requirement=f"The bidder shall demonstrate the total requirement of financial resources for concessionaire's contribution of Rs. {(tender_value_crores * 0.61):.2f} Crores. Bidder must demonstrate sufficient financial resources as stated above, comprising of liquid sources supplemented by unconditional commitment by bankers for finance term loan to the proposed SPV.",
            extractedValue=_extract_from_analysis(analysis, 'financial resources contribution requirement', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
        RequirementItem(
            description="2.2.2 B (iii) Loss-making Company",
            requirement="The bidder shall, in the last five financial years have neither been a loss-making company nor been in the list of Corporate Debt Restructuring (CDR) and/or Strategic Debt Restructuring (SDR) and/or having been declared Insolvent. The bidder should submit a certificate from its statutory auditor in this regard.",
            extractedValue=_extract_from_analysis(analysis, 'loss making company restriction', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
        RequirementItem(
            description="2.2.2 B (iv) Average Annual Construction Turnover",
            requirement=f"The bidder shall demonstrate an average annual construction turnover of Rs. {(tender_value_crores * 0.41):.2f} crores within last three years.",
            extractedValue=_extract_from_analysis(analysis, 'average annual construction turnover', 'eligibility') if analysis else "",
            ceigallValue=""
        ),
        RequirementItem(
            description="JV T & C",
            requirement="In case of a Consortium, the combined technical capability and net worth of those Members, who have and shall continue to have an equity share of at least 26% (twenty six per cent) each in the SPV, should satisfy the above conditions of eligibility.",
            extractedValue=_extract_from_analysis(analysis, 'consortium joint venture equity share', 'eligibility') if analysis else "",
            ceigallValue=""
        )
    ])

    return requirements


def generate_bid_synopsis(tender: Tender, scraped_tender: Optional[ScrapedTender] = None, analysis: Optional[TenderAnalysis] = None) -> BidSynopsisResponse:
    """
    Main function to generate complete bid synopsis from tender and scraped tender data.
    
    Args:
        tender: The Tender ORM object
        scraped_tender: Optional ScrapedTender ORM object for additional data
        analysis: Optional TenderAnalysis ORM object for enhanced data accuracy
    
    Returns:
        BidSynopsisResponse with both basicInfo and allRequirements
    """
    basic_info = generate_basic_info(tender, scraped_tender, analysis)
    all_requirements = generate_all_requirements(tender, scraped_tender, analysis)

    return BidSynopsisResponse(
        basicInfo=basic_info,
        allRequirements=all_requirements
    )