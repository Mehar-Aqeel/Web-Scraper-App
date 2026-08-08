import pytest
import httpx
import respx

from app.config import settings
from app.services.robots import check_robots, clear_cache, _cache


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROBOTS_ALLOW = "User-agent: *\nAllow: /"
ROBOTS_DISALLOW = "User-agent: *\nDisallow: /"
ROBOTS_DISALLOW_PATH = "User-agent: *\nDisallow: /private/"


def _mock_robots(url: str, body: str, status: int = 200):
    respx.get(url).mock(
        return_value=httpx.Response(status, text=body, headers={"content-type": "text/plain"})
    )


def _mocked_client(*mocks: tuple) -> httpx.AsyncClient:
    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    for url, response in mocks:
        router.get(url).mock(return_value=response)
    return httpx.AsyncClient(
        transport=httpx.MockTransport(router.async_handler),
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# Basic allow / disallow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_allowed_when_robots_permits():
    client = _mocked_client((
        "https://example.com/robots.txt",
        httpx.Response(200, text=ROBOTS_ALLOW, headers={"content-type": "text/plain"}),
    ))
    async with client:
        result = await check_robots("https://example.com/page", _client=client)
    assert result.allowed is True
    assert result.warning == ""


@pytest.mark.asyncio
async def test_disallowed_when_robots_blocks():
    client = _mocked_client((
        "https://example.com/robots.txt",
        httpx.Response(200, text=ROBOTS_DISALLOW, headers={"content-type": "text/plain"}),
    ))
    async with client:
        result = await check_robots("https://example.com/page", _client=client)
    assert result.allowed is False
    assert result.warning == ""


@pytest.mark.asyncio
async def test_disallowed_only_for_matching_path():
    client = _mocked_client((
        "https://example.com/robots.txt",
        httpx.Response(200, text=ROBOTS_DISALLOW_PATH, headers={"content-type": "text/plain"}),
    ))
    async with client:
        blocked = await check_robots("https://example.com/private/data", _client=client)
        allowed = await check_robots("https://example.com/public/data", _client=client)
    assert blocked.allowed is False
    assert allowed.allowed is True


@pytest.mark.asyncio
async def test_allowed_when_no_robots_txt():
    client = _mocked_client((
        "https://example.com/robots.txt",
        httpx.Response(404),
    ))
    async with client:
        result = await check_robots("https://example.com/page", _client=client)
    assert result.allowed is True


# ---------------------------------------------------------------------------
# Fail-open policy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fail_open_on_5xx():
    client = _mocked_client((
        "https://example.com/robots.txt",
        httpx.Response(500),
    ))
    async with client:
        result = await check_robots("https://example.com/page", _client=client)
    assert result.allowed is True
    assert "500" in result.warning


@pytest.mark.asyncio
async def test_fail_open_on_network_error():
    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    router.get("https://example.com/robots.txt").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(router.async_handler),
        follow_redirects=True,
    )
    async with client:
        result = await check_robots("https://example.com/page", _client=client)
    assert result.allowed is True
    assert result.warning != ""


@pytest.mark.asyncio
async def test_fail_open_on_timeout():
    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    router.get("https://example.com/robots.txt").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(router.async_handler),
        follow_redirects=True,
    )
    async with client:
        result = await check_robots("https://example.com/page", _client=client)
    assert result.allowed is True
    assert result.warning != ""


# ---------------------------------------------------------------------------
# Caching — TTL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_avoids_second_fetch():
    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    route = router.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_ALLOW)
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(router.async_handler),
        follow_redirects=True,
    )
    async with client:
        await check_robots("https://example.com/page", _client=client)
        await check_robots("https://example.com/other", _client=client)
    # robots.txt should only be fetched once
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_cache_refetches_after_ttl(monkeypatch):
    import time
    from app.services import robots as robots_module

    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    route = router.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_ALLOW)
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(router.async_handler),
        follow_redirects=True,
    )
    async with client:
        await check_robots("https://example.com/page", _client=client)
        assert route.call_count == 1

        # Expire the cache entry by backdating fetched_at
        domain = "https://example.com"
        robots_module._cache[domain].fetched_at -= (settings.ROBOTS_CACHE_TTL_SECONDS + 1)

        await check_robots("https://example.com/page", _client=client)
        assert route.call_count == 2
