from typing import Optional, Union
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
import re

from app.modules.tenderiq.db.schema import Tender
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

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return 0.0

    # Handle "Crore" conversion (1 Crore = 10,000,000)
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
        numeric_value = float(cleaned_value)
        # If the value is very large, assume it's in the base currency (Rs) and convert to Crores
        if numeric_value > 100000000:  # More than 1 Crore
            return numeric_value / 10000000
        return numeric_value
    except ValueError:
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


def generate_basic_info(tender: Tender) -> list[BasicInfoItem]:
    """
    Generates the basicInfo array with 10 key fields.
    Uses tender data with fallback defaults.
    """
    # Calculate costs in Crores
    tender_value_crores = get_estimated_cost_in_crores(tender)
    emd_crores = get_bid_security_in_crores(tender)

    basic_info = [
        BasicInfoItem(
            sno=1,
            item="Employer",
            description=tender.employer_name or "National Highways Authority of India (NHAI)"
        ),
        BasicInfoItem(
            sno=2,
            item="Name of Work",
            description=tender.tender_title or "Construction of 4-Lane Highway from Jaipur to Ajmer (NH-8)"
        ),
        BasicInfoItem(
            sno=3,
            item="Tender Value",
            description=f"Rs. {tender_value_crores:.2f} Crores (Excluding GST)"
        ),
        BasicInfoItem(
            sno=4,
            item="Project Length",
            description=f"{tender.length_km or 120} km"
        ),
        BasicInfoItem(
            sno=5,
            item="EMD",
            description=f"Rs. {emd_crores:.2f} Crores in form of Bank Guarantee"
        ),
        BasicInfoItem(
            sno=6,
            item="Cost of Tender Documents",
            description="Rs. 6,49,000/- (To be paid online)"
        ),
        BasicInfoItem(
            sno=7,
            item="Period of Completion",
            description="48 Months"
        ),
        BasicInfoItem(
            sno=8,
            item="Pre-Bid Meeting",
            description=(
                tender.prebid_meeting_date.strftime("%d/%m/%Y at %H%M Hours IST")
                if tender.prebid_meeting_date
                else "07/07/2025 at 1530 Hours IST"
            )
        ),
        BasicInfoItem(
            sno=9,
            item="Bid Due date",
            description=(
                tender.submission_deadline.strftime("%d.%m.%Y, %I.%M %p")
                if tender.submission_deadline
                else "28.07.2025, 3.00 PM"
            )
        ),
        BasicInfoItem(
            sno=10,
            item="Physical Submission",
            description=(
                tender.submission_deadline.strftime("%d.%m.%Y, %I.%M %p")
                if tender.submission_deadline
                else "28.07.2025, 3.00 PM"
            )
        ),
    ]

    return basic_info


def generate_all_requirements(tender: Tender) -> list[RequirementItem]:
    """
    Generates the allRequirements array with eligibility criteria.
    Uses tender data for calculations.
    """
    tender_value_crores = get_estimated_cost_in_crores(tender)
    tender_value = tender.estimated_cost or 0

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
            ceigallValue=f"Rs. {(tender_value_crores * 2.4):.2f} Crores"
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
            requirement=f"Capital cost of eligible projects should be more than Rs. {(tender_value / 1000000):.2f} Crores.",
            ceigallValue=""
        ),
        RequirementItem(
            description="Similar Work (JV Required)",
            requirement=f"Rs. {(tender_value_crores * 0.25):.2f} Crores",
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


def generate_bid_synopsis(tender: Tender) -> BidSynopsisResponse:
    """
    Main function to generate complete bid synopsis from tender data.
    Combines basicInfo and allRequirements arrays.
    """
    basic_info = generate_basic_info(tender)
    all_requirements = generate_all_requirements(tender)

    return BidSynopsisResponse(
        basicInfo=basic_info,
        allRequirements=all_requirements
    )