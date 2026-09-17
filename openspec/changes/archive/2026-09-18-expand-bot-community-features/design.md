## Context

See `proposal.md` for motivation. Relevant current state:

- `bot/handlers/user_handlers.py` only reacts to `F.chat.type == "private"`; the YES/NO keyboard (`bot/keyboards.py`) never expires and ticket escalation always posts to `settings.TELEGRAM_SUPPORT_GROUP_ID` — this group is what the proposal calls the admin group and stays unchanged.
- `bot/handlers/support_handlers.py` only accepts agent resolution replies from that same configured group; email resolution goes through `backend/main.py`'s webhook handlers. Neither path needs to change.
- The bot runs via long polling (`bot/main.py`, `dp.start_polling`), single process, no external scheduler/queue. `bot/middlewares/throttling.py` already keeps small in-memory per-user state across the polling loop, which is the existing pattern for ephemeral, non-critical state.
- `backend/config.py`'s `Settings` is the single source of truth for all `TELEGRAM_*` and feature configuration, with a `*_is_configured()` helper pattern (`support_group_is_configured`) used to gate optional integrations.
- Persistent state (tickets, KB articles) lives in the backend DB via SQLAlchemy models + Alembic migrations, with a thin service layer (`TicketService`, `KnowledgeBaseService`) called from `backend/main.py`.

## Goals / Non-Goals

**Goals:**
- Reuse the existing DM Q&A → ticket → admin-group/email pipeline unchanged; the community group is a new entry point, not a new pipeline.
- Keep new state (warnings) durable across bot restarts, consistent with how tickets/KB already live in the backend DB rather than in bot memory.
- Keep CoinGecko and moderation additive and independently deployable: a deployment without `TELEGRAM_COMMUNITY_GROUP_ID` set continues to behave exactly as today.

**Non-Goals:**
- No general-purpose "any bot mention" NLU trigger — the group trigger is one explicit command.
- No wallet/tipping functionality (the Firo Tip Bot reference is for command-list style only, per the user's explicit clarification).
- No multi-community support in this change (one `TELEGRAM_COMMUNITY_GROUP_ID` and one admin group, matching the current single-support-group model).

## Decisions

### 1. Group trigger command: a plain slash command, not @mention parsing
Use a dedicated command, e.g. `/ask <question>` (final literal name is a copy/UX detail, not a spec-level concern), instead of parsing free-form `@BotUsername <question>` mentions. Aiogram's command filters already give reliable parsing including the `/ask@BotUsername` form Telegram appends automatically in groups with multiple bots; free-text mention parsing would require custom entity parsing for a case Telegram's command filter already solves for free. Alternative considered: trigger on any message that `@mentions` the bot — rejected because it can't be reliably distinguished from a member mentioning the bot conversationally without invoking it.

### 2. Expiring resolution buttons: in-memory timer + timestamp check at click time (belt and suspenders)
Each group-triggered answer schedules an `asyncio.create_task` that edits the message to remove/disable the keyboard after the configured timeout (new setting, e.g. `COMMUNITY_RESOLUTION_TIMEOUT_SECONDS`). Because this is in-memory (lost on bot restart, same trade-off `ThrottlingMiddleware` already accepts), the callback handler for YES/NO also independently checks the answer's original timestamp (stored in the FSM context alongside `last_question`/`last_answer`, same mechanism the DM flow already uses) and rejects a stale click even if the scheduled edit never ran. Alternative considered: a persistent scheduled-job table polled by the backend — rejected as disproportionate for a cosmetic UX timeout with a cheap client-side fallback check.

### 3. Ticket hand-off stays chat-agnostic in the backend, group-aware only in the bot layer
`TicketService`/`QueryOrchestrator` already take `user_id`/`user_handle` with no notion of originating chat — no backend change needed there. A new `bot/handlers/community_handlers.py` mirrors `user_handlers.py`'s query → keyboard → escalate flow but (a) tags the asking member in its replies, (b) posts only a neutral "ticket opened" acknowledgement back into the community group instead of echoing ticket contents, and (c) reuses the exact same `BackendClient.create_ticket` / support-group card posting used today. The two handler modules share their escalation body via a small extracted helper to avoid duplicating the Markdown-fallback dance already present in `handle_resolve_no`.

### 4. Moderation warnings are persisted in the backend DB, mute/ban act live via the Telegram Bot API
`/mute`, `/unmute`, `/ban`, `/kick` are stateless calls to `bot.restrict_chat_member` / `ban_chat_member` / `unban_chat_member` (kick = ban immediately followed by unban, Telegram's documented kick idiom) — no new persistence needed, Telegram itself is the source of truth for membership/restriction state. `/warn` has no native Telegram equivalent, so warning counts must be tracked by this system; a new `CommunityWarning` table (mirroring the existing `Ticket`/`KnowledgeArticle` model + service pattern) persists `user_id`, `group_id`, `reason`, `warned_by`, `created_at`, exposed through a small backend service the same way ticket/KB state is exposed today. Alternative considered: keep warnings in bot memory like the resolution-button timers — rejected because losing warning history on every bot restart defeats the point of tracking repeat offenders.

### 5. Admin verification via live Telegram API call, short TTL cache
Every moderation/`purge` command calls `bot.get_chat_member(group_id, user_id)` and checks `status in {"administrator", "creator"}` at invocation time, rather than trusting a locally cached admin list — Telegram is the single source of truth for group roles and admins change over time. To avoid hammering the Bot API when an admin issues several commands in a row, results are cached in memory for a short TTL (e.g. 60s) keyed by `(group_id, user_id)`, the same lightweight in-memory pattern as the throttling middleware.

### 6. CoinGecko client: curated static symbol→id map + short TTL cache, no API key
Use CoinGecko's public (keyless) endpoints. CoinGecko's asset ids don't map 1:1 from ticker symbols (many coins share a symbol), so command names (`/btc`, `/firo`, ...) resolve through a small curated, extensible static mapping shipped with the bot rather than a live search-and-guess against `/coins/list`, keeping lookups deterministic. Responses are cached in memory for a short TTL (e.g. 30–60s) to stay well inside CoinGecko's free-tier rate limit even if several members query the same asset in quick succession. Alternative considered: CoinMarketCap — rejected per the user's explicit choice (no API key needed, simpler to operate).

## Risks / Trade-offs

- **[Risk]** In-memory resolution-button timers and admin-check cache are lost on bot restart → a button that should have expired stays visibly clickable until clicked. **Mitigation**: the timestamp check at click time (Decision 2) still rejects a stale confirmation/ticket-creation regardless of restart; worst case is a harmless still-visible button, not an incorrect resolution.
- **[Risk]** The bot must itself hold Telegram admin rights with restrict/ban/delete permissions in the community group, or all moderation and `/purge` calls fail. **Mitigation**: document this as a deployment prerequisite (README) and have moderation handlers surface Telegram's permission error back to the invoking admin instead of failing silently.
- **[Risk]** CoinGecko's free tier can throttle under load. **Mitigation**: TTL caching (Decision 6) plus the existing pattern of treating provider errors as recoverable (`crypto-market-data` spec's resilience requirement) rather than surfacing raw errors.
- **[Trade-off]** The curated symbol→id map (Decision 6) means a newly requested asset needs a small code/config change to support, instead of being auto-discovered. Accepted as the simpler, deterministic option; the mapping is designed to be a plain extendable config, not hardcoded logic.

## Migration Plan

1. Add settings: `TELEGRAM_COMMUNITY_GROUP_ID`, `COMMUNITY_RESOLUTION_TIMEOUT_SECONDS`, `CRYPTO_PROVIDER_TIMEOUT_SECONDS`, `CRYPTO_CACHE_TTL_SECONDS`, default mute duration — all optional with safe defaults, mirroring `support_group_is_configured()` with a new `community_group_is_configured()`.
2. Alembic migration adding the `community_warnings` table (additive only, no changes to existing tables).
3. Add the new bot routers (`community_handlers`, `crypto_handlers`, `moderation_handlers`) behind `community_group_is_configured()` where group-scoped, registered in `bot/main.py` alongside the existing routers.
4. Update `.env.example` and `README.md` with the new variables and required bot admin permissions in the community group.
5. Rollback: each new router/table is additive; disabling is done by unsetting `TELEGRAM_COMMUNITY_GROUP_ID` (group features no-op) and, if needed, reverting the single additive migration.

## Open Questions

- Exact literal command names/copy (e.g. `/ask` vs `/support`) and default mute duration — implementation-time detail, doesn't affect the specs or task breakdown.
- Initial curated crypto asset list beyond BTC/ETH/FIRO — can be extended after launch without a spec change (the requirement is the mechanism, not the exact asset roster).
