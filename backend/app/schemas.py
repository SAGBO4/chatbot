"""Request and response bodies of the REST API. The `max_length` limits bound the size of untrusted input."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

# Limits shared with the code that builds these values (the email and bot flows truncate to them)
MAX_QUESTION_LENGTH = 4096
MAX_SOLUTION_LENGTH = 5000


class ErrorResponse(BaseModel):
    """Body of every error the API returns (401, 403, 404, 429, 503...)."""

    detail: str = Field(description="What went wrong.", examples=["Ticket not found"])


class QueryRequest(BaseModel):
    query: str = Field(
        ..., min_length=1, max_length=MAX_QUESTION_LENGTH,
        description="The user's question, in French or English.",
        examples=["How do I restore my wallet from a seed phrase?"],
    )
    user_id: Optional[int] = Field(default=None, description="Telegram id of the user asking.", examples=[123456789])
    user_handle: Optional[str] = Field(default=None, description="Telegram @username of the user, if any.", examples=["alice"])


class QueryResponse(BaseModel):
    query: str = Field(description="The question, trimmed.")
    found: bool = Field(description="Whether a knowledge base article matched the question.")
    confidence: float = Field(description="Match score between 0 and 1 (0 when nothing matched).", examples=[0.82])
    answer: str = Field(description="Text to show the user: the article's solution (rewritten by the AI when enabled) or a fallback message.")
    article_id: Optional[int] = Field(default=None, description="Id of the matched knowledge base article.", examples=[7])
    requires_resolution_confirmation: bool = Field(
        default=True,
        description="Whether to ask the user to confirm the answer helped (false only for an empty question).",
    )


class TicketCreateRequest(BaseModel):
    user_id: int = Field(description="Telegram id of the user who needs help.", examples=[123456789])
    user_handle: Optional[str] = Field(default=None, description="Telegram @username of the user, if any.", examples=["alice"])
    question: str = Field(
        ..., min_length=1, max_length=MAX_QUESTION_LENGTH,
        description="What the user asked and could not get answered.",
        examples=["My swap has been pending for two hours."],
    )
    automated_answer: Optional[str] = Field(
        default=None, max_length=MAX_SOLUTION_LENGTH,
        description="The answer the bot gave, so the agent sees what already failed.",
    )


class TicketResolveRequest(BaseModel):
    solution: str = Field(
        ..., min_length=1, max_length=MAX_SOLUTION_LENGTH,
        description="The answer given to the user. It is also added to the knowledge base unless `add_to_knowledge_base` is false.",
        examples=["Restart the app, then re-import your wallet with the 24-word seed phrase."],
    )
    resolved_by: Optional[str] = Field(default=None, description="Name or @username of the agent.", examples=["agent_bob"])
    resolution_channel: Optional[str] = Field(default="TELEGRAM", description="Where the agent answered: `TELEGRAM` or `EMAIL`.", examples=["TELEGRAM"])
    add_to_knowledge_base: bool = Field(default=True, description="Index the question and solution so the bot can answer the next user directly.")


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Ticket id (shown as `TICKET #<id>` in the support group).", examples=[42])
    user_id: int = Field(description="Telegram id of the user who opened the ticket.", examples=[123456789])
    user_handle: Optional[str] = Field(default=None, description="Telegram @username of the user, if any.")
    question: str = Field(description="What the user asked.")
    status: str = Field(description="`OPEN` until an agent resolves it, then `RESOLVED`.", examples=["OPEN"])
    automated_answer: Optional[str] = Field(default=None, description="The answer the bot gave before escalating.")
    solution: Optional[str] = Field(default=None, description="The agent's answer, once resolved.")
    resolved_by: Optional[str] = Field(default=None, description="Who resolved the ticket.")
    resolution_channel: Optional[str] = Field(default=None, description="`TELEGRAM` or `EMAIL`, once resolved.")
    created_at: datetime = Field(description="When the ticket was opened (UTC).")
    resolved_at: Optional[datetime] = Field(default=None, description="When the ticket was resolved (UTC).")
    support_group_message_id: Optional[int] = Field(default=None, description="Telegram message id of the ticket card in the support group.")
    is_newly_resolved: Optional[bool] = Field(
        default=None,
        description="Only set by the resolve endpoint: false when another agent had already resolved the ticket.",
    )


class TicketSupportCardRequest(BaseModel):
    message_id: int = Field(description="Telegram message id of the ticket card posted in the support group.", examples=[9876])


class InboundEmailWebhookRequest(BaseModel):
    sender: str = Field(..., max_length=320, description="Email address of the agent replying (RFC 5321 maximum length).", examples=["agent@company.com"])
    subject: str = Field(..., max_length=998, description="Subject of the reply; it must contain `[Ticket #<id>]` (RFC 5322 maximum length).", examples=["Re: [Ticket #42] My swap is pending"])
    body: str = Field(..., max_length=200_000, description="Text of the reply. Quoted history is stripped before it is used as the solution.")


# The Brevo* models mirror Brevo's inbound-parsing payload, hence the capitalized field names.
class BrevoInboundFrom(BaseModel):
    Address: str = Field(..., max_length=320, description="Sender's email address.", examples=["agent@company.com"])


class BrevoInboundItem(BaseModel):
    From: BrevoInboundFrom = Field(description="Sender of the parsed email.")
    Subject: str = Field(..., max_length=998, description="Subject; it must contain `[Ticket #<id>]`.", examples=["Re: [Ticket #42] My swap is pending"])
    RawTextBody: Optional[str] = Field(default=None, max_length=200_000, description="Plain-text body, used when no extracted message is available.")
    ExtractedMarkdownMessage: Optional[str] = Field(default=None, max_length=200_000, description="The new text of the reply without quoted history; preferred over `RawTextBody`.")


class BrevoInboundWebhookRequest(BaseModel):
    items: List[BrevoInboundItem] = Field(description="The parsed emails of this batch.")


class InboundEmailResult(BaseModel):
    """Outcome of one inbound email."""

    status: str = Field(
        description="`resolved`, `already_resolved`, `unauthorized_sender`, `no_ticket_reference`, `empty_body`, "
        "`ticket_not_found` or `internal_error`.",
        examples=["resolved"],
    )
    ticket_id: Optional[int] = Field(default=None, description="The ticket the email referred to, if one was found.", examples=[42])
    message: Optional[str] = Field(default=None, description="Explanation, for statuses other than `resolved`.")


class BrevoBatchResponse(BaseModel):
    results: List[InboundEmailResult] = Field(description="One entry per item, in the same order. A failing item does not fail the batch.")


class KnowledgeIngestRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH, description="The question this article answers.", examples=["How do I back up my wallet?"])
    solution: str = Field(..., min_length=1, max_length=MAX_SOLUTION_LENGTH, description="The answer shown to users.", examples=["Open Settings > Backup and write down the 24 words."])
    keywords: Optional[str] = Field(default=None, max_length=1000, description="Comma-separated search terms, in French and English. Derived from the question when omitted.", examples=["backup, sauvegarde, seed"])
    source_ticket_id: Optional[int] = Field(default=None, description="Ticket this article comes from. Ingesting the same ticket twice updates the article instead of duplicating it.")


class KnowledgeArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Article id.", examples=[7])
    question: str = Field(description="The question this article answers.")
    solution: str = Field(description="The answer shown to users.")
    keywords: Optional[str] = Field(default=None, description="Comma-separated search terms.")
    source_ticket_id: Optional[int] = Field(default=None, description="Ticket this article was created from, if any.")
    created_at: datetime = Field(description="When the article was added (UTC).")


class WarningCreateRequest(BaseModel):
    user_id: int = Field(description="Telegram id of the member being warned.", examples=[123456789])
    group_id: int = Field(description="Telegram id of the group the warning applies to.", examples=[-1001234567890])
    warned_by: str = Field(..., min_length=1, max_length=255, description="Who issued the warning.", examples=["@moderator"])
    reason: Optional[str] = Field(default=None, max_length=1000, description="Why the member is warned.", examples=["Spam"])


class WarningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Warning id.")
    user_id: int = Field(description="Telegram id of the warned member.")
    group_id: int = Field(description="Telegram id of the group.")
    reason: Optional[str] = Field(default=None, description="Why the member was warned.")
    warned_by: str = Field(description="Who issued the warning.")
    created_at: datetime = Field(description="When the warning was issued (UTC).")


class WarningListResponse(BaseModel):
    count: int = Field(description="Number of warnings the member has in this group.", examples=[2])
    warnings: List[WarningResponse] = Field(description="The warnings, newest first.")


class CryptoPriceResponse(BaseModel):
    symbol: str = Field(description="Asset symbol, lower case.", examples=["btc"])
    price_usd: float = Field(description="Current price in US dollars.", examples=[64250.5])
    change_24h_pct: float = Field(description="Price change over the last 24 hours, in percent.", examples=[-1.2])
    market_cap_usd: float = Field(description="Market capitalisation in US dollars.")
    volume_24h_usd: float = Field(description="Trading volume over the last 24 hours, in US dollars.")


class BotSettingRequest(BaseModel):
    value: Optional[str] = Field(default=None, max_length=1000, description="New value; null clears it.", examples=["en"])
    updated_by: Optional[str] = Field(default=None, max_length=255, description="Who made the change.", examples=["@owner"])


class BotSettingResponse(BaseModel):
    key: str = Field(description="Setting name, `language` or `community_group_id`.", examples=["language"])
    value: Optional[str] = Field(default=None, description="Current value, or null if never set.")


class WhitelistAddRequest(BaseModel):
    user_id: int = Field(description="Telegram id of the user to make an admin.", examples=[123456789])
    added_by: str = Field(..., min_length=1, max_length=255, description="Who grants the right.", examples=["@owner"])


class WhitelistEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(description="Telegram id of the whitelisted admin.")
    added_by: str = Field(description="Who granted the right.")
    created_at: datetime = Field(description="When the user was added (UTC).")


class WhitelistListResponse(BaseModel):
    entries: List[WhitelistEntryResponse] = Field(description="Every whitelisted admin.")


class WhitelistCheckResponse(BaseModel):
    user_id: int = Field(description="The user that was checked.")
    is_whitelisted: bool = Field(description="Whether the backend counts this user as an admin (the bot owner, or whitelisted).")


class WhitelistRemoveResponse(BaseModel):
    removed: bool = Field(description="Always true: an unknown user gets a 404 instead.")
    user_id: int = Field(description="The user that was removed.")


class TicketAttachmentRequest(BaseModel):
    data_url: str = Field(
        ...,
        description=(
            "The image as a data: URL (data:<mime>;base64,<data>). Accepted types: PNG, JPEG, WebP, "
            "GIF. Limited to 5 MB decoded; never persisted, only forwarded to the support group."
        ),
        examples=["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="],
    )


class TicketAttachmentResponse(BaseModel):
    forwarded: bool = Field(
        description="Whether the image reached the support group (false only if Telegram rejected it; never fails ticket creation).",
    )


class HealthResponse(BaseModel):
    status: str = Field(description="`ok` when the API is up.", examples=["ok"])
    database: str = Field(description="`connected` when the database answered a ping.", examples=["connected"])
    service: str = Field(description="Service name.", examples=["support-bot-backend"])
