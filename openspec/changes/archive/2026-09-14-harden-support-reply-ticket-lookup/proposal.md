## Why

`bot/handlers/support_handlers.py` currently identifies which ticket (and which user) an agent's
group reply resolves purely by regex-matching the *text* of the replied-to message
(`TICKET_ID_REGEX`, `USER_ID_REGEX` against the string produced in `bot/handlers/user_handlers.py`
as `group_card`). This couples two independent code paths through a fragile shared string format:
any change to the card's wording (translation, template tweak, adding a line) silently breaks
resolution, and an agent replying to a message the bot itself later edited/reformatted (or a
forwarded/altered copy of the card) can produce no match at all - `handle_support_agent_reply`
then does nothing, with no feedback that a reply was ignored. Anchoring resolution to a stable
identifier - the Telegram message id of the posted ticket card, already available and persisted
by Telegram itself - removes this class of fragility instead of only making the regex more
tolerant of formatting variance.

## What Changes

- Persist the Telegram message id of the ticket card posted to the Support Group on the `Ticket`
  record when it is created/escalated.
- `handle_support_agent_reply` SHALL primarily resolve the ticket by looking up this stored
  message id (via `message.reply_to_message.message_id`) rather than parsing the reply's quoted
  text.
- Keep the existing text-based regex extraction as a fallback, only used when no ticket is found
  for the replied-to message id (e.g. tickets created before this change ships, or a card whose id
  was not recorded for any reason) - so no previously-working flow regresses.
- If neither the message-id lookup nor the fallback regex can identify a ticket, the bot SHALL
  reply in the group explaining the reply could not be matched to a ticket, instead of silently
  doing nothing (closes the "no feedback on a missed match" gap named above).

## Capabilities

### Modified Capabilities
- `ticket-escalation`: ticket creation additionally records the Telegram message id of the posted
  support-group card, so it can later be resolved independently of the card's text content.
- `telegram-bot`: the "Support group ticket notification and reply" requirement is strengthened so
  that matching an agent's reply to its ticket is based primarily on the replied-to message's
  identity, not on parsing its text, with the previous regex-based behavior kept only as a
  fallback; an unmatched reply now gets an explicit "could not identify a ticket" response instead
  of silence.

## Impact

- Code: `backend/models.py` (new `Ticket` column), `backend/schemas.py`,
  `backend/services/ticket_service.py`, `backend/main.py` (persist the id at creation and/or via a
  small update path), `bot/handlers/user_handlers.py` (capture the id from `bot.send_message`'s
  return value after posting the card), `bot/handlers/support_handlers.py` (resolve by id first,
  regex fallback second, explicit "not found" reply), `bot/api_client.py` (send the id to the
  backend).
- Data: adds a nullable column to the `tickets` table. `backend/database.py` uses
  `Base.metadata.create_all`, which does not alter existing tables - see design.md for how
  existing local/dev databases are handled.
- No breaking change to any existing API contract observed by external callers; the new field is
  additive and optional.
