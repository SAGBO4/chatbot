import re
import logging
from typing import Optional, Union
import httpx
from aiogram import Router, F, Bot
from aiogram.types import Message
from app.config import settings
from bot.admin_check import is_group_admin
from bot.api_client import BackendClient
from bot.language import get_active_language
from bot.i18n import t
from bot.utils import escape_telegram_markdown, truncate_telegram_text

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
    if settings.AI_PROVIDER != "openai" or not settings.AI_API_KEY:
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

    # Being in the group is not enough: only a verified admin may resolve tickets, message users on
    # the bot's behalf or feed the knowledge base (checked live with Telegram, see is_group_admin).
    if not message.from_user or not await is_group_admin(bot, message.chat.id, message.from_user.id):
        return

    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)

    # Primary match: the replied-to message's id, immune to changes in the card's wording.
    ticket_id: Optional[int] = None
    target_user_id: Optional[int] = None

    try:
        matched_ticket = await client.get_ticket_by_support_message(
            message.reply_to_message.message_id
        )
    except Exception as exc:
        logger.warning("Support-card lookup by message id failed, falling back to text: %s", exc)
        matched_ticket = None

    replied_author = getattr(message.reply_to_message, "from_user", None)
    replied_from_bot = replied_author is not None and replied_author.id == bot.id

    if matched_ticket:
        ticket_id = matched_ticket["id"]
        target_user_id = matched_ticket.get("user_id")
    elif replied_from_bot:
        # Fallback: parse the card's text (tickets created before the id lookup existed, or whose id
        # was never stored). Only trusted when the bot itself posted the replied-to message, or any
        # message crafted to look like a card would pass for a ticket.
        replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        ticket_match = TICKET_ID_REGEX.search(replied_text)
        user_match = USER_ID_REGEX.search(replied_text)

        if ticket_match:
            ticket_id = int(ticket_match.group(1))
            target_user_id = int(user_match.group(1)) if user_match else None

    # No match: tell the agent instead of doing nothing.
    if ticket_id is None:
        await message.reply(t("support_no_matching_ticket", lang))
        return

    # message.text is None for non-text replies: use the caption (a screenshot with an explanation is
    # a normal reply), then a voice transcription.
    solution_text = (message.text or message.caption or "").strip()

    if not solution_text and (message.voice or message.audio):
        transcribed = await _transcribe_voice_message(message, bot)
        if transcribed:
            solution_text = transcribed
            safe_transcribed = escape_telegram_markdown(solution_text)
            await message.reply(
                t("support_voice_transcribed", lang, transcribed=safe_transcribed),
                parse_mode="Markdown",
            )

    if not solution_text:
        await message.reply(t("support_no_text_content", lang))
        return

    agent_name = (
        message.from_user.username
        or f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        or f"Agent_{message.from_user.id}"
    )

    try:
        # The backend rejects solutions over 5000 characters
        api_solution = truncate_telegram_text(solution_text, max_length=5000)
        resolved_ticket = await client.resolve_ticket(
            ticket_id=ticket_id,
            solution=api_solution,
            resolved_by=agent_name,
            add_to_knowledge_base=True,
        )

        if resolved_ticket.get("is_newly_resolved") is False:
            already_by = escape_telegram_markdown(resolved_ticket.get("resolved_by") or "un autre agent")
            await message.reply(
                t("support_already_resolved", lang, ticket_id=ticket_id, resolved_by=already_by),
                parse_mode="Markdown",
            )
            return

        user_id = target_user_id or resolved_ticket.get("user_id")

        # Forward the solution to the user
        if user_id:
            capped_solution = truncate_telegram_text(solution_text, max_length=3500)
            safe_solution = escape_telegram_markdown(capped_solution)
            safe_agent = escape_telegram_markdown(agent_name)
            user_notification = t(
                "support_user_notification", lang, ticket_id=ticket_id, solution=safe_solution, agent=safe_agent
            )
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=user_notification,
                    parse_mode="Markdown",
                )
            except Exception as send_err:
                logger.warning("Markdown send failed for user %s, retrying in plain text: %s", user_id, send_err)
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=user_notification,
                    )
                except Exception as plain_err:
                    logger.error("Failed to send plain text user notification: %s", plain_err)

        # Confirm in the support group
        await message.reply(
            t("support_resolved_confirmation", lang, ticket_id=ticket_id, user_id=user_id),
            parse_mode="Markdown",
        )

    except Exception as exc:
        logger.error("Error resolving ticket %s via group reply: %s", ticket_id, exc)
        await message.reply(t("support_resolution_error", lang, ticket_id=ticket_id))
