from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Shared URL resolution helper (base-tag-aware) — reused by all extractors
# ---------------------------------------------------------------------------

def get_base_url(soup: BeautifulSoup, page_url: str) -> str:
    """Return the base URL for resolving relative links on this page.

    Checks for a <base href> tag first; falls back to the page URL.
    """
    base_tag = soup.find("base", href=True)
    if base_tag:
        return base_tag["href"]
    return page_url


def resolve_url(href: str, base_url: str) -> str | None:
    """Resolve *href* against *base_url*.

    Returns None for empty, anchor-only, or unparseable values.
    """
    if not href or href.startswith(("javascript:", "mailto:", "tel:")):
        return None
    try:
        resolved = urljoin(base_url, href.strip())
        parsed = urlparse(resolved)
        if parsed.scheme not in ("http", "https"):
            return None
        return resolved
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# TICKET-007: Title extraction
# ---------------------------------------------------------------------------

def extract_title(soup: BeautifulSoup) -> str | None:
    """Return the page <title> text, or None if absent."""
    tag = soup.find("title")
    if tag:
        text = tag.get_text(strip=True)
        return text if text else None
    return None


# ---------------------------------------------------------------------------
# TICKET-007: Heading extraction
# ---------------------------------------------------------------------------

def extract_headings(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """Return all H1–H6 headings as normalized records."""
    results = []
    for level in range(1, 7):
        for tag in soup.find_all(f"h{level}"):
            text = tag.get_text(strip=True)
            if text:
                results.append({
                    "type": "heading",
                    "level": f"h{level}",
                    "value": text,
                    "source_url": source_url,
                })
    return results


# ---------------------------------------------------------------------------
# TICKET-008: Link extraction (base-tag-aware)
# ---------------------------------------------------------------------------

def extract_links(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """Return all <a href> links as normalized records.

    - Resolves relative URLs against <base href> when present.
    - Skips malformed or non-http(s) hrefs silently.
    """
    base_url = get_base_url(soup, source_url)
    results = []
    for tag in soup.find_all("a", href=True):
        resolved = resolve_url(tag["href"], base_url)
        if resolved is None:
            continue
        results.append({
            "type": "link",
            "value": resolved,
            "text": tag.get_text(strip=True),
            "source_url": source_url,
        })
    return results


# ---------------------------------------------------------------------------
# TICKET-009: Meta extraction
# ---------------------------------------------------------------------------

def extract_meta(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """Return meta description and keywords as normalized records."""
    results = []
    for name in ("description", "keywords"):
        tag = soup.find("meta", attrs={"name": lambda v: v and v.lower() == name})
        if tag and tag.get("content"):
            results.append({
                "type": f"meta_{name}",
                "value": tag["content"].strip(),
                "source_url": source_url,
            })
    return results


# ---------------------------------------------------------------------------
# TICKET-009: Open Graph extraction
# ---------------------------------------------------------------------------

def extract_open_graph(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """Return og:* meta tags as normalized records.

    - Tags missing a content attribute are skipped.
    - Duplicate og:* properties keep only the first occurrence.
    - og:image and og:url values are resolved to absolute URLs.
    """
    base_url = get_base_url(soup, source_url)
    seen: set[str] = set()
    results = []
    for tag in soup.find_all("meta", property=True):
        prop = tag.get("property", "").strip().lower()
        if not prop.startswith("og:"):
            continue
        if not tag.get("content"):
            continue
        if prop in seen:
            continue
        seen.add(prop)
        value = tag["content"].strip()
        if prop in ("og:image", "og:url"):
            value = resolve_url(value, base_url) or value
        results.append({
            "type": "open_graph",
            "value": value,
            "text": prop,
            "source_url": source_url,
        })
    return results


# ---------------------------------------------------------------------------
# TICKET-009: Canonical URL extraction
# ---------------------------------------------------------------------------

def extract_canonical(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """Return the canonical URL if a <link rel='canonical'> tag is present."""
    tag = soup.find("link", rel=lambda v: v and "canonical" in v)
    if not tag or not tag.get("href"):
        return []
    resolved = resolve_url(tag["href"], source_url) or tag["href"]
    return [{
        "type": "canonical_url",
        "value": resolved,
        "source_url": source_url,
    }]


# ---------------------------------------------------------------------------
# TICKET-010: Paragraph extraction
# ---------------------------------------------------------------------------

def extract_paragraphs(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """Return non-empty <p> text as normalized records."""
    results = []
    for tag in soup.find_all("p"):
        text = tag.get_text(strip=True)
        if text:
            results.append({
                "type": "paragraph",
                "value": text,
                "source_url": source_url,
            })
    return results


# ---------------------------------------------------------------------------
# TICKET-010: Image extraction (base-tag-aware)
# ---------------------------------------------------------------------------

def extract_images(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """Return <img> tags as normalized records with absolute URLs and alt text."""
    base_url = get_base_url(soup, source_url)
    results = []
    for tag in soup.find_all("img", src=True):
        resolved = resolve_url(tag["src"], base_url)
        if resolved is None:
            continue
        results.append({
            "type": "image",
            "value": resolved,
            "text": tag.get("alt", "").strip(),
            "source_url": source_url,
        })
    return results


# ---------------------------------------------------------------------------
# TICKET-010: Table extraction (row-based model)
# ---------------------------------------------------------------------------

def extract_tables(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """Return table rows as normalized records.

    Each row becomes one record with cell values joined by ' | '.
    Column headers are captured once per table from <th> cells.
    """
    results = []
    for table_index, table in enumerate(soup.find_all("table")):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        table_headers = " | ".join(headers) if headers else ""

        rows = table.find_all("tr")
        data_rows = [r for r in rows if r.find("td")]
        for row_index, row in enumerate(data_rows):
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            value = " | ".join(cells)
            if not value.strip():
                continue
            record: dict = {
                "type": "table_row",
                "value": value,
                "table_index": table_index,
                "row_index": row_index,
                "source_url": source_url,
            }
            if table_headers:
                record["table_headers"] = table_headers
            results.append(record)
    return results
