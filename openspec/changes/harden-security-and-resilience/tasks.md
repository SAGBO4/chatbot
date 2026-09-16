## 1. Brevo Webhook Header Authentication & Log Protection

- [x] 1.1 Update `verify_brevo_inbound_token` in `backend/main.py` to accept `X-Webhook-Token` or `X-Brevo-Token` header, falling back to `?token=`, and verify with unit tests
- [x] 1.2 Add access log masking guidance/middleware so sensitive query tokens are never printed in plain text, and verify with caplog tests
- [x] 1.3 Update Brevo webhook tests in `tests/test_feature_webhooks_brevo_comprehensive.py` to validate header-based authentication and log redaction

## 2. Resilient Background Task Exception Isolation

- [x] 2.1 Implement a safe execution wrapper for all background task callables scheduled in `BackgroundTasks` (`EmailService.send_ticket_created_notification`, `EmailService.send_ticket_resolved_notification`, `TelegramRelay.send_message_to_user`, `TelegramRelay.notify_support_group`) in `backend/main.py`
- [x] 2.2 Verify that external connection dropouts, SMTP timeouts, or Telegram API errors in background tasks do not crash the HTTP response lifecycle or bubble to Starlette's ASGI response loop
- [x] 2.3 Add comprehensive tests in `tests/test_feature_tickets_comprehensive.py` and `tests/test_feature_webhooks_email_comprehensive.py` asserting uninterrupted HTTP 200/201 responses when background tasks fail

## 3. Ticket Ownership & IDOR Protection

- [x] 3.1 Extend `TicketService.get_ticket` and `TicketService.get_all_tickets` with optional `user_id` filtering in `backend/services/ticket_service.py`
- [x] 3.2 Update `/api/tickets` and `/api/tickets/{ticket_id}` in `backend/main.py` to support `user_id` validation, returning 404 or 403 when a user-scoped request accesses another user's ticket
- [x] 3.3 Add test cases in `tests/test_feature_tickets_comprehensive.py` verifying that cross-user ticket access is denied when user context is provided

## 4. Hermetic Test Fixtures & Final Verification

- [x] 4.1 Confirm `tests/conftest.py` has autouse network isolation fixtures preventing real outbound SMTP connections to Brevo and real calls to Telegram Bot API across the entire test suite
- [x] 4.2 Run the entire test suite with `pytest -v --cov=backend --cov=bot` and verify all tests pass with zero network leaks and high coverage
