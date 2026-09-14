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
The system SHALL accept inbound email replies to support tickets, extract the ticket ID from the subject, and transition the ticket to resolved.

#### Scenario: Inbound email with valid ticket ID
- **WHEN** an inbound email is received with subject matching `[Ticket #<id>]` and non-empty body
- **THEN** the system resolves the ticket, delivers the solution to the user on Telegram, and records the resolution channel as `EMAIL`

#### Scenario: Inbound email for already resolved ticket
- **WHEN** an inbound email is received for a ticket that is already `RESOLVED`
- **THEN** the system ignores duplicate delivery to the user and logs or sends a notification that the ticket is already closed

### Requirement: Cross-channel synchronization notification
When a ticket is resolved on one channel, the system SHALL notify the other channel of the resolution.

#### Scenario: Ticket resolved on Telegram
- **WHEN** an agent resolves a ticket in the Telegram support group
- **THEN** an email notification is dispatched to the support inbox indicating the ticket was resolved on Telegram

#### Scenario: Ticket resolved via Email
- **WHEN** an agent resolves a ticket via email
- **THEN** a notification is posted to the Telegram support group indicating the ticket was resolved via email

### Requirement: Inbound webhook secret logging protection
The system and deployment documentation SHALL ensure that reverse proxies and gateway access logs do not expose sensitive webhook query tokens (such as `BREVO_INBOUND_SECRET` transmitted via URL parameters).

#### Scenario: Request routed through reverse proxy
- **WHEN** Brevo delivers an inbound email webhook payload to `/api/webhooks/email-inbound/brevo?token=...`
- **THEN** reverse proxy configurations (Nginx/Caddy) strip or redact the token from standard access log outputs while passing the request intact to the backend service
