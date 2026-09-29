"""What the generated OpenAPI page (`/docs`) says about the API besides the routes themselves."""
from typing import Dict

from app.schemas import ErrorResponse

API_DESCRIPTION = """
Backend of the Telegram support bot: a knowledge base that answers questions, tickets escalated to a
support team, and the email and moderation features around them.

**Authentication.** Every `/api/*` route except the two email webhooks needs the shared secret in the
`X-API-Key` header (use the **Authorize** button). The server answers `503` until `API_KEY` is configured,
so it can never run unprotected by omission. The email webhooks have their own secrets, see their
descriptions.

**Errors.** They all share the body `{"detail": "..."}`. Validation errors (`422`) carry a list instead.

**Rate limits.** Some routes are limited per client IP (`429` when exceeded): ticket creation 10/min,
ticket resolution 15/min, knowledge ingestion 20/min, questions and webhooks 30/min.
""".strip()

TAGS_METADATA = [
    {"name": "system", "description": "Health check, for load balancers and platform health probes."},
    {"name": "query", "description": "Ask the knowledge base a question; the optional AI step rewrites the best article into an answer."},
    {"name": "tickets", "description": "Support tickets: opened when the bot could not help, resolved by an agent in Telegram or by email."},
    {"name": "knowledge", "description": "The knowledge base articles the bot answers from."},
    {"name": "moderation", "description": "Warnings issued to members of the community group."},
    {"name": "crypto", "description": "Market data for a crypto asset (cached, from a public price provider)."},
    {"name": "admin", "description": "Bot settings and the admin whitelist. Meant for the bot and the admin web portal."},
    {"name": "webhooks", "description": "Inbound support replies by email, from a signed relay or from Brevo. Each has its own secret, not the API key."},
]


def error_responses(codes: Dict[int, str]) -> dict:
    """The `responses=` entries for error statuses: every one is documented with the shared error body."""
    return {code: {"model": ErrorResponse, "description": description} for code, description in codes.items()}


# Statuses of every route that needs the API key
PROTECTED = error_responses({
    401: "The `X-API-Key` header is missing or wrong.",
    503: "`API_KEY` is not configured on the server (the API refuses everything until it is).",
})

RATE_LIMITED = error_responses({429: "Too many requests from this client: wait and retry."})
