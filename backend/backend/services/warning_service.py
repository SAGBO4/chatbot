from typing import List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import CommunityWarning


class WarningService:
    @staticmethod
    async def add_warning(
        session: AsyncSession,
        user_id: int,
        group_id: int,
        warned_by: str,
        reason: str = None,
    ) -> CommunityWarning:
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
        result = await session.execute(
            select(CommunityWarning)
            .where(CommunityWarning.user_id == user_id, CommunityWarning.group_id == group_id)
            .order_by(CommunityWarning.id.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_warnings(session: AsyncSession, user_id: int, group_id: int) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(CommunityWarning)
            .where(CommunityWarning.user_id == user_id, CommunityWarning.group_id == group_id)
        )
        return int(result.scalar_one())
