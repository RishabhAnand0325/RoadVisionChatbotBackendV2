"""
Service to generate and save bid synopsis data after tender analysis.
This runs as part of the analysis pipeline and stores results in DB.
"""
from typing import Optional
import json
from sqlalchemy.orm import Session

from app.modules.analyze.db.schema import TenderAnalysis
from app.modules.scraper.db.schema import ScrapedTender
from app.core.langchain_config import get_langchain_llm


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
        # Query Weaviate
        from app.core.services import get_vector_store
        vector_store = get_vector_store()

        weaviate_content = []

        if not vector_store or not vector_store.client:
            print("⚠️ Weaviate client not initialized, proceeding without vector search")
        else:
            try:
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
                        doc_content, properties, similarity = result
                        if doc_content and len(doc_content) > 100:
                            weaviate_content.append(doc_content)

                print(f"📚 Retrieved {len(weaviate_content)} detailed chunks from Weaviate")
            except Exception as weaviate_error:
                print(f"⚠️ Could not fetch from Weaviate: {weaviate_error}")
        
        # Collect tender data for LLM
        tender_data = {
            'one_pager': analysis.one_pager_json or {},
            'scope_of_work': analysis.scope_of_work_json or {},
            'data_sheet': analysis.data_sheet_json or {},
            'rfp_sections': [],
            'weaviate_detailed_content': weaviate_content[:10]
        }
        
        if hasattr(analysis, 'rfp_sections') and analysis.rfp_sections:
            for section in analysis.rfp_sections:
                tender_data['rfp_sections'].append({
                    'section_number': section.section_number,
                    'section_title': section.section_title,
                    'summary': section.summary,
                    'key_requirements': section.key_requirements
                })
        
        # Prepare LLM
        llm = get_langchain_llm()

        # Build detailed prompt
        prompt = f"""Extract QUALIFICATION/ELIGIBILITY CRITERIA from tender data.

QUALIFICATION CRITERIA DEFINITION:
Requirements that bidders must meet to be ELIGIBLE to participate in the tender.

DATA STRUCTURE:
{json.dumps(tender_data, indent=2, default=str)[:25000]}

Return valid JSON array only.
"""

        # Call LLM
        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)

        # Extract JSON fenced blocks
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()

        # If still not a JSON array, try regex extraction (✔ Option A)
        if not response_text.startswith('['):
            import re
            match = re.search(r'\[[\s\S]*\]', response_text)
            if match:
                response_text = match.group(0)

        # JSON-repair helper (✔ Option A)
        def fix_json_string(text):
            """Fix common JSON formatting issues."""
            fixed = []
            in_string = False
            escape_next = False

            for char in text:
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
                    continue

                if char == '\n' and in_string:
                    fixed.append('\\n')
                    continue
 
                if char == '\t' and in_string:
                    fixed.append('\\t')
                    continue

                fixed.append(char)

            return ''.join(fixed)

        # Parse JSON
        try:
            qualification_criteria = json.loads(response_text)
        except json.JSONDecodeError:
            print("⚠️ JSON decode error — attempting to fix")
            try:
                fixed_text = fix_json_string(response_text)
                qualification_criteria = json.loads(fixed_text)
                print("✅ Fixed JSON successfully")
            except Exception:
                print("❌ Could not fix JSON, returning empty criteria")
                qualification_criteria = []

        # Deduplicate & normalize
        seen = {}
        cleaned = []

        for item in qualification_criteria:
            desc = item.get("description", "").strip()
            req = item.get("requirement", "").strip()
            val = item.get("extractedValue", "").strip()

            key = desc.lower()[:40]

            if key in seen:
                if len(req) > len(seen[key]["requirement"]):
                    seen[key] = {"description": desc, "requirement": req, "extractedValue": val}
            else:
                seen[key] = {"description": desc, "requirement": req, "extractedValue": val}

        cleaned = list(seen.values())

        # Save to DB
        from sqlalchemy import text
        import json as json_lib

        bid_synopsis_data = {
            "qualification_criteria": cleaned,
            "generated_at": str(analysis.analysis_completed_at or analysis.updated_at),
            "source": "llm_extraction",
        }

        db.execute(
            text("UPDATE tender_analysis SET bid_synopsis_json = :data WHERE id = :id"),
            {"data": json_lib.dumps(bid_synopsis_data), "id": str(analysis.id)},
        )
        db.commit()

        print(f"✅ Saved {len(cleaned)} qualification criteria")
        return bid_synopsis_data

    except Exception as e:
        print(f"❌ Error generating bid synopsis: {e}")
        import traceback
        traceback.print_exc()
        return {"qualification_criteria": [], "error": str(e)}


def get_bid_synopsis_from_db(analysis: TenderAnalysis) -> list[dict]:
    """
    Retrieve pre-generated bid synopsis from database.
    """
    if analysis.bid_synopsis_json and "qualification_criteria" in analysis.bid_synopsis_json:
        criteria = analysis.bid_synopsis_json["qualification_criteria"]

        formatted = []
        for i, item in enumerate(criteria):
            req = item.get("requirement", "")
            formatted.append({
                "description": item.get("description", ""),
                "requirement": req,
                "extractedValue": item.get("extractedValue", ""),
                "context": req[:200] + "..." if len(req) > 200 else req,
                "source": "db_stored",
                "priority": 100 - i,
            })

        return formatted

    return []
