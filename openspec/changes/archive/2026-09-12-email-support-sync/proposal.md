## Why

Support teams often operate across multiple communication channels, notably instant messaging (Telegram) and email inboxes. To maximize reaction speed without duplicating support efforts, support tickets must be dispatched to both channels simultaneously, with atomic synchronization ensuring that whichever channel replies first resolves the ticket and updates or closes the other channel.

## What Changes

- Implement an asynchronous Email service sending ticket notification emails to the support inbox via SMTP upon ticket creation.
- Implement an inbound email resolution endpoint (`POST /api/webhooks/email-inbound` and API resolver) that extracts ticket IDs from email subjects (`[Ticket #<id>]`) and marks tickets as resolved.
- Implement cross-channel synchronization:
  - When resolved on Telegram, send an email confirmation update to the support email thread.
  - When resolved via Email, notify the Telegram Support Group and deliver the solution directly to the user on Telegram.
  - Maintain the automatic knowledge base ingestion loop regardless of which channel resolved the ticket.
- Enforce strict first-responder concurrency protection preventing duplicate resolutions.

## Capabilities

### New Capabilities
- `email-support`: Asynchronous SMTP ticket notifications, inbound email reply processing, and cross-channel synchronization hooks.

### Modified Capabilities
- `ticket-escalation`: Extended to support multi-channel dispatch upon ticket creation and recording resolution channel (`TELEGRAM` or `EMAIL`).

## Impact

- **Backend Configuration**: New environment variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SUPPORT_EMAIL_RECIPIENT`, `EMAIL_ENABLED`).
- **Database Schema**: Added `channel_source` and `resolution_channel` fields to `tickets` table.
- **API Endpoints**: New endpoint `POST /api/webhooks/email-inbound` for receiving email replies.
- **Telegram Bot**: Added notification helper to post resolution updates into the support group when resolved via email.
