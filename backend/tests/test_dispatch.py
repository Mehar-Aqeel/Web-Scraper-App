import pytest
import httpx
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from app.schemas.extraction import ExtractionType
from app.services.dispatch import extract, RobotsDisallowedError
from app.services.limiter import clear_response_cache
from app.services.page_fetcher import FetchedPage
from app.services.robots import RobotsResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_HTML = """
<html>
<head>
  <title>Test Page</title>
  <meta name="description" content="A test">
</head>
<body>
  <h1>Hello</h1>
  <a href="/about">About</a>
  <table>
    <tr><th>Col</th></tr>
    <tr><td>Val</td></tr>
  </table>
</body>
</html>
"""

_ALLOW = RobotsResult(allowed=True)
_FETCHED = FetchedPage(url="https://example.com/", html=SIMPLE_HTML, encoding="utf-8")


from contextlib import contextmanager

@pytest.fixture(autouse=True)
def reset_cache():
    clear_response_cache()
    yield
    clear_response_cache()


@contextmanager
def _patch_deps(robots=_ALLOW, page=_FETCHED):
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.dispatch.check_robots", new=AsyncMock(return_value=robots)))
        stack.enter_context(patch("app.services.dispatch.fetch_page", new=AsyncMock(return_value=page)))
        yield


# ---------------------------------------------------------------------------
# TICKET-011: Only selected extractors run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_only_selected_fields_returned():
    with _patch_deps():
        data, warnings = await extract(
            "https://example.com/",
            [ExtractionType.title],
        )
    types = {r["type"] for r in data}
    assert types == {"title"}
    assert warnings == []


@pytest.mark.asyncio
async def test_multiple_selected_fields():
    with _patch_deps():
        data, warnings = await extract(
            "https://example.com/",
            [ExtractionType.title, ExtractionType.headings, ExtractionType.links],
        )
    types = {r["type"] for r in data}
    assert "title" in types
    assert "heading" in types
    assert "link" in types
    assert "paragraph" not in types
    assert "image" not in types


@pytest.mark.asyncio
async def test_unselected_extractors_do_not_run():
    """Patch extract_tables to raise — it must not be called when not selected."""
    with _patch_deps():
        with patch("app.services.dispatch.extract_tables", side_effect=RuntimeError("should not run")):
            data, warnings = await extract(
                "https://example.com/",
                [ExtractionType.title],
            )
    assert all(r["type"] != "table_row" for r in data)


# ---------------------------------------------------------------------------
# TICKET-011: Normalized output shapes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_title_record_shape():
    with _patch_deps():
        data, _ = await extract("https://example.com/", [ExtractionType.title])
    record = next(r for r in data if r["type"] == "title")
    assert record["value"] == "Test Page"
    assert record["source_url"] == "https://example.com/"


@pytest.mark.asyncio
async def test_table_row_record_shape():
    with _patch_deps():
        data, _ = await extract("https://example.com/", [ExtractionType.tables])
    record = next(r for r in data if r["type"] == "table_row")
    assert "value" in record
    assert "table_index" in record
    assert "row_index" in record
    assert "source_url" in record


# ---------------------------------------------------------------------------
# TICKET-011a: Partial failure handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extractor_failure_does_not_fail_whole_request():
    """Force extract_tables to throw; title and links must still be returned."""
    with _patch_deps():
        with patch(
            "app.services.dispatch.extract_tables",
            side_effect=ValueError("malformed table"),
        ):
            data, warnings = await extract(
                "https://example.com/",
                [ExtractionType.title, ExtractionType.links, ExtractionType.tables],
            )
    types = {r["type"] for r in data}
    assert "title" in types
    assert "link" in types
    assert "table_row" not in types
    assert any("tables" in w for w in warnings)


@pytest.mark.asyncio
async def test_warning_message_names_failed_extractor():
    with _patch_deps():
        with patch(
            "app.services.dispatch.extract_headings",
            side_effect=RuntimeError("boom"),
        ):
            _, warnings = await extract(
                "https://example.com/",
                [ExtractionType.headings],
            )
    assert any("headings" in w for w in warnings)


@pytest.mark.asyncio
async def test_title_failure_reported_in_warnings():
    with _patch_deps():
        with patch(
            "app.services.dispatch.extract_title",
            side_effect=RuntimeError("title boom"),
        ):
            data, warnings = await extract(
                "https://example.com/",
                [ExtractionType.title, ExtractionType.links],
            )
    assert all(r["type"] != "title" for r in data)
    assert any("title" in w for w in warnings)
    assert any(r["type"] == "link" for r in data)


# ---------------------------------------------------------------------------
# TICKET-006 integration: robots disallow raises, robots warning propagates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_robots_disallowed_raises():
    disallowed = RobotsResult(allowed=False)
    with patch("app.services.dispatch.check_robots", new=AsyncMock(return_value=disallowed)):
        with pytest.raises(RobotsDisallowedError):
            await extract("https://example.com/", [ExtractionType.title])


@pytest.mark.asyncio
async def test_robots_warning_propagates():
    warn_result = RobotsResult(allowed=True, warning="robots.txt unreachable")
    with patch("app.services.dispatch.check_robots", new=AsyncMock(return_value=warn_result)):
        with patch("app.services.dispatch.fetch_page", new=AsyncMock(return_value=_FETCHED)):
            _, warnings = await extract("https://example.com/", [ExtractionType.title])
    assert any("robots.txt" in w for w in warnings)
