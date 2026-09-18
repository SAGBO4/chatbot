## Why

The bot currently only answers questions in a private DM and escalates tickets to a single Telegram group. The owner wants to deploy it into their public community group as a visible Q&A/crypto-info bot (in the style of common crypto community bots), while keeping ticket resolution, agent replies, and moderation logs confined to the existing admin group — never leaking into the community group. The owner also wants baseline crypto price lookups and basic community moderation, both entirely absent from the project today.

## What Changes

- Add a group-triggered Q&A flow in the community group: a user invokes the bot with a command + their question, the bot answers in the group thread tagging the asking user, and the YES/NO resolution buttons expire (become inert / are removed) after a fixed inactivity timeout instead of staying clickable indefinitely.
- Route ticket creation from the community group through the existing ticket-escalation pipeline, unchanged: the ticket card and agent resolution replies stay in the current admin group (`TELEGRAM_SUPPORT_GROUP_ID`) and/or email — no ticket internals are ever posted to the community group. The existing private-DM flow is kept as-is, unchanged, alongside the new group flow.
- Add a `/purge` admin command usable in the community group to bulk-delete recent bot/community messages (e.g. an overly long bot reply or spam), restricted to community-group admins.
- Add a crypto market-data lookup capability: a command per asset (e.g. `/btc`, `/firo`) queries CoinGecko's public API and replies with price, 24h change, market cap and volume, usable in the community group and in DM.
- Add baseline community moderation commands scoped to the community group: `/mute`, `/unmute`, `/ban`, `/kick`, `/warn`, restricted to users who are admins of that Telegram group (verified via the Telegram Bot API, not an internal allowlist).

## Capabilities

### New Capabilities
- `community-qa`: group-triggered Q&A in the community group (trigger command, tagged reply, expiring resolution buttons, ticket hand-off into the existing ticket-escalation pipeline, `/purge` cleanup command).
- `crypto-market-data`: per-asset price/stat lookup commands backed by CoinGecko, usable in DM and in the community group.
- `community-moderation`: admin-only moderation commands (`/mute`, `/unmute`, `/ban`, `/kick`, `/warn`) scoped to the community group, with Telegram-verified admin authorization.

### Modified Capabilities
(none — the existing `telegram-bot` DM flow and `ticket-escalation` pipeline are reused unchanged; the community group only adds a new entry point into them)

## Impact

- **bot/handlers/**: new `community_handlers.py` (group trigger, tagged replies, expiring buttons, `/purge`), new `crypto_handlers.py`, new `moderation_handlers.py`; `bot/main.py` registers the new routers.
- **backend/config.py**: new settings — `TELEGRAM_COMMUNITY_GROUP_ID`, resolution-button timeout, CoinGecko base URL/timeout, moderation defaults (e.g. default mute duration).
- **backend/services/**: new `crypto_service.py` (CoinGecko client with caching/timeout handling); ticket creation/resolution logic in `ticket_service.py` and the escalation targets in `user_handlers.py`/`support_handlers.py` are reused, not modified.
- **New dependency**: CoinGecko public REST API (no key required for the basic endpoints used).
- **Telegram Bot API usage**: `restrictChatMember`, `banChatMember`, `unbanChatMember`, `getChatMember` for moderation and admin verification; `deleteMessage` for `/purge`.
- **.env.example / README**: document the new community group id and moderation/crypto configuration.
