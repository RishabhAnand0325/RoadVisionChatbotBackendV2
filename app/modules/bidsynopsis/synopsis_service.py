from typing import Optional, Union
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
import re

from app.modules.tenderiq.db.schema import Tender, ScrapedTender
from .pydantic_models import (
    BasicInfoItem,
    RequirementItem,
    BidSynopsisResponse,
)


def parse_indian_currency(value: Union[str, int, float, None]) -> float:
    """
    Converts Indian currency format (with Crores) to a numeric value.
    1 Crore = 10,000,000
    """
    if value is None:
        return 0.0

    if isinstance(value, str):
        # Handle "Crore" conversion
        if "crore" in value.lower():
            match = re.search(r'[\d,.]+', value.lower().replace('crore', ''))
            if match:
                cleaned_value = match.group(0).replace(',', '')
                try:
                    return float(cleaned_value)
                except ValueError:
                    pass

        # General cleaning: Extract numeric part
        cleaned_value = re.sub(r'[^\d.]', '', value).replace(',', '')
        try:
            return float(cleaned_value)
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
    if value > 100000000:
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

    # If value is in base currency (Rs), convert to Crores
    if value > 10000000:
        return value / 10000000
    return value


def extract_document_cost(scraped_tender: Optional[ScrapedTender]) -> str:
    """
    Extracts document cost from scraped tender data.
    Returns formatted string or "N/A" if not available.
    """
    if not scraped_tender:
        return "N/A"

    # Try document_fees field first
    if scraped_tender.document_fees:
        cost_str = scraped_tender.document_fees.strip()
        if cost_str and cost_str.lower() != "n/a" and cost_str != "":
            return f"Rs. {cost_str}" if not cost_str.lower().startswith('rs') else cost_str

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

    basic_info = [
        BasicInfoItem(
            sno=1,
            item="Employer",
            description=tender.employer_name or scraped_tender.tendering_authority if scraped_tender else "N/A"
        ),
        BasicInfoItem(
            sno=2,
            item="Name of Work",
            description=tender.tender_title or (scraped_tender.tender_name if scraped_tender else "N/A")
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
            description=f"Rs. {emd_crores:.2f} Crores in form of Bank Guarantee" if emd_crores > 0 else "N/A"
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
    """
    tender_value_crores = get_estimated_cost_in_crores(tender)
    tender_value = tender.estimated_cost or 0

    # Try to extract requirement details from scraped_tender if available
    requirement_text = "N/A"
    if scraped_tender and scraped_tender.tender_details:
        requirement_text = scraped_tender.tender_details[:500]  # First 500 chars

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
            requirement=f"Capital cost of eligible projects should be more than Rs. {(tender_value / 1000000):.2f} Crores." if tender_value > 0 else "Capital cost of eligible projects should be as per tender requirements.",
            ceigallValue=""
        ),
        RequirementItem(
            description="Similar Work (JV Required)",
            requirement=f"Rs. {(tender_value_crores * 0.25):.2f} Crores" if tender_value_crores > 0 else "N/A",
            ceigallValue=""
        ),
        RequirementItem(
            description="a) Highway/Road Work",
            requirement=f"One project shall consist of Widening / reconstruction/ up-gradation works on NH/ SH/ Expressway or on any category for four lane road of at least 9 km, having completion cost of project equal to or more than Rs. {(tender_value_crores * 0.26):.2f} crores. For this purpose, a project shall be considered to be completed, if desired purpose of the project is achieved, and more than 90% of the value of work has been completed.",
            ceigallValue=""
        ),
        RequirementItem(
            description="b) Bridge Work",
            requirement="One project shall consist of four lane bridge constructed on perennial river with a minimum length of 4.00 km including viaduct approaches, if the bridge so constructed is of 2 lane then the minimum length shall be 6.00 km including viaduct approaches. The bridge constructed shall have span equal to or greater than 50 meters in last 7 years.",
            ceigallValue=""
        ),
        RequirementItem(
            description="Credit Rating",
            requirement="The Bidder shall have 'A' and above Credit Rating given by Credit Rating Agencies authorized by SEBI.",
            ceigallValue=""
        ),
        RequirementItem(
            description="Clause 2.2.2 A - Special Requirement",
            requirement="The bidder in last Seven years, shall have executed minimum 1,00,000 cum of soil stabilization / Full Depth Recycling in Roads / Yards/ Runways etc, using Cement and additives.",
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
    ]

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