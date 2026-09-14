import pytest
from backend.limiter import limiter


@pytest.fixture(autouse=True)
def manage_rate_limiting_for_tests(request):
    """
    Ensures tests don't inadvertently fail due to rate limits when creating
    tickets or querying rapidly, while allowing test_rate_limiting.py to test
    rate limiting behavior explicitly.
    """
    if "test_rate_limiting" in request.node.fspath.strpath:
        limiter.enabled = True
        if hasattr(limiter, "reset"):
            limiter.reset()
        yield
    else:
        prev = getattr(limiter, "enabled", True)
        limiter.enabled = False
        yield
        limiter.enabled = prev
