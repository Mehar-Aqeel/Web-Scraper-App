import base64
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator

from app.utils.url_validator import MAX_URL_LENGTH, ALLOWED_SCHEMES


class ExtractionType(str, Enum):
    title = "title"
    meta = "meta"
    headings = "headings"
    paragraphs = "paragraphs"
    links = "links"
    images = "images"
    tables = "tables"
    open_graph = "open_graph"
    canonical_url = "canonical_url"


class ExtractRequest(BaseModel):
    url: str
    extract: list[ExtractionType]

    @field_validator("url")
    @classmethod
    def validate_url_field(cls, v: str) -> str:
        from urllib.parse import urlparse
        if len(v) > MAX_URL_LENGTH:
            raise ValueError(f"URL exceeds the maximum allowed length of {MAX_URL_LENGTH} characters.")
        parsed = urlparse(v)
        if parsed.scheme not in ALLOWED_SCHEMES:
            raise ValueError(
                f"URL scheme '{parsed.scheme or '(none)'}' is not allowed. Only http and https are supported."
            )
        if not parsed.netloc:
            raise ValueError("URL is missing a host.")
        return v

    @field_validator("extract")
    @classmethod
    def validate_extract(cls, v: list[ExtractionType]) -> list[ExtractionType]:
        if not v:
            raise ValueError("At least one extraction type must be selected.")
        # Deduplicate while preserving order
        seen: set[ExtractionType] = set()
        result = []
        for item in v:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result


class CsvExportRequest(BaseModel):
    data: list[dict[str, Any]]

    @field_validator("data")
    @classmethod
    def validate_row_count(cls, v: list) -> list:
        from app.config import settings
        if len(v) > settings.MAX_RESULT_ROWS:
            raise ValueError(
                f"Row count {len(v)} exceeds the maximum allowed export size of {settings.MAX_RESULT_ROWS}."
            )
        return v


class ExtractResponse(BaseModel):
    success: bool
    url: str
    data: list[dict[str, Any]]
    warnings: list[str]
    next_cursor: str | None = None


class BatchExtractRequest(BaseModel):
    urls: list[str]
    extract: list[ExtractionType]

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        from urllib.parse import urlparse
        if not v:
            raise ValueError("At least one URL must be provided.")
        if len(v) > 20:
            raise ValueError("Maximum 20 URLs per batch request.")
        for url in v:
            if len(url) > MAX_URL_LENGTH:
                raise ValueError(f"URL exceeds maximum length: {url[:80]}")
            parsed = urlparse(url)
            if parsed.scheme not in ALLOWED_SCHEMES:
                raise ValueError(f"Invalid URL scheme in: {url[:80]}")
        return v

    @field_validator("extract")
    @classmethod
    def validate_extract(cls, v: list[ExtractionType]) -> list[ExtractionType]:
        if not v:
            raise ValueError("At least one extraction type must be selected.")
        seen: set[ExtractionType] = set()
        return [x for x in v if not (seen.add(x) or x in seen - {x})]


class BatchResultItem(BaseModel):
    url: str
    success: bool
    data: list[dict[str, Any]]
    warnings: list[str]
    error: str | None = None


class BatchExtractResponse(BaseModel):
    results: list[BatchResultItem]


class ExportRequest(BaseModel):
    data: list[dict[str, Any]]

    @field_validator("data")
    @classmethod
    def validate_row_count(cls, v: list) -> list:
        from app.config import settings
        if len(v) > settings.MAX_RESULT_ROWS:
            raise ValueError(f"Row count {len(v)} exceeds maximum export size of {settings.MAX_RESULT_ROWS}.")
        return v


class JobResponse(BaseModel):
    job_id: str
    status: str
    url: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    data: list[dict[str, Any]]
    warnings: list[str]
    error: str | None = None
    next_cursor: str | None = None


def make_cursor(offset: int) -> str:
    """Encode a row offset as an opaque base64 cursor token."""
    return base64.b64encode(str(offset).encode()).decode()


def parse_cursor(cursor: str | None) -> int:
    """Decode a cursor token back to a row offset. Returns 0 on invalid input."""
    if not cursor:
        return 0
    try:
        return int(base64.b64decode(cursor.encode()).decode())
    except Exception:
        return 0
