import asyncio
import pytest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from app.schemas.extraction import ExtractionType
from app.services.dispatch import extract, ParseTimeoutError, ServerBusyError
from app.services.limiter import (
    cache_get,
    cache_set,
    clear_response_cache,
    acquire_domain_slot,
    _domain_last_request,
    _cache_key,
)
from app.services.page_fetcher import FetchedPage
from app.services.robots import RobotsResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_HTML = "<html><head><title>T</title></head><body><a href='/x'>X</a></body></html>"
_ALLOW = RobotsResult(allowed=True)
_FETCHED = FetchedPage(url="https://example.com/", html=SIMPLE_HTML, encoding="utf-8")


@pytest.fixture(autouse=True)
def reset_cache():
    clear_response_cache()
    _domain_last_request.clear()
    yield
    clear_response_cache()
    _domain_last_request.clear()


from contextlib import contextmanager

@contextmanager
def _patch_deps(robots=_ALLOW, page=_FETCHED):
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.dispatch.check_robots", new=AsyncMock(return_value=robots)))
        stack.enter_context(patch("app.services.dispatch.fetch_page", new=AsyncMock(return_value=page)))
        yield


# ---------------------------------------------------------------------------
# TICKET-013b: Response cache
# ---------------------------------------------------------------------------

def test_cache_key_is_order_independent():
    k1 = _cache_key("https://example.com", ["links", "title"])
    k2 = _cache_key("https://example.com", ["title", "links"])
    assert k1 == k2


def test_cache_miss_returns_none():
    assert cache_get("https://example.com", ["title"]) is None


def test_cache_set_and_get():
    cache_set("https://example.com", ["title"], [{"type": "title"}], [])
    result = cache_get("https://example.com", ["title"])
    assert result is not None
    data, warnings = result
    assert data[0]["type"] == "title"


def test_cache_expires_after_ttl(monkeypatch):
    from app.config import settings
    cache_set("https://example.com", ["title"], [{"type": "title"}], [])
    # Backdate the entry
    from app.services import limiter as lm
    key = _cache_key("https://example.com", ["title"])
    lm._response_cache[key].stored_at -= (settings.CACHE_TTL_SECONDS + 1)
    assert cache_get("https://example.com", ["title"]) is None


@pytest.mark.asyncio
async def test_cached_result_returned_without_fetching():
    cache_set("https://example.com/", ["title"], [{"type": "title", "value": "Cached"}], [])
    fetch_mock = AsyncMock(return_value=_FETCHED)
    with patch("app.services.dispatch.fetch_page", new=fetch_mock):
        with patch("app.services.dispatch.check_robots", new=AsyncMock(return_value=_ALLOW)):
            data, _ = await extract("https://example.com/", [ExtractionType.title])
    fetch_mock.assert_not_called()
    assert data[0]["value"] == "Cached"


# ---------------------------------------------------------------------------
# TICKET-013: Per-domain throttle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_domain_throttle_delays_second_request(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "PER_DOMAIN_REQUEST_DELAY_MS", 100)

    import time
    await acquire_domain_slot("https://example.com/page1")
    t0 = time.monotonic()
    await acquire_domain_slot("https://example.com/page2")
    elapsed = time.monotonic() - t0
    # Should have waited ~100ms
    assert elapsed >= 0.08


@pytest.mark.asyncio
async def test_different_domains_not_throttled_together(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "PER_DOMAIN_REQUEST_DELAY_MS", 200)

    import time
    await acquire_domain_slot("https://example.com/")
    t0 = time.monotonic()
    await acquire_domain_slot("https://other.com/")  # different domain — no wait
    elapsed = time.monotonic() - t0
    assert elapsed < 0.05


# ---------------------------------------------------------------------------
# TICKET-013a: Global concurrency cap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_server_busy_when_semaphore_exhausted():
    from app.services import limiter as lm
    # Replace semaphore with one that's already at 0
    original = lm._global_semaphore
    lm._global_semaphore = asyncio.Semaphore(0)
    try:
        with pytest.raises(ServerBusyError):
            with _patch_deps():
                await extract("https://example.com/", [ExtractionType.title])
    finally:
        lm._global_semaphore = original


# ---------------------------------------------------------------------------
# TICKET-013c: Parse timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_timeout_raises_parse_timeout_error():
    async def slow_parse(*args, **kwargs):
        await asyncio.sleep(60)
        return [], []

    with _patch_deps():
        with patch("app.services.dispatch._parse_and_extract", new=slow_parse):
            with patch("app.services.dispatch._PARSE_TIMEOUT_SECONDS", 0.05):
                with pytest.raises(ParseTimeoutError):
                    await extract("https://example.com/", [ExtractionType.title])


@pytest.mark.asyncio
async def test_parse_timeout_does_not_affect_normal_pages():
    with _patch_deps():
        data, warnings = await extract("https://example.com/", [ExtractionType.title])
    assert any(r["type"] == "title" for r in data)
