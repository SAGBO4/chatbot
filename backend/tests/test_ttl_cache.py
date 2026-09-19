from bot.ttl_cache import MISSING, TTLCache


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def test_entries_expire_after_the_ttl_and_not_before():
    clock = Clock()
    cache = TTLCache(30.0, clock=clock)
    cache.set("a", 1)

    clock.now += 29.9
    assert cache.get("a") == 1
    clock.now += 0.1
    assert cache.get("a") is MISSING


def test_none_is_a_cacheable_value_and_absence_is_distinct():
    cache = TTLCache(30.0, clock=Clock())
    cache.set("group", None)

    assert cache.get("group") is None
    assert cache.get("other") is MISSING


def test_discard_discard_where_and_clear():
    cache = TTLCache(30.0, clock=Clock())
    for key in [(1, 10), (1, 11), (2, 10)]:
        cache.set(key, True)

    cache.discard((1, 10))
    assert cache.get((1, 10)) is MISSING and len(cache) == 2

    cache.discard_where(lambda key: key[0] == 2)
    assert cache.get((2, 10)) is MISSING and cache.get((1, 11)) is True

    cache.clear()
    assert len(cache) == 0


def test_expired_entries_are_purged_when_the_cache_grows_large(monkeypatch):
    monkeypatch.setattr("bot.ttl_cache._PURGE_ABOVE", 10)
    clock = Clock()
    cache = TTLCache(30.0, clock=clock)
    for i in range(10):
        cache.set(i, i)

    clock.now += 60  # all ten are now expired
    cache.set("fresh", 1)

    assert len(cache) == 1 and cache.get("fresh") == 1
