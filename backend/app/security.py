"""Authentication checks for the API: the shared API key and the two inbound-email webhook secrets."""
import hashlib
import hmac
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, APIKeyQuery

from app.config import settings

# The credentials are declared as OpenAPI security schemes, so /docs offers an Authorize button instead of a
# header field on every route. `auto_error=False`: the verify_* functions below give the precise error.
api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="ApiKey",
    auto_error=False,
    description="The shared secret configured as `API_KEY` on the server (the bot and the web portal send it).",
)
webhook_signature_header = APIKeyHeader(
    name="X-Webhook-Signature",
    scheme_name="WebhookSignature",
    auto_error=False,
    description="Hex HMAC-SHA256 of the raw request body, keyed with `EMAIL_WEBHOOK_SECRET` (a `sha256=` prefix is accepted).",
)
brevo_token_header = APIKeyHeader(
    name="X-Webhook-Token",
    scheme_name="BrevoTokenHeader",
    auto_error=False,
    description="Shared secret `BREVO_INBOUND_SECRET`. Preferred over the query parameter: it stays out of access logs.",
)
brevo_alt_token_header = APIKeyHeader(
    name="X-Brevo-Token",
    scheme_name="BrevoAltTokenHeader",
    auto_error=False,
    description="Same secret as `X-Webhook-Token`, for callers that cannot use that header name.",
)
brevo_token_query = APIKeyQuery(
    name="token",
    scheme_name="BrevoTokenQuery",
    auto_error=False,
    description="Same secret as `X-Webhook-Token`, kept for compatibility (the server redacts it from its logs).",
)


def verify_email_webhook_signature(raw_body: bytes, signature: Optional[str]) -> None:
    """
    Verifies the HMAC-SHA256 signature of an inbound email webhook request.

    Raises HTTPException if the webhook secret is not configured (fail closed),
    the signature header is missing, or the signature does not match.
    """
    if not settings.EMAIL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email support is disabled (EMAIL_ENABLED=False).",
        )
    if not settings.EMAIL_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email webhook is not configured (EMAIL_WEBHOOK_SECRET missing).",
        )
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Webhook-Signature header.",
        )
    sig = signature.strip()
    if sig.lower().startswith("sha256="):
        sig = sig.split("=", 1)[1].strip()
    expected = hmac.new(
        settings.EMAIL_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, sig.lower()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )


def verify_api_key(x_api_key: Optional[str] = Security(api_key_header)) -> None:
    """
    Verifies the shared API key sent by trusted callers (the Telegram bot).

    Raises HTTPException if the API key is not configured (fail closed, so
    the backend cannot be deployed unprotected by omission), the header is
    missing, or it does not match.
    """
    if not settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend API is not configured (API_KEY missing).",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header.",
        )


def verify_brevo_inbound_token(
    token: Optional[str] = None,
    header_token: Optional[str] = None,
) -> None:
    """
    Verify the shared secret sent with every Brevo inbound webhook call, either in an
    `X-Webhook-Token` / `X-Brevo-Token` header or as a `?token=` query parameter.

    Brevo does not sign its requests. The headers keep the token out of HTTP access logs;
    `?token=` remains supported for compatibility.

    Raises HTTPException if the secret is not configured (fail closed), or the token is missing or wrong.
    """
    if not settings.EMAIL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email support is disabled (EMAIL_ENABLED=False).",
        )
    if not settings.BREVO_INBOUND_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Brevo inbound webhook is not configured (BREVO_INBOUND_SECRET missing).",
        )
    candidate = header_token or token
    if not candidate or not hmac.compare_digest(candidate, settings.BREVO_INBOUND_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token query parameter or header.",
        )
