import asyncio
import hashlib
import time
from urllib.parse import urlparse

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# ---------------------------------------------------------------------------
# TICKET-013: Per-IP rate limiter (slowapi / token bucket)
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address, default_limits=[])

# ---------------------------------------------------------------------------
# TICKET-013: Per-domain throttle
# ---------------------------------------------------------------------------
# Maps domain -> timestamp of last request dispatched to that domain.
_domain_last_request: dict[str, float] = {}
_domain_locks: dict[str, asyncio.Lock] = {}


async def acquire_domain_slot(url: str) -> None:
    """Enforce PER_DOMAIN_REQUEST_DELAY_MS between requests to the same domain."""
    domain = urlparse(url).netloc
    if domain not in _domain_locks:
        _domain_locks[domain] = asyncio.Lock()

    async with _domain_locks[domain]:
        now = time.monotonic()
        last = _domain_last_request.get(domain, 0.0)
        delay_s = settings.PER_DOMAIN_REQUEST_DELAY_MS / 1000.0
        wait = delay_s - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _domain_last_request[domain] = time.monotonic()


# ---------------------------------------------------------------------------
# TICKET-013a: Global concurrency semaphore
# ---------------------------------------------------------------------------
# Lazily initialised so it picks up the settings value at first use.
_global_semaphore: asyncio.Semaphore | None = None


def get_semaphore() -> asyncio.Semaphore:
    global _global_semaphore
    if _global_semaphore is None:
        _global_semaphore = asyncio.Semaphore(settings.GLOBAL_CONCURRENCY_LIMIT)
    return _global_semaphore


# ---------------------------------------------------------------------------
# TICKET-013b: Response cache
# ---------------------------------------------------------------------------

class _CacheEntry:
    __slots__ = ("data", "warnings", "stored_at")

    def __init__(self, data: list, warnings: list):
        self.data = data
        self.warnings = warnings
        self.stored_at = time.monotonic()


_response_cache: dict[str, _CacheEntry] = {}


def _cache_key(url: str, fields: list) -> str:
    key = url + "|" + ",".join(sorted(f for f in fields))
    return hashlib.sha256(key.encode()).hexdigest()


def cache_get(url: str, fields: list) -> tuple[list, list] | None:
    key = _cache_key(url, fields)
    entry = _response_cache.get(key)
    if entry is None:
        return None
    if (time.monotonic() - entry.stored_at) > settings.CACHE_TTL_SECONDS:
        del _response_cache[key]
        return None
    return entry.data, entry.warnings


def cache_set(url: str, fields: list, data: list, warnings: list) -> None:
    key = _cache_key(url, fields)
    _response_cache[key] = _CacheEntry(data, warnings)


def clear_response_cache() -> None:
    _response_cache.clear()
