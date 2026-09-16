## Why

Recent comprehensive testing and security audits identified critical vulnerabilities and operational risks in the system:
1. The Brevo inbound email webhook relies on a shared secret passed via URL query parameter (`?token=...`), causing plain-text secret leakage in HTTP access logs, proxies, and monitoring tools.
2. Uncaught exceptions inside FastAPI `BackgroundTasks` (e.g., SMTP socket failures or Telegram relay outages) bubble up through Starlette's response serialization pipeline, triggering 500 Internal Server Errors on client requests even after data was already committed to the database.
3. The ticketing endpoints (`/api/tickets`, `/api/tickets/{id}`) lack user scoping or ownership validation, relying exclusively on the shared `X-API-Key`, which exposes an IDOR vulnerability if endpoints are called from browsers or multi-tenant frontends.
4. Test execution inadvertently triggered real external network dispatches to Brevo SMTP and Telegram when real credentials existed in `.env`, creating flaky test runs and unwanted live communications.

Hardening these security and resilience boundaries now ensures production readiness, prevents credential leakage, isolates background failures, and secures ticket access.

## What Changes

- **Brevo Webhook Authentication Hardening**: Support `X-Webhook-Token` (or `X-Brevo-Token`) header authentication alongside `?token=...` query parameter fallback, and redact sensitive tokens from access logs and error traces.
- **Resilient Background Task Execution**: Wrap all background task dispatches (`EmailService.send_ticket_created_notification`, `EmailService.send_ticket_resolved_notification`, `TelegramRelay` notifications) in defensive `try...except Exception` blocks to prevent unhandled exceptions from crashing Starlette's ASGI response loop.
- **Ticket Ownership & Access Boundary (IDOR Protection)**: Introduce explicit user-scoping on ticket retrieval (`user_id` validation) and restrict ticket listing/detail access to verified user identities or service callers. Disallow wildcard CORS credentials.
- **Hermetic Test Isolation**: Formalize hermetic test fixtures ensuring all external network boundaries (SMTP, Telegram, AI APIs) are completely mocked by default during tests regardless of `.env` configuration.

## Capabilities

### New Capabilities
<!-- None: all changes modify existing capabilities -->

### Modified Capabilities
- `email-support`: Enhance inbound email webhook authentication to support header-based token verification and log redaction; wrap asynchronous email background tasks in safe exception handlers.
- `ticket-escalation`: Enforce user ownership validation on ticket queries to prevent IDOR vulnerabilities; isolate background task dispatching from request lifecycle errors.

## Impact

- **Affected Code**: `backend/main.py`, `backend/services/ticket_service.py`, `backend/services/email_service.py`, `backend/services/telegram_relay.py`, `tests/conftest.py`.
- **APIs**:
  - `POST /api/webhooks/email-inbound/brevo`: accepts `X-Webhook-Token` header in addition to `?token=`.
  - `GET /api/tickets` & `GET /api/tickets/{id}`: accepts optional `user_id` query/header filter for ownership enforcement.
- **Dependencies**: No new external dependencies required; utilizes standard FastAPI/Starlette, Python logging, and asyncio constructs.
