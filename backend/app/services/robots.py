import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import settings


@dataclass
class _CacheEntry:
    parser: urllib.robotparser.RobotFileParser
    fetched_at: float


# In-process cache: domain -> _CacheEntry
_cache: dict[str, _CacheEntry] = {}


@dataclass
class RobotsResult:
    allowed: bool
    warning: str = ""  # non-empty only on fail-open


async def check_robots(
    url: str,
    _client: httpx.AsyncClient | None = None,
) -> RobotsResult:
    """Check robots.txt for *url*.

    - Returns RobotsResult(allowed=True) when allowed or when robots.txt
      cannot be fetched (fail-open), with a warning message in the latter case.
    - Returns RobotsResult(allowed=False) when explicitly disallowed.
    - Caches parsed robots.txt per domain for ROBOTS_CACHE_TTL_SECONDS.
    - Pass *_client* in tests to inject a pre-configured (e.g. respx-mocked) client.
    """
    parsed = urlparse(url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{domain}/robots.txt"

    entry = _cache.get(domain)
    now = time.monotonic()

    if entry is None or (now - entry.fetched_at) > settings.ROBOTS_CACHE_TTL_SECONDS:
        try:
            _default_client = _client is None
            if _default_client:
                _client = httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
                    headers={"User-Agent": settings.SCRAPER_USER_AGENT},
                    follow_redirects=True,
                )
            try:
                response = await _client.get(robots_url)
            finally:
                if _default_client:
                    await _client.aclose()

            if response.status_code == 404:
                # No robots.txt — everything is allowed
                parser = urllib.robotparser.RobotFileParser()
                parser.set_url(robots_url)
                parser.parse([])
            elif response.status_code >= 400:
                return RobotsResult(
                    allowed=True,
                    warning=f"robots.txt fetch returned HTTP {response.status_code}; proceeding without check.",
                )
            else:
                parser = urllib.robotparser.RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(response.text.splitlines())

            _cache[domain] = _CacheEntry(parser=parser, fetched_at=now)

        except Exception as exc:
            return RobotsResult(
                allowed=True,
                warning=f"robots.txt could not be fetched ({type(exc).__name__}); proceeding without check.",
            )

    parser = _cache[domain].parser
    allowed = parser.can_fetch(settings.SCRAPER_USER_AGENT, url)
    return RobotsResult(allowed=allowed)


def clear_cache() -> None:
    """Clear the in-process robots.txt cache (used in tests)."""
    _cache.clear()
