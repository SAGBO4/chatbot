## MODIFIED Requirements

### Requirement: Inbound webhook secret logging protection
The system and deployment configuration SHALL ensure that webhook secrets are not leaked into access logs or error logs. The Brevo inbound webhook SHALL accept authentication tokens supplied via the `X-Webhook-Token` header (or `X-Brevo-Token`) as the primary mechanism, while maintaining backward-compatible support for `?token=...` query parameters with log masking.

#### Scenario: Request authenticated via header
- **WHEN** Brevo or a relay delivers an inbound email webhook payload with a valid `X-Webhook-Token` header
- **THEN** the system authenticates the request without exposing any token in the URL query string

#### Scenario: Request authenticated via query parameter with log redaction
- **WHEN** Brevo delivers an inbound email webhook payload with `?token=...`
- **THEN** the system validates the token using constant-time comparison and ensures the token value is redacted from access logs and diagnostic logs

#### Scenario: Request routed through reverse proxy
- **WHEN** Brevo delivers an inbound email webhook payload to `/api/webhooks/email-inbound/brevo?token=...`
- **THEN** reverse proxy configurations (Nginx/Caddy) strip or redact the token from standard access log outputs while passing the request intact to the backend service

## ADDED Requirements

### Requirement: Resilient asynchronous email dispatch
The system SHALL isolate asynchronous email dispatches in defensive fault-handling blocks so that SMTP connection dropouts, timeouts, or unexpected network failures never propagate unhandled exceptions to the HTTP request lifecycle.

#### Scenario: Background ticket created email dispatch encounters connection failure
- **WHEN** a ticket is created and the background email task fails to reach the SMTP relay
- **THEN** the error is logged as an error with ticket context, and the client receives an uninterrupted HTTP 201 response with the ticket stored in the database

#### Scenario: Background ticket resolved email dispatch encounters socket timeout
- **WHEN** a ticket is resolved and the resolution notification email task encounters a socket timeout
- **THEN** the exception is caught and logged, preserving the ticket's resolved state and completing the API response cleanly
