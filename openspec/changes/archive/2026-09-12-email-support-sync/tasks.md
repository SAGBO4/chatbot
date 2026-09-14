## 1. Email Service & Configuration

- [x] 1.1 Add email configuration settings (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SUPPORT_EMAIL_RECIPIENT`, `EMAIL_ENABLED`) to `backend/config.py`. Verify with configuration tests.
- [x] 1.2 Implement `backend/services/email_service.py` with methods to dispatch ticket alert emails and closure confirmation emails asynchronously. Verify with unit tests.

## 2. Model & Webhook Endpoint

- [x] 2.1 Update `Ticket` model in `backend/models.py` and schemas in `backend/schemas.py` to include `resolution_channel`. Verify with database model tests.
- [x] 2.2 Implement inbound email webhook endpoint `POST /api/webhooks/email-inbound` that parses ticket ID, cleans email body, and resolves ticket. Verify with unit tests.

## 3. Multi-Channel Synchronization & Verification

- [x] 3.1 Connect ticket creation to dispatch email notification in the background whenever a ticket is created. Verify with API tests.
- [x] 3.2 Implement Telegram Bot notification relay when a ticket is resolved via email, and email notification when resolved via Telegram. Verify with mock bot and email tests.
- [x] 3.3 Add complete integration test verifying dual-channel race condition (Email resolves first -> Telegram notified and user receives answer; subsequent Telegram reply rejected safely). Verify with `pytest`.
