"""Database models. Timestamps are timezone-aware UTC."""
import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Integer, BigInteger, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base shared by every model (also used by Alembic autogenerate)."""


class TicketStatus(str, enum.Enum):
    """Ticket lifecycle. The current code only ever sets OPEN and RESOLVED; lookups are case-insensitive."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            upper = value.upper()
            for member in cls:
                if member.value == upper:
                    return member
        return None


def utc_now() -> datetime:
    """Current time as an aware UTC datetime (default for the created_at / updated_at columns)."""
    return datetime.now(timezone.utc)


class Ticket(Base):
    """A support request. `status` stores a TicketStatus value; `resolution_channel` is TELEGRAM or EMAIL."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_handle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=TicketStatus.OPEN.value, nullable=False, index=True
    )
    automated_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    solution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolution_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    support_group_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    # Telegram chat id where the ticket originated (community group or private chat).
    source_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    # Telegram message id of the question in the source chat, so resolution can reply in-thread.
    source_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class CommunityWarning(Base):
    """A moderation warning issued to a user in a community group."""

    __tablename__ = "community_warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    warned_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class BotSetting(Base):
    """A persisted bot setting (key/value), e.g. `community_group_id` or `language`."""

    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class BotAdminWhitelist(Base):
    """A user allowed to run admin commands, in addition to the bot owner."""

    __tablename__ = "bot_admin_whitelist"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    added_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class KnowledgeArticle(Base):
    """A question/solution pair the bot answers with: added manually, or from a resolved ticket (`source_ticket_id`)."""

    __tablename__ = "knowledge_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_ticket_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
