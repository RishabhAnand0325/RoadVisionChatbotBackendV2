# app/modules/legaliq/services/legal_bot_service.py
import os
import shutil
import google.generativeai as genai
import PyPDF2
from fastapi import UploadFile
from typing import List
import warnings

# Suppress warnings for cleaner console output
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="PyPDF2")

class LegalChatbotService:
    def __init__(self):
        # Load API Key from environment variable for security
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Temp storage for session documents
        self.upload_dir = "./temp_legal_docs"
        os.makedirs(self.upload_dir, exist_ok=True)
        self.case_context = ""
        # Simple in-memory store of per-page snippets for reference display
        # Each entry: {"content": str, "page": int, "source": str}
        self.page_sources = []

    async def process_uploads(self, files: List[UploadFile]):
        """Saves uploaded files and extracts text immediately."""
        combined_text = ""
        
        for file in files:
            file_path = os.path.join(self.upload_dir, file.filename)
            
            # Save file to disk
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Extract Text and populate per-page sources
            try:
                reader = PyPDF2.PdfReader(file_path)
                text = ""
                for idx, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
                    # Keep a short snippet per page for references
                    snippet = page_text.strip().replace("\n", " ")
                    if snippet:
                        self.page_sources.append(
                            {
                                "content": snippet[:300],
                                "page": idx + 1,
                                "source": file.filename,
                            }
                        )
                combined_text += f"\n--- START OF FILE: {file.filename} ---\n{text}\n--- END OF FILE ---\n"
            except Exception as e:
                print(f"Error reading {file.filename}: {e}")

        # In a real app, you'd save this context to a DB or Redis keyed by session_id
        # For now, we store it in memory for simplicity
        self.case_context += combined_text
        return {"message": f"Processed {len(files)} files successfully.", "context_length": len(combined_text)}

    async def ask_question(self, query: str, history: List[dict]):
        if not self.case_context:
            return {
                "response": "No documents uploaded. Please upload a legal brief or judgment first.",
                "sources": [],
            }

        system_instruction = """
        You are a Senior Legal Research Assistant. 
        Answer based strictly on the provided documents. 
        Cite specific sections where possible.
        """
        
        # Format history for context
        history_text = "\n".join([f"User: {h['user']}\nAI: {h['ai']}" for h in history[-3:]])

        full_prompt = f"""
        {system_instruction}
        
        === DOCUMENTS ===
        {self.case_context[:100000]} 
        
        === HISTORY ===
        {history_text}
        
        User Query: {query}
        """
        
        try:
            response = self.model.generate_content(full_prompt)
            answer_text = response.text

            # Naive relevance scoring: count keyword overlaps between query and each page snippet
            sources = self._get_relevant_sources(query)

            return {
                "response": answer_text,
                "sources": sources,
            }
        except Exception as e:
            return {
                "response": f"Error: {str(e)}",
                "sources": [],
            }

    def _get_relevant_sources(self, query: str, max_results: int = 3):
        """Return a small list of page snippets that are most relevant to the query.

        This is a lightweight heuristic based on keyword overlap, not full semantic search.
        """
        if not self.page_sources:
            return []

        query_words = {
            w.lower()
            for w in query.split()
            if len(w) > 3
        }
        if not query_words:
            return []

        scored = []
        for src in self.page_sources:
            content_lower = src["content"].lower()
            score = sum(1 for w in query_words if w in content_lower)
            if score > 0:
                scored.append((score, src))

        # Sort by descending score and take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:max_results]]

    async def analyze_document(self, file: UploadFile):
        """Analyze a legal document and return structured analysis results."""
        import json
        
        # Check if model is initialized
        if not self.api_key or not hasattr(self, 'model') or self.model is None:
            return {
                "error": "Google API key not configured. Please set GOOGLE_API_KEY environment variable."
            }
        
        # Save and extract text from the file
        file_path = os.path.join(self.upload_dir, file.filename)
        
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            return {
                "error": f"Error saving file: {str(e)}"
            }
        
        # Extract text
        document_text = ""
        try:
            reader = PyPDF2.PdfReader(file_path)
            for page in reader.pages:
                document_text += page.extract_text() or ""
                document_text += "\n"
        except Exception as e:
            return {
                "error": f"Error reading PDF: {str(e)}"
            }
        
        if not document_text.strip():
            return {
                "error": "No text could be extracted from the document."
            }
        
        # Create analysis prompt
        analysis_prompt = f"""
You are a Senior Legal Document Analyst. Analyze the following legal document and provide a comprehensive structured analysis.

=== DOCUMENT ===
{document_text[:50000]}

Please analyze this document and provide a JSON response with the following structure:
{{
    "riskLevel": "low" | "medium" | "high",
    "riskMessage": "Brief summary of risk assessment",
    "extractedFacts": {{
        "parties": "Names of parties involved (e.g., 'ABC Ltd. vs. XYZ Corp.')",
        "issueSummary": "Brief summary of the legal issue or dispute",
        "contractDate": "Date mentioned in the document (format: 'Month Day, Year' or 'Not specified')",
        "keyClauses": ["Clause 1.1 - Description", "Clause 2.3 - Description", ...]
    }},
    "aiSummary": "A comprehensive 2-3 paragraph summary of the document, including key legal points, risks, and implications",
    "riskAnalysis": [
        {{
            "level": "high" | "medium" | "low",
            "title": "Risk title",
            "description": "Detailed description of the risk"
        }},
        ...
    ],
    "nextSteps": [
        "Action item 1",
        "Action item 2",
        ...
    ]
}}

Focus on:
- Identifying parties and their roles
- Extracting key dates and deadlines
- Identifying important clauses and their implications
- Assessing legal risks (financial, compliance, procedural)
- Providing actionable next steps

Return ONLY valid JSON, no additional text.
"""
        
        try:
            response = self.model.generate_content(analysis_prompt)
            response_text = response.text.strip()
            
            # Clean up response (remove markdown code blocks if present)
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Parse JSON response
            analysis_result = json.loads(response_text)
            
            # Validate and set defaults
            if "riskLevel" not in analysis_result:
                analysis_result["riskLevel"] = "medium"
            if "riskMessage" not in analysis_result:
                analysis_result["riskMessage"] = "Document analysis completed"
            if "extractedFacts" not in analysis_result:
                analysis_result["extractedFacts"] = {
                    "parties": "Not specified",
                    "issueSummary": "Not specified",
                    "contractDate": "Not specified",
                    "keyClauses": []
                }
            if "aiSummary" not in analysis_result:
                analysis_result["aiSummary"] = "Analysis completed. Please review the document details."
            if "riskAnalysis" not in analysis_result:
                analysis_result["riskAnalysis"] = []
            if "nextSteps" not in analysis_result:
                analysis_result["nextSteps"] = []
            
            return analysis_result
            
        except json.JSONDecodeError as e:
            # If JSON parsing fails, return a basic structure with the raw response
            return {
                "riskLevel": "medium",
                "riskMessage": "Analysis completed with limited structure",
                "extractedFacts": {
                    "parties": "Not specified",
                    "issueSummary": "Not specified",
                    "contractDate": "Not specified",
                    "keyClauses": []
                },
                "aiSummary": response_text if 'response_text' in locals() else "Error parsing analysis response.",
                "riskAnalysis": [
                    {
                        "level": "medium",
                        "title": "Analysis Note",
                        "description": "The document was analyzed but the response format was unexpected."
                    }
                ],
                "nextSteps": [
                    "Review the AI summary for key information",
                    "Manually review the original document",
                    "Consult with legal counsel if needed"
                ]
            }
        except Exception as e:
            return {
                "error": f"Error during analysis: {str(e)}"
            }

    def generate_analysis_report(self, analysis_data: dict):
        """Generate a PDF report from the analysis results."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
            import io
            from datetime import datetime
        except ImportError:
            raise Exception("reportlab library is required for PDF generation. Install it with: pip install reportlab")
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch
        )
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles - all black text
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.black,
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.black,
            spaceAfter=16,
            spaceBefore=24,
            fontName='Helvetica-Bold'
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=10,
            spaceBefore=14,
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            spaceAfter=8,
            leading=14,
            alignment=TA_JUSTIFY,
            textColor=colors.black
        )
        
        # Table cell styles for proper text wrapping
        table_label_style = ParagraphStyle(
            'TableLabel',
            parent=body_style,
            fontSize=10,
            fontName='Helvetica-Bold',
            textColor=colors.black
        )
        
        table_value_style = ParagraphStyle(
            'TableValue',
            parent=body_style,
            fontSize=10,
            textColor=colors.black,
            alignment=TA_LEFT
        )
        
        # Cover Page
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph("LEGAL DOCUMENT ANALYSIS REPORT", title_style))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(f"Analysis Date: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(f"Risk Level: {analysis_data.get('riskLevel', 'N/A').upper()}", styles['Normal']))
        story.append(PageBreak())  # Only break after cover page
        
        # Risk Assessment
        story.append(Paragraph("1. RISK ASSESSMENT", heading_style))
        risk_level = analysis_data.get('riskLevel', 'medium')
        
        risk_badge_style = ParagraphStyle(
            'RiskBadge',
            parent=body_style,
            fontSize=14,
            textColor=colors.black,
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph(f"Risk Level: {risk_level.upper()}", risk_badge_style))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(analysis_data.get('riskMessage', 'No risk message provided.'), body_style))
        story.append(Spacer(1, 0.3*inch))  # Use spacer instead of page break
        
        # Extracted Facts
        story.append(Paragraph("2. EXTRACTED CASE FACTS", heading_style))
        facts = analysis_data.get('extractedFacts', {})
        
        # Use Paragraph objects in table cells for proper text wrapping
        facts_data = [
            [Paragraph('Parties', table_label_style), Paragraph(facts.get('parties', 'Not specified'), table_value_style)],
            [Paragraph('Issue Summary', table_label_style), Paragraph(facts.get('issueSummary', 'Not specified'), table_value_style)],
            [Paragraph('Contract Date', table_label_style), Paragraph(facts.get('contractDate', 'Not specified'), table_value_style)],
        ]
        
        table = Table(facts_data, colWidths=[2*inch, 4.5*inch], repeatRows=0)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.2*inch))
        
        # Key Clauses
        key_clauses = facts.get('keyClauses', [])
        if key_clauses:
            story.append(Paragraph("<b>Key Clauses Identified:</b>", subheading_style))
            for clause in key_clauses:
                story.append(Paragraph(f"• {clause}", body_style))
            story.append(Spacer(1, 0.3*inch))  # Use spacer instead of page break
        
        # AI Summary
        story.append(Paragraph("3. AI-GENERATED SUMMARY", heading_style))
        summary = analysis_data.get('aiSummary', 'No summary available.')
        story.append(Paragraph(summary, body_style))
        story.append(Spacer(1, 0.3*inch))  # Use spacer instead of page break
        
        # Risk Analysis Details
        story.append(Paragraph("4. DETAILED RISK ANALYSIS", heading_style))
        risk_analysis = analysis_data.get('riskAnalysis', [])
        
        for risk in risk_analysis:
            risk_title_style = ParagraphStyle(
                'RiskTitle',
                parent=subheading_style,
                textColor=colors.black
            )
            
            story.append(Paragraph(f"<b>{risk.get('title', 'Untitled Risk')}</b>", risk_title_style))
            story.append(Paragraph(risk.get('description', 'No description provided.'), body_style))
            story.append(Spacer(1, 0.15*inch))
        
        story.append(Spacer(1, 0.3*inch))  # Use spacer instead of page break
        
        # Next Steps
        story.append(Paragraph("5. SUGGESTED NEXT STEPS", heading_style))
        next_steps = analysis_data.get('nextSteps', [])
        
        for idx, step in enumerate(next_steps, 1):
            story.append(Paragraph(f"{idx}. {step}", body_style))
            story.append(Spacer(1, 0.1*inch))
        
        # Build PDF
        doc.build(story)
        
        filename = f"Legal_Analysis_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return buffer.getvalue(), filename

# Singleton instance for simple state management
legal_service = LegalChatbotService()