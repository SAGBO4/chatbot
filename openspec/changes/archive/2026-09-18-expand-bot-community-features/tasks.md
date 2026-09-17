## 1. Configuration

- [x] 1.1 Add `TELEGRAM_COMMUNITY_GROUP_ID`, `COMMUNITY_RESOLUTION_TIMEOUT_SECONDS`, `CRYPTO_PROVIDER_TIMEOUT_SECONDS`, `CRYPTO_CACHE_TTL_SECONDS` to `backend/config.py` `Settings`, and add a `community_group_is_configured()` helper mirroring `support_group_is_configured()`; verify with a unit test asserting default (unconfigured) and configured cases. (No default-mute-duration setting: the `community-moderation` spec requires `/mute` with no duration to mute indefinitely, so no default-duration config is introduced.)
- [x] 1.2 Document the new variables in `.env.example` and the required bot admin permissions (restrict members, ban users, delete messages) in `README.md`; verify by re-reading both files for consistency with `backend/config.py`.

## 2. Persistence for moderation warnings

- [x] 2.1 Add a `CommunityWarning` model to `backend/models.py` (`user_id`, `group_id`, `reason`, `warned_by`, `created_at`) and an Alembic migration for it; verify `alembic upgrade head` applies cleanly on a fresh SQLite DB.
- [x] 2.2 Add `WarningService` (or extend an existing service module) with `add_warning` and `count_warnings`/`list_warnings`; verify with unit tests covering creation and per-user counting.
- [x] 2.3 Add backend endpoints (`POST`/`GET` under `/api/moderation/warnings`, protected by `verify_api_key` like existing endpoints) so the bot can record and read warnings; verify with an integration test hitting the endpoints against a test DB.

## 3. Community group Q&A entry point

- [x] 3.1 Add the group trigger command handler in a new `bot/handlers/community_handlers.py`, scoped to `F.chat.id == settings.TELEGRAM_COMMUNITY_GROUP_ID`, that calls the same backend query pipeline as `user_handlers.handle_user_query`; verify with a unit test that a triggered message reaches `BackendClient.query` and a non-triggered group message does not.
- [x] 3.2 Extract the shared "post answer + YES/NO keyboard" and "escalate to ticket" logic from `user_handlers.py` into a small shared helper usable by both the DM and community handlers, tagging the asking member and posting only a neutral acknowledgement (never ticket internals) into the community group on escalation; verify with unit tests for both the DM and community code paths, and confirm no ticket-card/solution text appears in any community-group message sent during the escalation test.
- [x] 3.3 Implement expiring resolution buttons: schedule an `asyncio` task per group-triggered answer that disables/removes the keyboard after `COMMUNITY_RESOLUTION_TIMEOUT_SECONDS`, and store the answer's timestamp in FSM state so the YES/NO callback handlers reject a stale click even if the scheduled edit hasn't run yet; verify with a test using a short timeout that confirms the keyboard is disabled after expiry and that a callback after expiry is rejected without creating a ticket or resolving.
- [x] 3.4 Implement `/purge` in the community group, admin-verified (see task 4.1's helper), deleting a bounded number of the bot's recent messages via `bot.delete_message`; verify with a test that a non-admin invocation deletes nothing and an admin invocation deletes the requested count.
- [x] 3.5 Register the new router in `bot/main.py`'s `create_dispatcher`, guarded so it only activates meaningfully when `community_group_is_configured()` is true; verify existing DM-only tests still pass unchanged.

## 4. Community moderation commands

- [x] 4.1 Add an admin-verification helper (`bot.get_chat_member` check for `administrator`/`creator`, with a short in-memory TTL cache keyed by `(group_id, user_id)`) shared by moderation and `/purge` handlers; verify with a unit test covering admin, non-admin, and cache-hit behavior.
- [x] 4.2 Implement `/mute` and `/unmute` in a new `bot/handlers/moderation_handlers.py` using `bot.restrict_chat_member`, resolving the target via reply-to-message or explicit reference, restricted to the community group and to verified admins; verify with tests for admin success, non-admin rejection, and out-of-group rejection.
- [x] 4.3 Implement `/ban` and `/kick` (`ban_chat_member`, and `ban_chat_member` immediately followed by `unban_chat_member` for kick); verify with equivalent tests to 4.2.
- [x] 4.4 Implement `/warn`, persisting via `WarningService` from task 2.2 and confirming in-group without restricting the member; verify with a test that repeated warnings accumulate and are attributed to the correct `warned_by`/`group_id`.
- [x] 4.5 Register the moderation router in `bot/main.py`; verify with an end-to-end dispatcher test that all five commands route correctly only inside the configured community group.

## 5. Crypto market data

- [x] 5.1 Add `backend/services/crypto_service.py` with a curated static symbol→CoinGecko-id mapping (starting with BTC, ETH, FIRO) and a client for CoinGecko's `/simple/price` endpoint (price, 24h change, market cap, 24h volume), with timeout handling and an in-memory TTL cache per asset; verify with unit tests mocking the HTTP client for success, timeout, and rate-limit responses.
- [x] 5.2 Add `bot/handlers/crypto_handlers.py` exposing one command per mapped asset (e.g. `/btc`, `/eth`, `/firo`) usable in both DM and the community group, formatting the reply per the `crypto-market-data` spec; verify with tests for a known asset, an asset command with no mapping, and a provider-timeout path replying with the "temporarily unavailable" message instead of raising.
- [x] 5.3 Register the crypto router in `bot/main.py`; verify with a dispatcher test that asset commands work in both a private chat and the community group. (Fixed a real bug found while verifying this: `user_router`'s catch-all private-chat text handler was registered before the command routers and would have swallowed `/btc`, `/mute`, etc. in DMs — reordered router registration so command-specific routers are tried first.)

## 6. Documentation and end-to-end verification

- [x] 6.1 Update `README.md`'s feature list and project structure sections with the community group, crypto, and moderation capabilities; verify by re-reading against the final file layout.
- [x] 6.2 Run the full test suite (`pytest`) and confirm all existing and new tests pass, including that no test observes ticket/resolution content posted to the community group. (295/295 passed; `tests/test_community_handlers.py::test_resolve_no_creates_ticket_and_only_posts_neutral_ack_in_community` asserts the community message never contains the question/solution text.)
