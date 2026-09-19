"""A small in-memory cache whose entries expire after a fixed time."""
import time
from typing import Any, Callable, Dict, Hashable, Tuple

MISSING = object()

# Above this many entries, expired ones are dropped on the next write, so a busy bot does not keep every key forever
_PURGE_ABOVE = 1024


class TTLCache:
    """
    Values by key, each valid for `ttl_seconds` after it was stored.

    `get` returns `MISSING` (not None) for an absent or expired key, because None is a legitimate value to
    cache (for example "no community group configured"). The clock is injectable so expiry can be tested.
    """

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: Dict[Hashable, Tuple[Any, float]] = {}

    def get(self, key: Hashable) -> Any:
        entry = self._entries.get(key)
        if entry is None:
            return MISSING
        value, stored_at = entry
        if self._clock() - stored_at >= self.ttl_seconds:
            del self._entries[key]
            return MISSING
        return value

    def set(self, key: Hashable, value: Any) -> None:
        now = self._clock()
        if len(self._entries) >= _PURGE_ABOVE:
            self._entries = {k: e for k, e in self._entries.items() if now - e[1] < self.ttl_seconds}
        self._entries[key] = (value, now)

    def discard(self, key: Hashable) -> None:
        self._entries.pop(key, None)

    def discard_where(self, predicate: Callable[[Hashable], bool]) -> None:
        """Drop every entry whose key satisfies `predicate`."""
        for key in [key for key in self._entries if predicate(key)]:
            del self._entries[key]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
