import os
import requests
import tempfile
import traceback
import uuid

from app.modules.askai.models.document import ProcessingStage, ProcessingStatus, UploadJob
from app.modules.scraper.data_models import TenderDetailPage
from app.core.services import vector_store, pdf_processor, weaviate_client, excel_processor, llm_model
from app.core.global_stores import upload_jobs
from app.db.database import SessionLocal
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.tenderiq.db.repository import TenderRepository
from app.modules.tenderiq.models.pydantic_models import ReviewStatusEnum
from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository
from app.modules.analyze.db.schema import AnalysisStatusEnum
from app.modules.analyze.models.pydantic_models import OnePagerSchema


def start_tender_processing(tender: TenderDetailPage):
    """
    1. This function will download every file in the tender detail page, process them and save them in the
    vector database
    2. It will then perform some additional LLM magic on them and add them to the tender_analysis table
    """
    tender_id = tender.notice.tdr # DO NOT CHANGE THIS LINE
    if not tender_id:
        print("❌ Tender ID not found, cannot process.")
        return
    
    if not vector_store:
        print("❌ Vector store is not initialized, cannot process.")
        return

    print(f"\n--- Starting processing for Tender ID: {tender_id} ---")

    # 1. Download files to temporary storage
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Created temporary directory: {temp_dir}")
        all_tender_chunks = []

        for file_info in tender.other_detail.files:
            try:
                # a. Download the file
                print(f"  ⬇️  Downloading: {file_info.file_name} from {file_info.file_url}")
                response = requests.get(file_info.file_url, timeout=60)
                response.raise_for_status()

                # b. Save to temporary path
                temp_file_path = os.path.join(temp_dir, file_info.file_name)
                with open(temp_file_path, 'wb') as f:
                    f.write(response.content)
                print(f"  💾 Saved temporarily to: {temp_file_path}")

                # 2. Text extraction & 3. Chunking
                # The process_pdf method handles both extraction and chunking.
                doc_id = str(uuid.uuid4())
                job_id = str(uuid.uuid4()) # For progress tracking within the processor

                upload_jobs[job_id] = UploadJob(
                    job_id = job_id,
                    status=ProcessingStatus.QUEUED,
                    chat_id=str(tender_id),
                    filename=file_info.file_name or "unknown-file.pdf",
                    progress=0,
                    stage=ProcessingStage.NOT_PROCESSING,
                    finished_at="",
                    chunks_added=0,
                    error=None
                )

                # NOTE: Assuming all files are PDFs for now.
                if file_info.file_name.lower().endswith('.pdf'):
                    chunks, stats = pdf_processor.process_pdf(
                        job_id=job_id,
                        pdf_path=temp_file_path,
                        doc_id=doc_id,
                        filename=file_info.file_name
                    )
                    all_tender_chunks.extend(chunks)
                    print(f"  ✅ Processed {file_info.file_name}: created {stats['total_chunks']} chunks.")
                else:
                    print(f"  ⚠️  Skipping non-PDF file: {file_info.file_name}")

            except requests.RequestException as e:
                print(f"  ❌ Failed to download {file_info.file_name}: {e}")
            except Exception as e:
                print(f"  ❌ Failed to process {file_info.file_name}: {e}")

        if not all_tender_chunks:
            print("No chunks were generated. Aborting vector store operation.")
            return

        # 4. Vectorization and saving to the vector database
        try:
            # c. create a new collection for the tender
            print(f"\n📦 Accessing Weaviate collection for tender_id: {tender_id}")
            tender_collection = vector_store.create_tender_collection(tender_id)

            # d. save to the vector database
            print(f"  ⚡ Vectorizing and adding {len(all_tender_chunks)} chunks to Weaviate...")
            chunks_added = vector_store.add_tender_chunks(tender_collection, all_tender_chunks)
            print(f"  ✅ Successfully added {chunks_added} chunks to collection '{tender_collection.name}'.")

        except Exception as e:
            print(f"❌ Failed during Weaviate operation for tender {tender_id}: {e}")

    print(f"--- Finished vector processing for Tender ID: {tender_id} ---")

    # 5. LLM magic for analysis
    print(f"\n--- Starting LLM analysis for Tender ID: {tender_id} ---")
    db = SessionLocal()
    scraped_tender_orm = None
    main_tender_orm = None
    try:
        # Get DB records to update their status
        scraped_tender_orm = db.query(ScrapedTender).filter(ScrapedTender.tdr == tender_id).first()
        if not scraped_tender_orm:
            print(f"⚠️  ScrapedTender ORM object not found for TDR {tender_id}. Cannot update analysis status.")
        else:
            tender_repo = TenderRepository(db)
            main_tender_orm = tender_repo.get_or_create_by_id(scraped_tender_orm)
            if not main_tender_orm:
                print(f"⚠️  Tender ORM object not found/created for TDR {tender_id}. Cannot update tender status.")
        
        # Define a helper for LLM extraction
        def _extract_from_tender(question: str) -> str:
            """Queries Weaviate for context and asks the LLM a question."""
            print(f"  ❓ Querying tender '{tender_id}' with: '{question}'")
            context_chunks = vector_store.query_tender(tender_id, question, n_results=5)
            
            if not context_chunks:
                print("  ⚠️ No context found in vector store.")
                return "Not found in documents."

            context_text = "\n\n".join([chunk[0] for chunk in context_chunks])

            prompt = f"""Based on the following context from tender documents, answer the user's question.
If the information is not in the context, say "Not found in documents.". Be concise.

CONTEXT:
---
{context_text}
---

QUESTION: {question}

ANSWER:"""

            try:
                response = llm_model.generate_content(prompt)
                answer = response.text.strip()
                print(f"  🗣️ LLM Response: {answer[:100].replace('\n', ' ')}...")
                return answer
            except Exception as e:
                print(f"  ❌ LLM generation failed: {e}")
                return f"Error during generation: {e}"

        # a. Create a TenderAnalysis record
        analyze_repo = AnalyzeRepository(db)
        analysis = analyze_repo.create_for_tender(tender_id, user_id=None)
        
        analyze_repo.update(analysis, {"status": AnalysisStatusEnum.analyzing, "status_message": "Generating One-Pager..."})

        # c. Extract data for One-Pager
        print("\n📄 Generating One-Pager...")
        one_pager_data = {
            "project_overview": _extract_from_tender("Provide a brief overview of the project described in the tender."),
            "eligibility_highlights": _extract_from_tender("List the key eligibility requirements for bidders as bullet points.").split('\n'),
            "important_dates": _extract_from_tender("List the important dates and deadlines mentioned in the tender.").split('\n'),
            "financial_requirements": _extract_from_tender("Summarize the key financial requirements, like EMD, tender value, and performance security.").split('\n'),
            "risk_analysis": {"summary": _extract_from_tender("Identify potential risks for the project or bidder based on the document.")}
        }
        
        # d. Validate with Pydantic model and save
        one_pager = OnePagerSchema(**one_pager_data)
        analyze_repo.update(analysis, {"one_pager_json": one_pager.model_dump()})
        print("  ✅ One-Pager generated and saved.")

        # TODO: Repeat for ScopeOfWorkSchema and DataSheetSchema here

        # e. Finalize analysis
        analyze_repo.update(analysis, {"status": AnalysisStatusEnum.completed, "status_message": "Analysis complete."})

        if scraped_tender_orm:
            scraped_tender_orm.analysis_status = "completed"
            scraped_tender_orm.error_message = None
        if main_tender_orm:
            main_tender_orm.review_status = ReviewStatusEnum.Reviewed
        db.commit()

        print(f"--- ✅ LLM Analysis for Tender ID: {tender_id} complete ---")

    except Exception as e:
        print(f"❌ An error occurred during LLM analysis for tender {tender_id}: {e}")
        traceback.print_exc()
        if 'analysis' in locals() and analysis and 'analyze_repo' in locals():
            analyze_repo.update(analysis, {"status": AnalysisStatusEnum.failed, "error_message": str(e)})
        
        if scraped_tender_orm:
            scraped_tender_orm.analysis_status = "failed"
            scraped_tender_orm.error_message = str(e)
            db.commit()
    finally:
        db.close()
