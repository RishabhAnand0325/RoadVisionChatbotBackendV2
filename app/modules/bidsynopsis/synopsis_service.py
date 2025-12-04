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


def _extract_qualification_requirements_only(analysis: Optional[TenderAnalysis], scraped_tender: Optional[ScrapedTender]) -> list[dict]:
    """
    Extract qualification criteria - first tries DB, then generates if needed.
    Uses LLM to extract from tender analysis data WITHOUT hardcoding or hallucination.
    """
    from app.modules.bidsynopsis.bid_synopsis_generator import get_bid_synopsis_from_db
    
    requirements = []
    
    if not analysis:
        return requirements
    
    # Try to get from database first (much faster!)
    db_requirements = get_bid_synopsis_from_db(analysis)
    if db_requirements:
        print(f"✅ Retrieved {len(db_requirements)} qualification criteria from DB")
        return db_requirements
    
    # If not in DB, generate using LLM (will be saved to DB for next time)
    print("⚠️ Bid synopsis not in DB, generating with LLM...")
    
    # Use LLM to extract qualification criteria from all analysis data
    try:
        from app.core.langchain_config import get_langchain_llm
        from app.core.services import vector_store
        import json
        
        # Get LLM instance
        llm = get_langchain_llm()
        
        # Query Weaviate for detailed content
        weaviate_content = []
        try:
            if vector_store:
                search_queries = [
                    "eligibility criteria requirements qualifications",
                    "financial capacity turnover net worth",
                    "enlistment registration class category MES",
                    "EMD earnest money deposit bid security",
                    "performance guarantee bank guarantee security deposit",
                    "similar work experience past projects completion",
                    "technical capacity manpower equipment resources"
                ]
                
                for query in search_queries:
                    results = vector_store.query_tender(
                        tender_id=str(analysis.tender_id),
                        query=query,
                        n_results=3
                    )
                    for doc, metadata, similarity in results:
                        if len(doc) > 100:
                            weaviate_content.append(doc)
                
                print(f"📚 Retrieved {len(weaviate_content)} detailed chunks from Weaviate")
            else:
                print("⚠️ Weaviate vector_store not available")
        except Exception as weaviate_error:
            print(f"⚠️ Could not fetch from Weaviate: {weaviate_error}")
        
        # Prepare tender data for LLM
        tender_data = {
            'one_pager': analysis.one_pager_json or {},
            'scope_of_work': analysis.scope_of_work_json or {},
            'data_sheet': analysis.data_sheet_json or {},
            'rfp_sections': [],
            'weaviate_detailed_content': weaviate_content[:15]  # Top 15 chunks
        }
        
        # Add RFP sections
        if hasattr(analysis, 'rfp_sections') and analysis.rfp_sections:
            for section in analysis.rfp_sections:
                tender_data['rfp_sections'].append({
                    'section_number': section.section_number,
                    'section_title': section.section_title,
                    'summary': section.summary,
                    'key_requirements': section.key_requirements
                })
        
        # LLM Prompt for extracting qualification criteria with Weaviate content
        prompt = f"""Extract ALL bidder qualification/eligibility requirements from this tender data.

Tender Data:
{json.dumps(tender_data, indent=2, default=str)[:30000]}

INSTRUCTIONS:
- Use weaviate_detailed_content as PRIMARY source for detailed text
- Expand brief one_pager summaries with relevant details from weaviate_detailed_content
- Each requirement: 2-4 sentences with key clause numbers, values, formulas, conditions
- Be comprehensive for important requirements, brief for simple ones

Look for:
- Bid Capacity (formulas, calculations)
- Technical Capacity/Experience (past projects, similar work)
- Financial Capacity (turnover, net worth, thresholds)
- EMD/Bid Security (amount, payment terms)
- Performance Guarantee (security deposit requirements)
- Enlistment/Registration (MES, class/category requirements)
- Statutory compliance (PAN, GST, etc.)
- Equipment/Manpower requirements

For EACH criterion extract:
- **description**: Short label (e.g., "Bid Capacity", "TTC", "EMD")
- **requirement**: Clear explanation with key details from weaviate_detailed_content (2-4 sentences)
- **extractedValue**: Numeric value with currency if present (e.g., "Rs. 2,575.08 Crores")

Return ONLY valid JSON array:
[
  {{"description": "Bid Capacity", "requirement": "Brief description with formula and key conditions...", "extractedValue": ""}},
  {{"description": "TTC", "requirement": "Key project requirements and value thresholds...", "extractedValue": "Rs. 2,575.08 Crores"}}
]

If NO qualification criteria found, return: []"""

        # Call LLM
        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Extract JSON from response
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()
        
        # Parse LLM response
        extracted_reqs = json.loads(response_text)
        
        # Format requirements
        for i, req in enumerate(extracted_reqs):
            # Format currency value if present
            extracted_value = req.get('extractedValue', '')
            if extracted_value:
                extracted_value = _standardize_currency_format(extracted_value)
            
            requirements.append({
                'description': req.get('description', f'Requirement {i+1}'),
                'requirement': req.get('requirement', ''),
                'extractedValue': extracted_value,
                'context': req.get('requirement', '')[:200] + '...' if len(req.get('requirement', '')) > 200 else req.get('requirement', ''),
                'source': 'llm_extracted_qualification',
                'priority': 100 - i  # Higher priority for earlier items
            })
        
        print(f"✅ LLM extracted {len(requirements)} qualification requirements")
        
        # SAVE TO DATABASE to avoid regenerating every time
        try:
            from sqlalchemy import text
            from app.db.database import SessionLocal
            
            # Clean descriptions to remove prefixes
            for item in requirements:
                desc = item.get('description', '').strip()
                prefixes_to_remove = [
                    'Eligibility Highlights - ',
                    'Eligibility Highlights -',
                    'Financial Requirements - ',
                    'Financial Requirements -',
                    'Qualification - ',
                    'Qualification -',
                    'Criteria - ',
                    'Criteria -',
                    'Cl ', 'Clause ',
                ]
                for prefix in prefixes_to_remove:
                    if desc.startswith(prefix):
                        desc = desc[len(prefix):].strip()
                        break
                item['description'] = desc
            
            # Create DB data structure (matching bid_synopsis_generator format)
            db_data = {
                'qualification_criteria': [
                    {
                        'description': req['description'],
                        'requirement': req['requirement'],
                        'extractedValue': req.get('extractedValue', '')
                    }
                    for req in requirements
                ],
                'generated_at': str(analysis.updated_at),
                'source': 'synopsis_service_llm'
            }
            
            # Save to database using direct SQL
            db = SessionLocal()
            try:
                db.execute(
                    text("UPDATE tender_analysis SET bid_synopsis_json = :data WHERE id = :id"),
                    {"data": json.dumps(db_data), "id": str(analysis.id)}
                )
                db.commit()
                print(f"✅ Saved {len(requirements)} criteria to DB for future use")
            finally:
                db.close()
                
        except Exception as save_error:
            print(f"⚠️ Could not save to DB: {save_error}")
        
    except Exception as e:
        print(f"❌ LLM extraction failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback to basic extraction if LLM fails
        if analysis.one_pager_json and 'eligibility_highlights' in analysis.one_pager_json:
            for i, item in enumerate(analysis.one_pager_json['eligibility_highlights']):
                requirements.append({
                    'description': f'Eligibility Requirement {i+1}',
                    'requirement': item,
                    'extractedValue': '',
                    'context': item[:200] + '...' if len(item) > 200 else item,
                    'source': 'one_pager_eligibility',
                    'priority': 50
                })
    
    return requirements
    if analysis.one_pager_json and isinstance(analysis.one_pager_json, dict):
        eligibility = analysis.one_pager_json.get('eligibility_highlights', [])
        if isinstance(eligibility, list):
            for i, item in enumerate(eligibility):
                if isinstance(item, str) and len(item.strip()) > 10:
                    extracted_value = _extract_qualification_values(item)
                    
                    # Format like screenshot
                    requirements.append({
                        'description': f'Eligibility Criteria {i+1}',
                        'requirement': item,
                        'extractedValue': extracted_value,
                        'context': 'Eligibility Requirements',
                        'source': 'eligibility_highlights',
                        'priority': 85
                    })
    
    # 3. Extract from RFP sections if they have qualification content
    if hasattr(analysis, 'rfp_sections') and analysis.rfp_sections:
        for rfp_section in analysis.rfp_sections:
            section_title = getattr(rfp_section, 'section_title', '').lower()
            section_number = getattr(rfp_section, 'section_number', '')
            
            # Only extract from qualification-related sections
            is_qualification_section = any(term in section_title for term in [
                'eligibility', 'qualification', 'criteria', 'bid capacity', 
                'technical capacity', 'financial capacity', 'ttc', 'aat', 
                'networth', 'net worth', 'turnover', 'site visit'
            ])
            
            if is_qualification_section:
                key_requirements = getattr(rfp_section, 'key_requirements', [])
                
                if key_requirements and isinstance(key_requirements, list):
                    for req_text in key_requirements:
                        if isinstance(req_text, str) and len(req_text.strip()) > 10:
                            extracted_value = _extract_qualification_values(req_text)
                            
                            # Format like screenshot - use section number as description
                            requirements.append({
                                'description': f'Clause {section_number}',
                                'requirement': req_text,
                                'extractedValue': extracted_value,
                                'context': section_title.title(),
                                'source': f'rfp_section_{section_number}',
                                'priority': 80
                            })
    
    # Remove duplicates and sort by priority
    unique_requirements = _deduplicate_requirements(requirements)
    sorted_requirements = sorted(unique_requirements, key=lambda x: x.get('priority', 0), reverse=True)
    
    return sorted_requirements


def _extract_all_qualifications_from_section(section_data, source_name: str) -> list[dict]:
    """
    Dynamically extract ALL qualification criteria from any data structure.
    Recursively searches through nested data to find qualification content.
    NO hardcoding - adapts to any content structure.
    """
    requirements = []
    
    def _is_qualification_content(text: str) -> bool:
        """Dynamically identify if content contains qualification criteria."""
        if not isinstance(text, str) or len(text.strip()) < 15:
            return False
            
        text_lower = text.lower()
        
        # FINANCIAL qualification indicators - HIGH PRIORITY
        financial_indicators = [
            'turnover', 'net worth', 'financial capacity', 'revenue', 'profit',
            'capital', 'liquidity', 'credit rating', 'bank guarantee', 'financial strength',
            'working capital', 'paid up capital', 'annual income', 'crores', 'lakhs'
        ]
        
        # EXPERIENCE qualification indicators - HIGH PRIORITY
        experience_indicators = [
            'years of experience', 'experience in', 'similar projects', 'completed projects',
            'executed projects', 'project execution', 'past experience', 'track record',
            'construction experience', 'implementation experience', 'delivery experience',
            'executed works', 'completed works', 'project portfolio', 'demonstrated experience'
        ]
        
        # TECHNICAL qualification indicators - HIGH PRIORITY
        technical_indicators = [
            'license', 'registration', 'certification', 'accreditation', 'approval',
            'technical qualification', 'technical competency', 'technical capability',
            'class contractor', 'grade contractor', 'empanelled', 'authorized', 'certified',
            'technical expertise', 'technical resources'
        ]
        
        # EQUIPMENT/RESOURCE qualification indicators - MEDIUM PRIORITY
        equipment_indicators = [
            'equipment', 'machinery', 'plant', 'tools', 'resources', 'infrastructure',
            'manpower', 'technical staff', 'qualified personnel', 'engineers', 'supervisors',
            'availability of', 'possession of'
        ]
        
        # LEGAL/COMPLIANCE qualification indicators - MEDIUM PRIORITY
        legal_indicators = [
            'compliance', 'statutory', 'regulatory', 'legal', 'tax', 'gst',
            'pan', 'cin', 'udyam', 'msme', 'startup', 'valid documents', 'statutory compliance'
        ]
        
        # EXPLICIT requirement/eligibility language
        requirement_language = [
            'bidder shall', 'contractor shall', 'vendor must', 'supplier should',
            'must have', 'shall have', 'should have', 'required to have', 'need to have',
            'minimum', 'at least', 'not less than', 'not below', 'above',
            'eligibility', 'qualification', 'criteria', 'requirement'
        ]
        
        # Check for qualification indicators
        has_financial = any(indicator in text_lower for indicator in financial_indicators)
        has_experience = any(indicator in text_lower for indicator in experience_indicators)
        has_technical = any(indicator in text_lower for indicator in technical_indicators)
        has_equipment = any(indicator in text_lower for indicator in equipment_indicators)
        has_legal = any(indicator in text_lower for indicator in legal_indicators)
        has_requirement_language = any(indicator in text_lower for indicator in requirement_language)
        
        # BALANCED filtering - either strong qualification terms OR explicit eligibility/qualification language
        has_strong_qualification = has_financial or has_experience or has_technical
        has_moderate_qualification = has_equipment or has_legal
        
        # Accept if:
        # 1. Strong qualification indicators (financial/experience/technical)
        # 2. Moderate qualification + requirement language
        # 3. Explicit eligibility/qualification terms
        is_qualification = (
            has_strong_qualification or 
            (has_moderate_qualification and has_requirement_language) or
            any(term in text_lower for term in ['eligibility', 'qualification criteria', 'technical expertise'])
        )
        
        # EXCLUDE basic tender information - these are NOT qualification criteria
        basic_info_exclusions = [
            'tender value', 'contract value', 'project value', 'estimated cost',
            'document fee', 'tender fee', 'emd amount', 'earnest money',
            'submission deadline', 'due date', 'opening date', 'closing date',
            'tendering authority', 'issuing authority', 'contact person',
            'project location', 'site address', 'state', 'city', 'district',
            'project name', 'tender title', 'this tender is for', 'project involves'
        ]
        
        # EXCLUDE work specifications - but be more selective
        work_spec_exclusions = [
            'widening and strengthening', 'construction of bridge', 'pavement design',
            'this tender', 'project overview', 'work description', 'scope includes',
            'bituminous expansion joint', 'designed for specific loading'
        ]
        
        is_basic_info = any(exclusion in text_lower for exclusion in basic_info_exclusions)
        is_work_spec = any(exclusion in text_lower for exclusion in work_spec_exclusions)
        
        # Only accept if it's qualification content and NOT basic info or work specs
        return is_qualification and not is_basic_info and not is_work_spec
    
    def _extract_from_any_structure(data, path=""):
        """Recursively extract from any nested data structure."""
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                _extract_from_any_structure(value, current_path)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]" if path else f"[{i}]"
                _extract_from_any_structure(item, current_path)
        
        elif isinstance(data, str):
            if _is_qualification_content(data):
                # Extract qualification requirement
                extracted_value = _extract_qualification_values(data)
                context = _get_qualification_context({}, path, data)
                description = _generate_qualification_description(path, data)
                priority = _calculate_qualification_priority(path, data)
                
                requirements.append({
                    'description': description,
                    'requirement': data,
                    'context': context,
                    'extractedValue': extracted_value,
                    'source': f"{source_name}_{path}",
                    'priority': priority
                })
        
        # Handle structured data (like data_sheet items)
        elif isinstance(data, dict) and 'label' in data and 'value' in data:
            label = data.get('label', '')
            value = str(data.get('value', ''))
            combined_text = f"{label}: {value}"
            
            if _is_qualification_content(combined_text) or _is_qualification_content(label):
                extracted_value = _extract_qualification_values(value)
                context = _get_qualification_context(data, label, value)
                description = _generate_qualification_description(label, value)
                priority = _calculate_qualification_priority(label, value)
                
                requirements.append({
                    'description': description,
                    'requirement': combined_text,
                    'context': context,
                    'extractedValue': extracted_value,
                    'source': f"{source_name}_{path}",
                    'priority': priority
                })
    
    # Start recursive extraction
    _extract_from_any_structure(section_data)
    
    return requirements


def _extract_all_qualifications_from_rfp_section(rfp_section) -> list[dict]:
    """
    Extract qualification requirements from an RFP section object.
    """
    requirements = []
    
    if not rfp_section:
        return requirements
    
    # Extract from section title and summary
    section_data = {
        'section_number': getattr(rfp_section, 'section_number', ''),
        'section_title': getattr(rfp_section, 'section_title', ''),
        'summary': getattr(rfp_section, 'summary', ''),
        'key_requirements': getattr(rfp_section, 'key_requirements', [])
    }
    
    # Use the existing comprehensive extraction function
    section_reqs = _extract_all_qualifications_from_section(
        section_data, f'rfp_section_{rfp_section.section_number or "unknown"}'
    )
    
    return section_reqs


def _extract_qualification_from_scraped(scraped_tender: ScrapedTender) -> list[dict]:
    """
    Extract qualification requirements from scraped tender data.
    """
    requirements = []
    
    if scraped_tender:
        # Extract from scraped content using existing function but filter for qualifications only
        scraped_reqs = _extract_from_scraped_comprehensive(scraped_tender)
        
        # Filter to only qualification-related requirements
        for req in scraped_reqs:
            desc = req.get('description', '').lower()
            context = req.get('context', '').lower()
            requirement = req.get('requirement', '').lower()
            
            # Check if this is qualification-related content
            qualification_terms = [
                'experience', 'qualification', 'eligibility', 'turnover', 'net worth',
                'license', 'registration', 'certification', 'technical', 'financial',
                'equipment', 'machinery', 'manpower', 'capacity', 'competency'
            ]
            
            if any(term in f"{desc} {context} {requirement}" for term in qualification_terms):
                requirements.append(req)
    
    return requirements


def _extract_requirements_from_documents(analysis: Optional[TenderAnalysis], scraped_tender: Optional[ScrapedTender]) -> list[dict]:
    """
    Robustly extract ALL qualification criteria from tender documents.
    
    Returns comprehensive requirements found in documents.
    Each requirement dict contains: description, requirement, extractedValue
    """
    requirements = []
    
    if analysis:
        # Extract from ALL JSON fields comprehensively
        json_fields = [
            ('data_sheet', analysis.data_sheet_json),
            ('scope_of_work', analysis.scope_of_work_json),
            ('one_pager', analysis.one_pager_json)
        ]
        
        for field_name, json_data in json_fields:
            if json_data and isinstance(json_data, dict):
                # Extract from ALL sections, not just "requirement" ones
                for section_name, section_data in json_data.items():
                    if isinstance(section_data, (dict, list)):
                        extracted_reqs = _extract_from_section_comprehensive(section_name, section_data, field_name)
                        requirements.extend(extracted_reqs)
    
    # Also extract from scraped tender documents for additional coverage
    if scraped_tender:
        scraped_reqs = _extract_from_scraped_comprehensive(scraped_tender)
        requirements.extend(scraped_reqs)
    
    # Remove duplicates but keep all unique requirements
    unique_requirements = _deduplicate_requirements(requirements)
    
    # Sort by importance (financial first, then technical, then others)
    sorted_requirements = _sort_requirements_by_importance(unique_requirements)
    
    return sorted_requirements


def _extract_from_section_comprehensive(section_name: str, section_data, source: str) -> list[dict]:
    """Extract ONLY qualification criteria - NO basic tender information."""
    requirements = []
    
    if isinstance(section_data, dict):
        # Extract from dictionary - ONLY qualification criteria
        for key, value in section_data.items():
            if value and str(value).strip():
                key_clean = key.replace('_', ' ').title()
                value_str = str(value).strip()
                
                # AGGRESSIVE FILTERING: Exclude ALL basic tender information
                is_basic_tender_info = any([
                    # Project administrative details - EXCLUDE
                    any(basic_key in key.lower() for basic_key in [
                        'project_name', 'project_title', 'name', 'title',
                        'contract_value', 'project_value', 'tender_value', 'estimated_value',
                        'duration', 'period', 'completion_time', 'timeline',
                        'location', 'state', 'city', 'address', 'site',
                        'authority', 'department', 'organization', 'client',
                        'tender_type', 'procurement_type', 'contract_type',
                        'due_date', 'submission_date', 'deadline', 'opening_date',
                        'document_fee', 'tender_fee', 'emd', 'earnest_money',
                        'work_type', 'scope', 'details', 'description'
                    ]),
                    # Basic descriptive content - EXCLUDE  
                    any(basic_content in value_str.lower() for basic_content in [
                        'project name', 'tender for', 'construction of', 'supply of',
                        'maintenance of', 'installation of', 'procurement of',
                        'contract value', 'estimated value', 'total value',
                        'location', 'state', 'city', 'situated', 'located',
                        'duration', 'months', 'years', 'completion period',
                        'tendering authority', 'department', 'ministry', 
                        'work type', 'scope of work', 'nature of work'
                    ]),
                    # Short non-qualification descriptive text
                    len(value_str) < 80 and not any(qual_indicator in value_str.lower() for qual_indicator in [
                        'experience required', 'years of experience', 'turnover', 'net worth',
                        'license required', 'registration required', 'qualification required',
                        'eligibility', 'bidder must', 'contractor shall', 'minimum'
                    ])
                ])
                
                # Skip ALL basic tender information
                if is_basic_tender_info:
                    continue
                
                # ONLY extract TRUE qualification criteria with specific requirements
                is_qualification = any([
                    # Specific experience requirements
                    any(exp_phrase in value_str.lower() for exp_phrase in [
                        'years of experience in', 'minimum experience of', 'experience required',
                        'past experience', 'similar projects completed', 'executed projects of',
                        'construction experience', 'project execution experience',
                        'experience in similar', 'completed similar projects'
                    ]),
                    # Specific financial qualifications
                    any(fin_phrase in value_str.lower() for fin_phrase in [
                        'minimum annual turnover', 'average annual turnover', 'turnover of',
                        'minimum net worth', 'net worth of', 'financial capacity of',
                        'minimum financial', 'turnover during last', 'average turnover'
                    ]),
                    # Specific technical/licensing requirements
                    any(tech_phrase in value_str.lower() for tech_phrase in [
                        'license required', 'registration required', 'certification required',
                        'valid license', 'valid registration', 'technical qualification',
                        'class contractor', 'grade contractor', 'accredited', 'empanelled'
                    ]),
                    # Specific equipment/capacity requirements
                    any(equip_phrase in value_str.lower() for equip_phrase in [
                        'equipment required', 'machinery worth', 'plant worth',
                        'construction equipment', 'equipment value', 'possess equipment',
                        'adequate manpower', 'technical staff', 'qualified personnel'
                    ]),
                    # Explicit qualification statements
                    any(criteria_phrase in value_str.lower() for criteria_phrase in [
                        'eligibility criteria', 'qualification criteria', 'bidder must have',
                        'contractor shall have', 'minimum requirement', 'prequalification',
                        'eligibility requirement', 'qualification requirement'
                    ]),
                    # Check if this is from eligibility-specific sections
                    'eligibility' in key.lower() and len(value_str) > 30
                ])
                
                # ONLY proceed if this is a clear qualification requirement
                if is_qualification:
                    # Get meaningful context for qualification criteria
                    full_context = _get_qualification_context(section_data, key, value_str)
                    
                    # Extract relevant values (amounts, percentages, years, etc.)
                    extracted_value = _extract_qualification_values(value_str)
                    
                    requirements.append({
                        'description': _generate_qualification_description(key_clean, value_str),
                        'requirement': full_context,
                        'extractedValue': extracted_value,
                        'source': f'{source}_{section_name}',
                        'priority': _calculate_qualification_priority(key_clean, value_str)
                    })
    
    elif isinstance(section_data, list):
        for item in section_data:
            if isinstance(item, dict):
                # Handle structured data
                label = item.get('label', item.get('name', item.get('title', item.get('item', ''))))
                value = item.get('value', item.get('description', item.get('requirement', item.get('amount', ''))))
                item_type = item.get('type', '')
                
                if label and value:
                    label_clean = str(label).strip()
                    value_clean = str(value).strip()
                    
                    # Create meaningful context by combining label and value meaningfully
                    full_context = _create_contextual_sentence(label_clean, value_clean)
                    
                    # Only extract monetary values
                    extracted_value = _extract_monetary_values_only(value_clean)
                    
                    # Standardize currency formatting if it's a monetary value
                    if extracted_value:
                        extracted_value = _standardize_currency_format(extracted_value)
                    
                    requirements.append({
                        'description': label_clean,
                        'requirement': full_context,  # Full context
                        'extractedValue': extracted_value,
                        'source': f'{source}_{section_name}',
                        'type': item_type,
                        'priority': _calculate_priority(label_clean, value_clean)
                    })
                
                # Also extract other fields from the item
                for k, v in item.items():
                    if k not in ['label', 'name', 'title', 'value', 'description', 'type'] and v:
                        k_clean = str(k).replace('_', ' ').title()
                        v_clean = str(v).strip()
                        if len(v_clean) > 5 and _is_meaningful_content(v_clean):
                            # Create meaningful context
                            full_context_v = _create_contextual_sentence(k_clean, v_clean)
                            
                            # Only extract monetary values
                            extracted_val = _extract_monetary_values_only(v_clean)
                            
                            # Standardize currency formatting if it's a monetary value
                            if extracted_val:
                                extracted_val = _standardize_currency_format(extracted_val)
                                
                            requirements.append({
                                'description': k_clean,
                                'requirement': full_context_v,  # Use meaningful context
                                'extractedValue': extracted_val,
                                'source': f'{source}_{section_name}_{k}',
                                'priority': _calculate_priority(k_clean, v_clean)
                            })
            
            elif isinstance(item, str) and len(item.strip()) > 10:
                # Handle string items - use full string as context
                item_clean = item.strip()
                description = _generate_requirement_description(item_clean)
                if not description:
                    # Generate description from content
                    words = item_clean.split()[:3]
                    description = ' '.join(words).title()
                
                # Only extract monetary values
                extracted_value = _extract_monetary_values_only(item_clean)
                
                # Standardize currency formatting if it's a monetary value
                if extracted_value:
                    extracted_value = _standardize_currency_format(extracted_value)
                
                requirements.append({
                    'description': description,
                    'requirement': item_clean,  # Full context
                    'extractedValue': extracted_value,
                    'source': f'{source}_{section_name}',
                    'priority': _calculate_priority(description, item_clean)
                })
    
    return requirements


def _extract_from_scraped_comprehensive(scraped_tender: ScrapedTender) -> list[dict]:
    """Extract requirements from scraped tender data comprehensively."""
    requirements = []
    
    # Check all available fields
    fields_to_check = [
        ('Tender Brief', scraped_tender.tender_brief),
        ('Tender Details', getattr(scraped_tender, 'tender_details', None)),
        ('Tendering Authority', scraped_tender.tendering_authority),
        ('Tender Value', scraped_tender.tender_value),
        ('Document Fees', scraped_tender.document_fees),
        ('EMD', scraped_tender.emd),
        ('Due Date', scraped_tender.due_date),
        ('Tender Type', scraped_tender.tender_type),
        ('State', scraped_tender.state),
        ('City', scraped_tender.city)
    ]
    
    for field_name, field_value in fields_to_check:
        if field_value and str(field_value).strip() and str(field_value).strip() != 'N/A':
            value_clean = str(field_value).strip()
            
            # Extract requirements from longer text fields
            if len(value_clean) > 50:
                sentences = _split_into_meaningful_parts(value_clean)
                for sentence in sentences:
                    if len(sentence.strip()) > 20:
                        desc = _generate_requirement_description(sentence) or _extract_key_term(sentence)
                        if desc:
                            # Only extract monetary values
                            extracted_value = _extract_monetary_values_only(sentence)
                            
                            # Standardize currency formatting if it's a monetary value
                            if extracted_value:
                                extracted_value = _standardize_currency_format(extracted_value)
                            requirements.append({
                                'description': desc,
                                'requirement': sentence.strip(),
                                'extractedValue': extracted_value,
                                'source': f'scraped_{field_name.lower().replace(" ", "_")}',
                                'priority': _calculate_priority(desc, sentence)
                            })
            else:
                # For shorter fields, treat as direct requirements
                extracted_value = _extract_monetary_values_only(value_clean)
                
                # Always standardize currency formatting, especially for raw numbers
                if extracted_value:
                    extracted_value = _standardize_currency_format(extracted_value)
                
                requirements.append({
                    'description': field_name,
                    'requirement': _create_contextual_sentence(field_name, value_clean),  # Create meaningful context
                    'extractedValue': extracted_value,
                    'source': f'scraped_{field_name.lower().replace(" ", "_")}',
                    'priority': _calculate_priority(field_name, value_clean)
                })
    
    return requirements


def _is_important_standalone_value(value: str) -> bool:
    """Check if a value is important enough to be extracted as-is."""
    value_lower = value.lower().strip()
    
    # Financial values
    if any(indicator in value_lower for indicator in ['rs.', 'inr', 'crore', 'lakh', 'amount']):
        return True
    
    # Time periods
    if any(indicator in value_lower for indicator in ['day', 'month', 'year', 'week']):
        return True
        
    # Ratings and grades
    if any(indicator in value_lower for indicator in ['grade', 'rating', 'class', 'category']):
        return True
        
    # Locations and authorities
    if any(indicator in value_lower for indicator in ['limited', 'corporation', 'authority', 'board', 'ministry']):
        return True
        
    return False


def _is_meaningful_content(content: str) -> bool:
    """Check if content is meaningful and worth extracting."""
    content_lower = content.lower().strip()
    
    # Skip very generic or empty content
    if content_lower in ['n/a', 'na', 'nil', 'none', 'not applicable', 'tbd', 'to be decided', '']:
        return False
        
    # Skip pure numbers unless they're meaningful
    if content.strip().isdigit() and len(content.strip()) < 4:
        return False
        
    return len(content.strip()) > 3


def _get_full_context_from_section(section_data: dict, key: str, value: str) -> str:
    """Get full context surrounding a value in a section."""
    # If the value is long enough, return it as is
    if len(value) > 50:
        return value
    
    # Look for related fields that might provide context
    context_keys = ['description', 'details', 'note', 'remark', 'comment', 'info', 'specification']
    
    for context_key in context_keys:
        if context_key in section_data and section_data[context_key]:
            context_value = str(section_data[context_key]).strip()
            if context_value and context_value != value:
                return f"{value}. {context_value}"
    
    # Look for keys that start with the same word
    key_lower = key.lower()
    for k, v in section_data.items():
        if k != key and k.lower().startswith(key_lower.split('_')[0]) and v:
            related_value = str(v).strip()
            if related_value != value and len(related_value) > 10:
                return f"{value}. Related: {related_value}"
    
    # Default to just the value
    return value


def _get_qualification_context(section_data: dict, key: str, value: str) -> str:
    """Get meaningful context specifically for qualification criteria."""
    
    # If the value is already a detailed qualification requirement, use it
    if len(value) > 80 or any(indicator in value.lower() for indicator in [
        'shall have', 'must have', 'should have', 'required to', 'minimum of',
        'at least', 'not less than', 'experience in', 'completion of'
    ]):
        return value
    
    # Create contextual descriptions for qualification criteria
    key_lower = key.lower()
    
    if 'experience' in key_lower:
        return f"Bidder must have {value} of relevant project execution experience"
    elif 'turnover' in key_lower:
        return f"Minimum annual turnover requirement: {value}"
    elif 'net worth' in key_lower:
        return f"Required net worth for financial eligibility: {value}"
    elif 'rating' in key_lower:
        return f"Credit rating requirement: {value}"
    elif any(word in key_lower for word in ['technical', 'capacity', 'capability']):
        return f"Technical qualification requirement: {value}"
    elif 'registration' in key_lower or 'license' in key_lower:
        return f"Mandatory registration/licensing requirement: {value}"
    elif any(word in key_lower for word in ['equipment', 'machinery', 'plant']):
        return f"Required equipment/machinery specification: {value}"
    else:
        return f"Eligibility criteria - {key.replace('_', ' ').title()}: {value}"


def _extract_qualification_values(text: str) -> str:
    """Extract specific qualification values (years, amounts, percentages, etc.)."""
    import re
    
    if not text:
        return ""
    
    # Patterns for qualification-specific values
    patterns = [
        # Years of experience
        r'(\d+)\s*(?:years?|yrs?).*(?:experience|exp)',
        # Monetary amounts (for turnover, net worth, etc.)
        r'Rs\.\s*([\d,]+(?:\.\d+)?)\s*(?:crore|crores|lakh|lakhs)',
        r'INR\s+([\d,]+(?:\.\d+)?)',
        r'\b([\d,]{8,}(?:\.\d+)?)\b',  # Large numbers
        # Percentages
        r'(\d+(?:\.\d+)?%)',
        # Technical specifications
        r'(\d+(?:\.\d+)?)\s*(?:tons?|mt|kg|kw|mw|hp)',
        # Credit ratings
        r"'([A-Z]+)'\s*(?:and\s+above)?",
        # Project counts
        r'(\d+)\s*(?:projects?|works?|contracts?)',
        # Capacity/quantity specifications
        r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:units?|nos?|pieces?)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            matched_text = match.group(0)
            
            # For monetary amounts, standardize the format
            if any(curr in matched_text.lower() for curr in ['rs.', 'inr']) or re.match(r'\d{8,}', matched_text.replace(',', '')):
                return _standardize_currency_format(matched_text)
            
            # For other values, return as-is
            return matched_text
    
    return ""


def _generate_qualification_description(key: str, value: str) -> str:
    """Generate appropriate description for qualification criteria."""
    
    key_lower = key.lower()
    value_lower = value.lower()
    
    # Experience-related descriptions
    if any(word in key_lower for word in ['experience', 'executed', 'completed']):
        if 'similar' in value_lower:
            return "Similar Project Experience"
        elif any(word in value_lower for word in ['construction', 'building', 'infrastructure']):
            return "Construction Experience"
        else:
            return "Project Execution Experience"
    
    # Financial descriptions
    elif any(word in key_lower for word in ['turnover', 'revenue']):
        return "Financial Turnover Requirement"
    elif 'net worth' in key_lower or 'networth' in key_lower:
        return "Net Worth Requirement"
    elif 'rating' in key_lower:
        return "Credit Rating Requirement"
    
    # Technical descriptions
    elif any(word in key_lower for word in ['technical', 'capacity', 'capability']):
        return "Technical Qualification"
    elif any(word in key_lower for word in ['equipment', 'machinery', 'plant']):
        return "Equipment Requirement"
    elif any(word in key_lower for word in ['manpower', 'staff', 'personnel']):
        return "Manpower Requirement"
    
    # Licensing and registration
    elif any(word in key_lower for word in ['license', 'registration', 'approval']):
        return "Registration Requirement"
    elif any(word in key_lower for word in ['certificate', 'certification']):
        return "Certification Requirement"
    
    # Default based on content
    else:
        if any(word in value_lower for word in ['shall', 'must', 'required']):
            return "Mandatory Requirement"
        elif any(word in value_lower for word in ['minimum', 'at least']):
            return "Minimum Eligibility"
        else:
            return key


def _calculate_qualification_priority(key: str, value: str) -> int:
    """Calculate priority for qualification requirements (higher = more important)."""
    priority = 0
    key_lower = key.lower()
    value_lower = value.lower()
    
    # Highest priority for financial and experience requirements
    if any(word in key_lower for word in ['experience', 'turnover', 'net worth']):
        priority += 100
    
    # High priority for technical qualifications
    if any(word in key_lower for word in ['technical', 'capacity', 'qualification']):
        priority += 80
    
    # Medium priority for registration and licensing
    if any(word in key_lower for word in ['license', 'registration', 'certificate']):
        priority += 60
    
    # Boost for mandatory requirements
    if any(word in value_lower for word in ['shall', 'must', 'required', 'mandatory']):
        priority += 50
    
    # Boost for specific numerical requirements
    if any(word in value_lower for word in ['minimum', 'at least', 'not less than']):
        priority += 30
    
    # Boost for detailed requirements
    if len(value) > 50:
        priority += 20
    
    return priority


def _standardize_currency_format(text: str) -> str:
    """Standardize currency format to Rs. X.XX Crores like the rest of the project."""
    if not text:
        return text
    
    import re
    
    # Handle percentage - return as is if it's a meaningful percentage
    if '%' in text and any(word in text.lower() for word in ['turnover', 'revenue', 'contract', 'value', 'cost', 'ecpt']):
        return text
    
    # Pattern to match various currency formats
    patterns = [
        # Rs. X.XX Crore/Crores (already formatted) - return as is
        r'Rs\.\s*([\d,]+(?:\.\d+)?)\s*Crores?',
        # Rs. X.XX Lakhs - return as is  
        r'Rs\.\s*([\d,]+(?:\.\d+)?)\s*Lakhs?',
        # INR 35400000, INR 35,40,00,000
        r'INR\s+([\d,]+(?:\.\d+)?)',
        # Rs. 35400000, Rs 35,40,00,000 (without crore/lakh)
        r'Rs\.\s*([\d,]+(?:\.\d+)?)(?!\s*(?:crore|lakh))',
        # ₹ 35400000
        r'₹\s*([\d,]+(?:\.\d+)?)',
        # Just numbers with crore/lakh context
        r'([\d,]+(?:\.\d+)?)\s*(?:crore|crores|lakh|lakhs)',
        # Raw large numbers (8+ digits) - these need conversion
        r'^([\d,]{8,}(?:\.\d+)?)$',
    ]
    
    for i, pattern in enumerate(patterns):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # If it's already in the correct format (first two patterns), return as is
            if i < 2:
                return text
                
            amount_str = match.group(1).replace(',', '')
            try:
                amount = float(amount_str)
                
                # Convert to crores
                if amount >= 10000000:  # 1 crore or more
                    crores = amount / 10000000
                    if crores.is_integer():
                        return f"Rs. {int(crores)} Crores"
                    else:
                        return f"Rs. {crores:.2f} Crores"
                elif amount >= 100000:  # 1 lakh or more
                    lakhs = amount / 100000
                    if lakhs.is_integer():
                        return f"Rs. {int(lakhs)} Lakhs"
                    else:
                        return f"Rs. {lakhs:.2f} Lakhs"
                else:
                    return f"Rs. {amount:,.0f}"
            except ValueError:
                continue
    
    return text


def _calculate_priority(description: str, content: str) -> int:
    """Calculate priority for requirement sorting (higher = more important)."""
    priority = 0
    desc_lower = description.lower()
    content_lower = content.lower()
    
    # Financial requirements (highest priority)
    if any(keyword in desc_lower + content_lower for keyword in [
        'emd', 'amount', 'value', 'cost', 'fee', 'crore', 'lakh', 'financial', 'turnover', 'net worth'
    ]):
        priority += 100
    
    # Technical requirements
    if any(keyword in desc_lower + content_lower for keyword in [
        'technical', 'experience', 'capacity', 'qualification', 'capability'
    ]):
        priority += 80
        
    # Time-related requirements
    if any(keyword in desc_lower + content_lower for keyword in [
        'duration', 'period', 'deadline', 'date', 'time'
    ]):
        priority += 60
        
    # Project details
    if any(keyword in desc_lower + content_lower for keyword in [
        'project', 'work', 'construction', 'tender'
    ]):
        priority += 40
        
    # Basic info
    if any(keyword in desc_lower for keyword in [
        'name', 'location', 'authority', 'type', 'category'
    ]):
        priority += 20
        
    return priority


def _split_into_meaningful_parts(text: str) -> list[str]:
    """Split text into meaningful parts for requirement extraction."""
    import re
    
    # Split by common delimiters
    parts = re.split(r'[.!?;]+|\n|\r', text)
    
    meaningful_parts = []
    for part in parts:
        part = part.strip()
        if len(part) > 15:  # Only meaningful length parts
            # Further split by "and" or "or" if very long
            if len(part) > 200:
                sub_parts = re.split(r'\s+(?:and|or)\s+', part, flags=re.IGNORECASE)
                for sub_part in sub_parts:
                    if len(sub_part.strip()) > 15:
                        meaningful_parts.append(sub_part.strip())
            else:
                meaningful_parts.append(part)
    
    return meaningful_parts


def _extract_key_term(text: str) -> str:
    """Extract a key term from text to use as description."""
    import re
    
    # Look for key terms that could be descriptions
    key_patterns = [
        r'(?:the\s+)?(\w+\s+(?:requirement|criteria|specification|capacity|experience|qualification))',
        r'(?:minimum\s+|required\s+|mandatory\s+)(\w+(?:\s+\w+){0,2})',
        r'((?:financial|technical|construction|project)\s+\w+)',
        r'(\w+\s+(?:amount|value|cost|fee|period|duration))',
        r'(emd|turnover|net\s+worth|experience|capacity)'
    ]
    
    for pattern in key_patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1).title()
    
    # Fallback: use first few meaningful words
    words = [w for w in text.split() if len(w) > 2 and w.lower() not in ['the', 'and', 'or', 'for', 'with']]
    if words:
        return ' '.join(words[:3]).title()
    
    return ""


def _deduplicate_requirements(requirements: list[dict]) -> list[dict]:
    """Remove duplicate requirements while preserving the best version."""
    seen = {}
    unique = []
    
    for req in requirements:
        desc_key = req['description'].lower().strip()
        
        # If we haven't seen this description
        if desc_key not in seen:
            seen[desc_key] = req
            unique.append(req)
        else:
            # If current has higher priority, replace
            if req.get('priority', 0) > seen[desc_key].get('priority', 0):
                # Remove the old one and add the new one
                unique = [r for r in unique if r['description'].lower().strip() != desc_key]
                unique.append(req)
                seen[desc_key] = req
    
    return unique


def _sort_requirements_by_importance(requirements: list[dict]) -> list[dict]:
    """Sort requirements by importance (priority)."""
    return sorted(requirements, key=lambda x: x.get('priority', 0), reverse=True)


def _extract_from_section_comprehensive(section_name: str, section_data, source: str) -> list[dict]:
    """Extract requirements from a specific section of analysis data."""
    requirements = []
    
    if isinstance(section_data, dict):
        for key, value in section_data.items():
            if isinstance(value, str) and len(value.strip()) > 20:
                # Extract key terms that look like requirement descriptions
                key_clean = key.replace('_', ' ').title()
                value_clean = str(value).strip()
                
                # Only add if it looks like a real requirement
                if any(indicator in value_clean.lower() for indicator in [
                    'shall', 'must', 'required', 'minimum', 'experience',
                    'capacity', 'crore', 'year', 'rating', 'turnover'
                ]):
                    # Extract only monetary values from the requirement text
                    extracted_value = _extract_monetary_values_only(value_clean)
                    
                    # Standardize currency formatting if it's a monetary value
                    if extracted_value:
                        extracted_value = _standardize_currency_format(extracted_value)
                    
                    requirements.append({
                        'description': key_clean,
                        'requirement': value_clean,
                        'extractedValue': extracted_value,
                        'source': f'{source}_{section_name}'
                    })
    
    elif isinstance(section_data, list):
        for item in section_data:
            if isinstance(item, dict):
                # Handle structured analysis data format
                label = item.get('label', item.get('name', item.get('title', '')))
                value = item.get('value', item.get('description', item.get('requirement', '')))
                item_type = item.get('type', '')
                highlight = item.get('highlight', False)
                
                if label and value and len(str(value).strip()) > 10:
                    value_clean = str(value).strip()
                    label_clean = str(label).strip()
                    
                    # Check if this looks like a requirement or important value
                    is_requirement = any(indicator in value_clean.lower() for indicator in [
                        'shall', 'must', 'required', 'minimum', 'experience',
                        'capacity', 'crore', 'year', 'rating', 'turnover', 'lakhs'
                    ])
                    
                    # Or if it's a financial/important detail
                    is_important = (item_type in ['money', 'currency', 'financial'] or 
                                  highlight or 
                                  any(keyword in label_clean.lower() for keyword in [
                                      'emd', 'contract', 'value', 'fee', 'amount', 'duration'
                                  ]))
                    
                    if is_requirement or is_important:
                        extracted_value = _extract_monetary_values_only(value_clean)
                        
                        # Standardize currency formatting if it's a monetary value
                        if extracted_value:
                            extracted_value = _standardize_currency_format(extracted_value)
                        # Don't use the value itself as extracted value unless it's monetary
                        
                        requirements.append({
                            'description': label_clean,
                            'requirement': f"{label_clean}: {value_clean}",
                            'extractedValue': extracted_value,
                            'source': f'{source}_{section_name}',
                            'type': item_type,
                            'highlight': highlight
                        })
            elif isinstance(item, str) and len(item.strip()) > 20:
                # Handle string items (like eligibility_highlights)
                item_clean = item.strip()
                if any(indicator in item_clean.lower() for indicator in [
                    'shall', 'must', 'required', 'minimum', 'experience',
                    'capacity', 'crore', 'year', 'rating', 'turnover', 'bid'
                ]):
                    description = _generate_requirement_description(item_clean)
                    if description:
                        extracted_value = _extract_monetary_values_only(item_clean)
                        
                        # Standardize currency formatting if it's a monetary value
                        if extracted_value:
                            extracted_value = _standardize_currency_format(extracted_value)
                        
                        requirements.append({
                            'description': description,
                            'requirement': item_clean,
                            'extractedValue': extracted_value,
                            'source': f'{source}_{section_name}'
                        })
    
    return requirements


def _generate_requirement_description(requirement_text: str) -> str:
    """
    Generate a concise description from requirement text.
    Returns empty string if cannot generate meaningful description.
    """
    import re
    
    text_lower = requirement_text.lower()
    
    # Pattern matching for common requirement types
    patterns = {
        'technical': ['technical', 'capacity', 'capability', 'experience'],
        'financial': ['financial', 'net worth', 'turnover', 'resources'],
        'experience': ['experience', 'similar work', 'project'],
        'qualification': ['qualification', 'eligibility', 'criteria'],
        'credit': ['credit', 'rating', 'sebi'],
        'consortium': ['consortium', 'joint venture', 'jv'],
        'completion': ['completion', 'period', 'duration'],
        'site': ['site', 'visit', 'inspection']
    }
    
    # Find the best matching category
    for category, keywords in patterns.items():
        if any(keyword in text_lower for keyword in keywords):
            # Try to extract a more specific description
            if 'crore' in text_lower or 'lakh' in text_lower:
                if category == 'technical':
                    return 'Technical Capacity'
                elif category == 'financial':
                    if 'turnover' in text_lower:
                        return 'Annual Turnover'
                    elif 'net worth' in text_lower:
                        return 'Net Worth Requirement'
                    else:
                        return 'Financial Capacity'
            
            elif 'year' in text_lower:
                if category == 'experience':
                    return 'Work Experience'
                elif 'loss' in text_lower:
                    return 'Loss-making Restriction'
            
            elif 'rating' in text_lower:
                return 'Credit Rating'
            
            elif 'site' in text_lower:
                return 'Site Visit'
            
            elif 'consortium' in text_lower or 'joint venture' in text_lower:
                return 'Joint Venture Terms'
            
            # Generic category-based descriptions
            return f"{category.title()} Requirement"
    
    # If no pattern matches, return empty (don't hallucinate)
    return ""


def _get_meaningful_context(section_data: dict, key: str, value: str) -> str:
    """Get meaningful context for a value, creating rich natural sentences when possible."""
    
    # If the value is already a complete sentence or long description, use it
    if len(value) > 100 or any(indicator in value.lower() for indicator in [
        'shall', 'must', 'required', 'minimum', 'completion', 'including', 'construction',
        'development', 'procurement', 'engineering', 'tender for', 'project'
    ]):
        return value
    
    # Look for additional context in the section data
    context_fields = ['description', 'details', 'note', 'remark', 'specification', 'info']
    additional_context = []
    
    for field in context_fields:
        if field in section_data and section_data[field]:
            ctx = str(section_data[field]).strip()
            if ctx and ctx != value and len(ctx) > 10:
                additional_context.append(ctx)
    
    # Create rich context based on field type
    key_clean = key.replace('_', ' ').title()
    key_lower = key.lower()
    
    if 'amount' in key_lower or 'value' in key_lower or 'cost' in key_lower:
        if 'tender' in key_lower:
            base_text = f"The total tender value for this project is {value}"
        elif 'contract' in key_lower:
            base_text = f"The contract value for this project amounts to {value}"
        elif 'emd' in key_lower:
            base_text = f"Earnest Money Deposit (EMD) required for bidding is {value}"
        else:
            base_text = f"The {key_clean.lower()} specified for this tender is {value}"
    elif 'date' in key_lower:
        base_text = f"The {key_clean.lower()} for submission/completion is {value}"
    elif 'authority' in key_lower or 'organization' in key_lower:
        base_text = f"The {key_clean.lower()} responsible for this tender is {value}"
    elif 'type' in key_lower:
        base_text = f"This procurement is classified as a {value} type project"
    elif 'name' in key_lower or 'title' in key_lower:
        base_text = f"The project is titled: {value}"
    elif any(word in key_lower for word in ['fee', 'fees']):
        base_text = f"The {key_clean.lower()} for this tender documentation is {value}"
    else:
        base_text = f"{key_clean}: {value}"
    
    # Add additional context if available
    if additional_context:
        # Take the most relevant additional context (first one)
        base_text += f". Additional details: {additional_context[0][:100]}..."
    
    return base_text


def _create_contextual_sentence(label: str, value: str) -> str:
    """Create a meaningful contextual sentence from label and value with rich context."""
    
    # If value is already a complete sentence, use it
    if len(value) > 50 and any(char in value for char in '.!?'):
        return value
    
    # If value is very long description, use as-is
    if len(value) > 100:
        return value
    
    # Handle "Refer document" cases specially
    if 'refer' in value.lower() and 'document' in value.lower():
        return f"For {label.lower()}, bidders must refer to the tender document for specific details and requirements"
    
    label_lower = label.lower()
    
    # Create rich natural sentences based on label type
    if 'amount' in label_lower or 'value' in label_lower or 'cost' in label_lower:
        if 'emd' in label_lower:
            return f"Earnest Money Deposit (EMD) required for participating in this tender is {value}"
        elif 'contract' in label_lower:
            return f"Total contract value for the execution of this project is {value}"
        elif 'document' in label_lower or 'fee' in label_lower:
            return f"Document fees that must be paid to obtain tender documents amount to {value}"
        elif 'tender' in label_lower:
            return f"Total estimated tender value for this construction/procurement project is {value}"
        else:
            return f"The {label.lower()} specified in the tender documents is {value}"
    
    elif 'emd' in label_lower and 'amount' not in label_lower:
        return f"Earnest Money Deposit (EMD) requirement for this tender is {value}"
    
    elif 'document' in label_lower and 'fee' in label_lower:
        return f"Fees required for purchasing tender documents and specifications amount to {value}"
    
    elif 'date' in label_lower or 'deadline' in label_lower:
        if 'due' in label_lower:
            return f"Final deadline for submission of completed tender bids is {value}"
        else:
            return f"Important {label.lower()} specified in the tender schedule is {value}"
    
    elif 'authority' in label_lower or 'organization' in label_lower:
        return f"The {label.lower()} responsible for issuing and managing this tender is {value}"
    
    elif 'experience' in label_lower:
        return f"Experience qualification required from bidders: {value}"
    
    elif 'financial' in label_lower and 'requirement' in label_lower:
        return f"Financial eligibility criteria that bidders must meet: {value}"
    
    elif 'technical' in label_lower and 'requirement' in label_lower:
        return f"Technical qualification and capability requirements: {value}"
    
    elif 'type' in label_lower:
        return f"This procurement is categorized as a {value} type project"
    
    elif 'name' in label_lower or 'title' in label_lower:
        if 'project' in label_lower:
            return f"Official project name/title: {value}"
        else:
            return f"The project is officially named: {value}"
    
    elif any(word in label_lower for word in ['construction', 'development', 'work']):
        return f"Scope of construction/development work includes: {value}"
    
    elif 'state' in label_lower:
        return f"This project is located in the state of {value}"
    
    elif 'city' in label_lower:
        return f"Project location/implementation site is in {value}"
    
    else:
        # Enhanced generic format for other cases
        return f"Tender specification for {label.lower()}: {value}"
    
    return f"{label}: {value}"


def _clean_field_prefix(text: str, field_name: str) -> str:
    """Remove field name prefix if it exists at the start of the text."""
    if not text or not field_name:
        return text
    
    # Clean field name variations
    field_variations = [
        f"{field_name}:",
        f"{field_name} :",
        f"{field_name.replace(' ', '_')}:",
        f"{field_name.replace('_', ' ')}:",
        f"{field_name.lower()}:",
        f"{field_name.upper()}:",
        f"{field_name.title()}:"
    ]
    
    text_clean = text.strip()
    for variation in field_variations:
        if text_clean.lower().startswith(variation.lower()):
            return text_clean[len(variation):].strip()
    
    return text


def _extract_monetary_values_only(text: str) -> str:
    """Extract ONLY monetary/currency values from text - nothing else."""
    import re
    
    if not text:
        return ""
    
    # Clean up text for better matching
    text = text.strip()
    
    # Extract currency amounts - prioritize complete patterns, avoid partial matches
    currency_patterns = [
        # Rs. X.XX Crores (already formatted) - highest priority
        r'Rs\.\s*([\d,]+(?:\.\d+)?)\s*Crores?\b',
        # Rs. X.XX Lakhs
        r'Rs\.\s*([\d,]+(?:\.\d+)?)\s*Lakhs?\b',
        # Percentage with financial context
        r'(\d+(?:\.\d+)?%)\s*of\s+(?:turnover|revenue|contract|value|cost|ECPT|turnover)',
        # INR followed by amount with spaces/symbols
        r'INR\s+([\d,]+(?:\.\d+)?)\s*(?:/\-|\/-|$|\s)',
        # Rs. followed by large amount (must be substantial)
        r'Rs\.\s*([\d,]{4,}(?:\.\d+)?)\b',
        # ₹ followed by amount  
        r'₹\s*([\d,]+(?:\.\d+)?)\b',
        # Amount with explicit crore/lakh (must be meaningful)
        r'([\d,]+(?:\.\d+)?)\s*(?:crore|crores|lakh|lakhs)\b',
        # Large standalone numbers that look like tender values (8+ digits)
        r'\b([\d,]{8,}(?:\.\d+)?)\b',
        # Numbers in value/amount context
        r'(?:value|amount|cost|worth|tender)\s*(?:is|of)?\s*([\d,]+(?:\.\d+)?)\b',
    ]
    
    for pattern in currency_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            matched_text = match.group(0).strip()
            
            # Validate the match - avoid meaningless extractions
            if len(matched_text) < 4:  # Too short to be meaningful
                continue
                
            # If it contains just "rs" or "Rs." without numbers, skip
            if re.match(r'^Rs?\.?\s*,?\s*$', matched_text, re.IGNORECASE):
                continue
            
            # Special handling for percentage
            if '%' in matched_text:
                return matched_text
            
            # Extract the numeric part to validate
            numeric_part = re.search(r'[\d,]+(?:\.\d+)?', matched_text)
            if numeric_part:
                number_str = numeric_part.group(0).replace(',', '')
                try:
                    number = float(number_str)
                    # Skip very small amounts, but include large tender values
                    if number < 1:
                        continue
                    return matched_text
                except ValueError:
                    continue
    
    # Don't extract anything else - only valid monetary values
    return ""


def _extract_important_values_from_text(requirement_text: str) -> str:
    """Extract important specific values from text."""
    import re
    
    # Extract currency amounts - look for complete patterns first
    currency_patterns = [
        # Rs. X.XX Crores (already formatted)
        r'Rs\.\s*([\d,]+(?:\.\d+)?)\s*Crores?',
        # Rs. X.XX Lakhs
        r'Rs\.\s*([\d,]+(?:\.\d+)?)\s*Lakhs?',
        # INR followed by amount
        r'INR\s*([\d,]+(?:\.\d+)?)',
        # Rs. followed by amount
        r'Rs\.?\s*([\d,]+(?:\.\d+)?)',
        # ₹ followed by amount
        r'₹\s*([\d,]+(?:\.\d+)?)',
        # Amount with explicit crore/lakh
        r'([\d,]+(?:\.\d+)?)\s*(?:crore|crores|lakh|lakhs)',
    ]
    
    for pattern in currency_patterns:
        match = re.search(pattern, requirement_text, re.IGNORECASE)
        if match:
            # Return the full matched text for proper formatting
            return _standardize_currency_format(match.group(0))
    
    # Extract dates
    date_patterns = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}',
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, requirement_text, re.IGNORECASE)
        if match:
            return match.group(0)
    
    # Extract percentages
    percentage_match = re.search(r'\d+(?:\.\d+)?%', requirement_text)
    if percentage_match:
        return percentage_match.group(0)
    
    # Extract years of experience
    exp_match = re.search(r'(\d+)\s*(?:years?|yrs?).*(?:experience|exp)', requirement_text, re.IGNORECASE)
    if exp_match:
        return f"{exp_match.group(1)} years"
    
    # Extract technical specifications (numbers with units)
    spec_match = re.search(r'\d+(?:\.\d+)?\s*(?:mm|cm|m|km|kg|ton|kw|mw|hp|volts?|v)', requirement_text, re.IGNORECASE)
    if spec_match:
        return spec_match.group(0)
    
    # Extract time durations
    time_match = re.search(r'\d+\s*(?:days?|months?|weeks?|hours?|minutes?)', requirement_text, re.IGNORECASE)
    if time_match:
        return time_match.group(0)
    
    # Extract credit ratings
    rating_match = re.search(r"'([A-Z]+)'\s*(?:and\s+above)?\s*Credit\s*Rating", requirement_text, re.IGNORECASE)
    if rating_match:
        return f"'{rating_match.group(1)}' and above"
    
    return ""


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
    Generates the allRequirements array with ONLY qualification/eligibility criteria.
    Extracts ONLY from qualification-specific sections, NOT from basic project info.
    Enhanced with analysis data for improved accuracy.
    Only returns qualification requirements - no basic tender information.
    """
    
    # Extract ONLY qualification requirements from specific sections
    dynamic_requirements = _extract_qualification_requirements_only(analysis, scraped_tender)
    
    if dynamic_requirements:
        # Use dynamically extracted qualification requirements
        requirements = []
        for req_data in dynamic_requirements:
            # Clean the requirement text to remove field prefixes
            cleaned_requirement = _clean_field_prefix(req_data['requirement'], req_data['description'])
            
            # Ensure extracted value is properly formatted
            extracted_val = req_data['extractedValue']
            if extracted_val:
                extracted_val = _standardize_currency_format(extracted_val)
            
            requirements.append(RequirementItem(
                description=req_data['description'],
                requirement=cleaned_requirement,
                extractedValue=extracted_val,
                ceigallValue=""  # Empty for user input
            ))
        return requirements
    
    # Fallback: If no dynamic extraction possible, use minimal verified requirements
    tender_value_crores = get_estimated_cost_in_crores(tender, scraped_tender)
    
    # Only include requirements we can verify from basic tender data
    verified_requirements = []
    
    # Site Visit - Only if mentioned in scraped data
    if scraped_tender and scraped_tender.tender_brief:
        brief_lower = scraped_tender.tender_brief.lower()
        if any(term in brief_lower for term in ['site visit', 'site inspection', 'visit site']):
            verified_requirements.append(RequirementItem(
                description="Site Visit",
                requirement="Site visit is required as mentioned in tender documents.",
                extractedValue="Mandatory",
                ceigallValue=""
            ))
    
    # Technical/Financial requirements - Only if we have tender value
    if tender_value_crores > 0:
        verified_requirements.extend([
            RequirementItem(
                description="Project Value",
                requirement=f"Project estimated cost is Rs. {tender_value_crores:.2f} Crores as per tender documents.",
                extractedValue=f"Rs. {tender_value_crores:.2f} Crores",
                ceigallValue=""
            )
        ])
    
    # Add EMD if available
    if tender.bid_security and tender.bid_security > 0:
        verified_requirements.append(RequirementItem(
            description="Bid Security (EMD)",
            requirement=f"Earnest Money Deposit of Rs. {(tender.bid_security / 100000):.2f} Lakhs is required.",
            extractedValue=f"Rs. {(tender.bid_security / 100000):.2f} Lakhs",
            ceigallValue=""
        ))
    
    return verified_requirements if verified_requirements else [
        RequirementItem(
            description="Document Analysis Required",
            requirement="Detailed requirement analysis needed. Please upload tender documents for automatic extraction.",
            extractedValue="Analysis Required",
            ceigallValue=""
        )
    ]


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