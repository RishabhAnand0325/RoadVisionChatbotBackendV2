"""
Service to handle document parsing and vectorization for a tender analysis.
"""
import os
from uuid import UUID
from sqlalchemy.orm import Session
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository
from app.modules.tenderiq.db.tenderiq_repository import TenderIQRepository
from app.modules.askai.db.repository import ChatRepository
from app.modules.askai.services.document_service import PDFProcessor
from app.db.vector_store import VectorStoreManager

class DocumentParsingService:
    """Orchestrates document parsing, text extraction, and vectorization."""

    def __init__(self, db: Session):
        self.db = db
        self.analyze_repo = AnalyzeRepository(self.db)
        self.tender_repo = TenderIQRepository(self.db)
        self.chat_repo = ChatRepository(self.db)
        self.pdf_processor = PDFProcessor()
        self.vector_store = VectorStoreManager()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

    async def parse_documents_for_analysis(self, analysis_id: UUID) -> str:
        """
        Parses all documents associated with a tender, adds them to the vector store,
        and links them to the analysis via an AskAI chat session.
        """
        analysis = self.analyze_repo.get_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis with ID {analysis_id} not found.")

        tender = self.tender_repo.get_tender_by_id(analysis.tender_id)
        if not tender or not tender.files:
            raise ValueError(f"Tender {analysis.tender_id} or its documents not found.")

        # 1. Create a corresponding Chat in AskAI to host the documents
        chat = self.chat_repo.create(
            user_id=analysis.user_id,
            title=f"Analysis for Tender: {tender.tender_name[:50]}..."
        )
        self.analyze_repo.update(analysis, {"chat_id": chat.id})

        # 2. Process each file
        for document_file in tender.files:
            file_path = document_file.dms_path
            if not os.path.exists(file_path):
                # TODO: Handle file not found more gracefully
                continue

            # This would be a good place to publish "parsing file X" events
            
            text = self.pdf_processor.clean_text(file_path) # Simplified text extraction
            chunks = self.text_splitter.split_text(text)
            
            # Add chunks to the vector store for the created chat
            self.vector_store.add_texts(collection_name=str(chat.id), texts=chunks)

        return str(chat.id)
