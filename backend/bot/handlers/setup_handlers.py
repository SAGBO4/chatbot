import logging
from typing import Optional
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from bot.access_control import is_authorized, is_owner, invalidate_whitelist_cache
from bot.api_client import BackendClient
from bot.group_scope import invalidate_community_group_cache, get_community_group_id
from bot.language import get_active_language, invalidate_language_cache
from app.i18n import t, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)
setup_router = Router()


async def _should_show_setup_tutorial(message: Message) -> bool:
    """
    Filter: a private /start from the owner or a whitelisted admin while no community group is set.

    Being a filter (not a check in the handler) lets every other /start fall through to the normal
    welcome in user_handlers.handle_start.
    """
    if message.chat.type != "private":
        return False
    if not await is_authorized(message.from_user.id):
        return False
    return await get_community_group_id() is None


@setup_router.message(CommandStart(), _should_show_setup_tutorial)
async def handle_start_setup_tutorial(
    message: Message,
    state: FSMContext,
    backend_client: Optional[BackendClient] = None,
):
    """Show the community group setup tutorial."""
    await state.clear()
    lang = await get_active_language(backend_client=backend_client)
    await message.answer(t("setup_tutorial", lang), parse_mode="Markdown")


def _parse_whitelist_args(args: Optional[str]):
    """Parse `add|remove <user_id>` into `(action, user_id)`, or `(None, None)` if it is malformed."""
    parts = (args or "").split()
    if len(parts) != 2:
        return None, None
    action, raw_user_id = parts[0].lower(), parts[1]
    if action not in ("add", "remove") or not raw_user_id.lstrip("-").isdigit():
        return None, None
    return action, int(raw_user_id)


@setup_router.message(Command("whitelist"))
async def handle_whitelist(
    message: Message,
    command: CommandObject,
    backend_client: Optional[BackendClient] = None,
):
    """
    `/whitelist add|remove <user_id>`, owner only: manage who may configure the community group and
    the language. A whitelisted admin cannot manage the whitelist themselves.
    """
    requester_id = message.from_user.id
    lang = await get_active_language(backend_client=backend_client)
    if not await is_owner(requester_id):
        await message.reply(t("setup_not_owner", lang))
        return

    action, target_user_id = _parse_whitelist_args(command.args)
    if action is None:
        await message.reply(t("setup_whitelist_usage", lang), parse_mode="Markdown")
        return

    client = backend_client or BackendClient()
    requester_name = message.from_user.username or message.from_user.first_name or f"Owner_{requester_id}"

    if action == "add":
        try:
            await client.whitelist_add(target_user_id, added_by=requester_name)
        except Exception as exc:
            logger.error("Failed to add %s to whitelist: %s", target_user_id, exc)
            await message.reply(t("setup_whitelist_add_error", lang, user_id=target_user_id))
            return
        invalidate_whitelist_cache(target_user_id)
        await message.reply(t("setup_whitelist_added", lang, user_id=target_user_id), parse_mode="Markdown")
    else:
        try:
            removed = await client.whitelist_remove(target_user_id)
        except Exception as exc:
            logger.error("Failed to remove %s from whitelist: %s", target_user_id, exc)
            await message.reply(t("setup_whitelist_remove_error", lang, user_id=target_user_id))
            return
        invalidate_whitelist_cache(target_user_id)
        if removed:
            await message.reply(t("setup_whitelist_removed", lang, user_id=target_user_id), parse_mode="Markdown")
        else:
            await message.reply(t("setup_whitelist_not_present", lang, user_id=target_user_id), parse_mode="Markdown")


@setup_router.message(Command("setup_community"))
async def handle_setup_community(
    message: Message,
    backend_client: Optional[BackendClient] = None,
):
    """
    `/setup_community`: make the group it is sent in the active community group (owner or
    whitelisted admin only).

    The target is always the current chat, so there is no group id to mistype or forge.
    """
    requester_id = message.from_user.id
    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)
    if not await is_authorized(requester_id, backend_client=client):
        await message.reply(t("setup_not_authorized", lang))
        return

    if message.chat.type not in ("group", "supergroup"):
        await message.reply(t("setup_community_group_usage", lang), parse_mode="Markdown")
        return

    requester_name = message.from_user.username or message.from_user.first_name or f"User_{requester_id}"
    try:
        await client.set_setting("community_group_id", str(message.chat.id), updated_by=requester_name)
    except Exception as exc:
        logger.error("Failed to configure community group %s: %s", message.chat.id, exc)
        await message.reply(t("setup_community_group_error", lang))
        return

    invalidate_community_group_cache()
    await message.reply(t("setup_community_group_success", lang))


@setup_router.message(Command("language"))
async def handle_language(
    message: Message,
    command: CommandObject,
    backend_client: Optional[BackendClient] = None,
):
    """`/language fr|en`: set the language of every bot message (owner or whitelisted admin only)."""
    requester_id = message.from_user.id
    client = backend_client or BackendClient()
    current_lang = await get_active_language(backend_client=client)
    if not await is_authorized(requester_id, backend_client=client):
        await message.reply(t("setup_not_authorized", current_lang))
        return

    requested = (command.args or "").strip().lower()
    if requested not in SUPPORTED_LANGUAGES:
        await message.reply(t("setup_language_usage", current_lang), parse_mode="Markdown")
        return

    requester_name = message.from_user.username or message.from_user.first_name or f"User_{requester_id}"
    try:
        await client.set_setting("language", requested, updated_by=requester_name)
    except Exception as exc:
        logger.error("Failed to change bot language to %s: %s", requested, exc)
        await message.reply(t("setup_language_usage", current_lang), parse_mode="Markdown")
        return

    invalidate_language_cache()
    await message.reply(t("setup_language_changed", requested, language=requested))
