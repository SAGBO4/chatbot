## Why

The community group is currently a fixed `.env` value (`TELEGRAM_COMMUNITY_GROUP_ID`), so pointing the bot at a community requires a redeploy. The owner wants to (re)configure the community group at any time through a guided in-bot tutorial instead, without redeploying — while keeping the admin/support group (`TELEGRAM_SUPPORT_GROUP_ID`) fixed via `.env`, since letting that group be reconfigured from inside Telegram would let a malicious actor redirect ticket/resolution traffic and corrupt stored data. The owner also wants a small, owner-controlled access-control layer (an env-defined owner who can whitelist additional admins) to gate who may run that configuration, and wants the bot's messages available in both French and English.

## What Changes

- Introduce a bot owner, identified by a fixed Telegram user id in `.env` (`BOT_OWNER_TELEGRAM_ID`), who is always authorized to configure the community group and manage a whitelist of additional authorized admins.
- Add `/whitelist add|remove <user_id>` (owner-only) to grant/revoke other Telegram users the right to configure the community group. Whitelisted admins cannot manage the whitelist themselves.
- Replace the static `TELEGRAM_COMMUNITY_GROUP_ID` env var with a dynamically configurable, persisted community group id: an owner or whitelisted admin runs a guided setup command/tutorial (in DM, and confirmed from the target group) to set or change the active community group at any time. `TELEGRAM_SUPPORT_GROUP_ID` (the admin group) is unaffected and stays env-fixed.
- On first contact with the bot (`/start` in DM) an owner or whitelisted admin who hasn't configured a community group yet is shown a short guided tutorial explaining the setup steps.
- **BREAKING**: `community-qa`, `community-moderation`, and their `/purge` command no longer read `TELEGRAM_COMMUNITY_GROUP_ID` from settings; they resolve the active community group from the persisted, dynamically-configurable value instead. A deployment that only set the old env var must run the new setup flow once after upgrading.
- Add bilingual bot messages (French and English): all bot-authored text becomes translatable, with a bot-wide language setting that the owner or a whitelisted admin can change; French remains the default to match current behavior.

## Capabilities

### New Capabilities
- `bot-access-control`: env-defined owner + owner-managed whitelist of additional admins authorized to configure the bot.
- `community-group-setup`: guided tutorial and command(s) to set/change the active, persisted community group at any time, restricted to the owner/whitelisted admins.
- `bot-localization`: bot-wide language setting (French/English) for all bot-authored messages, changeable by the owner/whitelisted admins.

### Modified Capabilities
- `community-qa`: the community group the Q&A trigger, resolution buttons, and `/purge` operate in is resolved from the dynamically configured value instead of a fixed env var.
- `community-moderation`: the community group moderation commands are scoped to is resolved from the dynamically configured value instead of a fixed env var.

## Impact

- **backend/config.py**: add `BOT_OWNER_TELEGRAM_ID`; remove `TELEGRAM_COMMUNITY_GROUP_ID`/`community_group_is_configured()` as the source of truth (kept only as a one-time migration input, see design.md).
- **backend/models.py / alembic**: new tables for the admin whitelist, the persisted active community group, and the bot language setting.
- **bot/group_scope.py**: `is_community_group_chat` resolves against the persisted value instead of `settings.TELEGRAM_COMMUNITY_GROUP_ID`.
- **bot/handlers/**: new `setup_handlers.py` (tutorial, configure command, `/whitelist`, language command); `community_handlers.py`, `moderation_handlers.py` updated to resolve the community group dynamically.
- **New i18n layer**: bot-authored strings move behind a translation lookup keyed by the bot-wide language setting.
- **.env.example / README**: document `BOT_OWNER_TELEGRAM_ID`, remove `TELEGRAM_COMMUNITY_GROUP_ID` as a required setup step, document the new `/configurer`(`/setup`)/`/whitelist`/language commands.
