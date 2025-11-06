import os
import requests
import tempfile
import uuid

from app.modules.scraper.data_models import TenderDetailPage
from app.core.services import vector_store, pdf_processor, weaviate_client, excel_processor


def start_tender_processing(tender: TenderDetailPage):
    """
    1. This function will download every file in the tender detail page, process them and save them in the
    vector database
    2. It will then perform some additional LLM magic on them and add them to the tender_analysis table
    """
    tender_id = tender.notice.tender_id
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

    print(f"--- Finished processing for Tender ID: {tender_id} ---")

    # 5. LLM magic (to be implemented later)
