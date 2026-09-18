## 1. Configuration & Readiness Helpers

- [x] 1.1 Add `is_email_configured()` and `is_email_inbound_configured()` helper methods to `Settings` in `backend/backend/config.py` and verify with unit tests in `tests/test_config.py`
- [x] 1.2 Optimize `EmailService.send_email_async` in `backend/backend/services/email_service.py` to return early when `is_email_configured()` is false, verified via `tests/test_email_service.py`

## 2. Background Task Guarding on Ticket Routes

- [x] 2.1 Update `create_ticket` in `backend/backend/main.py` to conditionally dispatch `EmailService.send_ticket_created_notification` only when `settings.is_email_configured()`, verified via unit test asserting no background task is queued when `EMAIL_ENABLED=false`
- [x] 2.2 Update `resolve_ticket` in `backend/backend/main.py` to conditionally dispatch `EmailService.send_ticket_resolved_notification` only when `settings.is_email_configured()`, verified via unit test asserting no background task is queued when `EMAIL_ENABLED=false`

## 3. Inbound Webhook Guarding

- [x] 3.1 Guard `handle_inbound_email` (`/api/webhooks/email-inbound`) in `backend/backend/main.py` to return HTTP 503 when email support is not enabled, verified via tests in `tests/test_feature_webhooks_email_comprehensive.py`
- [x] 3.2 Guard `handle_brevo_inbound_email` (`/api/webhooks/email-inbound/brevo`) in `backend/backend/main.py` to return HTTP 503 when email support is not enabled, verified via tests in `tests/test_brevo_inbound_webhook.py`

## 4. Verification & Testing

- [x] 4.1 Run all test suites hermetically via `pytest` to ensure 100% test pass rate across both Telegram-only mode and Email-enabled mode
