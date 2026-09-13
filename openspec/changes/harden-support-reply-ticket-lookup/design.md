## Context

See proposal.md - Why. Today `bot/handlers/user_handlers.py::handle_resolve_no` creates the ticket
(getting its id from the backend), builds `group_card` text embedding `TICKET SUPPORT #{ticket_id}`
and `ID: {user_id}`, and posts it with `bot.send_message(...)` - discarding the returned `Message`
(which carries a `message_id`). `bot/handlers/support_handlers.py::handle_support_agent_reply` then
recovers `ticket_id`/`user_id` purely by regex over `message.reply_to_message.text` (that same
card). The two are joined only by string formatting, not by any stored reference.

`backend/database.py::init_db` calls `Base.metadata.create_all`, which creates missing tables but
does not add columns to existing ones - relevant to how this change's new `Ticket` column reaches
already-created local/dev databases (see Risks).

## Goals / Non-Goals

**Goals:**
- Make ticket resolution-by-reply robust to the *text* of the ticket card changing, by anchoring
  it to the Telegram message's identity instead.
- Never regress: a reply that would have resolved a ticket before this change (via text matching)
  must still resolve it after, via the same regex kept as a fallback.
- Give the agent visible feedback when a reply cannot be matched to any ticket at all, instead of
  silence.

**Non-Goals:**
- No general migration framework (e.g. Alembic) for this project - out of scope; see Risks for how
  the one new column is handled instead.
- No change to how the card's text is worded or formatted.
- No support for multiple support groups - the single configured `TELEGRAM_SUPPORT_GROUP_ID`
  remains the only trusted chat (see the `fix-support-group-auth-check` change), so a Telegram
  message id alone (unique within that one chat) is enough as a lookup key without also storing a
  chat id.

## Decisions

- **New field**: add `support_group_message_id: Optional[int]` to the `Ticket` model
  (`backend/models.py`), set once when the card is posted. Chosen over encoding richer state in
  the card text (e.g. a hidden marker) because a plain integer column is trivial to query and
  cannot be affected by any future wording change to the card.
- **Two-step write, not one**: the ticket is created first (`POST /api/tickets`, unchanged) to
  obtain its id, which the card text itself needs (`TICKET SUPPORT #{ticket_id}`); only after
  `bot.send_message(...)` returns does the card's `message_id` exist. A new endpoint,
  `POST /api/tickets/{ticket_id}/support-card`, attaches it in a second call
  (`bot/handlers/user_handlers.py::handle_resolve_no`, right after posting the card). Alternative
  considered: have the backend construct and post the card itself (removing the two-step dance
  entirely) - rejected as out of scope; it would move Telegram-sending responsibility from the bot
  process into the backend, a much larger architectural change than this fix warrants.
- **Lookup endpoint**: `GET /api/tickets/by-support-message/{message_id}` returns the ticket whose
  `support_group_message_id` matches, or 404. `bot/api_client.py` gains
  `attach_support_card(ticket_id, message_id)` and `get_ticket_by_support_message(message_id)`.
- **Resolution order in `handle_support_agent_reply`**: (1) look up by
  `message.reply_to_message.message_id` via the new endpoint; (2) on no match, fall back to the
  existing `TICKET_ID_REGEX`/`USER_ID_REGEX` parsing of the replied-to text, unchanged; (3) on no
  match from either, reply in the group that the message could not be matched to a ticket, and
  take no further action. This ordering means the id-based path is preferred whenever available,
  while every previously-working case (including tickets created before this change ships, whose
  `support_group_message_id` is `NULL`) keeps working exactly as before.
- **Best-effort attach, not transactional**: if `attach_support_card` fails (network hiccup,
  backend momentarily down) the bot logs and continues - the ticket still exists and the fallback
  regex path still resolves it. The id-based path is a robustness improvement, not a new
  requirement the rest of the flow depends on.
- **When the fallback also fails to find a ticket** (a reply to some unrelated message that
  happens to be in the support group), the bot must not attempt any backend call using a garbage
  `ticket_id` - the "no match" reply is sent instead, before any `resolve_ticket` call.

## Risks / Trade-offs

- [Risk] Adding a column to `Ticket` does not retroactively appear in an already-created SQLite
  file (`Base.metadata.create_all` only creates missing tables). → Mitigation: this project has no
  migration tooling and is still in local/dev testing (per `TODO.md`), so the simplest correct
  action is to delete the local `chatbot.db` once after this change lands, letting `init_db`
  recreate the schema from scratch; call this out explicitly in tasks.md so it isn't missed. A real
  migration tool (Alembic) is worth adopting later if the schema keeps evolving, but introducing it
  just for one nullable column is disproportionate here (Non-Goal).
- [Risk] `attach_support_card` can race with a very fast agent reply (card posted, agent replies
  before the id is attached). → Mitigation: the regex fallback covers exactly this window; no
  behavior is lost, only the robustness improvement is momentarily unavailable.
- [Risk] Two backend calls per escalation (create, then attach) instead of one. → Accepted: the
  attach call is small, best-effort, and does not block the user-facing "ticket created" message,
  which is already sent before the group card in the existing flow.

## Migration Plan

- Add the column, the two endpoints, and the bot-side wiring in one change (see tasks.md).
- Operationally: delete the local `chatbot.db` (or any pre-existing dev database) once after
  deploying this change, so `init_db`'s `create_all` includes the new column from a clean schema.
  No action needed for a database that does not exist yet.
- Rollback: revert the commit; the fallback regex path means older ticket cards keep resolving
  correctly even if this change is reverted after some tickets already have
  `support_group_message_id` set (that field is simply unused again).
