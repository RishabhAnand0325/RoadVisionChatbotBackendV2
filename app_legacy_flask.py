import re
from typing import List, Dict, Any, Tuple, Optional
import os
import warnings
import json
import uuid
import traceback
import threading
import tempfile
import time
import stat
import hashlib
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import tiktoken
from llama_parse import LlamaParse
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

# --- STABILITY FIXES ---
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GRPC_CPP_VERBOSITY"] = "NONE"
os.environ["GLOG_minloglevel"] = "3"
warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
class Config:
    CHROMA_PATH = Path("./chroma_db").resolve()
    MAX_CHUNKS_PER_DOCUMENT = 2000
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    MAX_PDFS_PER_CHAT = 5
    MAX_EXCEL_PER_CHAT = 2
    RAG_TOP_K = 15
    MAX_PDF_SIZE_MB = 50
    MAX_EXCEL_SIZE_MB = 10

config = Config()

# --- UTILITIES ---

def get_consistent_timestamp():
    """Return ISO format timestamp"""
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def ensure_directory_exists(path):
    """Ensure directory exists with proper permissions"""
    Path(path).mkdir(parents=True, exist_ok=True)

def get_file_hash(file_path: str) -> str:
    """Generate unique hash for file"""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

# --- ENVIRONMENT LOADING ---

def load_environment():
    """Load and validate environment variables"""
    print("🔍 Loading environment variables...")
    
    env_paths = [Path('.env'), Path(__file__).parent / '.env']
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, verbose=True)
            break
    else:
        load_dotenv()

    google_api_key = os.getenv("GOOGLE_API_KEY")
    llama_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    
    if not google_api_key:
        raise Exception("❌ GOOGLE_API_KEY not found in environment!")
    
    print(f"✅ GOOGLE_API_KEY: configured")
    print(f"✅ LLAMA_CLOUD_API_KEY: {'configured' if llama_api_key else 'not configured (optional)'}")
    
    return True

load_environment()

# --- INITIALIZATION ---

ensure_directory_exists(config.CHROMA_PATH)

try:
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    print("✅ Gemini 2.0 Flash configured")

    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    print("✅ SentenceTransformer loaded")
    
    chroma_client = chromadb.PersistentClient(
        path=str(config.CHROMA_PATH),
        settings=Settings(anonymized_telemetry=False, allow_reset=True)
    )
    print(f"✅ ChromaDB initialized at {config.CHROMA_PATH}")
    
    tokenizer = tiktoken.get_encoding("cl100k_base")

except ImportError as e:
    print(f"❌ Missing package: {e}")
    exit(1)

# --- GLOBAL STATE ---
app = Flask(__name__)
CORS(app)

active_conversations = {}
chat_history = []
document_collections = {}
upload_jobs = {}

# --- DOCUMENT STORE ---
class DocumentStore:
    """Manages document metadata"""
    
    def __init__(self):
        self.documents = {}
        self.chat_documents = defaultdict(list)
    
    def add_document(self, chat_id: str, doc_metadata: Dict) -> str:
        """Add document and return doc_id"""
        doc_id = str(uuid.uuid4())
        doc_metadata['doc_id'] = doc_id
        doc_metadata['chat_id'] = chat_id
        doc_metadata['added_at'] = get_consistent_timestamp()
        
        self.documents[doc_id] = doc_metadata
        self.chat_documents[chat_id].append(doc_id)
        
        return doc_id
    
    def get_chat_documents(self, chat_id: str) -> List[Dict]:
        """Get all documents for a chat"""
        doc_ids = self.chat_documents.get(chat_id, [])
        return [self.documents[doc_id] for doc_id in doc_ids if doc_id in self.documents]
    
    def remove_document(self, chat_id: str, doc_id: str):
        """Remove document from tracking"""
        if doc_id in self.documents:
            del self.documents[doc_id]
        
        if chat_id in self.chat_documents:
            self.chat_documents[chat_id] = [
                d for d in self.chat_documents[chat_id] if d != doc_id
            ]

document_store = DocumentStore()

# --- PDF PROCESSOR ---

class PDFProcessor:
    """Enhanced PDF processing with LlamaParse OCR"""
    
    def __init__(self, embedding_model, tokenizer):
        self.embedding_model = embedding_model
        self.tokenizer = tokenizer
        
        llama_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if llama_key:
            self.llama_parser = LlamaParse(
                api_key=llama_key,
                result_type="markdown",
                parsing_instruction="Extract all text, tables, and structure.",
                num_workers=2,
                verbose=False,
                max_timeout=600,
            )
            self.has_llamaparse = True
            print("✅ LlamaParse OCR initialized")
        else:
            self.has_llamaparse = False
            print("⚠️  LlamaParse not available")
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\[\]\"\'\/\@\#\$\%\&\*\+\=]', ' ', text)
        return text.strip()
    
    def _clean_metadata(self, metadata: Dict) -> Dict:
        """Clean metadata for ChromaDB compatibility"""
        cleaned = {}
        for k, v in metadata.items():
            str_val = str(v)
            # Remove special characters
            str_val = re.sub(r'[^\w\s\-\.\,\/]', '_', str_val)
            str_val = str_val.strip()
            cleaned[k] = str_val if str_val else "unknown"
        return cleaned
    
    def create_smart_chunks(self, text: str, metadata: Dict) -> List[Dict]:
        """Create overlapping chunks with metadata"""
        words = text.split()
        chunks = []
        
        if len(words) <= config.CHUNK_SIZE:
            return [{
                "content": text,
                "metadata": self._clean_metadata(metadata),
                "word_count": len(words)
            }]
        
        chunk_index = 0
        start = 0
        
        while start < len(words):
            end = min(start + config.CHUNK_SIZE, len(words))
            chunk_words = words[start:end]
            chunk_text = ' '.join(chunk_words)
            
            chunk_meta = metadata.copy()
            chunk_meta["chunk_index"] = chunk_index
            
            chunks.append({
                "content": chunk_text,
                "metadata": self._clean_metadata(chunk_meta),
                "word_count": len(chunk_words)
            })
            
            chunk_index += 1
            start = end - config.CHUNK_OVERLAP
            
            if start >= len(words) - config.CHUNK_OVERLAP:
                break
        
        return chunks
    
    def extract_with_llamaparse(self, pdf_path: str) -> Dict[int, str]:
        """Primary extraction using LlamaParse"""
        if not self.has_llamaparse:
            return {}
        
        try:
            print(f"🔍 LlamaParse processing for {Path(pdf_path).name}...")
            documents = self.llama_parser.load_data(pdf_path)
            
            page_texts = {}
            for doc in documents:
                # Use page_label first, then page, default to 1
                page_num_str = doc.metadata.get('page_label', doc.metadata.get('page', '1'))
                
                try:
                    # Robustly convert page number to integer
                    page_num = int(float(page_num_str))
                except (ValueError, TypeError, AttributeError):
                    # Handle cases where page_label might be a complex string or missing
                    page_num = 1
                
                if page_num not in page_texts:
                    page_texts[page_num] = []
                
                page_texts[page_num].append(doc.text)
            
            result = {p: self.clean_text("\n\n".join(texts)) 
                    for p, texts in page_texts.items()}
            
            print(f"✅ LlamaParse extracted {len(result)} pages.")
            return result
            
        except Exception as e:
            # THIS LOG IS CRUCIAL to see why it failed
            print(f"❌ LlamaParse FATAL error on {Path(pdf_path).name}: {e}")
            traceback.print_exc()
            return {} # Return empty to trigger fallback
    
    def extract_with_pymupdf(self, pdf_path: str) -> Dict[int, str]:
        """Fallback extraction using PyMuPDF"""
        page_texts = {}
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                if text and text.strip():
                    page_texts[page_num + 1] = self.clean_text(text)
            doc.close()
            print(f"✅ PyMuPDF extracted {len(page_texts)} pages")
        except Exception as e:
            print(f"❌ PyMuPDF error: {e}")
        return page_texts
    
    def extract_with_tesseract(self, pdf_path: str) -> Dict[int, str]:
        """Final fallback OCR using Tesseract for purely scanned documents."""
        page_texts = {}
        try:
            print(f"🔎 Tesseract OCR processing...")
            doc = fitz.open(pdf_path)
            for i, page in enumerate(doc):
                # Render page as image (pixmap)
                pix = page.get_pixmap(dpi=200) 
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                # Run Tesseract OCR on the image
                text = pytesseract.image_to_string(img)
                if text and text.strip():
                    page_texts[i + 1] = self.clean_text(text)
            print(f"✅ Tesseract OCR extracted {len(page_texts)} pages.")
        except Exception as e:
            print(f"❌ Tesseract OCR error: {e}")
            traceback.print_exc()
        return page_texts
    
    def extract_tables(self, pdf_path: str) -> List[Dict]:
        """Extract tables using pdfplumber"""
        tables = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_tables = page.extract_tables() or []
                    
                    for table_idx, table in enumerate(page_tables):
                        if len(table) < 2:
                            continue
                        
                        headers = table[0] if table[0] else []
                        table_text = f"Table {table_idx + 1} on page {page_num}:\n"
                        
                        if headers:
                            table_text += "Headers: " + " | ".join(str(h) for h in headers if h) + "\n"
                        
                        for row in table[1:]:
                            if not any(row):
                                continue
                            row_text = " | ".join(str(cell) if cell else "" for cell in row)
                            table_text += row_text + "\n"
                        
                        tables.append({
                            "content": self.clean_text(table_text),
                            "page": page_num,
                            "type": "table",
                            "table_index": table_idx
                        })
            
            print(f"✅ Extracted {len(tables)} tables")
        except Exception as e:
            print(f"⚠️  Table extraction error: {e}")
        
        return tables
    
    def process_pdf(self, pdf_path: str, doc_id: str, filename: str) -> Tuple[List[Dict], Dict]:
        """Main PDF processing pipeline"""
        print(f"\n{'='*60}")
        print(f"📄 Processing PDF: {filename}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        # Try LlamaParse first
        page_texts = self.extract_with_llamaparse(pdf_path)
        
        if not page_texts:
            print("⚠️  LlamaParse failed, attempting PyMuPDF fallback...")
            page_texts = self.extract_with_pymupdf(pdf_path)
            
        # NEW FINAL FALLBACK: Tesseract
        if not page_texts:
            print("⚠️  PyMuPDF also failed, attempting Tesseract OCR fallback...")
            page_texts = self.extract_with_tesseract(pdf_path)
            
        if not page_texts:
            raise Exception("Failed to extract any text from PDF")
        
        # Extract tables
        tables = self.extract_tables(pdf_path)
        
        # Create chunks from text
        all_chunks = []
        for page_num, text in page_texts.items():
            if not text.strip():
                continue
            
            base_metadata = {
                "doc_id": str(doc_id),
                "source": str(filename),
                "page": str(page_num),
                "type": "text",
                "doc_type": "pdf"
            }
            
            chunks = self.create_smart_chunks(text, base_metadata)
            all_chunks.extend(chunks)
        
        # Add table chunks
        for table in tables:
            table_meta = {
                "doc_id": str(doc_id),
                "source": str(filename),
                "page": str(table["page"]),
                "type": "table",
                "doc_type": "pdf",
                "table_index": str(table.get("table_index", 0))
            }
            all_chunks.append({
                "content": table["content"],
                "metadata": self._clean_metadata(table_meta),
                "word_count": len(table["content"].split())
            })
        
        # Limit chunks
        if len(all_chunks) > config.MAX_CHUNKS_PER_DOCUMENT:
            print(f"⚠️  Limiting to {config.MAX_CHUNKS_PER_DOCUMENT} chunks")
            all_chunks = all_chunks[:config.MAX_CHUNKS_PER_DOCUMENT]
        
        stats = {
            "total_chunks": len(all_chunks),
            "pages": len(page_texts),
            "tables": len(tables),
            "processing_time": time.time() - start_time
        }
        
        print(f"✅ Created {stats['total_chunks']} chunks from {stats['pages']} pages")
        print(f"⏱️  Processing time: {stats['processing_time']:.2f}s\n")
        
        return all_chunks, stats

# --- EXCEL PROCESSOR (Dummy for Structure) ---
class ExcelProcessor:
    """Placeholder for Excel processing logic (if required later)"""
    def __init__(self, embedding_model, tokenizer):
        pass
        
    def process_excel(self, excel_path: str, doc_id: str, filename: str) -> Tuple[List[Dict], Dict]:
        """Returns dummy data for now"""
        print(f"⚠️  Excel processing is not yet fully implemented for {filename}. Returning dummy data.")
        time.sleep(1) # Simulate work
        chunks = [{
            "content": f"Dummy chunk for Excel file {filename}",
            "metadata": {"doc_id": doc_id, "source": filename, "doc_type": "excel"},
            "word_count": 10
        }]
        stats = {"total_chunks": 1, "sheets": 1, "processing_time": 1.0}
        return chunks, stats

# --- VECTOR STORE MANAGER ---

class VectorStoreManager:
    """Manages ChromaDB collections"""
    
    def __init__(self, chroma_client, embedding_model):
        self.client = chroma_client
        self.embedding_model = embedding_model
        self.collections = {}
    
    def get_or_create_collection(self, chat_id: str):
        """Get or create collection for chat"""
        if chat_id in self.collections:
            return self.collections[chat_id]
        
        collection_name = f"chat_{chat_id}"
        
        try:
            collection = self.client.get_collection(collection_name)
            print(f"📂 Retrieved collection: {collection_name}")
        except:
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"chat_id": chat_id}
            )
            print(f"📂 Created collection: {collection_name}")
        
        self.collections[chat_id] = collection
        return collection
    
    def add_chunks(self, collection, chunks: List[Dict]) -> int:
        """Add chunks to collection"""
        if not chunks:
            return 0
        
        try:
            documents = [chunk["content"] for chunk in chunks]
            metadatas = []
            
            for chunk in chunks:
                meta = chunk["metadata"].copy()
                # Ensure all values are clean strings
                cleaned_meta = {}
                for k, v in meta.items():
                    str_val = str(v)
                    str_val = re.sub(r'[^\w\s\-\.\,\/]', '_', str_val).strip()
                    cleaned_meta[k] = str_val if str_val else "unknown"
                
                metadatas.append(cleaned_meta)
            
            # Generate safe IDs
            ids = []
            for i, chunk in enumerate(chunks):
                doc_id = chunk['metadata'].get('doc_id', 'unknown')[:8]
                safe_id = f"doc_{doc_id}_chunk_{i}_{uuid.uuid4().hex[:6]}"
                safe_id = re.sub(r'[^\w\-]', '_', safe_id)
                ids.append(safe_id)
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(
                documents,
                show_progress_bar=True,
                batch_size=32
            )
            
            # Add in batches
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                end_idx = min(i + batch_size, len(documents))
                
                collection.add(
                    documents=documents[i:end_idx],
                    metadatas=metadatas[i:end_idx],
                    ids=ids[i:end_idx],
                    embeddings=embeddings[i:end_idx].tolist()
                )
            
            print(f"✅ Added {len(documents)} chunks to {collection.name}")
            return len(documents)
            
        except Exception as e:
            print(f"❌ Error adding chunks: {e}")
            if metadatas:
                print(f"   Sample metadata: {metadatas[0]}")
            if ids:
                print(f"   Sample ID: {ids[0]}")
            traceback.print_exc()
            return 0
    
    def query(self, collection, query: str, n_results: int = 15) -> List[Tuple]:
        """Query collection"""
        try:
            query_embedding = self.embedding_model.encode([query])
            
            results = collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=n_results,
                include=['documents', 'metadatas', 'distances']
            )
            
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            
            results_list = []
            seen_content = set()
            
            for doc, meta, dist in zip(documents, metadatas, distances):
                content_hash = doc[:100]
                if content_hash in seen_content:
                    continue
                seen_content.add(content_hash)
                
                similarity = 1 - (dist / 2)
                results_list.append((doc, meta, similarity))
            
            results_list.sort(key=lambda x: x[2], reverse=True)
            return results_list
            
        except Exception as e:
            print(f"❌ Query error: {e}")
            return []
    
    def delete_collection(self, chat_id: str):
        """Delete collection"""
        try:
            collection_name = f"chat_{chat_id}"
            self.client.delete_collection(collection_name)
            if chat_id in self.collections:
                del self.collections[chat_id]
            print(f"🗑️  Deleted collection: {collection_name}")
        except Exception as e:
            print(f"⚠️  Error deleting collection: {e}")

# Initialize processors
pdf_processor = PDFProcessor(embedding_model, tokenizer)
# Using a dummy Excel processor for now
excel_processor = ExcelProcessor(embedding_model, tokenizer) 
vector_store = VectorStoreManager(chroma_client, embedding_model)

# --- PERSISTENCE ---

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"⚠️  Failed to save {path}: {e}")
        return False

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"⚠️  Failed to load {path}: {e}")
        return {}

def load_chat_history():
    global chat_history
    data = load_json("chat_history.json")
    chat_history[:] = data if isinstance(data, list) else []
    print(f"📁 Loaded {len(chat_history)} chats")

def save_chat_history():
    save_json("chat_history.json", chat_history)

def load_conversation(chat_id):
    data = load_json(f"memory_{chat_id}.json")
    return data if isinstance(data, list) else []

def save_conversation(chat_id, conversation):
    save_json(f"memory_{chat_id}.json", conversation)

# --- API ENDPOINTS ---

@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": get_consistent_timestamp(),
        "llamaparse": "available" if pdf_processor.has_llamaparse else "unavailable"
    })

@app.route("/api/chats", methods=["GET"])
def get_chats():
    """Get all chats"""
    try:
        sorted_chats = sorted(
            chat_history,
            key=lambda c: c.get('updated_at', '1970'),
            reverse=True
        )
        return jsonify(sorted_chats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chats", methods=["POST"])
def create_chat():
    """Create new chat"""
    try:
        chat_id = str(uuid.uuid4())
        
        new_chat = {
            "id": chat_id,
            "title": f"New Chat {len(chat_history) + 1}",
            "created_at": get_consistent_timestamp(),
            "updated_at": get_consistent_timestamp(),
            "message_count": 0,
            "has_pdf": False,
            "pdf_count": 0,
            "pdf_list": []
        }
        
        chat_history.insert(0, new_chat)
        active_conversations[chat_id] = []
        
        save_chat_history()
        save_conversation(chat_id, [])
        
        return jsonify(new_chat), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chats/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    """Get chat messages"""
    try:
        conversation = load_conversation(chat_id)
        messages = []
        
        for msg in conversation:
            if msg["role"] == "user":
                messages.append({
                    "id": str(uuid.uuid4()),
                    "text": msg["parts"][0],
                    "sender": "user",
                    "timestamp": get_consistent_timestamp()
                })
            elif msg["role"] == "model":
                messages.append({
                    "id": str(uuid.uuid4()),
                    "text": msg["parts"][0],
                    "sender": "bot",
                    "timestamp": get_consistent_timestamp()
                })
        
        return jsonify(messages)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chats/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    """Delete chat"""
    try:
        global chat_history
        chat_history = [c for c in chat_history if c["id"] != chat_id]
        
        if chat_id in active_conversations:
            del active_conversations[chat_id]
        
        vector_store.delete_collection(chat_id)
        
        try:
            os.remove(f"memory_{chat_id}.json")
        except FileNotFoundError:
            pass
        
        save_chat_history()
        return jsonify({"message": "Chat deleted successfully"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chats/<chat_id>/rename", methods=["PUT"])
def rename_chat(chat_id):
    """Rename chat"""
    try:
        data = request.get_json()
        new_title = data.get("title", "").strip()
        
        if not new_title:
            return jsonify({"error": "Title cannot be empty"}), 400
        
        for chat in chat_history:
            if chat["id"] == chat_id:
                chat["title"] = new_title
                chat["updated_at"] = get_consistent_timestamp()
                break
        
        save_chat_history()
        return jsonify({"message": "Chat renamed successfully"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chats/<chat_id>/upload-pdf", methods=["POST"])
def upload_pdf(chat_id):
    """Upload PDF - compatible with old frontend"""
    try:
        if "pdf" not in request.files:
            return jsonify({"error": "No PDF file provided"}), 400
        
        pdf_file = request.files["pdf"]
        filename = pdf_file.filename
        
        if not filename.lower().endswith(".pdf"):
            return jsonify({"error": "File must be a PDF"}), 400
        
        # Check chat exists
        chat = next((c for c in chat_history if c["id"] == chat_id), None)
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
        
        # Check limits
        pdf_list = chat.get("pdf_list", [])
        if len(pdf_list) >= config.MAX_PDFS_PER_CHAT:
            return jsonify({"error": f"Maximum {config.MAX_PDFS_PER_CHAT} PDFs per chat"}), 400
        
        # Check duplicate
        for pdf_meta in pdf_list:
            if pdf_meta.get("name") == filename:
                return jsonify({"error": f"PDF '{filename}' already uploaded"}), 400
        
        # Save temp file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        try:
            pdf_file.save(tmp.name)
            tmp.flush()
            os.chmod(tmp.name, stat.S_IRUSR | stat.S_IWUSR)
            temp_path = tmp.name
            
            file_size = os.path.getsize(temp_path)
            if file_size > config.MAX_PDF_SIZE_MB * 1024 * 1024:
                os.unlink(temp_path)
                return jsonify({"error": f"File too large. Max: {config.MAX_PDF_SIZE_MB}MB"}), 400
            
            file_hash = get_file_hash(temp_path)
        finally:
            tmp.close()
        
        # Process async
        job_id = str(uuid.uuid4())
        
        def process_pdf():
            """Background processing"""
            status = upload_jobs.get(job_id, {})
            status.update({
                "status": "processing",
                "started_at": get_consistent_timestamp()
            })
            
            try:
                # Process PDF
                doc_id = str(uuid.uuid4())
                chunks, stats = pdf_processor.process_pdf(temp_path, doc_id, filename)
                
                if not chunks:
                    raise Exception("No content extracted")
                
                # Add to vector store
                collection = vector_store.get_or_create_collection(chat_id)
                added_count = vector_store.add_chunks(collection, chunks)
                
                # Save metadata
                doc_metadata = {
                    "filename": filename,
                    "doc_type": "pdf",
                    "file_hash": file_hash,
                    "file_size": file_size,
                    "chunks_count": added_count,
                    **stats
                }
                document_store.add_document(chat_id, doc_metadata)
                
                # Update chat
                new_pdf_meta = {
                    "name": filename,
                    "upload_time": get_consistent_timestamp(),
                    "chunks_added": added_count,
                    "status": "active"
                }
                
                for chat in chat_history:
                    if chat["id"] == chat_id:
                        if "pdf_list" not in chat:
                            chat["pdf_list"] = []
                        
                        chat["pdf_list"].append(new_pdf_meta)
                        chat["has_pdf"] = True
                        chat["pdf_count"] = len(chat["pdf_list"])
                        chat["updated_at"] = get_consistent_timestamp()
                        break
                
                save_chat_history()
                
                status.update({
                    "status": "done",
                    "finished_at": get_consistent_timestamp(),
                    "chunks_added": added_count
                })
                
                print(f"✅ PDF {filename} processed successfully")
                
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Processing error: {error_msg}")
                traceback.print_exc()
                
                status.update({
                    "status": "error",
                    "error": error_msg,
                    "finished_at": get_consistent_timestamp()
                })
            
            finally:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as e:
                    print(f"⚠️  Cleanup error: {e}")
        
        # Start processing thread
        thread = threading.Thread(target=process_pdf, daemon=True)
        thread.start()
        
        # --- FIX/UPDATE: Store chat_id and filename for tracking ---
        upload_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "started_at": get_consistent_timestamp(),
            "chat_id": chat_id,             # <-- NEW
            "filename": filename            # <-- NEW
        }
        
        return jsonify({
            "message": "Upload accepted",
            "job_id": job_id,
            "processing": True
        }), 202
        
    except Exception as e:
        print(f"❌ Upload error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload-status/<job_id>", methods=["GET"])
def get_upload_status(job_id):
    """Get upload job status"""
    status = upload_jobs.get(job_id)
    if not status:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(status)

# ----------------------------------------------------------------------
## NEW ENDPOINT: /api/chats/<chat_id>/docs
# ----------------------------------------------------------------------

@app.route("/api/chats/<chat_id>/docs", methods=["GET"])
def get_chat_docs(chat_id):
    """
    Get all document information (completed and processing) for a chat,
    categorized by type, matching the requested specification.
    """
    try:
        # 1. Get completed documents from DocumentStore
        completed_docs = document_store.get_chat_documents(chat_id)
        
        # Initialize response lists
        pdfs = []
        excel = []
        
        # 2. Separate completed documents by type
        for doc in completed_docs:
            doc_info = {
                "name": doc.get("filename", "Unknown Document"),
                "chunks": doc.get("chunks_count", 0),
                "status": "active" 
            }
            if doc.get("doc_type") == "pdf":
                pdfs.append(doc_info)
            # Assuming Excel is tracked by "doc_type": "excel"
            elif doc.get("doc_type") == "excel":
                excel.append(doc_info)

        # 3. Get currently processing jobs from global upload_jobs
        processing_jobs = []
        for job_id, job_status in upload_jobs.items():
            # Filter for jobs belonging to this chat and are currently active
            if job_status.get("chat_id") == chat_id and job_status.get("status") in ["queued", "processing"]:
                
                filename = job_status.get("filename", "Unknown File")
                
                processing_jobs.append({
                    "name": filename,
                    "job_id": job_id,
                    "status": job_status.get("status")
                })

        # 4. Construct final response
        response = {
            "pdfs": pdfs,
            "xlsx": excel, 
            "processing": processing_jobs,
            "total_docs": len(pdfs) + len(excel) + len(processing_jobs), # Total includes active and processing
            "chat_id": chat_id
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Error getting chat documents for {chat_id}: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ----------------------------------------------------------------------
## END NEW ENDPOINT
# ----------------------------------------------------------------------

@app.route("/api/chats/<chat_id>/pdfs", methods=["GET"])
def get_chat_pdfs(chat_id):
    """Get PDF information for chat (Kept for compatibility)"""
    print(f"🔍 DEBUG: get_chat_pdfs called for chat_id={chat_id}")
    
    try:
        chat = next((c for c in chat_history if c["id"] == chat_id), None)
        
        if not chat:
            print(f"❌ DEBUG: Chat {chat_id} not found")
            return jsonify({"error": "Chat not found"}), 404
        
        print(f"✅ DEBUG: Chat found: {chat.get('title')}")
        
        pdf_list_metadata = chat.get("pdf_list", [])
        print(f"📄 DEBUG: pdf_list has {len(pdf_list_metadata)} items")
        
        if not pdf_list_metadata:
            return jsonify({"pdfs": [], "total_pdfs": 0, "chat_id": chat_id})
        
        collection = vector_store.collections.get(chat_id)
        collection_status = "inactive"
        
        if collection:
            try:
                collection.count()
                collection_status = "active"
            except:
                collection_status = "error"
        
        # Build response
        current_pdfs_info = []
        for pdf_meta in pdf_list_metadata:
            pdf_name = pdf_meta.get("name", "Unknown Document")
            chunks_added = pdf_meta.get("chunks_added", 0)
            pdf_status = pdf_meta.get("status", collection_status)
            
            current_pdfs_info.append({
                "name": pdf_name,
                "chunks": chunks_added,
                "status": pdf_status
            })
        
        print(f"✅ DEBUG: Returning {len(current_pdfs_info)} PDFs")
        
        return jsonify({
            "pdfs": current_pdfs_info,
            "total_pdfs": len(current_pdfs_info),
            "chat_id": chat_id
        })
        
    except Exception as e:
        print(f"❌ Error getting PDFs: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/pdfs", methods=["GET"])
def get_all_pdfs():
    """Get all PDFs across all chats"""
    try:
        all_pdfs = []
        for chat in chat_history:
            pdf_list = chat.get("pdf_list", [])
            
            for pdf_meta in pdf_list:
                all_pdfs.append({
                    "chat_id": chat["id"],
                    "chat_title": chat.get("title", "Untitled Chat"),
                    "name": pdf_meta.get("name", "Unknown"),
                    "chunks": pdf_meta.get("chunks_added", 0),
                    "status": pdf_meta.get("status", "unknown"),
                    "uploaded_at": pdf_meta.get("upload_time")
                })
        
        return jsonify({"pdfs": all_pdfs, "total_pdfs": len(all_pdfs)})
        
    except Exception as e:
        print(f"❌ Error getting all PDFs: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/chats/<chat_id>/pdfs/<pdf_name>", methods=["DELETE"])
def delete_chat_pdf(chat_id, pdf_name):
    """Delete specific PDF"""
    try:
        chat_found = False
        pdf_found = False
        
        for chat in chat_history:
            if chat["id"] == chat_id:
                chat_found = True
                
                pdf_list = chat.get("pdf_list", [])
                updated_pdf_list = []
                
                for pdf_meta in pdf_list:
                    if pdf_meta.get("name") == pdf_name:
                        pdf_found = True
                        print(f"🗑️  Removing PDF '{pdf_name}'")
                    else:
                        updated_pdf_list.append(pdf_meta)
                
                if not pdf_found:
                    return jsonify({"error": f"PDF '{pdf_name}' not found"}), 404
                
                chat["pdf_list"] = updated_pdf_list
                chat["pdf_count"] = len(updated_pdf_list)
                chat["has_pdf"] = len(updated_pdf_list) > 0
                chat["updated_at"] = get_consistent_timestamp()
                
                if len(updated_pdf_list) == 0:
                    vector_store.delete_collection(chat_id)
                
                save_chat_history()
                
                return jsonify({
                    "message": "PDF removed successfully",
                    "chat_id": chat_id,
                    "pdf_name": pdf_name
                })
        
        if not chat_found:
            return jsonify({"error": "Chat not found"}), 404
            
    except Exception as e:
        print(f"❌ Error deleting PDF: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/chats/<chat_id>/messages", methods=["POST"])
def send_message(chat_id):
    """Send message and get AI response"""
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()
        
        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        if chat_id not in active_conversations:
            active_conversations[chat_id] = load_conversation(chat_id)
        
        conversation = active_conversations[chat_id]
        
        # Check for documents
        chat_docs = document_store.get_chat_documents(chat_id)
        has_documents = len(chat_docs) > 0
        
        context_text = ""
        sources = []
        
        if has_documents:
            collection = vector_store.get_or_create_collection(chat_id)
            results = vector_store.query(collection, user_message, n_results=config.RAG_TOP_K)
            
            if results:
                context_parts = []
                for idx, (doc, meta, score) in enumerate(results, 1):
                    doc_type = meta.get('doc_type', 'unknown')
                    source = meta.get('source', 'Unknown')
                    
                    if doc_type == 'pdf':
                        page = meta.get('page', 'unknown')
                        content_type = meta.get('type', 'text')
                        location = f"Page {page}"
                        
                        if content_type == 'table':
                            location += f", Table"
                    else:
                        location = "Unknown location"
                        content_type = meta.get('type', 'unknown')
                    
                    context_parts.append(f"[Source {idx}: {source} - {location}]\n{doc}\n")
                    
                    sources.append({
                        "id": idx,
                        "source": source,
                        "location": location,
                        "doc_type": doc_type,
                        "content_type": content_type,
                        "content": doc[:800],
                        "full_content": doc,
                        "page": meta.get('page', 'unknown')
                    })
                
                context_text = "\n\n".join(context_parts)
                print(f"🔍 Retrieved {len(sources)} relevant sources")
        
        # Build prompt
        if context_text:
            prompt = f"""You are a helpful AI assistant that answers questions based on provided document context.

CONTEXT:
{context_text}

USER QUESTION: {user_message}

INSTRUCTIONS:
1. Answer using ONLY the information in the context above
2. Be specific and cite which sources support your answer
3. If the context doesn't contain the answer, clearly state: "I don't have that information in the provided documents"
4. Be concise but thorough"""
        else:
            prompt = f"""You are a helpful AI assistant. Please answer: {user_message}"""
        
        # Build history
        recent_history = conversation[-10:] if len(conversation) > 10 else conversation
        
        gemini_history = []
        for msg in recent_history:
            gemini_history.append({
                "role": msg["role"],
                "parts": [{"text": msg["parts"][0]}]
            })
        
        gemini_history.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        # Get AI response
        try:
            response = model.generate_content(gemini_history)
            bot_response = response.text if hasattr(response, "text") else "I couldn't generate a response."
        except Exception as api_error:
            print(f"❌ Gemini API error: {api_error}")
            bot_response = f"I encountered an error: {str(api_error)}"
        
        # Save conversation
        conversation.append({
            "role": "user",
            "parts": [user_message],
            "timestamp": get_consistent_timestamp()
        })
        
        conversation.append({
            "role": "model",
            "parts": [bot_response],
            "timestamp": get_consistent_timestamp()
        })
        
        save_conversation(chat_id, conversation)
        
        # Update chat metadata
        for chat in chat_history:
            if chat["id"] == chat_id:
                chat["message_count"] = len(conversation)
                chat["updated_at"] = get_consistent_timestamp()
                break
        
        save_chat_history()
        
        return jsonify({
            "reply": bot_response,
            "sources": sources,
            "message_count": len(conversation)
        })
        
    except Exception as e:
        print(f"❌ Message error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# --- STARTUP ---

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 PRODUCTION RAG BACKEND SERVER")
    print("="*70)
    print(f"📦 Vector DB: ChromaDB at {config.CHROMA_PATH}")
    print(f"🤖 LLM: Gemini 2.0 Flash")
    print(f"🔍 OCR: LlamaParse {'✅' if pdf_processor.has_llamaparse else '❌'}")
    print(f"📊 Embedding: SentenceTransformer")
    print(f"\n📝 Limits:")
    print(f"   - Max PDFs per chat: {config.MAX_PDFS_PER_CHAT}")
    print(f"   - Max PDF size: {config.MAX_PDF_SIZE_MB}MB")
    print("="*70 + "\n")
    
    load_chat_history()
    
    print("🌐 Starting Flask server on http://0.0.0.0:5000")
    
    # Print all registered routes for debugging
    print("\n📍 Registered Routes:")
    for rule in app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
        print(f"   {methods:8} {rule.rule}")
    
    print("="*70 + "\n")
    
    try:
        app.run(
            debug=True,
            host="0.0.0.0",
            port=5000,
            threaded=True,
            use_reloader=False  # Disable reloader to prevent double initialization
        )
    except Exception as e:
        print(f"❌ Server error: {e}")
        traceback.print_exc()