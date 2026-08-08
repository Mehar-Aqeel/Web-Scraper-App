import pytest
import httpx
import respx

from app.services.fetcher import (
    fetch_url,
    SSRFError,
    TooManyRedirectsError,
    _is_private_ip,
    _resolve_and_check,
)


# ---------------------------------------------------------------------------
# _is_private_ip unit tests (no I/O)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ip", [
    "127.0.0.1",        # loopback
    "127.0.0.2",
    "10.0.0.1",         # private class A
    "172.16.0.1",       # private class B
    "192.168.1.1",      # private class C
    "169.254.169.254",  # AWS metadata endpoint
    "169.254.0.1",      # link-local
    "0.0.0.1",          # "this" network
    "100.64.0.1",       # shared address space
    "::1",              # IPv6 loopback
    "fe80::1",          # IPv6 link-local
    "fc00::1",          # IPv6 unique-local
])
def test_private_ips_are_blocked(ip):
    assert _is_private_ip(ip) is True


@pytest.mark.parametrize("ip", [
    "93.184.216.34",    # example.com
    "8.8.8.8",          # Google DNS
    "2606:2800:220:1:248:1893:25c8:1946",  # example.com IPv6
])
def test_public_ips_are_allowed(ip):
    assert _is_private_ip(ip) is False


# ---------------------------------------------------------------------------
# _resolve_and_check — mock socket to avoid real DNS in tests
# ---------------------------------------------------------------------------

def test_resolve_and_check_blocks_private_hostname(monkeypatch):
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(SSRFError, match="blocked range"):
        _resolve_and_check("metadata.internal")


def test_resolve_and_check_passes_public_hostname(monkeypatch):
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    ip = _resolve_and_check("example.com")
    assert ip == "93.184.216.34"


def test_resolve_and_check_raises_on_dns_failure(monkeypatch):
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(SSRFError, match="DNS resolution failed"):
        _resolve_and_check("nonexistent.invalid")


# ---------------------------------------------------------------------------
# fetch_url integration tests — respx mocks HTTP, monkeypatch mocks DNS
# ---------------------------------------------------------------------------

def _patch_dns_public(monkeypatch):
    """Make all DNS lookups resolve to a safe public IP."""
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


def _patch_dns_private_for(monkeypatch, private_host: str):
    """Resolve *private_host* to a private IP; everything else resolves public."""
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == private_host:
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.1", 0))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


@pytest.mark.asyncio
@respx.mock
async def test_successful_fetch(monkeypatch):
    _patch_dns_public(monkeypatch)
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(200, text="<html><title>OK</title></html>")
    )
    response = await fetch_url("https://example.com/")
    assert response.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_redirect_to_private_ip_is_blocked(monkeypatch):
    """A public URL that redirects to a private-IP host must be blocked."""
    _patch_dns_private_for(monkeypatch, "internal.corp")

    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            301, headers={"location": "http://internal.corp/secret"}
        )
    )
    with pytest.raises(SSRFError, match="blocked range"):
        await fetch_url("https://example.com/")


@pytest.mark.asyncio
@respx.mock
async def test_max_redirects_enforced(monkeypatch, settings_override):
    _patch_dns_public(monkeypatch)
    # Chain: /r1 → /r2 → /r3 → /r4  (4 hops, default MAX_REDIRECTS=3)
    for i in range(1, 5):
        dest = f"https://example.com/r{i + 1}" if i < 4 else "https://example.com/final"
        respx.get(f"https://example.com/r{i}").mock(
            return_value=httpx.Response(302, headers={"location": dest})
        )
    with pytest.raises(TooManyRedirectsError):
        await fetch_url("https://example.com/r1")


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_503_then_success(monkeypatch):
    _patch_dns_public(monkeypatch)
    route = respx.get("https://example.com/")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, text="<html>ok</html>"),
    ]
    response = await fetch_url("https://example.com/")
    assert response.status_code == 200
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_no_retry_on_404(monkeypatch):
    _patch_dns_public(monkeypatch)
    route = respx.get("https://example.com/missing").mock(
        return_value=httpx.Response(404)
    )
    response = await fetch_url("https://example.com/missing")
    assert response.status_code == 404
    assert route.call_count == 1  # no retry


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_transport_error_then_success(monkeypatch):
    _patch_dns_public(monkeypatch)
    route = respx.get("https://example.com/")
    route.side_effect = [
        httpx.TransportError("connection reset"),
        httpx.Response(200, text="<html>ok</html>"),
    ]
    response = await fetch_url("https://example.com/")
    assert response.status_code == 200
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_user_agent_sent(monkeypatch):
    from app.config import settings as cfg

    _patch_dns_public(monkeypatch)
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )
    await fetch_url("https://example.com/")
    sent_ua = respx.calls.last.request.headers.get("user-agent", "")
    assert sent_ua == cfg.SCRAPER_USER_AGENT


# ---------------------------------------------------------------------------
# Fixture: temporarily lower MAX_REDIRECTS to 3 for redirect-chain test
# ---------------------------------------------------------------------------

@pytest.fixture
def settings_override():
    from app.config import settings as cfg
    original = cfg.MAX_REDIRECTS
    cfg.MAX_REDIRECTS = 3
    yield
    cfg.MAX_REDIRECTS = original
