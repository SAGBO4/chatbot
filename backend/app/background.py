"""Running work after the HTTP response without letting a failure escape."""
import inspect

from app.observability import get_logger

logger = get_logger(__name__)


async def safe_background_task(coro_fn, *args, **kwargs):
    """Run a background task and log any exception (timeout, network drop...) instead of letting it reach Starlette."""
    try:
        if inspect.iscoroutinefunction(coro_fn):
            await coro_fn(*args, **kwargs)
        else:
            res = coro_fn(*args, **kwargs)
            if inspect.isawaitable(res):
                await res
    except Exception as exc:
        logger.error(
            "Background task %s failed with exception: %s",
            getattr(coro_fn, "__name__", str(coro_fn)),
            exc,
            exc_info=True,
        )
