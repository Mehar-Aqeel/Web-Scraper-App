"""Playwright-based page fetcher for JavaScript-heavy pages.

Requires `playwright install chromium` to be run once after pip install.
Progress is reported via an async callback: callback(stage: str, pct: int).
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from app.services.fetcher import SSRFError, _resolve_and_check

ProgressCallback = Callable[[str, int], Awaitable[None]]

_PLAYWRIGHT_TIMEOUT_MS = 30_000  # 30 s navigation timeout


async def fetch_page_js(
    url: str,
    progress: ProgressCallback | None = None,
) -> str:
    """Fetch *url* using a headless Chromium browser and return the rendered HTML.

    Raises SSRFError if the resolved IP is private.
    """
    async def _emit(stage: str, pct: int) -> None:
        if progress is not None:
            await progress(stage, max(0, min(100, pct)))
    from playwright.async_api import async_playwright

    # SSRF check before launching the browser
    from urllib.parse import urlparse
    hostname = urlparse(url).hostname or ""
    _resolve_and_check(hostname)

    await _emit("launching browser", 10)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent="UniversalWebDataExtractor/1.0 (Playwright)",
                java_script_enabled=True,
            )
            page = await context.new_page()

            await _emit("navigating", 30)
            await page.goto(url, wait_until="domcontentloaded", timeout=_PLAYWRIGHT_TIMEOUT_MS)

            await _emit("waiting for JS", 60)
            await asyncio.sleep(1.5)

            await _emit("reading DOM", 85)
            html = await page.content()
        finally:
            await browser.close()

    await _emit("done", 100)
    return html
