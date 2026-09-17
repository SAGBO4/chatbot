## Context

See `proposal.md` for motivation. Relevant current state:

- `backend/config.py` has `TELEGRAM_COMMUNITY_GROUP_ID` (static env) and `community_group_is_configured()`; `bot/group_scope.py`'s `is_community_group_chat` reads it synchronously with zero I/O, called on every incoming group message/command in `community_handlers.py` and `moderation_handlers.py`.
- `TELEGRAM_SUPPORT_GROUP_ID` (the admin group) stays exactly as-is - untouched by this change, per the user's explicit requirement that only the community group becomes dynamic, to avoid a malicious actor redirecting ticket/resolution/moderation-log traffic.
- All bot-authored strings are hardcoded French f-strings scattered across `bot/handlers/*.py` (no existing i18n layer).
- Persisted, admin-managed state already follows one pattern in this project: a SQLAlchemy model + Alembic migration + a thin `*Service` class + (where the bot needs it) a `BackendClient` method calling a backend endpoint (see `WarningService`/`community_warnings` from the previous change).

## Goals / Non-Goals

**Goals:**
- Let an authorized owner/admin (re)point the community group at any time without a redeploy.
- Keep the admin group's trust model exactly as strong as today (env-only, operator-controlled).
- Cover all bot-authored user-facing text with FR/EN translations.

**Non-Goals:**
- No true multi-tenancy (multiple independent communities on one bot instance) - there is exactly one active community group at a time, paired with the one fixed admin group.
- No per-chat or per-user language preference - the language setting is bot-wide.
- No self-service group pairing between two arbitrary groups (the earlier multi-tenant "linking code" idea is dropped): authorization comes from bot-access-control (owner/whitelist), not from proving control of both groups.

## Decisions

### 1. Configuration is run directly inside the target group, not via a pairing code
Since the admin group stays fixed and trusted, there is no second group to cross-link and no need for the linking-code mechanism considered in the earlier (dropped) multi-tenant draft. An authorized user (owner or whitelisted admin) simply runs `/setup_community` **inside** the Telegram group they want to become the active community group; the bot reads that command's own `chat.id` as the target, checks the sender's authorization via bot-access-control, and persists it. This is simpler and removes an entire class of pairing-flow bugs. Alternative considered: configure by pasting a numeric group id from DM (mirrors the current `.env` tip) - kept as a fallback for an admin who cannot easily get the bot to respond inside the group yet (e.g. before granting it admin rights), documented in the tutorial, but the in-group command is the primary path.

### 2. Persisted state: two small tables, following the existing service-layer pattern
- `bot_settings`: a simple key/value table (`key` unique, `value`, `updated_at`, `updated_by`) holding `community_group_id` and `language` - avoids two near-identical single-row tables for two loosely related scalar settings.
- `bot_admin_whitelist`: `(user_id unique, added_by, created_at)` - a list, so a proper table rather than a settings row.
Both get a thin service (`BotSettingsService`, `WhitelistService`) mirroring `WarningService`, and backend endpoints under `/api/admin/...` (protected by the existing `verify_api_key`) that the bot calls via `BackendClient`, consistent with how every other piece of bot-visible persisted state is read/written today.

### 3. Short-TTL in-memory cache for the community group id, invalidated on write
`is_community_group_chat` runs on every group message/command, so it cannot afford a DB round-trip each time. Mirroring `bot/admin_check.py`'s pattern, the bot process caches the resolved community group id for a short TTL (e.g. 30s) and additionally invalidates that cache immediately whenever `/setup_community` succeeds in the same process, so the requirement "community-qa and community-moderation commands immediately apply to the newly configured group" holds without waiting out the TTL in the common case (the admin configuring it and testing it are the same process). A stale read past a reconfiguration from a different process (e.g. a second bot replica) self-heals within the TTL.

### 4. Authorization check order: owner id first (no I/O), then whitelist (cached DB read)
`BOT_OWNER_TELEGRAM_ID` is a plain settings comparison (no I/O, cannot be bypassed by whitelist data corruption). Only if the sender isn't the owner does the bot consult the whitelist, cached with the same short-TTL pattern as decision 3. This keeps the owner's authority independent of the database even if the whitelist table were somehow corrupted - directly addressing the user's stated concern.

### 5. i18n: a flat translation-key module, not a template engine
`bot/i18n.py` holds a dict `{key: {"fr": "...", "en": "..."}}` and a `t(key, lang, **kwargs)` helper doing `str.format` substitution. Every hardcoded string in `bot/handlers/*.py` that is sent to a Telegram chat is replaced by a call to `t(...)` with the bot-wide language (resolved via the same cached settings lookup as the community group id). Alternative considered: a full i18n library (e.g. `gettext`) - rejected as disproportionate for a bounded, known set of bot messages; a flat dict keeps translations reviewable in one file.

### 6. Legacy `TELEGRAM_COMMUNITY_GROUP_ID` becomes a one-time seed, then ignored
On startup, if `bot_settings.community_group_id` has never been set and the legacy `TELEGRAM_COMMUNITY_GROUP_ID` env var is still present, the bot seeds the persisted value from it once (so upgrading an existing deployment doesn't silently disable community features) and logs that it did so. After that first seed, the env var is never consulted again - `/setup_community` is the only way to change it going forward.

## Risks / Trade-offs

- **[Risk]** The short-TTL cache (decisions 3-4) means a reconfiguration from a different bot replica/process can take up to the TTL to apply elsewhere. **Mitigation**: TTL kept short (~30s); acceptable for an admin-driven, infrequent operation, and each process converges independently without coordination.
- **[Risk]** Moving the community group off a fixed env var means a compromised owner account (or a compromised whitelist entry) can redirect the community group. **Mitigation**: this is the accepted trade-off requested by the user (community group only, not the admin group); the owner id itself stays env-controlled and out of reach of any in-bot command.
- **[Trade-off]** Full FR/EN coverage (decision 5) touches every existing user-facing string across `bot/handlers/*.py`, a broad but mechanical refactor with no behavior change beyond language selection.

## Migration Plan

1. Add `BOT_OWNER_TELEGRAM_ID` to `backend/config.py`; keep `TELEGRAM_COMMUNITY_GROUP_ID` read-only as the one-time seed input (decision 6), remove it from new documentation as an ongoing requirement.
2. Alembic migration adding `bot_settings` and `bot_admin_whitelist` (additive only).
3. Add `BotSettingsService`/`WhitelistService` + backend endpoints; add corresponding `BackendClient` methods.
4. Add `bot/i18n.py` and the FR/EN translation table; refactor `bot/handlers/*.py` strings to use it, resolving the active language per decision 3's cache.
5. Add `bot/handlers/setup_handlers.py`: `/start` tutorial branch, `/setup_community`, `/whitelist add|remove`, language command - all gated by bot-access-control.
6. Update `bot/group_scope.py` to resolve the community group dynamically (with the cache from decision 3) instead of `settings.TELEGRAM_COMMUNITY_GROUP_ID`.
7. Update `.env.example`/README: document `BOT_OWNER_TELEGRAM_ID`, mark `TELEGRAM_COMMUNITY_GROUP_ID` as legacy/one-time-seed-only, document the new commands.
8. Rollback: additive migration only; reverting the code leaves the persisted settings unused (the bot falls back to requiring `TELEGRAM_COMMUNITY_GROUP_ID` again once the old code is restored).

## Open Questions

- Exact literal command names (`/setup_community` vs `/configurer`) and exact tutorial copy - implementation-time detail, doesn't affect the specs or task breakdown.
- Whether `/whitelist` and the language command are usable from DM only or also from the admin group - either satisfies the specs (which only constrain *who*, not *where*); resolved in design decision terms only as "not the community group," left to implementation.
