## Context

See proposal.md - Why. Confirmed against Brevo's published Inbound Parsing documentation: the
webhook POSTs a JSON body shaped as `{"items": [...]}`- one or more parsed emails per call - where
each item carries (among other fields) `From.Address`, `Subject`, `RawTextBody`,
`ExtractedMarkdownMessage` (Brevo's own signature-stripped plain-text extraction), and `MessageId`.
Brevo does not sign the request or offer a shared-secret header of its own; the only way to
authenticate that a call genuinely comes from the webhook you configured is a secret you choose
and embed in the URL you give Brevo.

The existing endpoint `backend/main.py::handle_inbound_email` already implements every piece of
resolution logic this needs (ticket lookup by `[Ticket #<id>]` in the subject, already-resolved
handling, `clean_email_reply_body`, Telegram delivery, knowledge-base ingestion via
`TicketService.resolve_ticket`) - just wired to a single-item, HMAC-signed request shape.

## Goals / Non-Goals

**Goals:**
- Let a real support agent's email reply, relayed through Brevo, resolve a ticket automatically -
  closing the gap named in `TODO.md` section 5.
- Reuse the existing resolution behavior byte-for-byte (same subject regex, same body cleanup,
  same Telegram/KB side effects) rather than re-implementing it for Brevo.
- Handle Brevo's batching (`items[]`) without one bad item aborting the whole webhook call.

**Non-Goals:**
- No support for any other provider's native webhook shape - only Brevo, since that is what the
  user uses. The generic `/api/webhooks/email-inbound` endpoint remains available for anything
  that already speaks its simple format.
- No attachment handling (Brevo's `Attachments` field) - out of scope; agents are expected to reply
  in the email body, as today.
- No change to how outbound emails are sent (already documented as Brevo-SMTP-compatible in
  `TODO.md` section 4, no code change needed there).

## Decisions

- **Native parsing over an adapter (Option B, chosen over Option A)**: implement a dedicated
  endpoint that understands Brevo's shape directly, rather than a separate small relay
  service/script that converts Brevo's payload and re-POSTs to the existing endpoint. Rationale:
  one fewer service to deploy, configure, and keep alive/monitored; the "convert and re-sign"
  adapter would duplicate the same field-mapping logic this endpoint needs anyway, just with an
  extra network hop and an extra place authentication can silently break. Trade-off accepted: the
  backend now has one provider-specific endpoint, whereas the generic one stays provider-agnostic.
- **New endpoint, not a modified existing one**: `POST /api/webhooks/email-inbound/brevo` is
  additive. The existing `/api/webhooks/email-inbound` (HMAC-signed, single-item) is left exactly
  as-is - nothing currently depends on Brevo's shape, and a future second provider can get its own
  endpoint the same way without disturbing this one.
- **Authentication: shared secret via query parameter, not HMAC**: Brevo cannot compute an
  HMAC signature over a secret it doesn't have, and its documented webhook configuration does not
  expose a "custom header" option - only the destination URL is configurable. A secret embedded in
  that URL (`?token=<BREVO_INBOUND_SECRET>`) is therefore the practical option, checked with
  `hmac.compare_digest` (constant-time, same discipline as the other secrets) and fail-closed
  (503) if `BREVO_INBOUND_SECRET` is unset - consistent with `verify_email_webhook_signature` and
  `verify_api_key`. New dedicated setting rather than reusing `EMAIL_WEBHOOK_SECRET`: the two
  secrets protect different transports (an HTTP body HMAC vs. a URL token) with different exposure
  risks (see Risks), so keeping them distinct means rotating one never silently affects the other.
- **Shared resolution helper**: extract the per-email resolution logic already in
  `handle_inbound_email` (ticket lookup, `clean_email_reply_body`, `TicketService.resolve_ticket`,
  Telegram notifications) into a plain function taking `(sender, subject, body, session,
  background_tasks)` and returning a result (status/ticket_id/message) instead of raising
  HTTPException directly. `handle_inbound_email` keeps its current single-item contract (raises on
  no-subject-match/not-found, as it does today); the new Brevo endpoint calls the same helper once
  per `items[]` entry and collects results into a list, converting a "not found"/"no ticket in
  subject" outcome into a per-item entry in the response rather than aborting the batch.
- **Body extraction preference**: use `ExtractedMarkdownMessage` when Brevo provides a non-empty
  value (it already strips quoted history and signatures on Brevo's side), falling back to
  `RawTextBody` otherwise; either way the result still passes through the existing
  `clean_email_reply_body` as a second pass, so behavior degrades gracefully if Brevo's extraction
  ever misses a quote marker our own regex still catches.
- **Sender identity**: use the item's `From.Address` as `resolved_by`, matching what the generic
  endpoint does with its `sender` field.

## Risks / Trade-offs

- [Risk] A secret in a URL query string can end up in web-server access logs or browser history in
  a way a header/body signature would not. → Mitigation: HTTPS still encrypts the URL in transit;
  document (README/`.env.example`) that access-log query-string capture should be disabled for
  this path on whatever reverse proxy fronts the backend, and that the secret should be a long
  random value treated like any other credential.
- [Risk] Brevo's exact field names/shape could differ from what current documentation describes,
  or change over time. → Mitigation: parsing is isolated to one small function
  (`_parse_brevo_item` or similar) with a schema that fails clearly (422) on an unexpected shape,
  rather than silently misreading a field; easy to adjust in one place if Brevo's payload evolves.
- [Risk] Duplicate delivery: Brevo (like most webhook providers) may retry a delivery it considers
  failed. → Mitigation: already handled - `TicketService.resolve_ticket` is idempotent per ticket
  (a second resolution attempt on an already-`RESOLVED` ticket is a no-op that reports
  "already_resolved", exactly as the existing generic endpoint already relies on).

## Migration Plan

- Purely additive: new endpoint, new setting, no schema/data changes. Safe to deploy without any
  pre-existing behavior changing.
- Rollout: after deploying, set `BREVO_INBOUND_SECRET` in `.env`, then configure Brevo's dashboard
  to POST its Inbound Parsing webhook to
  `https://<backend-host>/api/webhooks/email-inbound/brevo?token=<BREVO_INBOUND_SECRET>`.
- Rollback: remove/disable the Brevo webhook configuration in Brevo's dashboard and/or revert the
  commit; the generic endpoint and all other behavior are unaffected either way.
