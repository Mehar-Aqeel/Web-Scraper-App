import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.csv_exporter import generate_csv

client = TestClient(app)


# ---------------------------------------------------------------------------
# TICKET-018: generate_csv unit tests
# ---------------------------------------------------------------------------

def test_csv_contains_headers():
    rows = [{"type": "title", "value": "Hello", "source_url": "https://example.com"}]
    csv = generate_csv(rows).decode()
    assert "type" in csv
    assert "value" in csv
    assert "source_url" in csv


def test_csv_contains_row_data():
    rows = [{"type": "title", "value": "Hello", "source_url": "https://example.com"}]
    csv = generate_csv(rows).decode()
    assert "Hello" in csv
    assert "https://example.com" in csv


def test_csv_empty_rows_returns_header_only():
    csv = generate_csv([]).decode()
    lines = [l for l in csv.strip().splitlines() if l]
    assert len(lines) == 1  # header row only


def test_formula_injection_equals_prefixed():
    rows = [{"type": "link", "value": "=CMD|'/C calc'!A0", "source_url": "https://x.com"}]
    csv = generate_csv(rows).decode()
    assert "'=CMD" in csv


def test_formula_injection_plus_prefixed():
    rows = [{"type": "link", "value": "+1234567890", "source_url": "https://x.com"}]
    csv = generate_csv(rows).decode()
    assert "'+1234567890" in csv


def test_formula_injection_minus_prefixed():
    rows = [{"type": "link", "value": "-1+2", "source_url": "https://x.com"}]
    csv = generate_csv(rows).decode()
    assert "'-1+2" in csv


def test_formula_injection_at_prefixed():
    rows = [{"type": "link", "value": "@SUM(A1)", "source_url": "https://x.com"}]
    csv = generate_csv(rows).decode()
    assert "'@SUM" in csv


def test_safe_value_not_prefixed():
    rows = [{"type": "title", "value": "Normal text", "source_url": "https://x.com"}]
    csv = generate_csv(rows).decode()
    assert "'Normal" not in csv
    assert "Normal text" in csv


def test_returns_bytes():
    result = generate_csv([])
    assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# TICKET-018: /export/csv endpoint tests
# ---------------------------------------------------------------------------

def test_export_csv_endpoint_returns_csv_content_type():
    rows = [{"type": "title", "value": "Hello", "source_url": "https://example.com"}]
    res = client.post("/api/v1/export/csv", json={"data": rows})
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]


def test_export_csv_endpoint_has_content_disposition():
    rows = [{"type": "title", "value": "Hello", "source_url": "https://example.com"}]
    res = client.post("/api/v1/export/csv", json={"data": rows})
    assert "attachment" in res.headers["content-disposition"]
    assert "extraction.csv" in res.headers["content-disposition"]


def test_export_csv_endpoint_has_content_length():
    rows = [{"type": "title", "value": "Hello", "source_url": "https://example.com"}]
    res = client.post("/api/v1/export/csv", json={"data": rows})
    assert "content-length" in res.headers
    assert int(res.headers["content-length"]) > 0


def test_export_csv_endpoint_row_cap_returns_validation_error(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MAX_RESULT_ROWS", 2)
    rows = [{"type": "title", "value": f"v{i}", "source_url": "https://x.com"} for i in range(5)]
    res = client.post("/api/v1/export/csv", json={"data": rows})
    assert res.status_code == 422


def test_export_csv_endpoint_empty_data_returns_header_only():
    res = client.post("/api/v1/export/csv", json={"data": []})
    assert res.status_code == 200
    lines = [l for l in res.text.strip().splitlines() if l]
    assert len(lines) == 1
