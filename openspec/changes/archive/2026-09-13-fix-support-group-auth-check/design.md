## Context

See proposal.md - Why. `support_router` (bot/handlers/support_handlers.py) is included globally in `bot/main.py` (`dp.include_router(support_router)`) with no per-chat scoping; aiogram delivers updates from every chat the bot is a member of (groups) or that DM it directly. `settings.TELEGRAM_SUPPORT_GROUP_ID` (backend/config.py) is a `Union[int, str]` defaulting to `0`, and is already used the same way in `bot/handlers/user_handlers.py:134-135` to decide whether/where to post the escalation card (`if support_group_id and str(support_group_id) != "0"`).

## Goals / Non-Goals

**Goals:**
- Make `handle_support_agent_reply` a no-op for any chat other than the configured support group, with no observable side effect (no backend call, no Telegram send).
- Reuse the exact "is the support group configured" check already used in `user_handlers.py` so both places agree on what counts as "no group configured".
- Keep the fix local to the handler (a filter/guard), not a redesign of routing.

**Non-Goals:**
- Verifying the *sender* is actually a support agent (e.g. via Telegram admin list) - out of scope; the trust boundary here is "this chat is the support group", consistent with the existing spec and with how tickets are posted there in the first place.
- Changing how the ticket card text is generated or parsed (regexes in `support_handlers.py` stay as-is).
- Handling multiple support groups - the system supports exactly one, per existing config.

## Decisions

- **Guard placement**: implement the check as an early guard at the top of `handle_support_agent_reply`'s body (return before any backend/Telegram call if the chat does not match), rather than only as an aiogram router filter. Rationale: `tests/test_bot_handlers.py` already calls handlers as plain async functions (e.g. `await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)`), bypassing aiogram's filter/dispatch pipeline entirely - a decorator-only filter (`F.chat.id == ...`) would be invisible to that test style and to any direct/programmatic call of the handler. An in-body guard is exercised the same way regardless of how the handler is invoked, matches the project's existing test pattern, and keeps the enforcement point next to the logic it protects. As defense-in-depth this does not preclude also narrowing what the router delivers, but the authoritative check - and the one the tests target - is the in-body guard.
- **Id comparison**: compare `str(message.chat.id) == str(settings.TELEGRAM_SUPPORT_GROUP_ID)`. `TELEGRAM_SUPPORT_GROUP_ID` is typed `Union[int, str]` and may come from `.env` as a string; Telegram group chat ids are always negative integers. String comparison after normalization avoids a subtle type-mismatch bypass (e.g. `int` config vs `str` env value never comparing equal) while still requiring an exact id match.
- **Unconfigured group guard**: if `settings.TELEGRAM_SUPPORT_GROUP_ID` is falsy or `"0"` (the documented "not configured" sentinel, same as `user_handlers.py`), the handler must not match any chat at all - it must not use `0`/`None` as a valid comparison target that could coincide with a real chat id. Implemented as an explicit early guard rather than relying on the filter alone.
- **Where the check lives**: implemented as a small pure predicate (e.g. `_is_support_group_chat(chat_id) -> bool`) so it can be unit-tested directly and reused by the filter, instead of duplicating the `str(...) != "0"` guard inline.

## Risks / Trade-offs

- [Risk] If `TELEGRAM_SUPPORT_GROUP_ID` is misconfigured to the wrong chat (e.g. a personal DM id), that chat becomes the trusted "support group" - this is an existing configuration responsibility, unchanged by this fix, and matches how the ticket card is already addressed via the same setting.
- [Risk] Telegram forum/topic sub-threads within the support group share the same `chat.id`; this fix does not add topic-level scoping since the current spec and card format don't use topics.
- Mitigation for both: out of scope for this change; documented here so a future change can tighten further if needed.

## Migration Plan

- Pure code change to `bot/handlers/support_handlers.py`; no data migration, no API contract change, no config addition (reuses existing `TELEGRAM_SUPPORT_GROUP_ID`).
- Deploy: ship with the next bot release. Rollback: revert the commit; no state to unwind since the handler is stateless.
