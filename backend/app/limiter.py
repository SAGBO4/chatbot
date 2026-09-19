"""
Rate limiting for the API, built on `slowapi` (a hard dependency, see requirements.txt).

Exposes `limiter` (used as `@limiter.limit("30/minute")`), `RateLimitExceeded` and the 429 handler.
Counters live in the process, so limits are per worker, not shared between workers.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address as slowapi_get_remote_address

__all__ = ["limiter", "Limiter", "RateLimitExceeded", "get_remote_address", "_rate_limit_exceeded_handler"]


def _rate_limit_exceeded_handler(request: Request, exc: Exception):
    """Turn a rate-limit error into a 429 JSON response (the message goes in both `detail` and `error`)."""
    detail = getattr(exc, "detail", "Rate limit exceeded")
    msg = f"Rate limit exceeded: {detail}" if "Rate limit exceeded" not in str(detail) else str(detail)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": msg, "error": msg},
    )


def get_remote_address(*args, **kwargs) -> str:
    """Client IP used as the rate-limit key; `127.0.0.1` when no request is available."""
    if args and hasattr(args[0], "client"):
        return slowapi_get_remote_address(args[0])
    request = kwargs.get("request")
    if request and hasattr(request, "client"):
        return slowapi_get_remote_address(request)
    return "127.0.0.1"


limiter = Limiter(key_func=get_remote_address)
