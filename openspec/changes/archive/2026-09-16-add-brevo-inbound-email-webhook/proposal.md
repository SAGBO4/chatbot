## Why

The existing inbound-email path (`POST /api/webhooks/email-inbound`) expects a simple
`{sender, subject, body}` JSON body signed with an HMAC-SHA256 header, which nothing produces
today - it was designed generically, ahead of picking an actual provider. The user has since
chosen Brevo for outbound/inbound email, and Brevo's "Inbound Parsing" webhook posts a materially
different payload: a batch (`items[]`) of parsed emails, each with its own field names
(`From.Address`, `Subject`, `RawTextBody`, `ExtractedMarkdownMessage`, `MessageId`, ...), and no
request signing or shared-secret mechanism of its own. Without support for this exact shape, a
support agent's email reply can never resolve a ticket automatically - only the Telegram channel
works today (see `TODO.md`, section 5).

## What Changes

- Add a dedicated endpoint, `POST /api/webhooks/email-inbound/brevo`, that natively parses Brevo's
  Inbound Parsing payload shape (chosen over adapting a separate relay service - see design.md).
  The existing generic `/api/webhooks/email-inbound` endpoint is left untouched, for any other
  future relay/provider that already speaks its simple format.
- Since Brevo does not sign its webhook requests, authenticate calls to the new endpoint with a
  shared secret Brevo is configured to send back on every call (`BREVO_INBOUND_SECRET`, checked
  with a constant-time comparison, fail-closed if unconfigured - same posture as
  `EMAIL_WEBHOOK_SECRET` and `API_KEY`).
- Process every item in a Brevo payload's `items[]` array independently: a per-item failure (no
  matching `[Ticket #<id>]` in its subject, ticket not found) SHALL NOT prevent other items in the
  same batch from being processed; the response reports a per-item outcome.
- Reuse the existing ticket-subject regex and reply-body cleanup (`clean_email_reply_body`) so
  behavior (ticket lookup, resolution, Telegram delivery, knowledge-base ingestion, already-resolved
  handling) matches the existing generic endpoint exactly - extracted into a shared helper so both
  endpoints call the same resolution logic instead of duplicating it.

## Capabilities

### Modified Capabilities
- `email-support`: "Inbound email resolution processing" is extended to also accept Brevo's native
  Inbound Parsing webhook shape (a batch of items, processed independently), authenticated by a
  shared secret rather than the existing HMAC-signed body, while preserving all existing resolution
  behavior (ticket lookup by subject, already-resolved handling, Telegram delivery, knowledge-base
  ingestion).

## Impact

- Code: `backend/main.py` (new endpoint + shared resolution helper extracted from
  `handle_inbound_email`), `backend/config.py` (`BREVO_INBOUND_SECRET` setting), `backend/schemas.py`
  (Brevo payload schema), `.env.example`.
- No breaking change: the existing `/api/webhooks/email-inbound` endpoint, its request format, and
  its HMAC verification are unchanged.
- External: once this ships, configure Brevo's dashboard to POST its Inbound Parsing webhook to
  `https://<your-backend>/api/webhooks/email-inbound/brevo?token=<BREVO_INBOUND_SECRET>` (see
  design.md for why the secret travels as a query parameter here, unlike the HMAC-signed body used
  elsewhere).
