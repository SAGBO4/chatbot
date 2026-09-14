## Context

See `proposal.md` for background. The system extends the existing Telegram support bot architecture with an email notification and resolution engine, enabling support teams to monitor and answer tickets across both Telegram and Email simultaneously.

## Goals / Non-Goals

**Goals:**
- Dispatch email alerts to the support inbox via SMTP whenever a new ticket is escalated.
- Accept incoming email replies through an inbound webhook (`POST /api/webhooks/email-inbound`), parsing the ticket ID from the subject (`[Ticket #<id>]`).
- Enforce strict concurrency safety: whichever channel replies first resolves the ticket, delivers the answer to the user on Telegram, and ingests the solution into the Knowledge Base.
- Synchronize closure state: notify the Telegram group when resolved via email; notify the email thread when resolved via Telegram.

**Non-Goals:**
- Hosting an internal mail server (relies on standard external SMTP servers like Gmail, Mailgun, SendGrid, Postmark, or local postfix).
- Complex HTML email parsing (clean extraction of plain text reply content).

## Decisions

### Decision 1: Email Notification Dispatcher
- **Choice**: Standard Python `email.message.EmailMessage` executed asynchronously.
- **Rationale**: Zero external heavy dependencies, maximum reliability, standard compliant across all SMTP hosts.

### Decision 2: Inbound Email Webhook Interface
- **Choice**: `POST /api/webhooks/email-inbound` accepting `sender`, `subject`, and `body` payload (or form-data), parsing ticket ID regex `r"\[Ticket #(\d+)\]"`.
- **Rationale**: Standard interface easily integrated with webhooks from Mailgun, SendGrid, Postmark, AWS SES, or a simple IMAP relay script.

### Decision 3: Atomic Channel Synchronization & Race Prevention
- **Choice**: `TicketService.resolve_ticket` checks whether `status == TicketStatus.RESOLVED`. If already resolved, returns `is_newly_resolved = False`.
- **Rationale**: Completely prevents sending duplicate responses to the user if two agents reply on different channels at the exact same moment.

## Risks / Trade-offs

- **[Risk] SMTP Network Latency**: Sending an email via SMTP could take several hundred milliseconds.
  - *Mitigation*: Run SMTP sending as a background task (`asyncio.create_task` or FastAPI `BackgroundTasks`) so that the Telegram bot UI responds instantaneously to the user.
- **[Risk] Quoted Email Reply Bloat**: Email replies often include previous thread history.
  - *Mitigation*: Apply clean delimiter stripping (e.g. cutting off text at `On ... wrote:`, `Le ... a écrit :`, or `---`).
