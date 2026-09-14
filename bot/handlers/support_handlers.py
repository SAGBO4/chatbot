import re
import logging
from typing import Optional, Union
import httpx
from aiogram import Router, F, Bot
from aiogram.types import Message
from backend.config import settings
from bot.api_client import BackendClient
from bot.utils import escape_telegram_markdown

logger = logging.getLogger(__name__)
support_router = Router()

TICKET_ID_REGEX = re.compile(r"TICKET SUPPORT #(\d+)")
USER_ID_REGEX = re.compile(r"ID:\s*(\d+)")

# OpenAI's Whisper API rejects files above 25 MB.
WHISPER_MAX_BYTES = 25 * 1024 * 1024


async def _transcribe_voice_message(message: Message, bot: Bot) -> Optional[str]:
    """
    Best-effort speech-to-text for a voice/audio agent reply, via OpenAI's
    Whisper API (`audio/transcriptions`).

    Only attempted when AI_PROVIDER is "openai" with an API key configured -
    Whisper is OpenAI-specific, so Gemini/DeepSeek deployments fall back to
    asking the agent to reply with text instead. Never raises: any failure
    (unsupported provider, download error, API error) returns None so the
    caller falls through to that same "please reply with text" message
    rather than crashing.
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
    """
    Returns True only if chat_id matches the configured Telegram Support Group.

    Returns False when TELEGRAM_SUPPORT_GROUP_ID is unconfigured (falsy or the
    "0" sentinel), so an unconfigured group can never accidentally match.
    """
    if not settings.support_group_is_configured():
        return False
    return str(chat_id) == str(settings.TELEGRAM_SUPPORT_GROUP_ID)


@support_router.message(F.reply_to_message)
async def handle_support_agent_reply(
    message: Message,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """
    Captures replies made by support team agents to ticket cards posted in the support group.

    Only replies sent in the configured Telegram Support Group are treated as
    agent resolutions; replies from any other chat (private DMs included) are
    ignored to prevent unauthenticated users from resolving arbitrary tickets,
    messaging arbitrary Telegram users, or injecting content into the
    knowledge base.
    """
    if not _is_support_group_chat(message.chat.id):
        return

    client = backend_client or BackendClient()

    # 1. Primary: resolve by the replied-to message's identity, so wording
    # changes to the card's text can never break matching.
    ticket_id: Optional[int] = None
    target_user_id: Optional[int] = None

    try:
        matched_ticket = await client.get_ticket_by_support_message(
            message.reply_to_message.message_id
        )
    except Exception as exc:
        logger.warning("Support-card lookup by message id failed, falling back to text: %s", exc)
        matched_ticket = None

    if matched_ticket:
        ticket_id = matched_ticket["id"]
        target_user_id = matched_ticket.get("user_id")
    else:
        # 2. Fallback: parse the card's text (covers tickets created before
        # this lookup existed, or a card whose id was never recorded).
        replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        ticket_match = TICKET_ID_REGEX.search(replied_text)
        user_match = USER_ID_REGEX.search(replied_text)

        if ticket_match:
            ticket_id = int(ticket_match.group(1))
            target_user_id = int(user_match.group(1)) if user_match else None

    # 3. Neither the id-based lookup nor the text fallback found a ticket:
    # tell the agent explicitly instead of silently doing nothing.
    if ticket_id is None:
        await message.reply(
            "⚠️ Je n'ai pas pu associer ce message à un ticket. "
            "Répondez directement au message de la carte du ticket pour le résoudre."
        )
        return

    # `message.text` is None for any non-text reply (photo, sticker, voice,
    # video, animation, ...) - `.strip()` on it used to crash the handler.
    # Fall back to the media's caption (an agent attaching a screenshot with
    # an explanation is a normal workflow), then to a Whisper transcription
    # for a voice/audio reply, before giving up.
    solution_text = (message.text or message.caption or "").strip()

    if not solution_text and (message.voice or message.audio):
        transcribed = await _transcribe_voice_message(message, bot)
        if transcribed:
            solution_text = transcribed
            await message.reply(
                f"🎙️ Message vocal transcrit automatiquement :\n\n_{solution_text}_",
                parse_mode="Markdown",
            )

    if not solution_text:
        await message.reply(
            "⚠️ Je ne peux résoudre un ticket qu'à partir d'un texte (ou d'une légende, ou d'un "
            "vocal transcrit automatiquement si l'IA OpenAI est configurée). Réécrivez votre "
            "solution en texte, ou ajoutez-la en légende de votre média."
        )
        return

    agent_name = (
        message.from_user.username
        or f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        or f"Agent_{message.from_user.id}"
    )

    try:
        # Resolve ticket and trigger KB ingestion
        resolved_ticket = await client.resolve_ticket(
            ticket_id=ticket_id,
            solution=solution_text,
            resolved_by=agent_name,
            add_to_knowledge_base=True,
        )

        if resolved_ticket.get("is_newly_resolved") is False:
            already_by = escape_telegram_markdown(resolved_ticket.get("resolved_by") or "un autre agent")
            await message.reply(
                f"ℹ️ **Ticket #{ticket_id} déjà résolu !**\n"
                f"Ce ticket a déjà été résolu par *{already_by}*.\n"
                f"Votre réponse n'a pas été renvoyée à l'utilisateur pour éviter les doublons.",
                parse_mode="Markdown",
            )
            return

        user_id = target_user_id or resolved_ticket.get("user_id")

        # 1. Forward the solution to the user via Telegram
        if user_id:
            safe_solution = escape_telegram_markdown(solution_text)
            safe_agent = escape_telegram_markdown(agent_name)
            user_notification = (
                f"📬 **Réponse de l'équipe support (Ticket #{ticket_id})**\n\n"
                f"{safe_solution}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"Traité par : *{safe_agent}*\n"
                f"Merci de votre confiance ! 👋"
            )
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=user_notification,
                    parse_mode="Markdown",
                )
            except Exception as send_err:
                logger.warning("Markdown send failed for user %s, retrying in plain text: %s", user_id, send_err)
                plain_notification = (
                    f"📬 Réponse de l'équipe support (Ticket #{ticket_id})\n\n"
                    f"{solution_text}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"Traité par : {agent_name}\n"
                    f"Merci de votre confiance ! 👋"
                )
                await bot.send_message(
                    chat_id=user_id,
                    text=plain_notification,
                )

        # 2. Confirm to the support team in group
        await message.reply(
            f"✅ **Ticket #{ticket_id} résolu !**\n"
            f"• La réponse a été transmise à l'utilisateur (`ID: {user_id}`).\n"
            f"• La solution a été automatiquement intégrée dans la base de connaissances.",
            parse_mode="Markdown",
        )

    except Exception as exc:
        logger.error("Error resolving ticket %s via group reply: %s", ticket_id, exc)
        await message.reply(
            f"❌ **Erreur lors de la résolution du ticket #{ticket_id}** : {exc}"
        )
