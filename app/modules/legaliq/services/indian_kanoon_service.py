# app/modules/legaliq/services/indian_kanoon_service.py
import httpx
import logging
import re
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)

def clean_html(raw_html):
  """Remove HTML tags from a string."""
  cleanr = re.compile('<.*?>')
  cleantext = re.sub(cleanr, '', raw_html)
  return cleantext

def extract_date_from_title(title):
    """Extracts date from title string and returns a clean title and a date string."""
    # Regex for formats like "on 18 April, 2013"
    match = re.search(r'on (\d{1,2} \w+, \d{4})', title, re.IGNORECASE)
    if match:
        try:
            date_str = match.group(1)
            date_obj = datetime.strptime(date_str, '%d %B, %Y')
            # Remove the matched part from the title for a cleaner look
            clean_title = title.replace(match.group(0), '').strip()
            return clean_title, date_obj.strftime('%Y-%m-%d')
        except ValueError:
            # Date format was not as expected
            return title, None
    return title, None

class IndianKanoonService:
    def __init__(self):
        self.api_key = settings.LEGAL_CASE_API_KEY.strip() if settings.LEGAL_CASE_API_KEY else None
        self.base_url = "https://api.indiankanoon.org"
        if self.api_key:
            self.headers = {
                "Authorization": f"Token {self.api_key}"
            }
        else:
            self.headers = {}

    async def search_cases(self, query: str, page: int = 0):
        """
        Search for legal cases using the Indian Kanoon API.
        """
        if not self.api_key:
            logger.error("Indian Kanoon API key is not configured.")
            return {"error": "Indian Kanoon API key is not configured."}

        search_url = f"{self.base_url}/search/"
        params = {
            "formInput": query,
            "pagenum": page
        }
        logger.info(f"Searching Indian Kanoon with query: '{query}'")

        # Set a longer timeout (e.g., 20 seconds) to prevent ReadTimeout errors
        timeout = httpx.Timeout(20.0, connect=5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                # Reverting to POST as GET is explicitly not allowed (405 error).
                # The API is unconventional, requiring POST with URL parameters.
                response = await client.post(search_url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Received response from Indian Kanoon API: {data}")

                # Clean the data before returning
                if "docs" in data:
                    for doc in data["docs"]:
                        title = doc.get("title", "")
                        
                        # 1. Clean HTML from title
                        clean_title_html = clean_html(title)
                        
                        # 2. Extract date from the cleaned title
                        final_title, extracted_date = extract_date_from_title(clean_title_html)
                        
                        doc["title"] = final_title
                        doc["date"] = extracted_date

                return data

            except httpx.ReadTimeout:
                logger.error("Request to Indian Kanoon API timed out.")
                return {"error": "The legal research service took too long to respond. Please try again."}
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error from Indian Kanoon API: {e.response.status_code} - {e.response.text}")
                if e.response.status_code == 403:
                    return {"error": "Authentication failed. Please check your Indian Kanoon API key."}
                if e.response.status_code == 405:
                    return {"error": "Method Not Allowed. The API endpoint requires a different HTTP method."}
                return {"error": f"Error from API: {e.response.status_code} - {e.response.text}"}
            except Exception as e:
                logger.error(f"An unexpected error occurred while calling Indian Kanoon API: {str(e)}", exc_info=True)
                return {"error": f"An unexpected error occurred: {str(e)}"}

indian_kanoon_service = IndianKanoonService()
