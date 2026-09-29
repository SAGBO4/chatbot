"""Moderation warnings issued in the community group."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.observability import get_logger
from app.openapi_docs import PROTECTED
from app.schemas import WarningCreateRequest, WarningListResponse, WarningResponse
from app.security import verify_api_key
from app.services.warning_service import WarningService

logger = get_logger(__name__)
router = APIRouter(tags=["moderation"], responses=PROTECTED)


@router.post(
    "/api/moderation/warnings",
    response_model=WarningResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def create_warning(
    payload: WarningCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    """Record a moderation warning for a user in a group."""
    return await WarningService.add_warning(
        session=session,
        user_id=payload.user_id,
        group_id=payload.group_id,
        warned_by=payload.warned_by,
        reason=payload.reason,
    )


@router.get(
    "/api/moderation/warnings",
    response_model=WarningListResponse,
    dependencies=[Depends(verify_api_key)],
)
async def list_warnings(
    user_id: int = Query(..., description="Telegram user id to look up warnings for"),
    group_id: int = Query(..., description="Telegram group id the warnings were issued in"),
    session: AsyncSession = Depends(get_db),
):
    """List a user's warnings in a group, with their count."""
    warnings = await WarningService.list_warnings(session=session, user_id=user_id, group_id=group_id)
    return WarningListResponse(count=len(warnings), warnings=warnings)
