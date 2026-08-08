import pytest
from app.utils.url_validator import validate_url, MAX_URL_LENGTH


@pytest.mark.parametrize("url", [
    "http://example.com",
    "https://example.com",
    "https://example.com/path?q=1#anchor",
    "http://sub.domain.example.com/page",
])
def test_valid_urls(url):
    result = validate_url(url)
    assert result.valid is True
    assert result.error_code == ""


@pytest.mark.parametrize("url, expected_fragment", [
    ("ftp://example.com",       "ftp"),
    ("file:///etc/passwd",      "file"),
    ("javascript:alert(1)",     "javascript"),
    ("//example.com",           "(none)"),
    ("example.com",             "(none)"),
    ("",                        "(none)"),
])
def test_rejects_bad_schemes(url, expected_fragment):
    result = validate_url(url)
    assert result.valid is False
    assert result.error_code == "INVALID_URL"
    assert expected_fragment in result.error_message


def test_rejects_url_over_max_length():
    url = "https://example.com/" + "a" * MAX_URL_LENGTH
    result = validate_url(url)
    assert result.valid is False
    assert result.error_code == "INVALID_URL"
    assert str(MAX_URL_LENGTH) in result.error_message


def test_accepts_url_at_exact_max_length():
    # Build a valid URL that is exactly MAX_URL_LENGTH chars
    prefix = "https://example.com/"
    url = prefix + "a" * (MAX_URL_LENGTH - len(prefix))
    assert len(url) == MAX_URL_LENGTH
    result = validate_url(url)
    assert result.valid is True


def test_rejects_url_missing_host():
    result = validate_url("https://")
    assert result.valid is False
    assert result.error_code == "INVALID_URL"
    assert "host" in result.error_message
