## MODIFIED Requirements

### Requirement: Email notification upon ticket escalation
When a support ticket is created and email support is enabled (`EMAIL_ENABLED=true`), the system SHALL dispatch an email notification to the configured support inbox containing ticket details. When email support is disabled (`EMAIL_ENABLED=false`), no email notification SHALL be dispatched and the ticket workflow SHALL proceed solely on Telegram.

#### Scenario: Dispatching ticket creation email
- **WHEN** a support ticket is created and email support is enabled (`EMAIL_ENABLED=true`)
- **THEN** the system sends an email with the subject format `[Ticket #<id>] Nouvelle demande de support de @<user>` containing the inquiry and user details

#### Scenario: Bypassing ticket creation email when disabled
- **WHEN** a support ticket is created and email support is disabled (`EMAIL_ENABLED=false`)
- **THEN** the system does not dispatch any email notification and logs no SMTP errors, proceeding purely with Telegram notification

### Requirement: Inbound email resolution processing
The system SHALL accept inbound email replies to support tickets only when email support is enabled (`EMAIL_ENABLED=true`), extract the ticket ID from the subject, and transition the ticket to resolved. When email support is disabled (`EMAIL_ENABLED=false`), the inbound email endpoints SHALL reject requests with HTTP 503 Service Unavailable. In addition to the generic single-email inbound webhook, the system SHALL accept Brevo's native Inbound Parsing webhook shape when enabled, authenticated by a shared secret rather than the generic endpoint's HMAC-signed body, and SHALL process every email in a Brevo batch independently so that one item's failure does not prevent the others in the same batch from being resolved.

#### Scenario: Inbound email with valid ticket ID
- **WHEN** an inbound email is received with subject matching `[Ticket #<id>]` and non-empty body while email support is enabled
- **THEN** the system resolves the ticket, delivers the solution to the user on Telegram, and records the resolution channel as `EMAIL`

#### Scenario: Inbound email for already resolved ticket
- **WHEN** an inbound email is received for a ticket that is already `RESOLVED` while email support is enabled
- **THEN** the system ignores duplicate delivery to the user and logs or sends a notification that the ticket is already closed

#### Scenario: Brevo batch webhook with multiple emails
- **WHEN** Brevo's Inbound Parsing webhook posts a payload containing more than one parsed email in the same request while email support is enabled
- **THEN** the system resolves each email's ticket independently and reports a per-email outcome, without letting one email's failure block the others

#### Scenario: Brevo webhook request missing or with an invalid shared secret
- **WHEN** a request to the Brevo inbound webhook endpoint does not carry the configured shared secret, or carries the wrong one
- **THEN** the system rejects the request and performs no ticket resolution

#### Scenario: Brevo item whose subject has no ticket reference
- **WHEN** one email within a Brevo batch has a subject that does not match `[Ticket #<id>]`
- **THEN** that email is reported as unresolved in the response, while other emails in the same batch are still processed normally

#### Scenario: Inbound email rejected when email support is disabled
- **WHEN** a request is made to an inbound email endpoint while email support is disabled (`EMAIL_ENABLED=false`)
- **THEN** the system returns HTTP 503 Service Unavailable and does not process any ticket resolution

### Requirement: Cross-channel synchronization notification
When a ticket is resolved on one channel, the system SHALL notify the other channel of the resolution if that channel is enabled. Specifically, resolution on Telegram notifies the email channel only when `EMAIL_ENABLED=true`.

#### Scenario: Ticket resolved on Telegram
- **WHEN** an agent resolves a ticket in the Telegram support group and `EMAIL_ENABLED=true`
- **THEN** an email notification is dispatched to the support inbox indicating the ticket was resolved on Telegram

#### Scenario: Ticket resolved on Telegram with email disabled
- **WHEN** an agent resolves a ticket in the Telegram support group and `EMAIL_ENABLED=false`
- **THEN** no email notification task is scheduled and resolution completes exclusively on Telegram

#### Scenario: Ticket resolved via Email
- **WHEN** an agent resolves a ticket via email while email support is enabled
- **THEN** a notification is posted to the Telegram support group indicating the ticket was resolved via email

## ADDED Requirements

### Requirement: Dormant email subsystem in Telegram-only mode
The system SHALL support operating in a pure Telegram mode when email configuration is omitted or disabled in `.env`.

#### Scenario: Pure Telegram deployment without email configuration
- **WHEN** the application starts with default or unconfigured email settings (`EMAIL_ENABLED=false`)
- **THEN** all user queries, ticket escalations, admin notifications, and agent replies execute cleanly on Telegram without attempting any external SMTP connections or requiring email webhook secrets
