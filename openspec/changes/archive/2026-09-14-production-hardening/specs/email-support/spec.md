## ADDED Requirements

### Requirement: Inbound webhook secret logging protection
The system and deployment documentation SHALL ensure that reverse proxies and gateway access logs do not expose sensitive webhook query tokens (such as `BREVO_INBOUND_SECRET` transmitted via URL parameters).

#### Scenario: Request routed through reverse proxy
- **WHEN** Brevo delivers an inbound email webhook payload to `/api/webhooks/email-inbound/brevo?token=...`
- **THEN** reverse proxy configurations (Nginx/Caddy) strip or redact the token from standard access log outputs while passing the request intact to the backend service
