from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
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
    question: str = Field(..., min_length=1, max_length=4096)
    automated_answer: Optional[str] = Field(default=None, max_length=5000)


class TicketResolveRequest(BaseModel):
    solution: str = Field(..., min_length=1, max_length=5000)
    resolved_by: Optional[str] = None
    resolution_channel: Optional[str] = "TELEGRAM"
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
    resolution_channel: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    support_group_message_id: Optional[int] = None
    is_newly_resolved: Optional[bool] = None


class TicketSupportCardRequest(BaseModel):
    message_id: int


class InboundEmailWebhookRequest(BaseModel):
    sender: str = Field(..., max_length=320)  # RFC 5321 max mailbox length
    subject: str = Field(..., max_length=998)  # RFC 5322 max header line length
    body: str = Field(..., max_length=200_000)


class BrevoInboundFrom(BaseModel):
    Address: str = Field(..., max_length=320)


class BrevoInboundItem(BaseModel):
    From: BrevoInboundFrom
    Subject: str = Field(..., max_length=998)
    RawTextBody: Optional[str] = Field(default=None, max_length=200_000)
    ExtractedMarkdownMessage: Optional[str] = Field(default=None, max_length=200_000)


class BrevoInboundWebhookRequest(BaseModel):
    items: List[BrevoInboundItem]


class KnowledgeIngestRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4096)
    solution: str = Field(..., min_length=1, max_length=5000)
    keywords: Optional[str] = Field(default=None, max_length=1000)
    source_ticket_id: Optional[int] = None


class KnowledgeArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    solution: str
    keywords: Optional[str] = None
    source_ticket_id: Optional[int] = None
    created_at: datetime


class WarningCreateRequest(BaseModel):
    user_id: int
    group_id: int
    warned_by: str = Field(..., min_length=1, max_length=255)
    reason: Optional[str] = Field(default=None, max_length=1000)


class WarningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    group_id: int
    reason: Optional[str] = None
    warned_by: str
    created_at: datetime


class WarningListResponse(BaseModel):
    count: int
    warnings: List[WarningResponse]


class CryptoPriceResponse(BaseModel):
    symbol: str
    price_usd: float
    change_24h_pct: float
    market_cap_usd: float
    volume_24h_usd: float


class BotSettingRequest(BaseModel):
    value: Optional[str] = Field(default=None, max_length=1000)
    updated_by: Optional[str] = Field(default=None, max_length=255)


class BotSettingResponse(BaseModel):
    key: str
    value: Optional[str] = None


class WhitelistAddRequest(BaseModel):
    user_id: int
    added_by: str = Field(..., min_length=1, max_length=255)


class WhitelistEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    added_by: str
    created_at: datetime


class WhitelistListResponse(BaseModel):
    entries: List[WhitelistEntryResponse]


class WhitelistCheckResponse(BaseModel):
    user_id: int
    is_whitelisted: bool
