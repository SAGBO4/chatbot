from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class QueryRequest(BaseModel):
    query: str
    user_id: Optional[int] = None
    user_handle: Optional[str] = None


class QueryResponse(BaseModel):
    query: str
    found: bool
    confidence: float
    answer: str
    article_id: Optional[int] = None
    requires_resolution_confirmation: bool = True


class TicketCreateRequest(BaseModel):
    user_id: int
    user_handle: Optional[str] = None
    question: str
    automated_answer: Optional[str] = None


class TicketResolveRequest(BaseModel):
    solution: str
    resolved_by: Optional[str] = None
    add_to_knowledge_base: bool = True


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    user_handle: Optional[str] = None
    question: str
    status: str
    automated_answer: Optional[str] = None
    solution: Optional[str] = None
    resolved_by: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class KnowledgeIngestRequest(BaseModel):
    question: str
    solution: str
    keywords: Optional[str] = None
    source_ticket_id: Optional[int] = None


class KnowledgeArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    solution: str
    keywords: Optional[str] = None
    source_ticket_id: Optional[int] = None
    created_at: datetime
