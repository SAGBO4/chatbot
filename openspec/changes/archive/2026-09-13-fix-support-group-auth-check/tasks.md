## 1. Implement the chat-scoping guard

- [x] 1.1 Add a `_is_support_group_chat(chat_id) -> bool` predicate in `bot/handlers/support_handlers.py` that returns `False` when `settings.TELEGRAM_SUPPORT_GROUP_ID` is falsy/`"0"` (unconfigured), and otherwise compares `str(chat_id) == str(settings.TELEGRAM_SUPPORT_GROUP_ID)`; verify with a quick manual check (`python -c` or a throwaway test) that it returns `False` for an unconfigured group id and `True`/`False` correctly for matching/mismatching ids.
- [x] 1.2 In `handle_support_agent_reply`, call `_is_support_group_chat(message.chat.id)` first and `return` immediately (no backend call, no Telegram send, no reply) when it is `False`, before any other processing (including the ticket/user id regex extraction). Verify by reading the diff that no side-effecting call is reachable before this guard.

## 2. Tests

- [x] 2.1 Update `tests/test_support_agent_reply_handler` (or add a new test) in `tests/test_bot_handlers.py` to set `monkeypatch.setattr("backend.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)` and use that id as the group chat id, so the existing "happy path" assertions (resolve_ticket called, message sent to user, group reply confirmed) keep passing under the new guard; verify with `pytest tests/test_bot_handlers.py -q`.
- [x] 2.2 Add a new test asserting a reply from a private chat (`Chat(id=<agent's own user id>, type="private")`) carrying the same ticket-card reply pattern is ignored: `backend_client.resolve_ticket` is not called, `bot.send_message` is not called, and `message.reply` is not called; verify it passes and fails if the guard is removed (sanity-check by temporarily reverting 1.2 locally, do not commit the revert).
- [x] 2.3 Add a new test asserting a reply from a different, unrelated group chat id (not equal to the configured `TELEGRAM_SUPPORT_GROUP_ID`) is likewise ignored, covering the "another group, not just DM" case; verify with `pytest tests/test_bot_handlers.py -q`.
- [x] 2.4 Add a test for the unconfigured-group case: with `TELEGRAM_SUPPORT_GROUP_ID` left at its default (`0`), a reply in a chat whose id happens to be `0`/falsy is still ignored (guards against the sentinel value silently matching); verify it passes.

## 3. Audit other handlers for the same class of gap

- [x] 3.1 Review `bot/handlers/user_handlers.py` (`handle_start`, `handle_help`, `handle_user_query`, `handle_resolve_yes`, `handle_resolve_no`) for missing chat/authorization scoping equivalent to this vulnerability; confirm in writing (a short note in the PR/change description) that `handle_user_query` is correctly scoped to `F.chat.type == "private"` and that the `resolve:yes`/`resolve:no` callback handlers only ever act on the callback's own `from_user`/chat context, so no cross-user or cross-chat privilege issue exists there.

  **Audit findings** (no code change required):
  - `handle_start` / `handle_help`: unscoped by chat/type, but only ever answer the sender with a static welcome/help text - no parameter is taken from elsewhere, no backend call, no cross-user effect possible.
  - `handle_user_query`: correctly filtered with `F.chat.type == "private"`; only queries the KB with the sender's own `message.from_user.id`/text and replies to that same sender - no way to act on behalf of, or against, another user.
  - `handle_resolve_yes`: only edits the message belonging to the callback it was invoked on (`callback.message`), scoped by Telegram itself to the callback's own chat/message - no ticket id or user id is taken from attacker-controlled text.
  - `handle_resolve_no`: creates a ticket using `callback.from_user.id`/`username` (the caller's own identity) and the `last_question`/`last_answer` from that same user's FSM state - a caller can only ever create a ticket for themselves, never resolve or impersonate another ticket. It reads `TELEGRAM_SUPPORT_GROUP_ID` only to choose where to *post* the resulting card, not to authorize an inbound action, so it is not the same trust boundary as `support_handlers.py`.
  - Conclusion: no equivalent vulnerability exists in `user_handlers.py`. The vulnerability fixed in this change was specific to `support_handlers.py` treating unauthenticated reply content as authoritative regardless of chat origin.
- [x] 3.2 If the audit in 3.1 finds an equivalent gap, fix it following the same guard pattern as 1.1/1.2 and add the corresponding rejection/happy-path tests as in section 2; if no gap is found, record that explicitly instead (e.g. in the change's final summary) so the audit is traceable.

  **No gap found** - see the audit findings recorded under 3.1 above. No additional fix or tests were required for `user_handlers.py`.

## 4. Full verification

- [x] 4.1 Run the full test suite (`pytest -q`) and confirm all tests pass, including the pre-existing 20 tests plus the new ones from section 2.

  **Result**: `23 passed in 2.47s` (20 pre-existing + 3 new rejection tests from section 2; 2.1 updates an existing test in place rather than adding a new one).
