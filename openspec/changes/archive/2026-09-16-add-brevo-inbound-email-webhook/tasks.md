## 1. Config

- [x] 1.1 Add `BREVO_INBOUND_SECRET: Optional[str] = None` to `Settings` in `backend/config.py`,
  documented the same way as `EMAIL_WEBHOOK_SECRET`. Add it to `.env.example` and the local `.env`
  with a freshly generated random value (`openssl rand -hex 32`), matching the pattern already
  used for `API_KEY`/`EMAIL_WEBHOOK_SECRET`.

## 2. Extract the shared resolution helper

- [x] 2.1 In `backend/main.py`, extract the per-email resolution logic currently inline in
  `handle_inbound_email` (ticket-id-from-subject regex, `clean_email_reply_body`,
  `TicketService.resolve_ticket` call, Telegram user notification, Telegram group notification)
  into a plain async helper, e.g. `_resolve_inbound_email(session, background_tasks, sender,
  subject, body) -> dict`, returning a result dict (`status`, `ticket_id`, and either `message` or
  `resolved_by`/`channel` matching today's response shapes) instead of raising `HTTPException` for
  the "no ticket id in subject" and "ticket not found" cases - it returns a
  `{"status": "no_ticket_reference", ...}` / `{"status": "ticket_not_found", ...}` dict instead.
- [x] 2.2 Update `handle_inbound_email` to call this helper and translate `no_ticket_reference` /
  `ticket_not_found` results back into the existing `HTTPException(400)` / `HTTPException(404)`,
  so its observable behavior and response bodies are byte-for-byte unchanged. Verify with
  `pytest tests/test_email_sync.py -q` (must still fully pass, unmodified).

## 3. Brevo payload schema and parsing

- [x] 3.1 Add `BrevoInboundItem` and `BrevoInboundWebhookRequest` (or similarly named) Pydantic
  models in `backend/schemas.py` matching Brevo's Inbound Parsing shape: top-level `items: List[...]`,
  each item with at least `From` (object with `Address`), `Subject`, `RawTextBody`, and
  `ExtractedMarkdownMessage` (optional/nullable - Brevo may omit it).
- [x] 3.2 Add a small helper that picks the body to use per item: `ExtractedMarkdownMessage` if
  present and non-empty, else `RawTextBody`, then still passed through the existing
  `clean_email_reply_body` (per design.md - second pass for safety). Verify with a direct unit test
  covering both the "markdown present" and "markdown empty/missing" cases.

## 4. New endpoint

- [x] 4.1 Add `POST /api/webhooks/email-inbound/brevo` in `backend/main.py`, accepting `token` as a
  query parameter, verifying it against `settings.BREVO_INBOUND_SECRET` with
  `hmac.compare_digest` - fail-closed (503) if the secret is not configured, 401 if missing/wrong,
  mirroring `verify_email_webhook_signature`'s structure.
- [x] 4.2 On success, iterate the payload's `items`, calling the helper from 2.1 for each (using
  the body-selection helper from 3.2), and collect one result entry per item (ticket id, status,
  from 2.1's result dict) into a response list - a single item's `no_ticket_reference` or
  `ticket_not_found` outcome must not raise or stop processing the remaining items.
- [x] 4.3 Return `{"results": [...]}` (one entry per input item, same shape used per-item as the
  existing endpoint's success/already_resolved/error bodies) with HTTP 200 as long as the request
  itself was authenticated and well-formed, regardless of individual item outcomes.

## 5. Tests

- [x] 5.1 Add `tests/test_brevo_inbound_webhook.py` (or extend `tests/test_email_sync.py`) covering:
  - a single-item Brevo payload resolving a real ticket end-to-end (ticket created, Brevo webhook
    posted, ticket resolved, Telegram relay called, KB updated) - mirroring the existing
    `test_email_inbound_resolution_and_race_condition` assertions;
  - a two-item batch where one item resolves successfully and the other has a subject with no
    ticket reference - assert both outcomes are reported and the valid one is actually resolved;
  - missing `token` query parameter → 401;
  - wrong `token` value → 401;
  - `BREVO_INBOUND_SECRET` unset → 503;
  - an item using `RawTextBody` only (no `ExtractedMarkdownMessage`) still resolves correctly.
  Verify with `pytest tests/test_brevo_inbound_webhook.py -q` (or the extended file).

## 6. Docs and full verification

- [x] 6.1 Update `TODO.md` section 5 (Brevo inbound email) to reflect that the endpoint now exists,
  with the exact webhook URL format to configure in Brevo's dashboard
  (`https://<backend-host>/api/webhooks/email-inbound/brevo?token=<BREVO_INBOUND_SECRET>`), and a
  note that access-log query-string capture should be disabled for this path if a reverse proxy
  sits in front of the backend (per design.md Risks).
- [x] 6.2 Run the full test suite (`pytest -q`) and confirm every pre-existing test still passes
  alongside the new ones from section 5.
