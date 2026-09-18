## Why

Currently, while `EMAIL_ENABLED` defaults to `false` in configuration, email tasks and endpoints still interact with background queues and webhooks. When email is not configured in `.env`, deployments should operate exclusively and cleanly through Telegram without dispatching redundant background tasks, logging unconfigured SMTP attempts, or accepting dead email webhook payloads. Making the email module strictly optional and fully dormant when disabled ensures a zero-overhead, 100% Telegram-native operation for administrators who do not use or want an external email service.

## What Changes

- Make email support completely optional: when `EMAIL_ENABLED=false` (or when SMTP configuration is unset/default placeholder), email notifications are completely bypassed before dispatching background tasks.
- Disable cross-channel email notifications on ticket resolution when email support is not enabled.
- Protect inbound email webhook endpoints (`/api/webhooks/email-inbound` and `/api/webhooks/email-inbound/brevo`): when email support is disabled, return `503 Service Unavailable` with a clear message indicating email support is disabled.
- Add configuration helper `is_email_configured()` to validate that `EMAIL_ENABLED` is true and valid SMTP/relay parameters are provided.
- Ensure the system runs cleanly and exclusively on Telegram when email is omitted in `.env`, with zero overhead, zero mock logs, and no external email requirements.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `email-support`: Clarify that all email notifications (ticket creation, resolution sync) and inbound webhook ingestion are conditional on `EMAIL_ENABLED` and valid configuration. When disabled, the system operates purely on Telegram without dispatching email tasks or accepting inbound email webhooks.

## Impact

- `backend/backend/config.py`: Add helper methods for email readiness and active status checking.
- `backend/backend/main.py`: Guard background email task additions in `/api/tickets` and `/api/tickets/{ticket_id}/resolve` against `EMAIL_ENABLED`. Guard inbound webhook endpoints with explicit check for email readiness.
- `backend/backend/services/email_service.py`: Streamline bypass checks and configuration validation.
- Tests: Update and add tests verifying behavior when email is disabled vs. enabled.
