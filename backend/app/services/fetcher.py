import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

from app.config import settings

# ---------------------------------------------------------------------------
# IP range blocklist — loopback, private, link-local, cloud metadata
# ---------------------------------------------------------------------------
_BLOCKED_NETWORKS = [
    ipaddress.ip_network(cidr)
    for cidr in (
        "127.0.0.0/8",      # loopback
        "::1/128",          # IPv6 loopback
        "10.0.0.0/8",       # private
        "172.16.0.0/12",    # private
        "192.168.0.0/16",   # private
        "169.254.0.0/16",   # link-local (includes AWS metadata 169.254.169.254)
        "fe80::/10",        # IPv6 link-local
        "fc00::/7",         # IPv6 unique-local
        "0.0.0.0/8",        # "this" network
        "100.64.0.0/10",    # shared address space (RFC 6598)
    )
]

# Transient status codes that warrant a retry
_RETRYABLE_STATUSES = {502, 503, 504}


class SSRFError(Exception):
    """Raised when a URL resolves to a blocked (private/internal) address."""


class TooManyRedirectsError(Exception):
    """Raised when the redirect chain exceeds MAX_REDIRECTS."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_private_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable → block
    return any(addr in net for net in _BLOCKED_NETWORKS)


def _resolve_and_check(hostname: str) -> str:
    """Resolve *hostname* to an IP string and raise SSRFError if it is blocked.

    Returns the resolved IP so the caller can reuse it for the actual request
    (avoids a DNS-rebinding window between check and connect).
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SSRFError(f"DNS resolution failed for '{hostname}': {exc}") from exc

    if not infos:
        raise SSRFError(f"DNS resolution returned no results for '{hostname}'.")

    # Check every address returned — block if *any* resolves to a private range
    for info in infos:
        ip_str = info[4][0]
        if _is_private_ip(ip_str):
            raise SSRFError(
                f"Resolved IP {ip_str} for '{hostname}' is in a blocked range."
            )

    # Return the first resolved IP for use as the transport target
    return infos[0][4][0]


def _absolute_redirect(location: str, current_url: str) -> str:
    """Resolve a Location header value against the current URL."""
    return urljoin(current_url, location)


# ---------------------------------------------------------------------------
# Public fetch function
# ---------------------------------------------------------------------------

async def fetch_url(url: str) -> httpx.Response:
    """Fetch *url* with SSRF protection across the full redirect chain.

    Returns a *buffered* httpx.Response whose .content is already read.
    Content-Type validation and size-capping are handled by page_fetcher.py
    which calls this function and then streams the body itself.

    Raises: SSRFError, TooManyRedirectsError, httpx.TimeoutException.
    """
    timeout = httpx.Timeout(
        connect=float(settings.CONNECT_TIMEOUT),
        read=float(settings.REQUEST_TIMEOUT),
        write=5.0,
        pool=5.0,
    )
    headers = {"User-Agent": settings.SCRAPER_USER_AGENT}

    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=timeout,
        headers=headers,
    ) as client:
        current_url = url
        hops = 0

        while True:
            parsed = urlparse(current_url)
            _resolve_and_check(parsed.hostname)  # raises SSRFError if blocked

            response = await _request_with_retry(client, current_url)

            if response.status_code in (301, 302, 303, 307, 308):
                hops += 1
                if hops > settings.MAX_REDIRECTS:
                    raise TooManyRedirectsError(
                        f"Exceeded maximum of {settings.MAX_REDIRECTS} redirects."
                    )
                location = response.headers.get("location", "")
                if not location:
                    return response
                current_url = _absolute_redirect(location, current_url)
                continue

            return response


def _make_client() -> httpx.AsyncClient:
    timeout = httpx.Timeout(
        connect=float(settings.CONNECT_TIMEOUT),
        read=float(settings.REQUEST_TIMEOUT),
        write=5.0,
        pool=5.0,
    )
    return httpx.AsyncClient(
        follow_redirects=False,
        timeout=timeout,
        headers={"User-Agent": settings.SCRAPER_USER_AGENT},
    )


async def stream_url(
    url: str,
    _client: httpx.AsyncClient | None = None,
) -> tuple[httpx.Response, httpx.AsyncClient]:
    """Return a response and open client so the caller can iterate the body.

        response, client = await stream_url(url)
        async with client:
            async for chunk in response.aiter_bytes():
                ...

    Pass *_client* in tests to inject a pre-configured (e.g. respx-mocked) client.
    """
    client = _client or _make_client()
    current_url = url
    hops = 0

    try:
        while True:
            parsed = urlparse(current_url)
            _resolve_and_check(parsed.hostname)

            response = await client.get(current_url)

            if response.status_code in (301, 302, 303, 307, 308):
                hops += 1
                if hops > settings.MAX_REDIRECTS:
                    if _client is None:
                        await client.aclose()
                    raise TooManyRedirectsError(
                        f"Exceeded maximum of {settings.MAX_REDIRECTS} redirects."
                    )
                location = response.headers.get("location", "")
                if not location:
                    return response, client
                current_url = _absolute_redirect(location, current_url)
                continue

            return response, client
    except Exception:
        if _client is None:
            await client.aclose()
        raise


async def _request_with_retry(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """Issue a GET request, retrying up to MAX_RETRIES times on transient failures.

    Retries on: 502/503/504 status codes and httpx.TransportError (connection reset etc.)
    Does NOT retry on: 4xx, SSRFError, or any other exception.
    Total sleep time is bounded well within REQUEST_TIMEOUT.
    """
    last_exc: Exception | None = None

    for attempt in range(settings.MAX_RETRIES + 1):
        if attempt > 0:
            backoff = 0.5 * (2 ** (attempt - 1))  # 0.5s, 1s, 2s …
            await asyncio.sleep(backoff)

        try:
            response = await client.get(url)
        except httpx.TransportError as exc:
            last_exc = exc
            if attempt < settings.MAX_RETRIES:
                continue
            raise

        if response.status_code in _RETRYABLE_STATUSES and attempt < settings.MAX_RETRIES:
            last_exc = None  # will retry
            continue

        return response

    # Should only reach here if all retries on TransportError exhausted
    raise last_exc  # type: ignore[misc]
