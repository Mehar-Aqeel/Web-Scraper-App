import pytest
import httpx
import respx

from app.services.page_fetcher import (
    fetch_page,
    detect_encoding,
    ContentTypeError,
    ResponseTooLargeError,
)
from app.services.fetcher import SSRFError, TooManyRedirectsError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_dns_public(monkeypatch):
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


def _mocked_client(*mocks: tuple) -> httpx.AsyncClient:
    """Return an AsyncClient backed by a respx router as its httpx transport."""
    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    for url, response in mocks:
        router.get(url).mock(return_value=response)
    transport = httpx.MockTransport(router.async_handler)
    return httpx.AsyncClient(
        transport=transport,
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# TICKET-004: Content-Type guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rejects_pdf_content_type(monkeypatch):
    _patch_dns_public(monkeypatch)
    client = _mocked_client((
        "https://example.com/doc.pdf",
        httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4"),
    ))
    async with client:
        with pytest.raises(ContentTypeError, match="application/pdf"):
            await fetch_page("https://example.com/doc.pdf", _client=client)


@pytest.mark.asyncio
async def test_rejects_json_content_type(monkeypatch):
    _patch_dns_public(monkeypatch)
    client = _mocked_client((
        "https://example.com/api",
        httpx.Response(200, headers={"content-type": "application/json"}, content=b'{"k":"v"}'),
    ))
    async with client:
        with pytest.raises(ContentTypeError, match="application/json"):
            await fetch_page("https://example.com/api", _client=client)


@pytest.mark.asyncio
async def test_accepts_text_html(monkeypatch):
    _patch_dns_public(monkeypatch)
    client = _mocked_client((
        "https://example.com/",
        httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html><title>Hello</title></html>",
        ),
    ))
    async with client:
        page = await fetch_page("https://example.com/", _client=client)
    assert "Hello" in page.html


@pytest.mark.asyncio
async def test_accepts_xhtml_content_type(monkeypatch):
    _patch_dns_public(monkeypatch)
    client = _mocked_client((
        "https://example.com/xhtml",
        httpx.Response(
            200,
            headers={"content-type": "application/xhtml+xml; charset=utf-8"},
            content=b"<html><title>XHTML</title></html>",
        ),
    ))
    async with client:
        page = await fetch_page("https://example.com/xhtml", _client=client)
    assert "XHTML" in page.html


@pytest.mark.asyncio
async def test_rejects_body_exceeding_max_size(monkeypatch):
    from app.config import settings
    _patch_dns_public(monkeypatch)
    oversized = b"x" * (settings.MAX_RESPONSE_SIZE + 1)
    client = _mocked_client((
        "https://example.com/big",
        httpx.Response(200, headers={"content-type": "text/html"}, content=oversized),
    ))
    async with client:
        with pytest.raises(ResponseTooLargeError):
            await fetch_page("https://example.com/big", _client=client)


@pytest.mark.asyncio
async def test_accepts_body_at_exact_max_size(monkeypatch):
    from app.config import settings
    _patch_dns_public(monkeypatch)
    exact = b"<html>" + b"a" * (settings.MAX_RESPONSE_SIZE - 6)
    client = _mocked_client((
        "https://example.com/exact",
        httpx.Response(200, headers={"content-type": "text/html"}, content=exact),
    ))
    async with client:
        page = await fetch_page("https://example.com/exact", _client=client)
    assert page.html is not None


@pytest.mark.asyncio
async def test_size_cap_ignores_content_length_header(monkeypatch):
    """A lying Content-Length header must not bypass the streaming cap."""
    from app.config import settings
    _patch_dns_public(monkeypatch)
    oversized = b"x" * (settings.MAX_RESPONSE_SIZE + 1)
    client = _mocked_client((
        "https://example.com/lying",
        httpx.Response(
            200,
            headers={"content-type": "text/html", "content-length": "100"},
            content=oversized,
        ),
    ))
    async with client:
        with pytest.raises(ResponseTooLargeError):
            await fetch_page("https://example.com/lying", _client=client)


# ---------------------------------------------------------------------------
# TICKET-005: detect_encoding() unit tests (pure, no I/O)
# ---------------------------------------------------------------------------

def test_encoding_from_content_type_header():
    raw = "<html><body>caf\xe9</body></html>".encode("windows-1252")
    encoding = detect_encoding(raw, "text/html; charset=windows-1252")
    assert encoding.lower().replace("-", "") == "windows1252"


def test_encoding_from_meta_charset_tag():
    raw = b'<html><head><meta charset="windows-1252"></head><body>caf\xe9</body></html>'
    encoding = detect_encoding(raw, "text/html")
    assert encoding.lower().replace("-", "") == "windows1252"


def test_encoding_from_meta_http_equiv():
    raw = (
        b'<html><head>'
        b'<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">'
        b'</head><body>caf\xe9</body></html>'
    )
    encoding = detect_encoding(raw, "text/html")
    assert "iso" in encoding.lower() or "8859" in encoding.lower()


def test_encoding_sniffed_when_no_declaration():
    raw = b"<html><body>Hello world</body></html>"
    encoding = detect_encoding(raw, "text/html")
    assert encoding


# ---------------------------------------------------------------------------
# TICKET-005: Full round-trip encoding tests through fetch_page
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_utf8_page_decoded_correctly(monkeypatch):
    _patch_dns_public(monkeypatch)
    html_bytes = "<html><title>Héllo</title></html>".encode("utf-8")
    client = _mocked_client((
        "https://example.com/utf8",
        httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=html_bytes,
        ),
    ))
    async with client:
        page = await fetch_page("https://example.com/utf8", _client=client)
    assert "Héllo" in page.html
    assert page.encoding.lower() == "utf-8"


@pytest.mark.asyncio
async def test_windows1252_page_decoded_correctly(monkeypatch):
    _patch_dns_public(monkeypatch)
    html_bytes = "<html><title>caf\xe9</title></html>".encode("windows-1252")
    client = _mocked_client((
        "https://example.com/latin",
        httpx.Response(
            200,
            headers={"content-type": "text/html; charset=windows-1252"},
            content=html_bytes,
        ),
    ))
    async with client:
        page = await fetch_page("https://example.com/latin", _client=client)
    assert "café" in page.html
    assert "1252" in page.encoding.replace("-", "")


@pytest.mark.asyncio
async def test_no_charset_declaration_does_not_crash(monkeypatch):
    _patch_dns_public(monkeypatch)
    client = _mocked_client((
        "https://example.com/nocharset",
        httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<html><body>Hello world</body></html>",
        ),
    ))
    async with client:
        page = await fetch_page("https://example.com/nocharset", _client=client)
    assert "Hello world" in page.html
    assert page.encoding


# ---------------------------------------------------------------------------
# TICKET-032: Meta-refresh redirect following
# ---------------------------------------------------------------------------

from app.services.page_fetcher import _parse_meta_refresh


def test_parse_meta_refresh_returns_absolute_url():
    html = '<html><head><meta http-equiv="refresh" content="0; url=/new-page"></head></html>'
    result = _parse_meta_refresh(html, "https://example.com/old")
    assert result == "https://example.com/new-page"


def test_parse_meta_refresh_absolute_url_unchanged():
    html = '<meta http-equiv="refresh" content="5; url=https://other.com/page">'
    result = _parse_meta_refresh(html, "https://example.com/")
    assert result == "https://other.com/page"


def test_parse_meta_refresh_returns_none_when_absent():
    html = "<html><head><title>No refresh</title></head></html>"
    assert _parse_meta_refresh(html, "https://example.com/") is None


def test_parse_meta_refresh_returns_none_for_hash_only():
    html = '<meta http-equiv="refresh" content="0; url=#">'
    assert _parse_meta_refresh(html, "https://example.com/") is None


@pytest.mark.asyncio
async def test_fetch_page_follows_meta_refresh(monkeypatch):
    """A page with a meta-refresh tag should transparently redirect."""
    _patch_dns_public(monkeypatch)

    refresh_html = (
        b'<html><head>'
        b'<meta http-equiv="refresh" content="0; url=https://example.com/final">'
        b'</head></html>'
    )
    final_html = b"<html><title>Final Page</title></html>"

    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    router.get("https://example.com/start").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/html"}, content=refresh_html)
    )
    router.get("https://example.com/final").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/html"}, content=final_html)
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(router.async_handler), follow_redirects=False)

    async with client:
        page = await fetch_page("https://example.com/start", _client=client)

    assert "Final Page" in page.html
    assert page.url == "https://example.com/final"


@pytest.mark.asyncio
async def test_meta_refresh_to_private_ip_is_blocked(monkeypatch):
    """Meta-refresh to a private IP must be blocked by SSRF check."""
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == "internal.corp":
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.1", 0))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    refresh_html = (
        b'<html><head>'
        b'<meta http-equiv="refresh" content="0; url=http://internal.corp/secret">'
        b'</head></html>'
    )
    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    router.get("https://example.com/start").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/html"}, content=refresh_html)
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(router.async_handler), follow_redirects=False)

    async with client:
        with pytest.raises(SSRFError):
            await fetch_page("https://example.com/start", _client=client)


@pytest.mark.asyncio
async def test_meta_refresh_hop_limit_enforced(monkeypatch):
    """A chain of meta-refresh redirects exceeding MAX_REDIRECTS must raise."""
    from app.config import settings
    _patch_dns_public(monkeypatch)

    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    for i in range(settings.MAX_REDIRECTS + 2):
        next_url = f"https://example.com/step{i + 1}"
        html = f'<html><head><meta http-equiv="refresh" content="0; url={next_url}"></head></html>'.encode()
        router.get(f"https://example.com/step{i}").mock(
            return_value=httpx.Response(200, headers={"content-type": "text/html"}, content=html)
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(router.async_handler), follow_redirects=False)
    async with client:
        with pytest.raises(TooManyRedirectsError):
            await fetch_page("https://example.com/step0", _client=client)
