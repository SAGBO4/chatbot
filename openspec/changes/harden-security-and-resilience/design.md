## Context

The backend is built with FastAPI, SQLAlchemy 2.0 (asyncio + aiosqlite), and integrates with Telegram (via Aiogram / HTTP relay) and email (SMTP + inbound webhooks). 

Recent security tests highlighted four key issues (see `proposal.md`):
1. Brevo inbound webhook token passed via `?token=...` is logged in plain text by access logs, reverse proxies, and HTTP clients.
2. Background task failures inside FastAPI `BackgroundTasks` bubble up during response transmission, triggering 500 errors after DB commit.
3. Ticket endpoints rely solely on a single global `API_KEY` header without user-scoping or IDOR validation.
4. Unit tests inadvertently initiated real SMTP and Telegram network connections when active credentials existed in `.env`.

## Goals / Non-Goals

**Goals:**
- Provide dual authentication for the Brevo webhook: support `X-Webhook-Token` (or `X-Brevo-Token`) header as primary, while keeping `?token=...` for backward compatibility with query log redaction guidance.
- Guard all asynchronous task calls (`EmailService`, `TelegramRelay`) with safe exception boundaries so that background network failures never fail the main request or bubble into Starlette's ASGI response loop.
- Introduce user ownership validation on ticket retrieval endpoints (`user_id` query/header check) to protect against IDOR vulnerabilities when invoked on behalf of end-users.
- Formalize hermetic test fixtures in `tests/conftest.py` ensuring that no test initiates real outbound network traffic to SMTP relays or Telegram APIs.

**Non-Goals:**
- Implementing a full OAuth2/OIDC or JWT session provider for the Telegram bot itself (the bot continues using `X-API-Key` as a trusted service caller, but passes user context).
- Removing Brevo `?token=` completely (this would break existing deployments where Brevo does not support custom webhook headers).

## Decisions

### Decision 1: Dual-mode Token Verification for Brevo Inbound Webhook
- **Choice**: In `verify_brevo_inbound_token`, check for `X-Webhook-Token` or `X-Brevo-Token` request header first. If absent, fall back to checking the `?token=` query parameter using `hmac.compare_digest`.
- **Rationale**: Reverse proxies and modern webhook relays can forward secrets in custom headers, preventing URL logging. Keeping the query parameter maintains 100% backward compatibility with standard Brevo configurations.
- **Alternatives Considered**: Rejecting `?token=` entirely would break existing Brevo webhook delivery since Brevo's native webhook settings sometimes restrict custom headers.

### Decision 2: Defensive Wrapper for Background Tasks
- **Choice**: Wrap background task functions (`EmailService.send_ticket_created_notification`, `EmailService.send_ticket_resolved_notification`, `TelegramRelay.send_message_to_user`, `TelegramRelay.notify_support_group`) in a resilient wrapper that catches all `Exception` classes, logs the error with full diagnostic context, and returns `False` instead of bubbling up.
- **Rationale**: Starlette's `BackgroundTasks` executes tasks inside `response(scope, receive, send)`. An unhandled exception during response serialization leads to a server crash or 500 error even if database transactions succeeded.
- **Alternatives Considered**: Using Celery/Redis for background jobs was considered too heavyweight for this single-node bot deployment.

### Decision 3: User Ownership Scoping on Ticket Endpoints (IDOR Mitigation)
- **Choice**: Extend `/api/tickets` and `/api/tickets/{ticket_id}` with an optional `request_user_id` parameter. When provided, verify that the ticket's `user_id` matches `request_user_id`. When called by the bot administrative context without `request_user_id`, allow master access via `API_KEY`.
- **Rationale**: Prevents IDOR if a user-facing client or frontend calls the backend, while preserving the Telegram bot's administrative capabilities.
- **Alternatives Considered**: Full JWT user auth. Deferred to when a dedicated web portal is introduced.

### Decision 4: Hermetic Mocking in Test Configuration
- **Choice**: Keep the autouse fixtures in `tests/conftest.py` that intercept and mock `EmailService._send_smtp_sync` and `TelegramRelay._send_telegram_message` unless running a dedicated integration test file.
- **Rationale**: Guarantees fast, deterministic, and safe tests without spamming production inboxes or Telegram chats.

## Risks / Trade-offs

- **[Risk] Brevo sends token only in query parameter** → *Mitigation*: Support query parameter fallback with constant-time check, and provide reverse proxy configuration templates (Nginx/Caddy) to strip query strings from access log formats (`$request_uri` vs `$uri`).
- **[Risk] Silent failure of background notifications** → *Mitigation*: Log all caught background exceptions at `logging.ERROR` level with structured ticket context and send telemetry to Sentry if configured.
- **[Risk] Breaking bot ticket lookups with user-scoping** → *Mitigation*: Make `request_user_id` optional on service-to-service calls authenticated with `API_KEY`.

## Migration Plan

1. Deploy updated backend code supporting header-based token verification and defensive background wrappers.
2. Update reverse proxy configuration to mask `?token=` in access logs or configure relay to pass `X-Webhook-Token`.
3. Verify test suite passes cleanly with hermetic fixtures enabled.
