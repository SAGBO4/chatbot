## 1. Data model

- [x] 1.1 Add `support_group_message_id: Mapped[Optional[int]]` (nullable) to `Ticket` in
  `backend/models.py`; verify by importing the model and confirming the column appears in
  `Ticket.__table__.columns`.
- [x] 1.2 Delete any local/dev `chatbot.db` (and files under `tmp_path` test fixtures are already
  fresh per test, so unaffected) so `init_db`'s `create_all` picks up the new column on a clean
  schema; verify by starting the backend locally and confirming no SQLite "no such column" error
  on the first ticket-related request.

  **Result**: no pre-existing local `chatbot.db` was present (nothing to delete). Verified via
  `init_db()` against a fresh file: `PRAGMA table_info(tickets)` includes
  `support_group_message_id`. Test file removed afterwards.

## 2. Backend: persist and look up by support-card message id

- [x] 2.1 Add `TicketService.attach_support_card(session, ticket_id, message_id) -> Optional[Ticket]`
  in `backend/services/ticket_service.py` that sets `support_group_message_id` and commits; returns
  `None` if the ticket does not exist. Verify with a direct unit test.
- [x] 2.2 Add `TicketService.get_ticket_by_support_message_id(session, message_id) -> Optional[Ticket]`
  querying by the new column. Verify with a direct unit test (found and not-found cases).
- [x] 2.3 Add `POST /api/tickets/{ticket_id}/support-card` in `backend/main.py` (protected by the
  existing `verify_api_key` dependency, same as the other `/api/tickets*` routes) accepting
  `{"message_id": int}`, calling 2.1, returning 404 if the ticket does not exist. Add the matching
  request schema in `backend/schemas.py`.
- [x] 2.4 Add `GET /api/tickets/by-support-message/{message_id}` in `backend/main.py` (same
  `verify_api_key` protection), calling 2.2, returning 404 if no ticket matches, otherwise the
  ticket (reuse `TicketResponse`).
- [x] 2.5 Add tests in `tests/test_api.py` for both new endpoints: attach then fetch-by-id
  round-trip, attach on a non-existent ticket (404), lookup on an unattached/unknown message id
  (404); verify with `pytest tests/test_api.py -q`.

## 3. Bot: capture and send the support-card message id

- [x] 3.1 In `bot/api_client.py`, add `attach_support_card(ticket_id, message_id)` and
  `get_ticket_by_support_message(message_id)` wrapping the two new endpoints (same pattern and
  header handling as the existing methods).
- [x] 3.2 In `bot/handlers/user_handlers.py::handle_resolve_no`, capture the `Message` returned by
  `bot.send_message(...)` when posting the group card, and call
  `backend_client.attach_support_card(ticket_id, sent_message.message_id)` right after; wrap in a
  try/except that logs a warning and continues on failure (per design.md: best-effort, must not
  block the user-facing flow). Verify by extending
  `tests/test_bot_handlers.py::test_bot_resolution_no_escalates_to_group` (or a new test) to assert
  `attach_support_card` was called with the right ids.

## 4. Bot: resolve by message id first, regex fallback second, explicit "no match" reply

- [x] 4.1 In `bot/handlers/support_handlers.py::handle_support_agent_reply`, after the existing
  support-group chat guard, first call
  `backend_client.get_ticket_by_support_message(message.reply_to_message.message_id)`; if found,
  use its `id` and `user_id` directly (skip the regex extraction entirely for this path).
- [x] 4.2 If the id-based lookup finds nothing, fall back to the existing
  `TICKET_ID_REGEX`/`USER_ID_REGEX` parsing of `replied_text`, unchanged from current behavior.
- [x] 4.3 If neither the id-based lookup nor the regex fallback identifies a ticket, send a group
  reply explaining the message could not be matched to a ticket, and return before any
  `resolve_ticket` call.
- [x] 4.4 Update `tests/test_bot_handlers.py::test_support_agent_reply_handler` to mock
  `get_ticket_by_support_message` (e.g. returning a match) and assert the id-based path is used
  without needing the regex text at all.

  **Renamed** to `test_support_agent_reply_handler_resolves_by_message_id`, and the replied-to
  card's text deliberately does NOT match the regex pattern, proving the id-based lookup alone
  resolves the ticket.
- [x] 4.5 Add a new test: id-based lookup returns nothing, but the replied-to text still matches
  the regex pattern → ticket is resolved via the fallback (same outcome as before this change).

  **Added**: `test_support_agent_reply_falls_back_to_text_when_id_lookup_misses`.
- [x] 4.6 Add a new test: neither id-based lookup nor regex match → `resolve_ticket` is never
  called, `bot.send_message` (to the user) is never called, and the group receives a "could not be
  matched" reply.

  **Added**: `test_support_agent_reply_no_match_replies_with_explicit_notice`.

## 5. End-to-end and full verification

- [x] 5.1 Update `tests/test_e2e.py::test_full_support_lifecycle_loop`'s `BackendClient` stub to
  cover `attach_support_card` / `get_ticket_by_support_message` so the full create → card posted →
  agent reply → user notified → KB updated loop still passes using the id-based path.

  **Verified explicitly**: the posted card's mocked `message_id` is asserted to be persisted on
  the ticket (`support_group_message_id`) via a direct DB query, and the same id is reused on the
  replied-to message so the agent-reply step resolves through the id-based lookup.
- [x] 5.2 Run the full test suite (`pytest -q`) and confirm all tests pass, including every
  pre-existing test plus the new ones from sections 2 and 4.

  **Result**: `32 passed`.
