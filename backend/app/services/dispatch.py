import asyncio

import structlog
from bs4 import BeautifulSoup

from app.schemas.extraction import ExtractionType
from app.services.extractor import (
    extract_canonical,
    extract_headings,
    extract_images,
    extract_links,
    extract_meta,
    extract_open_graph,
    extract_paragraphs,
    extract_tables,
    extract_title,
)
from app.services.limiter import acquire_domain_slot, cache_get, cache_set, get_semaphore
from app.services.page_fetcher import FetchedPage, fetch_page
from app.services.robots import check_robots

logger = structlog.get_logger()

_EXTRACTORS: dict = {
    ExtractionType.meta:          extract_meta,
    ExtractionType.headings:      extract_headings,
    ExtractionType.paragraphs:    extract_paragraphs,
    ExtractionType.links:         extract_links,
    ExtractionType.images:        extract_images,
    ExtractionType.tables:        extract_tables,
    ExtractionType.open_graph:    extract_open_graph,
    ExtractionType.canonical_url: extract_canonical,
}

_PARSE_TIMEOUT_SECONDS = 10.0


class RobotsDisallowedError(Exception):
    """Raised when robots.txt explicitly disallows the target URL."""


class ParseTimeoutError(Exception):
    """Raised when BeautifulSoup parsing/extraction exceeds the time budget."""


class ServerBusyError(Exception):
    """Raised when the global concurrency limit is reached."""


async def extract(
    url: str,
    selected: list[ExtractionType],
) -> tuple[list[dict], list[str]]:
    """Fetch *url* and run only the *selected* extractors.

    Pipeline: cache → concurrency cap → robots → domain throttle →
              HTTP fetch → parse timeout → per-extractor isolation → cache store.
    """
    field_values = [t.value for t in selected]

    # TICKET-013b: return cached result if available
    cached = cache_get(url, field_values)
    if cached is not None:
        logger.info("cache_hit", url=url)
        return cached

    # TICKET-013a: non-blocking semaphore acquire — reject immediately if full
    semaphore = get_semaphore()
    if not semaphore._value:  # type: ignore[attr-defined]
        raise ServerBusyError("Server is at capacity. Please try again shortly.")

    async with semaphore:
        result = await _do_extract(url, selected, field_values)

    return result


async def _do_extract(
    url: str,
    selected: list[ExtractionType],
    field_values: list[str],
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []

    robots = await check_robots(url)
    if not robots.allowed:
        raise RobotsDisallowedError(f"robots.txt disallows scraping {url}")
    if robots.warning:
        warnings.append(robots.warning)

    await acquire_domain_slot(url)

    page: FetchedPage = await fetch_page(url)
    warnings.extend(page.warnings)

    # TICKET-013c: bound the parse phase independently of the HTTP timeout
    try:
        data, parse_warnings = await asyncio.wait_for(
            _parse_and_extract(page.html, url, selected),
            timeout=_PARSE_TIMEOUT_SECONDS,
        )
        warnings.extend(parse_warnings)
    except asyncio.TimeoutError:
        raise ParseTimeoutError(
            f"Parsing {url} exceeded the {_PARSE_TIMEOUT_SECONDS}s time limit."
        )

    cache_set(url, field_values, data, warnings)
    return data, warnings


async def _parse_and_extract(
    html: str,
    url: str,
    selected: list[ExtractionType],
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    soup = BeautifulSoup(html, "html.parser")
    data: list[dict] = []

    if ExtractionType.title in selected:
        try:
            title = extract_title(soup)
            if title is not None:
                data.append({"type": "title", "value": title, "source_url": url})
        except Exception as exc:
            warnings.append(f"title: extraction failed — {exc}")
            logger.warning("extractor_failed", field="title", error=str(exc))

    # Look up each extractor by name at call time so unittest.mock.patch works
    import app.services.dispatch as _self
    _live_extractors = {
        ExtractionType.meta:          _self.extract_meta,
        ExtractionType.headings:      _self.extract_headings,
        ExtractionType.paragraphs:    _self.extract_paragraphs,
        ExtractionType.links:         _self.extract_links,
        ExtractionType.images:        _self.extract_images,
        ExtractionType.tables:        _self.extract_tables,
        ExtractionType.open_graph:    _self.extract_open_graph,
        ExtractionType.canonical_url: _self.extract_canonical,
    }

    for field_type, fn in _live_extractors.items():
        if field_type not in selected:
            continue
        try:
            data.extend(fn(soup, url))
        except Exception as exc:
            warnings.append(f"{field_type.value}: extraction failed — {exc}")
            logger.warning("extractor_failed", field=field_type.value, error=str(exc))

    return data, warnings
