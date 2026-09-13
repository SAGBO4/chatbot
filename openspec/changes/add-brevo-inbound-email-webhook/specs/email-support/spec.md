## MODIFIED Requirements

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
