"""Authentication checks for the API: the shared API key and the two inbound-email webhook secrets."""
import hashlib
import hmac
from typing import Optional

from fastapi import Header, HTTPException, status

from app.config import settings


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


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
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
