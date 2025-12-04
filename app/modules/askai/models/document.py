from enum import Enum
from typing import List, Optional, Any
from uuid import UUID, uuid4
from pydantic import Field, BaseModel, ConfigDict


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    chunks: int
    status: str

class ProcessingStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    FINISHED = "finished"
    FAILED = "failed"

class ProcessingStage(Enum):
    NOT_PROCESSING = "not_processing"
    LLAMA_LOADING = "llama_loading"
    PYMUPDF_LOADING = "pymupdf_loading"
    TESSERACT_LOADING = "tesseract_loading"
    HTML_LOADING = "html_loading"
    PARSING_CONTENT = "parsing_content"
    EXTRACTING_CONTENT = "extracting_content"
    EXTRACTING_TABLES = "extracting_tables"
    EXTRACTING_LINKS = "extracting_links"
    CREATING_CHUNKS = "creating_chunks"
    ADDING_TO_VECTOR_STORE = "adding_to_vector_store"
    SAVING_METADATA = "saving_metadata"

class UploadJob(BaseModel):
    job_id: str
    filename: str
    chat_id: str
    status: ProcessingStatus
    stage: ProcessingStage
    progress: float
    finished_at: str
    chunks_added: int
    error: Optional[str]

class ProcessingJob(BaseModel):
    name: str
    job_id: str
    status: ProcessingStatus
    stage: ProcessingStage
    progress: float

class DriveFile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    # Some drive related metadata
    id: str
    name: str
    mime_type: str = Field(..., alias="mimeType")
    size: Optional[str] = None

class DriveFolder(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    files: List[DriveFile]
    subfolders: List['DriveFolder']

DriveFolder.model_rebuild()

class ChatDocumentsResponse(BaseModel):
    pdfs: List[DocumentMetadata]
    xlsx: List[DocumentMetadata]
    processing: List[ProcessingJob]
    drive_folders: List[DriveFolder]
    total_docs: int
    chat_id: str

class AddDriveRequest(BaseModel):
    driveUrl: str

class UploadAcceptedResponse(BaseModel):
    message: str
    job_id: str
    processing: bool
