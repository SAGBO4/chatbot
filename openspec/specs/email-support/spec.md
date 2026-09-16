# email-support Specification

## Purpose
Provides email notification dispatching for escalated support tickets via SMTP, handles inbound email solutions from support agents, and synchronizes cross-channel resolution state between email and Telegram.

## Requirements

### Requirement: Email notification upon ticket escalation
When a support ticket is created, the system SHALL dispatch an email notification to the configured support inbox containing ticket details.

#### Scenario: Dispatching ticket creation email
- **WHEN** a support ticket is created
- **THEN** the system sends an email with the subject format `[Ticket #<id>] Nouvelle demande de support de @<user>` containing the inquiry and user details

### Requirement: Inbound email resolution processing
The system SHALL accept inbound email replies to support tickets, extract the ticket ID from the subject, and transition the ticket to resolved. In addition to the generic single-email inbound webhook, the system SHALL accept Brevo's native Inbound Parsing webhook shape, authenticated by a shared secret rather than the generic endpoint's HMAC-signed body, and SHALL process every email in a Brevo batch independently so that one item's failure does not prevent the others in the same batch from being resolved.

#### Scenario: Inbound email with valid ticket ID
- **WHEN** an inbound email is received with subject matching `[Ticket #<id>]` and non-empty body
- **THEN** the system resolves the ticket, delivers the solution to the user on Telegram, and records the resolution channel as `EMAIL`

#### Scenario: Inbound email for already resolved ticket
- **WHEN** an inbound email is received for a ticket that is already `RESOLVED`
- **THEN** the system ignores duplicate delivery to the user and logs or sends a notification that the ticket is already closed

#### Scenario: Brevo batch webhook with multiple emails
- **WHEN** Brevo's Inbound Parsing webhook posts a payload containing more than one parsed email in the same request
- **THEN** the system resolves each email's ticket independently and reports a per-email outcome, without letting one email's failure block the others

#### Scenario: Brevo webhook request missing or with an invalid shared secret
- **WHEN** a request to the Brevo inbound webhook endpoint does not carry the configured shared secret, or carries the wrong one
- **THEN** the system rejects the request and performs no ticket resolution

#### Scenario: Brevo item whose subject has no ticket reference
- **WHEN** one email within a Brevo batch has a subject that does not match `[Ticket #<id>]`
- **THEN** that email is reported as unresolved in the response, while other emails in the same batch are still processed normally

### Requirement: Cross-channel synchronization notification
When a ticket is resolved on one channel, the system SHALL notify the other channel of the resolution.

#### Scenario: Ticket resolved on Telegram
- **WHEN** an agent resolves a ticket in the Telegram support group
- **THEN** an email notification is dispatched to the support inbox indicating the ticket was resolved on Telegram

#### Scenario: Ticket resolved via Email
- **WHEN** an agent resolves a ticket via email
- **THEN** a notification is posted to the Telegram support group indicating the ticket was resolved via email

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

### Requirement: Resilient asynchronous email dispatch
The system SHALL isolate asynchronous email dispatches in defensive fault-handling blocks so that SMTP connection dropouts, timeouts, or unexpected network failures never propagate unhandled exceptions to the HTTP request lifecycle.

#### Scenario: Background ticket created email dispatch encounters connection failure
- **WHEN** a ticket is created and the background email task fails to reach the SMTP relay
- **THEN** the error is logged as an error with ticket context, and the client receives an uninterrupted HTTP 201 response with the ticket stored in the database

#### Scenario: Background ticket resolved email dispatch encounters socket timeout
- **WHEN** a ticket is resolved and the resolution notification email task encounters a socket timeout
- **THEN** the exception is caught and logged, preserving the ticket's resolved state and completing the API response cleanly
