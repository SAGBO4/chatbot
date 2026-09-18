## Context

The chatbot architecture supports multi-channel support escalation across Telegram and Email. Currently, `EMAIL_ENABLED` exists as a flag, but background tasks and webhook endpoints remain wired even when email is disabled or unconfigured in `.env`. See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**
- Provide a clean, zero-overhead Telegram-only mode when `EMAIL_ENABLED` is `false` or when SMTP settings are not provided.
- Prevent scheduling unnecessary background email tasks on ticket creation and ticket resolution when email is disabled.
- Fail closed with HTTP 503 on inbound email webhook endpoints (`/api/webhooks/email-inbound` and `/api/webhooks/email-inbound/brevo`) when email support is disabled.
- Add central configuration validation helpers (`is_email_configured()`, `is_email_inbound_configured()`) to standardise email readiness checks across the codebase.
- Maintain full backward compatibility for existing deployments that actively use email.

**Non-Goals:**
- Altering the Telegram bot ticket flow or Telegram escalation keyboards.
- Removing or deprecating the email subsystem; it remains fully functional when configured.

## Decisions

1. **Explicit Gatekeeper at the Call Site vs. Internal Service Return**
   - *Decision:* Check `settings.is_email_configured()` directly before registering `BackgroundTasks.add_task(...)` in `main.py` (both in `create_ticket` and `resolve_ticket`), while retaining the internal bypass check in `EmailService.send_email_async`.
   - *Rationale:* Avoids scheduling empty asynchronous background tasks in FastAPI when email is disabled, reducing event loop churn and memory overhead.
   - *Alternative considered:* Relying solely on `EmailService` returning early. Rejected because scheduling no-op background tasks still allocates task wrappers and executor futures unnecessarily.

2. **Inbound Webhook 503 Guard**
   - *Decision:* At the entry of `/api/webhooks/email-inbound` and `/api/webhooks/email-inbound/brevo`, immediately reject requests with `503 Service Unavailable` if `settings.EMAIL_ENABLED` is false or email is unconfigured.
   - *Rationale:* Webhook providers (such as Brevo or custom relays) receive a clear HTTP 503 indicating the service is inactive, rather than cryptic signature errors or unhandled execution paths.

3. **Central Configuration Inspection Helpers**
   - *Decision:* Define `is_email_configured()` and `is_email_inbound_configured()` on `Settings` in `backend/config.py`.
   - *Rationale:* Consolidates checking `EMAIL_ENABLED`, placeholder detection (`smtp.example.com`), and secret existence in one single place.

## Risks / Trade-offs

- [Risk] An operator sets `EMAIL_ENABLED=true` but leaves default placeholder values for `SMTP_HOST`.
  → Mitigation: `is_email_configured()` detects default placeholders (`smtp.example.com`, `support-team@example.com`) and treats them as unconfigured.
- [Risk] Existing test fixtures might run with `EMAIL_ENABLED=False` and expect webhook responses.
  → Mitigation: In test fixtures covering webhook ingestion, explicitly set `EMAIL_ENABLED=True` via monkeypatching.
