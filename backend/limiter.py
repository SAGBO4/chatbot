import time
from typing import Callable, Optional, Dict, List
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback when slowapi not installed
    SLOWAPI_AVAILABLE = False

    class RateLimitExceeded(HTTPException):
        def __init__(self, detail: str = "Rate limit exceeded"):
            super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)

    def _rate_limit_exceeded_handler(request: Request, exc: Exception):
        detail = getattr(exc, "detail", "Rate limit exceeded")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": detail},
        )

    def get_remote_address(request: Request) -> str:
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    def _parse_limit_string(limit_string: str) -> tuple[int, float]:
        parts = limit_string.lower().split("/")
        count = int(parts[0])
        unit = parts[1] if len(parts) > 1 else "minute"
        seconds_map = {
            "second": 1.0,
            "seconds": 1.0,
            "minute": 60.0,
            "minutes": 60.0,
            "hour": 3600.0,
            "hours": 3600.0,
            "day": 86400.0,
            "days": 86400.0,
        }
        window = seconds_map.get(unit, 60.0)
        return count, window

    class FallbackLimiter:
        def __init__(self, key_func: Callable[[Request], str] = get_remote_address, default_limits: Optional[List[str]] = None):
            self.key_func = key_func
            self.default_limits = default_limits or []
            self._history: Dict[str, List[float]] = {}

        def limit(self, limit_string: str):
            count, window = _parse_limit_string(limit_string)

            def decorator(func):
                from functools import wraps
                import inspect

                if inspect.iscoroutinefunction(func):
                    @wraps(func)
                    async def async_wrapper(*args, **kwargs):
                        request = kwargs.get("request")
                        if not request:
                            for arg in args:
                                if isinstance(arg, Request):
                                    request = arg
                                    break
                        if request:
                            key = f"{self.key_func(request)}:{func.__name__}"
                            now = time.time()
                            cutoff = now - window
                            timestamps = [t for t in self._history.get(key, []) if t > cutoff]
                            if len(timestamps) >= count:
                                raise RateLimitExceeded(detail=f"Rate limit exceeded: {count} per {window}s")
                            timestamps.append(now)
                            self._history[key] = timestamps
                        return await func(*args, **kwargs)
                    return async_wrapper
                else:
                    @wraps(func)
                    def sync_wrapper(*args, **kwargs):
                        request = kwargs.get("request")
                        if not request:
                            for arg in args:
                                if isinstance(arg, Request):
                                    request = arg
                                    break
                        if request:
                            key = f"{self.key_func(request)}:{func.__name__}"
                            now = time.time()
                            cutoff = now - window
                            timestamps = [t for t in self._history.get(key, []) if t > cutoff]
                            if len(timestamps) >= count:
                                raise RateLimitExceeded(detail=f"Rate limit exceeded: {count} per {window}s")
                            timestamps.append(now)
                            self._history[key] = timestamps
                        return func(*args, **kwargs)
                    return sync_wrapper

            return decorator

    Limiter = FallbackLimiter  # type: ignore

limiter = Limiter(key_func=get_remote_address)
