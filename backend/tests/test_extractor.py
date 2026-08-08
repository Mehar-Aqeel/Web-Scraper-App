import pytest
from bs4 import BeautifulSoup

from app.services.extractor import (
    extract_title,
    extract_headings,
    extract_links,
    resolve_url,
    get_base_url,
)

PAGE_URL = "https://example.com/page"


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# TICKET-007: extract_title
# ---------------------------------------------------------------------------

def test_title_returns_text():
    soup = _soup("<html><head><title>Hello World</title></head></html>")
    assert extract_title(soup) == "Hello World"


def test_title_strips_whitespace():
    soup = _soup("<html><head><title>  Trimmed  </title></head></html>")
    assert extract_title(soup) == "Trimmed"


def test_title_returns_none_when_absent():
    soup = _soup("<html><head></head></html>")
    assert extract_title(soup) is None


def test_title_returns_none_when_empty():
    soup = _soup("<html><head><title>   </title></head></html>")
    assert extract_title(soup) is None


# ---------------------------------------------------------------------------
# TICKET-007: extract_headings
# ---------------------------------------------------------------------------

def test_headings_returns_all_levels():
    html = """
    <h1>Title</h1>
    <h2>Section</h2>
    <h3>Sub</h3>
    <h4>Sub-sub</h4>
    <h5>Deep</h5>
    <h6>Deepest</h6>
    """
    results = extract_headings(_soup(html), PAGE_URL)
    levels = [r["level"] for r in results]
    assert levels == ["h1", "h2", "h3", "h4", "h5", "h6"]


def test_headings_correct_fields():
    soup = _soup("<h1>Welcome</h1>")
    results = extract_headings(soup, PAGE_URL)
    assert len(results) == 1
    assert results[0] == {
        "type": "heading",
        "level": "h1",
        "value": "Welcome",
        "source_url": PAGE_URL,
    }


def test_headings_skips_empty():
    soup = _soup("<h1></h1><h2>  </h2><h3>Real</h3>")
    results = extract_headings(soup, PAGE_URL)
    assert len(results) == 1
    assert results[0]["level"] == "h3"


def test_headings_empty_page():
    soup = _soup("<html><body></body></html>")
    assert extract_headings(soup, PAGE_URL) == []


# ---------------------------------------------------------------------------
# TICKET-008: resolve_url helper
# ---------------------------------------------------------------------------

def test_resolve_absolute_url_unchanged():
    assert resolve_url("https://other.com/page", PAGE_URL) == "https://other.com/page"


def test_resolve_relative_url():
    assert resolve_url("/about", PAGE_URL) == "https://example.com/about"


def test_resolve_returns_none_for_javascript():
    assert resolve_url("javascript:void(0)", PAGE_URL) is None


def test_resolve_returns_none_for_mailto():
    assert resolve_url("mailto:a@b.com", PAGE_URL) is None


def test_resolve_returns_none_for_empty():
    assert resolve_url("", PAGE_URL) is None


def test_resolve_returns_none_for_anchor_only():
    # urljoin("https://example.com/page", "#section") → "https://example.com/page#section"
    # which is valid http — so this should resolve, not return None
    result = resolve_url("#section", PAGE_URL)
    assert result == "https://example.com/page#section"


# ---------------------------------------------------------------------------
# TICKET-008: get_base_url helper
# ---------------------------------------------------------------------------

def test_base_url_from_base_tag():
    soup = _soup('<html><head><base href="https://cdn.example.com/"></head></html>')
    assert get_base_url(soup, PAGE_URL) == "https://cdn.example.com/"


def test_base_url_falls_back_to_page_url():
    soup = _soup("<html><head></head></html>")
    assert get_base_url(soup, PAGE_URL) == PAGE_URL


# ---------------------------------------------------------------------------
# TICKET-008: extract_links
# ---------------------------------------------------------------------------

def test_links_resolves_relative_urls():
    soup = _soup('<a href="/about">About</a>')
    results = extract_links(soup, PAGE_URL)
    assert results[0]["value"] == "https://example.com/about"


def test_links_uses_base_tag():
    html = '<html><head><base href="https://cdn.example.com/"></head><body><a href="img/logo.png">Logo</a></body></html>'
    results = extract_links(_soup(html), PAGE_URL)
    assert results[0]["value"] == "https://cdn.example.com/img/logo.png"


def test_links_captures_text():
    soup = _soup('<a href="/contact">Contact Us</a>')
    results = extract_links(soup, PAGE_URL)
    assert results[0]["text"] == "Contact Us"


def test_links_skips_malformed_href():
    soup = _soup('<a href="javascript:void(0)">Bad</a><a href="/good">Good</a>')
    results = extract_links(soup, PAGE_URL)
    assert len(results) == 1
    assert results[0]["value"] == "https://example.com/good"


def test_links_correct_fields():
    soup = _soup('<a href="https://other.com/">Visit</a>')
    results = extract_links(soup, PAGE_URL)
    assert results[0] == {
        "type": "link",
        "value": "https://other.com/",
        "text": "Visit",
        "source_url": PAGE_URL,
    }


def test_links_empty_page():
    soup = _soup("<html><body><p>No links</p></body></html>")
    assert extract_links(soup, PAGE_URL) == []


def test_links_skips_anchor_with_no_href():
    soup = _soup('<a name="top">Anchor</a><a href="/real">Real</a>')
    results = extract_links(soup, PAGE_URL)
    assert len(results) == 1

from app.services.extractor import (
    extract_meta,
    extract_open_graph,
    extract_canonical,
    extract_paragraphs,
    extract_images,
    extract_tables,
)


# ---------------------------------------------------------------------------
# TICKET-009: extract_meta
# ---------------------------------------------------------------------------

def test_meta_returns_description_and_keywords():
    html = '''
    <meta name="description" content="A test page">
    <meta name="keywords" content="test, page">
    '''
    results = extract_meta(_soup(html), PAGE_URL)
    types = {r["type"]: r["value"] for r in results}
    assert types["meta_description"] == "A test page"
    assert types["meta_keywords"] == "test, page"


def test_meta_returns_empty_when_absent():
    soup = _soup("<html><head></head></html>")
    assert extract_meta(soup, PAGE_URL) == []


def test_meta_skips_tag_without_content():
    soup = _soup('<meta name="description">')
    assert extract_meta(soup, PAGE_URL) == []


def test_meta_case_insensitive_name():
    soup = _soup('<meta name="Description" content="Hello">')
    results = extract_meta(soup, PAGE_URL)
    assert results[0]["type"] == "meta_description"


# ---------------------------------------------------------------------------
# TICKET-009: extract_open_graph
# ---------------------------------------------------------------------------

def test_og_returns_present_tags():
    html = '''
    <meta property="og:title" content="OG Title">
    <meta property="og:description" content="OG Desc">
    '''
    results = extract_open_graph(_soup(html), PAGE_URL)
    props = {r["text"]: r["value"] for r in results}
    assert props["og:title"] == "OG Title"
    assert props["og:description"] == "OG Desc"


def test_og_skips_tag_without_content():
    soup = _soup('<meta property="og:title">')
    assert extract_open_graph(soup, PAGE_URL) == []


def test_og_deduplicates_keeps_first():
    html = '''
    <meta property="og:title" content="First">
    <meta property="og:title" content="Second">
    '''
    results = extract_open_graph(_soup(html), PAGE_URL)
    og_titles = [r for r in results if r["text"] == "og:title"]
    assert len(og_titles) == 1
    assert og_titles[0]["value"] == "First"


def test_og_resolves_image_to_absolute():
    html = '<meta property="og:image" content="/images/hero.jpg">'
    results = extract_open_graph(_soup(html), PAGE_URL)
    assert results[0]["value"] == "https://example.com/images/hero.jpg"


def test_og_resolves_url_to_absolute():
    html = '<meta property="og:url" content="/home">'
    results = extract_open_graph(_soup(html), PAGE_URL)
    assert results[0]["value"] == "https://example.com/home"


def test_og_uses_base_tag_for_resolution():
    html = '''
    <html><head>
    <base href="https://cdn.example.com/">
    <meta property="og:image" content="img/hero.jpg">
    </head></html>
    '''
    results = extract_open_graph(_soup(html), PAGE_URL)
    assert results[0]["value"] == "https://cdn.example.com/img/hero.jpg"


def test_og_empty_page():
    soup = _soup("<html><head></head></html>")
    assert extract_open_graph(soup, PAGE_URL) == []


# ---------------------------------------------------------------------------
# TICKET-009: extract_canonical
# ---------------------------------------------------------------------------

def test_canonical_returns_href():
    soup = _soup('<link rel="canonical" href="https://example.com/canonical">')
    results = extract_canonical(soup, PAGE_URL)
    assert len(results) == 1
    assert results[0]["type"] == "canonical_url"
    assert results[0]["value"] == "https://example.com/canonical"


def test_canonical_resolves_relative_href():
    soup = _soup('<link rel="canonical" href="/canonical-path">')
    results = extract_canonical(soup, PAGE_URL)
    assert results[0]["value"] == "https://example.com/canonical-path"


def test_canonical_returns_empty_when_absent():
    soup = _soup("<html><head></head></html>")
    assert extract_canonical(soup, PAGE_URL) == []


def test_canonical_returns_empty_when_no_href():
    soup = _soup('<link rel="canonical">')
    assert extract_canonical(soup, PAGE_URL) == []


# ---------------------------------------------------------------------------
# TICKET-010: extract_paragraphs
# ---------------------------------------------------------------------------

def test_paragraphs_returns_text():
    soup = _soup("<p>Hello</p><p>World</p>")
    results = extract_paragraphs(soup, PAGE_URL)
    values = [r["value"] for r in results]
    assert values == ["Hello", "World"]


def test_paragraphs_skips_empty():
    soup = _soup("<p></p><p>  </p><p>Real</p>")
    results = extract_paragraphs(soup, PAGE_URL)
    assert len(results) == 1
    assert results[0]["value"] == "Real"


def test_paragraphs_correct_fields():
    soup = _soup("<p>Test paragraph</p>")
    results = extract_paragraphs(soup, PAGE_URL)
    assert results[0] == {
        "type": "paragraph",
        "value": "Test paragraph",
        "source_url": PAGE_URL,
    }


def test_paragraphs_empty_page():
    soup = _soup("<html><body></body></html>")
    assert extract_paragraphs(soup, PAGE_URL) == []


# ---------------------------------------------------------------------------
# TICKET-010: extract_images
# ---------------------------------------------------------------------------

def test_images_returns_absolute_url_and_alt():
    soup = _soup('<img src="/img/logo.png" alt="Logo">')
    results = extract_images(soup, PAGE_URL)
    assert results[0] == {
        "type": "image",
        "value": "https://example.com/img/logo.png",
        "text": "Logo",
        "source_url": PAGE_URL,
    }


def test_images_uses_base_tag():
    html = '<html><head><base href="https://cdn.example.com/"></head><body><img src="img/photo.jpg" alt="Photo"></body></html>'
    results = extract_images(_soup(html), PAGE_URL)
    assert results[0]["value"] == "https://cdn.example.com/img/photo.jpg"


def test_images_empty_alt_when_absent():
    soup = _soup('<img src="/img/no-alt.png">')
    results = extract_images(soup, PAGE_URL)
    assert results[0]["text"] == ""


def test_images_skips_invalid_src():
    soup = _soup('<img src="javascript:void(0)"><img src="/valid.png" alt="ok">')
    results = extract_images(soup, PAGE_URL)
    assert len(results) == 1
    assert "valid.png" in results[0]["value"]


def test_images_empty_page():
    soup = _soup("<html><body></body></html>")
    assert extract_images(soup, PAGE_URL) == []


# ---------------------------------------------------------------------------
# TICKET-010: extract_tables
# ---------------------------------------------------------------------------

_TABLE_HTML = """
<table>
  <tr><th>Plan</th><th>Price</th><th>Seats</th></tr>
  <tr><td>Basic</td><td>$10/mo</td><td>5</td></tr>
  <tr><td>Pro</td><td>$25/mo</td><td>20</td></tr>
</table>
"""

def test_tables_returns_one_record_per_data_row():
    results = extract_tables(_soup(_TABLE_HTML), PAGE_URL)
    assert len(results) == 2


def test_tables_preserves_headers():
    results = extract_tables(_soup(_TABLE_HTML), PAGE_URL)
    assert results[0]["table_headers"] == "Plan | Price | Seats"


def test_tables_row_value_joins_cells():
    results = extract_tables(_soup(_TABLE_HTML), PAGE_URL)
    assert results[0]["value"] == "Basic | $10/mo | 5"
    assert results[1]["value"] == "Pro | $25/mo | 20"


def test_tables_correct_indices():
    results = extract_tables(_soup(_TABLE_HTML), PAGE_URL)
    assert results[0]["table_index"] == 0
    assert results[0]["row_index"] == 0
    assert results[1]["row_index"] == 1


def test_tables_multiple_tables():
    html = "<table><tr><td>A</td></tr></table><table><tr><td>B</td></tr></table>"
    results = extract_tables(_soup(html), PAGE_URL)
    assert results[0]["table_index"] == 0
    assert results[1]["table_index"] == 1


def test_tables_no_headers_omits_field():
    html = "<table><tr><td>A</td><td>B</td></tr></table>"
    results = extract_tables(_soup(html), PAGE_URL)
    assert "table_headers" not in results[0]


def test_tables_skips_empty_rows():
    html = "<table><tr><td></td><td>  </td></tr><tr><td>Real</td></tr></table>"
    results = extract_tables(_soup(html), PAGE_URL)
    assert len(results) == 1
    assert results[0]["value"] == "Real"


def test_tables_empty_page():
    soup = _soup("<html><body></body></html>")
    assert extract_tables(soup, PAGE_URL) == []
