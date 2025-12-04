"""
Service to generate and save bid synopsis data after tender analysis.
This runs as part of the analysis pipeline and stores results in DB.
"""
from typing import Optional
import json
from app.modules.analyze.db.schema import TenderAnalysis
from app.modules.scraper.db.schema import ScrapedTender
from app.core.langchain_config import get_langchain_llm
from sqlalchemy.orm import Session


async def generate_and_save_bid_synopsis(
    analysis: TenderAnalysis,
    scraped_tender: Optional[ScrapedTender],
    db: Session
) -> dict:
    """
    Generate qualification criteria from tender analysis and save to database.
    Called automatically after tender analysis completes.
    
    Returns the generated bid synopsis data.
    """
    try:
        # Query Weaviate for detailed eligibility/qualification content
        from app.core.services import get_vector_store
        vector_store = get_vector_store()

        weaviate_content = []

        if not vector_store or not vector_store.client:
            print("⚠️ Weaviate client not initialized, proceeding without vector search")
            # Continue without Weaviate data - we can still generate synopsis from analysis data
        else:
            try:
                # Search for eligibility, qualification, and financial requirement content
                search_queries = [
                    "eligibility criteria requirements conditions",
                    "qualification financial capacity turnover",
                    "enlistment registration class category",
                    "EMD earnest money deposit bid security",
                    "performance guarantee bank guarantee",
                    "similar work experience past projects"
                ]

                for query in search_queries:
                    results = vector_store.similarity_search(
                        collection_name=f"Tender_{analysis.tender_id}",
                        query_text=query,
                        limit=5
                    )
                    for result in results:
                        # result is a tuple: (doc_content, properties, similarity)
                        doc_content, properties, similarity = result
                        if doc_content and len(doc_content) > 100:  # Only include substantial content
                            weaviate_content.append(doc_content)

                print(f"📚 Retrieved {len(weaviate_content)} detailed chunks from Weaviate")
            except Exception as weaviate_error:
                print(f"⚠️ Could not fetch from Weaviate: {weaviate_error}")
        
        # Collect ALL available tender data
        tender_data = {
            'one_pager': analysis.one_pager_json or {},
            'scope_of_work': analysis.scope_of_work_json or {},
            'data_sheet': analysis.data_sheet_json or {},
            'rfp_sections': [],
            'weaviate_detailed_content': weaviate_content[:10]  # Top 10 most relevant chunks
        }
        
        # Add RFP sections data
        if hasattr(analysis, 'rfp_sections') and analysis.rfp_sections:
            for section in analysis.rfp_sections:
                tender_data['rfp_sections'].append({
                    'section_number': section.section_number,
                    'section_title': section.section_title,
                    'summary': section.summary,
                    'key_requirements': section.key_requirements
                })
        
        # Use LLM to extract qualification criteria
        llm = get_langchain_llm()
        
        # Build detailed prompt focusing on qualification criteria only
        prompt = f"""Extract QUALIFICATION/ELIGIBILITY CRITERIA from tender data.

QUALIFICATION CRITERIA DEFINITION:
Requirements that bidders must meet to be ELIGIBLE to participate in the tender.
This includes: Financial capacity, Experience, Technical qualifications, Compliance requirements.

EXCLUDE (these are NOT qualification criteria):
- Project specifications (SBC, materials, design parameters)
- Project value/cost estimates  
- Work scope/deliverables
- Construction methods/technical details

DATA STRUCTURE:
{json.dumps(tender_data, indent=2, default=str)[:25000]}

EXTRACTION RULES:
1. **PRIORITY SOURCE**: Use weaviate_detailed_content - this has the FULL original tender document text
2. From data_sheet → financial_details: Extract EMD, Performance Security values
3. From one_pager → eligibility_highlights: Use as headlines, but EXPAND with Weaviate content
4. Cross-reference all sources to build comprehensive requirement text

CRITICAL REQUIREMENT TEXT RULES:
- **PRIMARY SOURCE**: weaviate_detailed_content contains the actual tender document text - USE THIS!
- one_pager and rfp_sections are summaries - Weaviate has the FULL details
- For each requirement, search weaviate_detailed_content for matching context
- MINIMUM 150 words per requirement (aim for 200-300 words from Weaviate content)
- Include VERBATIM text from tender documents (found in Weaviate)
- Include ALL details: exact clause numbers, formulas, calculations, conditions, exemptions, procedures, timelines, documents needed
- Include specific enlistment procedures, classification details, financial thresholds
- Include exact percentage requirements, calculation methods, exemption clauses
- Quote relevant sections from tender document directly
- DO NOT summarize - copy detailed text from weaviate_detailed_content
- Think: "Extract the EXACT requirement as written in tender document"

EXAMPLE OF USING WEAVIATE CONTENT:
If one_pager says: "Enlisted with MES in Class SS"
Search weaviate_detailed_content for: "MES", "enlistment", "Class SS", "Category"
Extract full paragraph(s) explaining: registration process, required documents, class/category definitions, application procedure, fees, timelines

EXAMPLE OF GOOD REQUIREMENT TEXT:
"The bidder must demonstrate Bid Capacity calculated using the formula: Bid Capacity = (A x N x 2) - B, where A is the Average Annual Financial Turnover during the last three financial years (2020-21, 2021-22, 2022-23) updated to price level of current year using WPI, N is the number of years prescribed for completion of works for which bids are invited (2 years in this case), and B is the value of existing commitments and ongoing works to be completed during the period of completion of work for which bids are invited. The assessed Bid Capacity should be equal to or more than the estimated cost put to tender. Bidders must submit audited balance sheets and profit & loss statements for the last 3 financial years, along with CA certificate in prescribed format. Joint ventures shall combine the capacity of all partners as per their profit sharing ratio."

CRITICAL FORMATTING RULES FOR CURRENCY:
- Convert all amounts to Crores or Lakhs format: "Rs. X.XX Crores" or "Rs. X.XX Lakhs"
- 1 Crore = 10,000,000 (1,00,00,000)
- 1 Lakh = 100,000 (1,00,000)
- Examples: 
  * "INR 46300000" → "Rs. 4.63 Crores"
  * "Rs 25000000" → "Rs. 2.50 Crores"
  * "500000" → "Rs. 5.00 Lakhs"

FORMAT each as:
{{
  "description": "Clear, short label WITHOUT prefixes (e.g., 'EMD Amount', 'Minimum Turnover', 'Similar Work Experience')",
  "requirement": "COMPLETE DETAILED requirement text with FULL CONTEXT (MINIMUM 100 words, include ALL formulas, conditions, exemptions, procedures, clause references, numerical values)",
  "extractedValue": "Amount in 'Rs. X.XX Crores' or 'Rs. X.XX Lakhs' format, or empty string if not applicable"
}}

AVOID DUPLICATES:
- If you see multiple mentions of EMD, include only ONE EMD entry with the MOST COMPLETE requirement text
- If you see multiple mentions of turnover, include only ONE turnover entry with ALL details combined
- Combine similar requirements into single comprehensive entry

CRITICAL JSON FORMATTING:
- ALL string values MUST properly escape special characters
- Use \\n for newlines, \\" for quotes, \\\\ for backslashes
- Ensure ALL strings are properly terminated with closing quotes
- Do NOT include literal newlines or unescaped quotes in strings
- Test that your JSON is valid before responding

Return valid JSON array with DETAILED requirements (remember: MINIMUM 100 words per requirement).
"""

        # Call LLM
        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)

        # Extract JSON from response with better handling
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()

        # Try to find JSON array if extraction failed
        if not response_text.startswith('['):
            # Look for a JSON array in the response
            import re
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                response_text = json_match.group(0)

        # Helper function to fix common JSON issues
        def fix_json_string(text):
            """Fix common JSON formatting issues."""
            import re

            # Try to fix unterminated strings by finding the problematic section
            # This is a heuristic approach - look for unescaped newlines in string values

            # Strategy: Parse char by char and track if we're inside a string
            fixed = []
            in_string = False
            escape_next = False

            for i, char in enumerate(text):
                if escape_next:
                    fixed.append(char)
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    fixed.append(char)
                    continue

                if char == '"':
                    in_string = not in_string
                    fixed.append(char)
                elif char == '\n' and in_string:
                    # Escape unescaped newlines inside strings
                    fixed.append('\\n')
                elif char == '\r' and in_string:
                    # Skip carriage returns inside strings
                    continue
                elif char == '\t' and in_string:
                    # Escape tabs inside strings
                    fixed.append('\\t')
                else:
                    fixed.append(char)

            return ''.join(fixed)

        # Parse LLM response with better error handling
        try:
            qualification_criteria = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parsing error at position {e.pos}: {e.msg}")
            print(f"Response text (first 500 chars): {response_text[:500]}")
            # Try to fix common JSON issues
            try:
                fixed_text = fix_json_string(response_text)
                qualification_criteria = json.loads(fixed_text)
                print("✅ Fixed JSON by escaping special characters")
            except Exception as fix_error:
                print(f"❌ Could not fix JSON ({fix_error}), returning empty criteria")
                qualification_criteria = []
        
        # AGGRESSIVE deduplication and cleanup
        seen_types = {}
        unique_criteria = []
        
        for item in qualification_criteria:
            desc = item.get('description', '').strip()
            req_text = item.get('requirement', '').strip()
            value = item.get('extractedValue', '').strip()
            
            # Clean description - remove ALL prefixes
            prefixes_to_remove = [
                'Eligibility Highlights - ', 'Eligibility Highlights -', 'Eligibility Highlights-',
                'Financial Requirements - ', 'Financial Requirements -', 'Financial Requirements-',
                'Qualification - ', 'Qualification -', 'Qualification-',
                'Criteria - ', 'Criteria -', 'Criteria-',
                'Cl ', 'Clause ', 'Section ',
            ]
            for prefix in prefixes_to_remove:
                if desc.startswith(prefix):
                    desc = desc[len(prefix):].strip()
                    break
            
            # Normalize description to detect duplicates
            desc_lower = desc.lower()
            
            # Determine unique key for deduplication
            if 'emd' in desc_lower or 'earnest money' in desc_lower or 'bid security' in desc_lower:
                key = 'emd'
            elif 'performance' in desc_lower and ('security' in desc_lower or 'guarantee' in desc_lower or 'bank guarantee' in desc_lower):
                key = 'performance_guarantee'
            elif 'turnover' in desc_lower:
                key = 'turnover'
            elif 'net worth' in desc_lower or 'networth' in desc_lower:
                key = 'networth'
            elif 'experience' in desc_lower or 'similar work' in desc_lower:
                key = 'experience'
            elif 'technical' in desc_lower and 'capacity' in desc_lower:
                key = 'technical_capacity'
            elif 'financial' in desc_lower and 'capacity' in desc_lower:
                key = 'financial_capacity'
            elif 'bid capacity' in desc_lower or 'bidding capacity' in desc_lower:
                key = 'bid_capacity'
            elif 'tender fee' in desc_lower or 'document fee' in desc_lower:
                key = 'tender_fee'
            else:
                # Use normalized description as key
                key = desc_lower.replace(' ', '_')[:50]
            
            # If duplicate, keep the one with MORE detailed requirement text
            if key in seen_types:
                existing_req_len = len(seen_types[key]['requirement'])
                new_req_len = len(req_text)
                if new_req_len > existing_req_len:
                    # Replace with more detailed version
                    seen_types[key] = {
                        'description': desc,
                        'requirement': req_text,
                        'extractedValue': value or seen_types[key]['extractedValue']  # Keep value if exists
                    }
            else:
                seen_types[key] = {
                    'description': desc,
                    'requirement': req_text,
                    'extractedValue': value
                }
        
        # Convert to list
        unique_criteria = list(seen_types.values())
        qualification_criteria = unique_criteria
        
        # Save to database using direct SQL UPDATE to avoid FK issues
        bid_synopsis_data = {
            'qualification_criteria': qualification_criteria,
            'generated_at': str(analysis.analysis_completed_at or analysis.updated_at),
            'source': 'llm_extraction'
        }
        
        # Use direct SQL UPDATE to avoid FK validation issues
        from sqlalchemy import text
        import json as json_lib
        db.execute(
            text("UPDATE tender_analysis SET bid_synopsis_json = :data WHERE id = :id"),
            {"data": json_lib.dumps(bid_synopsis_data), "id": str(analysis.id)}
        )
        db.commit()
        
        print(f"✅ Generated and saved {len(qualification_criteria)} qualification criteria to DB")
        return bid_synopsis_data
        
    except Exception as e:
        print(f"❌ Error generating bid synopsis: {e}")
        import traceback
        traceback.print_exc()
        return {'qualification_criteria': [], 'error': str(e)}


def get_bid_synopsis_from_db(analysis: TenderAnalysis) -> list[dict]:
    """
    Retrieve pre-generated bid synopsis from database.
    Much faster than generating on-the-fly.
    """
    if analysis.bid_synopsis_json and 'qualification_criteria' in analysis.bid_synopsis_json:
        criteria = analysis.bid_synopsis_json['qualification_criteria']
        
        # Format for API response
        formatted_requirements = []
        for i, item in enumerate(criteria):
            formatted_requirements.append({
                'description': item.get('description', ''),
                'requirement': item.get('requirement', ''),
                'extractedValue': item.get('extractedValue', ''),
                'context': item.get('requirement', '')[:200] + '...' if len(item.get('requirement', '')) > 200 else item.get('requirement', ''),
                'source': 'db_stored',
                'priority': 100 - i
            })
        
        return formatted_requirements
    
    return []
