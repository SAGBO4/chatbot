import re
import logging
from typing import Optional, Tuple, Union
import httpx
from aiogram import Router, F, Bot
from aiogram.types import Message, User
from app.config import settings
from bot.admin_check import is_bot_admin
from bot.api_client import BackendClient
from bot.language import get_active_language
from bot.messaging import call_with_markdown_fallback
from app.i18n import t
from app.schemas import MAX_SOLUTION_LENGTH
from app.telegram_text import escape_telegram_markdown, truncate_telegram_text, FORWARDED_SOLUTION_MAX_LENGTH

logger = logging.getLogger(__name__)
support_router = Router()

TICKET_ID_REGEX = re.compile(r"TICKET\s*(?:SUPPORT\s*)?#(\d+)", re.IGNORECASE)
USER_ID_REGEX = re.compile(r"ID:\s*(\d+)")

# OpenAI's Whisper API rejects files above 25 MB.
WHISPER_MAX_BYTES = 25 * 1024 * 1024


async def _transcribe_voice_message(message: Message, bot: Bot) -> Optional[str]:
    """
    Best-effort speech-to-text for a voice/audio reply, using OpenAI's Whisper API.

    Only tried with AI_PROVIDER "openai" and an API key (Whisper is OpenAI-specific). Never raises:
    any failure returns None and the caller asks the agent to reply with text instead.
    """
    media = message.voice or message.audio
    if media is None:
        return None
    if (settings.AI_PROVIDER or "").strip().lower() != "openai" or not settings.AI_API_KEY:
        logger.info("Voice reply received but speech-to-text needs AI_PROVIDER=openai with AI_API_KEY set.")
        return None
    if media.file_size and media.file_size > WHISPER_MAX_BYTES:
        logger.warning("Voice reply too large to transcribe (%s bytes).", media.file_size)
        return None

    try:
        file_info = await bot.get_file(media.file_id)
        buffer = await bot.download_file(file_info.file_path)
        audio_bytes = buffer.read()
    except Exception as exc:
        logger.error("Failed to download voice message for transcription: %s", exc)
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
                data={"model": "whisper-1"},
                files={"file": ("voice.ogg", audio_bytes, "audio/ogg")},
            )
        if response.status_code == 200:
            return (response.json().get("text") or "").strip() or None
        logger.warning("Whisper transcription failed (%s): %s", response.status_code, response.text)
        return None
    except Exception as exc:
        logger.error("Error calling Whisper transcription API: %s", exc)
        return None


def _is_support_group_chat(chat_id: Union[int, str]) -> bool:
    """True only if chat_id is the configured support group; False while it is unconfigured (unset or 0)."""
    if not settings.support_group_is_configured():
        return False
    return str(chat_id) == str(settings.TELEGRAM_SUPPORT_GROUP_ID)


async def _find_ticket(message: Message, bot: Bot, client: BackendClient) -> Tuple[Optional[int], Optional[int]]:
    """
    The ticket an agent's reply is about: `(ticket_id, user_id)`, `(None, None)` when none is found.

    First by the replied-to message's id, which is immune to changes in the card's wording. Otherwise by
    parsing the card's text (tickets created before the id lookup existed, or whose id was never stored),
    which is only trusted when the bot itself posted the replied-to message: any message crafted to look
    like a card would otherwise pass for a ticket.
    """
    try:
        matched_ticket = await client.get_ticket_by_support_message(message.reply_to_message.message_id)
    except Exception as exc:
        logger.warning("Support-card lookup by message id failed, falling back to text: %s", exc)
        matched_ticket = None

    if matched_ticket:
        return matched_ticket["id"], matched_ticket.get("user_id")

    replied_author = getattr(message.reply_to_message, "from_user", None)
    if replied_author is None or replied_author.id != bot.id:
        return None, None

    replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    ticket_match = TICKET_ID_REGEX.search(replied_text)
    if not ticket_match:
        return None, None
    user_match = USER_ID_REGEX.search(replied_text)
    return int(ticket_match.group(1)), int(user_match.group(1)) if user_match else None


async def _solution_text(message: Message, bot: Bot, lang: str) -> str:
    """
    The solution an agent wrote: the text, else the caption (a screenshot with an explanation is a normal
    reply), else a transcription of a voice message, which is echoed back to the agent. "" if none.
    """
    solution_text = (message.text or message.caption or "").strip()
    if not solution_text and (message.voice or message.audio):
        transcribed = await _transcribe_voice_message(message, bot)
        if transcribed:
            solution_text = transcribed
            await message.reply(
                t("support_voice_transcribed", lang, transcribed=escape_telegram_markdown(solution_text)),
                parse_mode="Markdown",
            )
    return solution_text


def _agent_name(user: User) -> str:
    """How the agent is named in the ticket and to the user: username, else full name, else `Agent_<id>`."""
    return (
        user.username
        or f"{user.first_name} {user.last_name or ''}".strip()
        or f"Agent_{user.id}"
    )


async def _is_reply_in_support_group(message: Message) -> bool:
    """
    Filter: only replies sent in the support group reach `handle_support_agent_reply`.

    In aiogram a handler whose filters pass consumes the event even when it returns nothing. Matching
    every reply (`F.reply_to_message` alone) would swallow replies in other chats before the
    moderation and user routers see them: `/mute` sent as a reply, or a question asked as a reply.
    """
    return _is_support_group_chat(message.chat.id)


@support_router.message(F.reply_to_message, _is_reply_in_support_group)
async def handle_support_agent_reply(
    message: Message,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """
    Turn a support agent's reply to a ticket card into the ticket's resolution.

    Only replies inside the configured support group count, and only from a verified group admin;
    otherwise anyone could resolve tickets, message arbitrary users or feed the knowledge base.
    """
    if not _is_support_group_chat(message.chat.id):
        return

    # Being in the group is not enough: only a bot admin (owner, whitelisted, or a native Telegram
    # group admin) may resolve tickets, message users on the bot's behalf or feed the knowledge base.
    if not message.from_user or not await is_bot_admin(
        bot, message.chat.id, message.from_user.id, backend_client=backend_client
    ):
        return

    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)

    ticket_id, target_user_id = await _find_ticket(message, bot, client)
    if ticket_id is None:
        await message.reply(t("support_no_matching_ticket", lang))
        return

    solution_text = await _solution_text(message, bot, lang)
    if not solution_text:
        await message.reply(t("support_no_text_content", lang))
        return

    agent_name = _agent_name(message.from_user)

    try:
        # The backend rejects longer solutions
        api_solution = truncate_telegram_text(solution_text, max_length=MAX_SOLUTION_LENGTH, lang=lang)
        resolved_ticket = await client.resolve_ticket(
            ticket_id=ticket_id,
            solution=api_solution,
            resolved_by=agent_name,
            add_to_knowledge_base=True,
        )

        if resolved_ticket.get("is_newly_resolved") is False:
            already_by = escape_telegram_markdown(resolved_ticket.get("resolved_by") or t("another_agent", lang))
            await message.reply(
                t("support_already_resolved", lang, ticket_id=ticket_id, resolved_by=already_by),
                parse_mode="Markdown",
            )
            return

        user_id = target_user_id or resolved_ticket.get("user_id")

        # Forward the solution to the user
        if user_id:
            capped_solution = truncate_telegram_text(solution_text, max_length=FORWARDED_SOLUTION_MAX_LENGTH, lang=lang)
            safe_solution = escape_telegram_markdown(capped_solution)
            safe_agent = escape_telegram_markdown(agent_name)
            user_notification = t(
                "support_user_notification", lang, ticket_id=ticket_id, solution=safe_solution, agent=safe_agent
            )
            await call_with_markdown_fallback(
                bot.send_message, chat_id=user_id, text=user_notification,
                what=f"Notification to user {user_id}", swallow_failure=True, failure_level=logging.ERROR,
            )

        # Confirm in the support group
        await message.reply(
            t("support_resolved_confirmation", lang, ticket_id=ticket_id, user_id=user_id),
            parse_mode="Markdown",
        )

    except Exception as exc:
        logger.error("Error resolving ticket %s via group reply: %s", ticket_id, exc)
        await message.reply(t("support_resolution_error", lang, ticket_id=ticket_id))
