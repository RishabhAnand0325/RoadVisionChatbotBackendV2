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
from .pydantic_models import (
    BasicInfoItem,
    RequirementItem,
    BidSynopsisResponse,
)


def parse_indian_currency(value: Union[str, int, float, None]) -> float:
    """
    Converts Indian currency format (with Crores, Lakhs) to a numeric value.
    1 Crore = 10,000,000
    1 Lakh = 100,000
    """
    if value is None:
        return 0.0

    if isinstance(value, str):
        value_lower = value.lower()
        
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


def get_estimated_cost_in_crores(tender: Tender) -> float:
    """
    Extracts and converts estimated cost to Crores.
    """
    if tender.estimated_cost is None:
        return 0.0

    if isinstance(tender.estimated_cost, Decimal):
        value = float(tender.estimated_cost)
    else:
        value = float(tender.estimated_cost)

    # If value is in base currency (Rs), convert to Crores
    # 1 Crore = 10,000,000 Rs
    if value > 10000000:  # If > 1 Crore, assume it's in Rs
        return value / 10000000
    return value


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


def _get_work_name(tender: Tender, scraped_tender: Optional[ScrapedTender]) -> str:
    """
    Gets the work name prioritizing scraped tender data over tender table.
    """
    # First try scraped tender data (usually more detailed)
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


def extract_emd_from_scraped(scraped_tender: Optional[ScrapedTender]) -> float:
    """
    Extracts EMD value from scraped tender data.
    Returns value in Crores or 0.0 if not found.
    """
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


def extract_completion_period(scraped_tender: Optional[ScrapedTender]) -> str:
    """
    Extracts completion period from scraped tender data.
    Returns formatted string or "N/A" if not available.
    """
    if not scraped_tender:
        return "N/A"

    # Try tender_details field (parse for duration/period info)
    if scraped_tender.tender_details:
        details = scraped_tender.tender_details.lower()
        # Look for patterns like "X months", "X years", "X days"
        month_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:months?|month|m\.?)', details)
        if month_match:
            return f"{month_match.group(1)} Months"

        year_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:years?|year|y\.?)', details)
        if year_match:
            years = float(year_match.group(1))
            months = int(years * 12)
            return f"{months} Months"

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


def generate_basic_info(tender: Tender, scraped_tender: Optional[ScrapedTender]) -> list[BasicInfoItem]:
    """
    Generates the basicInfo array with 10 key fields.
    Dynamically fetches data from both tender and scraped_tender tables.
    """
    tender_value_crores = get_estimated_cost_in_crores(tender)
    emd_crores = get_bid_security_in_crores(tender)

    # Extract dynamic data from scraped tender
    document_cost = extract_document_cost(scraped_tender)
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
            description=f"{tender.length_km} km" if tender.length_km else "N/A"
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


def generate_all_requirements(tender: Tender, scraped_tender: Optional[ScrapedTender]) -> list[RequirementItem]:
    """
    Generates the allRequirements array with eligibility criteria.
    Uses tender data for calculations and scraped data for requirement details.
    Uses generic requirements suitable for most infrastructure projects.
    """
    tender_value_crores = get_estimated_cost_in_crores(tender)
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
            ceigallValue=""
        ),
        RequirementItem(
            description="Technical Capacity",
            requirement="For demonstrating technical capacity and experience (the \"Technical Capacity\"), the Bidder shall, over the past 7 (Seven) financial years preceding the Bid Due Date, have:",
            ceigallValue=""
        ),
        RequirementItem(
            description="(i)",
            requirement="paid for, or received payments for, construction of Eligible Project(s);",
            ceigallValue=""
        ),
        RequirementItem(
            description="Clause 2.2.2 A",
            requirement="updated in accordance with clause 2.2.2.(I) and/ or (ii) paid for development of Eligible Project(s) in Category 1 and/or Category 2 specified in Clause 3.4.1; updated in accordance with clause 2.2.2.(I) and/ or",
            ceigallValue=f"Rs. {(tender_value_crores * 2.4):.2f} Crores" if tender_value_crores > 0 else "N/A"
        ),
        RequirementItem(
            description="(iii)",
            requirement=f"collected and appropriated revenues from Eligible Project(s) in Category 1 and/or Category 2 specified in Clause 3.4.1, updated in accordance with clause 2.2.2.(I) such that the sum total of the above as further adjusted in accordance with clause 3.4.6, is more than Rs. {(tender_value_crores * 2.4 * 1.02):.2f} Crore (the \"Threshold Technical Capability\").",
            ceigallValue=""
        ),
        RequirementItem(
            description="",
            requirement="Provided that at least one fourth of the Threshold Technical Capability shall be from the Eligible Projects in Category 1 and/ or Category 3 specified in Clause 3.4.1.",
            ceigallValue=""
        ),
        RequirementItem(
            description="",
            requirement=f"Capital cost of eligible projects should be more than Rs. {tender_value_crores:.2f} Crores." if tender_value_crores > 0 else "Capital cost of eligible projects should be as per tender requirements.",
            ceigallValue=""
        ),
        RequirementItem(
            description="Similar Work (JV Required)",
            requirement=f"Rs. {(tender_value_crores * 0.25):.2f} Crores" if tender_value_crores > 0 else "N/A",
            ceigallValue=""
        ),
    ]

    # Generic infrastructure work requirements (suitable for all project types)
    requirements.extend([
        RequirementItem(
            description="a) Similar Work Experience",
            requirement=f"One project of {project_description} with completion cost of project equal to or more than Rs. {(tender_value_crores * 0.26):.2f} crores. For this purpose, a project shall be considered to be completed if desired purpose of the project is achieved, and more than 90% of the value of work has been completed.",
            ceigallValue=""
        ),
        RequirementItem(
            description="b) Technical Capability",
            requirement=f"Experience in executing similar {project_description} with required technical specifications and quality standards as per relevant Indian Standards and project requirements.",
            ceigallValue=""
        ),
    ])

    # Common financial requirements
    requirements.extend([
        RequirementItem(
            description="Credit Rating",
            requirement="The Bidder shall have 'A' and above Credit Rating given by Credit Rating Agencies authorized by SEBI.",
            ceigallValue=""
        ),
        RequirementItem(
            description="Clause 2.2.2 A - Special Requirement",
            requirement=f"The bidder shall have experience in executing {project_description} with required materials and construction standards as per relevant specifications and quality requirements.",
            ceigallValue=""
        ),
        RequirementItem(
            description="2.2.2 B (i) Financial Capacity",
            requirement=f"The Bidder shall have a minimum Financial Capacity of Rs. {(tender_value_crores * 0.2):.2f} Crore at the close of the preceding financial year. Net Worth: Rs. {(tender_value_crores * 0.2):.2f} Crores (Each Member) / Rs. {(tender_value_crores * 0.2):.2f} Crore (JV Total). Provided further that each member of the Consortium shall have a minimum Net Worth of 7.5% of Estimated Project Cost in the immediately preceding financial year.",
            ceigallValue=""
        ),
        RequirementItem(
            description="2.2.2 B (ii) Financial Resources",
            requirement=f"The bidder shall demonstrate the total requirement of financial resources for concessionaire's contribution of Rs. {(tender_value_crores * 0.61):.2f} Crores. Bidder must demonstrate sufficient financial resources as stated above, comprising of liquid sources supplemented by unconditional commitment by bankers for finance term loan to the proposed SPV.",
            ceigallValue=""
        ),
        RequirementItem(
            description="2.2.2 B (iii) Loss-making Company",
            requirement="The bidder shall, in the last five financial years have neither been a loss-making company nor been in the list of Corporate Debt Restructuring (CDR) and/or Strategic Debt Restructuring (SDR) and/or having been declared Insolvent. The bidder should submit a certificate from its statutory auditor in this regard.",
            ceigallValue=""
        ),
        RequirementItem(
            description="2.2.2 B (iv) Average Annual Construction Turnover",
            requirement=f"The bidder shall demonstrate an average annual construction turnover of Rs. {(tender_value_crores * 0.41):.2f} crores within last three years.",
            ceigallValue=""
        ),
        RequirementItem(
            description="JV T & C",
            requirement="In case of a Consortium, the combined technical capability and net worth of those Members, who have and shall continue to have an equity share of at least 26% (twenty six per cent) each in the SPV, should satisfy the above conditions of eligibility.",
            ceigallValue=""
        )
    ])

    return requirements


def generate_bid_synopsis(tender: Tender, scraped_tender: Optional[ScrapedTender] = None) -> BidSynopsisResponse:
    """
    Main function to generate complete bid synopsis from tender and scraped tender data.
    
    Args:
        tender: The Tender ORM object
        scraped_tender: Optional ScrapedTender ORM object for additional data
    
    Returns:
        BidSynopsisResponse with both basicInfo and allRequirements
    """
    basic_info = generate_basic_info(tender, scraped_tender)
    all_requirements = generate_all_requirements(tender, scraped_tender)

    return BidSynopsisResponse(
        basicInfo=basic_info,
        allRequirements=all_requirements
    )