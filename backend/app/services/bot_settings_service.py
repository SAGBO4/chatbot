import logging
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.i18n import DEFAULT_LANGUAGE
from app.models import BotSetting, BotAdminWhitelist

logger = logging.getLogger(__name__)

COMMUNITY_GROUP_ID_KEY = "community_group_id"
LANGUAGE_KEY = "language"


class BotSettingsService:
    """Key/value settings persisted in the database (community group id, language)."""

    @staticmethod
    async def get_value(session: AsyncSession, key: str) -> Optional[str]:
        """The stored value, or None when the key was never set."""
        result = await session.execute(select(BotSetting).where(BotSetting.key == key))
        setting = result.scalars().first()
        return setting.value if setting else None

    @staticmethod
    async def set_value(
        session: AsyncSession, key: str, value: Optional[str], updated_by: Optional[str] = None
    ) -> BotSetting:
        """Create or update a setting."""
        result = await session.execute(select(BotSetting).where(BotSetting.key == key))
        setting = result.scalars().first()
        if setting is None:
            setting = BotSetting(key=key, value=value, updated_by=updated_by)
            session.add(setting)
        else:
            setting.value = value
            setting.updated_by = updated_by
        await session.commit()
        await session.refresh(setting)
        return setting

    @classmethod
    async def get_community_group_id(cls, session: AsyncSession) -> Optional[int]:
        raw = await cls.get_value(session, COMMUNITY_GROUP_ID_KEY)
        return int(raw) if raw is not None else None

    @classmethod
    async def set_community_group_id(
        cls, session: AsyncSession, group_id: int, updated_by: Optional[str] = None
    ) -> None:
        await cls.set_value(session, COMMUNITY_GROUP_ID_KEY, str(group_id), updated_by=updated_by)

    @classmethod
    async def get_language(cls, session: AsyncSession) -> str:
        raw = await cls.get_value(session, LANGUAGE_KEY)
        return raw or DEFAULT_LANGUAGE

    @classmethod
    async def set_language(cls, session: AsyncSession, language: str, updated_by: Optional[str] = None) -> None:
        await cls.set_value(session, LANGUAGE_KEY, language, updated_by=updated_by)

    @classmethod
    async def seed_legacy_community_group(
        cls, session: AsyncSession, legacy_group_id: int
    ) -> bool:
        """
        One-time seed of the persisted community_group_id from the legacy
        TELEGRAM_COMMUNITY_GROUP_ID env var, so an upgrading deployment
        doesn't silently lose its community group. Only seeds when no
        persisted value exists yet; never overwrites an existing one.
        Returns True if seeding happened.
        """
        existing = await cls.get_value(session, COMMUNITY_GROUP_ID_KEY)
        if existing is not None:
            return False
        await cls.set_community_group_id(session, legacy_group_id, updated_by="legacy_env_seed")
        logger.info(
            "Seeded persisted community_group_id=%s from legacy TELEGRAM_COMMUNITY_GROUP_ID env var.",
            legacy_group_id,
        )
        return True


class WhitelistService:
    """Users allowed to run admin commands, on top of the bot owner who always is."""

    @staticmethod
    async def add(session: AsyncSession, user_id: int, added_by: str) -> BotAdminWhitelist:
        """Add a user; adding one who is already listed returns the existing entry."""
        result = await session.execute(select(BotAdminWhitelist).where(BotAdminWhitelist.user_id == user_id))
        entry = result.scalars().first()
        if entry is not None:
            return entry
        entry = BotAdminWhitelist(user_id=user_id, added_by=added_by)
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return entry

    @staticmethod
    async def remove(session: AsyncSession, user_id: int) -> bool:
        """Remove a user; False if they were not listed."""
        result = await session.execute(select(BotAdminWhitelist).where(BotAdminWhitelist.user_id == user_id))
        entry = result.scalars().first()
        if entry is None:
            return False
        await session.delete(entry)
        await session.commit()
        return True

    @staticmethod
    async def is_whitelisted(session: AsyncSession, user_id: int) -> bool:
        result = await session.execute(select(BotAdminWhitelist).where(BotAdminWhitelist.user_id == user_id))
        return result.scalars().first() is not None

    @staticmethod
    async def list_entries(session: AsyncSession) -> List[BotAdminWhitelist]:
        """All entries, oldest first."""
        result = await session.execute(select(BotAdminWhitelist).order_by(BotAdminWhitelist.created_at.asc()))
        return list(result.scalars().all())
