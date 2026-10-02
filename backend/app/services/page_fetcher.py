import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from charset_normalizer import from_bytes

from app.config import settings
from app.services.fetcher import SSRFError, TooManyRedirectsError, _resolve_and_check, stream_url

# Matches <meta http-equiv="refresh" content="0; url=https://example.com">
# Also handles content="5;URL='...'" and content="0;url=..." variants
_META_REFRESH_RE = re.compile(
    r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\']\s*\d+\s*;\s*url=[\'"\s]?([^\'">\s]+)',
    re.IGNORECASE,
)


def _parse_meta_refresh(html: str, base_url: str) -> str | None:
    """Return the absolute redirect URL from a meta-refresh tag, or None."""
    match = _META_REFRESH_RE.search(html[:8192])  # only scan the <head>
    if not match:
        return None
    target = match.group(1).strip("'\"")
    if not target or target.lower() == "#":
        return None
    return urljoin(base_url, target)

# Matches: charset=utf-8  charset="windows-1252"  charset='iso-8859-1'
_CHARSET_RE = re.compile(r'charset=["\']?([\w-]+)', re.IGNORECASE)


_ALLOWED_CONTENT_TYPES = {
    "text/html",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
}


class ContentTypeError(Exception):
    """Raised when the response Content-Type is not HTML."""


class ResponseTooLargeError(Exception):
    """Raised when the response body exceeds MAX_RESPONSE_SIZE."""


@dataclass
class FetchedPage:
    url: str
    html: str
    encoding: str
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Encoding detection
# ---------------------------------------------------------------------------

def detect_encoding(raw: bytes, content_type_header: str) -> str:
    """Detect charset using three-stage fallback.

    1. HTTP Content-Type header  (e.g. ``text/html; charset=windows-1252``)
    2. HTML ``<meta charset>`` / ``<meta http-equiv>`` tag in the first 4 KB
    3. charset-normalizer byte-sniffing
    """
    # Stage 1 — Content-Type header
    match = _CHARSET_RE.search(content_type_header)
    if match:
        return match.group(1)

    # Stage 2 — <meta> tag (only scan the head; 4 KB is enough)
    head = raw[:4096].decode("ascii", errors="ignore")
    match = _CHARSET_RE.search(head)
    if match:
        return match.group(1)

    # Stage 3 — byte-sniffing via charset-normalizer
    result = from_bytes(raw).best()
    if result:
        return result.encoding

    return "utf-8"  # safe fallback


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def fetch_page(
    url: str,
    _client: httpx.AsyncClient | None = None,
    _meta_refresh_hops: int = 0,
) -> FetchedPage:
    """Fetch *url*, enforce Content-Type and size limits, decode to str.

    Follows <meta http-equiv="refresh"> redirects up to MAX_REDIRECTS hops,
    applying the same SSRF checks as HTTP redirects.

    Pass *_client* in tests to inject a respx-mocked client.

    Raises:
        ContentTypeError      — response is not HTML
        ResponseTooLargeError — body exceeds MAX_RESPONSE_SIZE
        SSRFError, TooManyRedirectsError, httpx.TimeoutException — from fetcher
    """
    response, client = await stream_url(url, _client=_client)

    ct_header = response.headers.get("content-type", "")
    mime = ct_header.split(";")[0].strip().lower()
    if mime not in _ALLOWED_CONTENT_TYPES:
        await response.aclose()
        raise ContentTypeError(
            f"Unsupported Content-Type '{mime}'. "
            f"Only {', '.join(sorted(_ALLOWED_CONTENT_TYPES))} are accepted."
        )

    chunks: list[bytes] = []
    total = 0
    too_large = False
    try:
        async for chunk in response.aiter_bytes(chunk_size=65536):
            total += len(chunk)
            if total > settings.MAX_RESPONSE_SIZE:
                too_large = True
                break
            chunks.append(chunk)
    finally:
        if _client is None:
            await client.aclose()

    if too_large:
        raise ResponseTooLargeError(
            f"Response body exceeds the {settings.MAX_RESPONSE_SIZE}-byte limit."
        )

    raw = b"".join(chunks)

    # --- Encoding detection -------------------------------------------------
    encoding = detect_encoding(raw, ct_header)
    try:
        html = raw.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        html = raw.decode("utf-8", errors="replace")
        encoding = "utf-8"

    # --- Meta-refresh redirect (TICKET-032) ---------------------------------
    meta_target = _parse_meta_refresh(html, url)
    if meta_target:
        if _meta_refresh_hops >= settings.MAX_REDIRECTS:
            raise TooManyRedirectsError(
                f"Exceeded maximum of {settings.MAX_REDIRECTS} meta-refresh redirects."
            )
        from urllib.parse import urlparse
        _resolve_and_check(urlparse(meta_target).hostname or "")  # SSRF check
        return await fetch_page(
            meta_target,
            _client=_client,
            _meta_refresh_hops=_meta_refresh_hops + 1,
        )

    return FetchedPage(url=url, html=html, encoding=encoding)
