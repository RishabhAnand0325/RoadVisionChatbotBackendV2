from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class CaseBase(BaseModel):
    case_title: str
    description: Optional[str] = None
    case_type: str
    status: str = 'Pending'

class CaseCreate(CaseBase):
    pass

class Case(CaseBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DocumentBase(BaseModel):
    document_name: str
    document_type: str
    case_id: UUID

class DocumentCreate(DocumentBase):
    pass

class Document(DocumentBase):
    id: UUID
    uploaded_at: datetime
    model_config = ConfigDict(from_attributes=True)
