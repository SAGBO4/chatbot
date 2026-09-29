"""Bot settings and the admin whitelist."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.observability import get_logger
from app.openapi_docs import PROTECTED, error_responses
from app.schemas import (
    BotSettingRequest,
    BotSettingResponse,
    WhitelistAddRequest,
    WhitelistCheckResponse,
    WhitelistEntryResponse,
    WhitelistListResponse,
    WhitelistRemoveResponse,
)
from app.security import verify_api_key
from app.services.bot_settings_service import BotSettingsService, WhitelistService

logger = get_logger(__name__)
router = APIRouter(tags=["admin"], responses=PROTECTED)


@router.get(
    "/api/admin/settings/{key}",
    response_model=BotSettingResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_bot_setting(key: Annotated[str, Path(description="Setting name: `language` or `community_group_id`.")], session: AsyncSession = Depends(get_db)):
    """Read a persisted bot setting."""
    value = await BotSettingsService.get_value(session=session, key=key)
    return BotSettingResponse(key=key, value=value)


@router.put(
    "/api/admin/settings/{key}",
    response_model=BotSettingResponse,
    dependencies=[Depends(verify_api_key)],
)
async def set_bot_setting(
    key: Annotated[str, Path(description="Setting name: `language` or `community_group_id`.")],
    payload: BotSettingRequest,
    session: AsyncSession = Depends(get_db),
):
    """Create or update a persisted bot setting."""
    setting = await BotSettingsService.set_value(
        session=session, key=key, value=payload.value, updated_by=payload.updated_by
    )
    return BotSettingResponse(key=setting.key, value=setting.value)


@router.post(
    "/api/admin/whitelist",
    response_model=WhitelistEntryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def add_whitelist_entry(
    payload: WhitelistAddRequest,
    session: AsyncSession = Depends(get_db),
):
    """Add a user to the admin whitelist."""
    return await WhitelistService.add(session=session, user_id=payload.user_id, added_by=payload.added_by)


@router.delete(
    "/api/admin/whitelist/{user_id}",
    dependencies=[Depends(verify_api_key)],
    responses={200: {"model": WhitelistRemoveResponse}, **error_responses({404: "This user is not in the whitelist."})},
)
async def remove_whitelist_entry(user_id: Annotated[int, Path(description="Telegram id of the user to remove.")], session: AsyncSession = Depends(get_db)):
    """Remove a user from the admin whitelist (404 if not listed)."""
    removed = await WhitelistService.remove(session=session, user_id=user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Whitelist entry not found")
    return {"removed": True, "user_id": user_id}


@router.get(
    "/api/admin/whitelist",
    response_model=WhitelistListResponse,
    dependencies=[Depends(verify_api_key)],
)
async def list_whitelist_entries(session: AsyncSession = Depends(get_db)):
    """List the admin whitelist."""
    entries = await WhitelistService.list_entries(session=session)
    return WhitelistListResponse(entries=entries)


@router.get(
    "/api/admin/whitelist/{user_id}/check",
    response_model=WhitelistCheckResponse,
    dependencies=[Depends(verify_api_key)],
)
async def check_whitelist_entry(user_id: Annotated[int, Path(description="Telegram id of the user to check.")], session: AsyncSession = Depends(get_db)):
    """Whether a user counts as admin: the bot owner always does, everyone else must be whitelisted."""
    is_whitelisted = settings.is_bot_owner(user_id) or await WhitelistService.is_whitelisted(session=session, user_id=user_id)
    return WhitelistCheckResponse(user_id=user_id, is_whitelisted=is_whitelisted)
