## 1. Configuration and persistence

- [x] 1.1 Add `BOT_OWNER_TELEGRAM_ID` to `backend/config.py` `Settings`; verify with a unit test for unset (no owner) vs. configured cases.
- [x] 1.2 Add `BotSetting` and `BotAdminWhitelist` models to `backend/models.py` and an Alembic migration for both (additive only); verify `alembic upgrade head` applies cleanly on a fresh SQLite DB.
- [x] 1.3 Add `BotSettingsService` (`get_value`/`set_value` by key, e.g. `community_group_id`, `language`) and `WhitelistService` (`add`, `remove`, `is_whitelisted`, `list`); verify with unit tests covering set/get, add/remove, and idempotent re-add.
- [x] 1.4 Add backend endpoints under `/api/admin/settings` and `/api/admin/whitelist` (protected by `verify_api_key`) wrapping those services; verify with integration tests hitting the endpoints against a test DB, including auth-required checks.
- [x] 1.5 Add corresponding `BackendClient` methods (`get_setting`, `set_setting`, `whitelist_add`, `whitelist_remove`, `is_whitelisted`); verify by exercising them against the test app via `httpx.ASGITransport` (same pattern as existing `BackendClient` tests).

## 2. Bot access control (owner + whitelist)

- [x] 2.1 Add `bot/access_control.py` with `is_authorized(user_id) -> bool` (owner id check first, no I/O; falls back to a short-TTL cached whitelist lookup) per design.md decision 4; verify with unit tests covering owner, whitelisted, non-whitelisted, and cache-hit behavior.
- [x] 2.2 Add `/whitelist add <user_id>` / `/whitelist remove <user_id>` in a new `bot/handlers/setup_handlers.py`, usable only by the owner (not by whitelisted admins); verify with tests for owner success, whitelisted-admin rejection, and non-authorized rejection, and that the in-memory whitelist cache is invalidated on a successful change.

## 3. Community group setup

- [x] 3.1 Add `/setup_community`, usable only by an authorized user (bot-access-control), that persists the invoking chat's id as `community_group_id` via `BotSettingsService`/`BackendClient`, replacing any previous value; verify with tests for authorized success, unauthorized rejection, and that reconfiguring replaces the prior value.
- [x] 3.2 Update `bot/group_scope.py`'s `is_community_group_chat` to resolve the community group id from the persisted setting (short-TTL cache per design.md decision 3, invalidated immediately on a successful `/setup_community`) instead of `settings.TELEGRAM_COMMUNITY_GROUP_ID`; verify with tests that behavior follows a live reconfiguration without a restart, and that the previous community group stops matching once replaced.
- [x] 3.3 Add the first-contact `/start` tutorial branch in `setup_handlers.py`: for an authorized user with no community group configured yet, show the setup tutorial instead of (or alongside) the normal welcome message; verify with a test that an authorized user with no community group configured sees the tutorial, and that a configured deployment or a non-authorized user sees the normal welcome message.
- [x] 3.4 On backend startup, if `community_group_id` has never been set and the legacy `TELEGRAM_COMMUNITY_GROUP_ID` env var is present, seed the persisted setting from it once and log that this happened; verify with a test that seeding occurs only when the persisted value is absent, and never overwrites an existing persisted value.
- [x] 3.5 Register `setup_handlers`'s router in `bot/main.py`; verify existing community/moderation tests still pass with `bot/group_scope.py`'s new resolution path (update their fixtures/monkeypatches as needed).

## 4. Bot localization (FR/EN)

- [x] 4.1 Add `bot/i18n.py` with a flat `{key: {"fr": ..., "en": ...}}` translation table and a `t(key, lang, **kwargs)` helper; verify with unit tests for known keys in both languages, `str.format` substitution, and a missing-key fallback that doesn't crash.
- [x] 4.2 Add the language command (e.g. `/language en|fr`), usable only by an authorized user, persisting via `BotSettingsService`; verify with tests for authorized success, unauthorized rejection, and an invalid language argument.
- [x] 4.3 Refactor `bot/handlers/user_handlers.py`, `support_handlers.py`, `community_handlers.py`, `moderation_handlers.py`, `crypto_handlers.py`, and `setup_handlers.py` to source every bot-authored user-facing string through `t(...)` using the active language (same cached-lookup pattern as the community group id); verify with tests asserting at least one representative message per handler module renders in English when the language is set to English, and that existing French-language assertions in prior tests still pass when the language is (still) French. (Also added a conftest.py autouse fixture resetting the language/community-group/whitelist in-memory caches between tests, after discovering a real cross-test leak: an "en"-language test bled into later French-asserting tests via the process-wide language cache.)

## 5. Documentation and end-to-end verification

- [x] 5.1 Update `.env.example` and `README.md`: add `BOT_OWNER_TELEGRAM_ID`, mark `TELEGRAM_COMMUNITY_GROUP_ID` as a legacy one-time-seed value (not required for new deployments), and document `/setup_community`, `/whitelist`, and the language command; verify by re-reading both files for consistency with `backend/config.py`. (Also fixed a real bug found while doing this: `BOT_OWNER_TELEGRAM_ID` is `Optional[int]`, and pydantic-settings raised a `ValidationError` at import time for a blank `.env` value — added a `field_validator` treating blank as unset, with a regression test.)
- [x] 5.2 Run the full test suite (`pytest`) and confirm all existing and new tests pass, including that community-qa/community-moderation tests exercise the dynamic (not env-based) group resolution path. (376/376 passed.)
