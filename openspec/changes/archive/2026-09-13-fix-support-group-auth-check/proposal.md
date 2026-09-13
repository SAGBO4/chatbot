## Why

`bot/handlers/support_handlers.py` registers `handle_support_agent_reply` on `@support_router.message(F.reply_to_message)` with no filter on the originating chat. The handler only pattern-matches the *text* of the replied-to message (`TICKET SUPPORT #<id>` / `ID: <id>`), so it fires identically whether the reply comes from the Telegram Support Group or from a private DM with the bot. Any Telegram user can privately send the bot a message containing that pattern and then reply to it, causing the bot to treat them as a support agent. This lets an unauthenticated user resolve an arbitrary ticket, push arbitrary text to any Telegram `user_id`, and inject arbitrary content into the knowledge base (poisoning future automated answers) — a critical authorization bypass. The existing `telegram-bot` spec already assumes replies are captured "in the support group", so this is implementation catching up to a requirement that was never actually enforced; this change makes that constraint explicit and testable.

## What Changes

- Restrict `handle_support_agent_reply` to only process messages whose `chat.id` matches `settings.TELEGRAM_SUPPORT_GROUP_ID`; messages from any other chat (private DM, other groups) are ignored without side effects.
- Guard against a misconfigured/unset support group id (`0` or falsy) so the check cannot be silently bypassed by default configuration.
- Add unit tests asserting: a reply from an arbitrary/other chat id is ignored (no ticket resolution call, no Telegram send, no KB ingestion), and a reply from the configured support group id still resolves the ticket and notifies the user as before.
- Audit `bot/handlers/user_handlers.py` for the same class of missing chat/authorization scoping; document findings and fix any equivalent gap found.

## Capabilities

### Modified Capabilities
- `telegram-bot`: the "Support group ticket notification and reply" requirement is strengthened to explicitly require that only replies originating from the configured Telegram Support Group chat are treated as agent resolutions; replies from any other chat must be ignored.

## Impact

- Code: `bot/handlers/support_handlers.py` (chat-scoping filter), `tests/test_bot_handlers.py` (new/updated tests).
- No API or schema changes; no breaking change for legitimate support-group usage.
- Depends on `settings.TELEGRAM_SUPPORT_GROUP_ID` already present in `backend/config.py`.
