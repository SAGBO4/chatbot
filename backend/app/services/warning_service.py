from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CommunityWarning


class WarningService:
    """Moderation warnings issued to a user within a community group."""

    @staticmethod
    async def add_warning(
        session: AsyncSession,
        user_id: int,
        group_id: int,
        warned_by: str,
        reason: Optional[str] = None,
    ) -> CommunityWarning:
        """Record a warning; a blank `reason` is stored as null."""
        warning = CommunityWarning(
            user_id=user_id,
            group_id=group_id,
            warned_by=warned_by,
            reason=reason.strip() if reason else None,
        )
        session.add(warning)
        await session.commit()
        await session.refresh(warning)
        return warning

    @staticmethod
    async def list_warnings(
        session: AsyncSession, user_id: int, group_id: int
    ) -> List[CommunityWarning]:
        """A user's warnings in a group, newest first."""
        result = await session.execute(
            select(CommunityWarning)
            .where(CommunityWarning.user_id == user_id, CommunityWarning.group_id == group_id)
            .order_by(CommunityWarning.id.desc())
        )
        return list(result.scalars().all())
