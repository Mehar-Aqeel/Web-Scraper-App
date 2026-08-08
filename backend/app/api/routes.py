import httpx
import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas.extraction import (
    ExtractionType,
    ExtractRequest,
    ExtractResponse,
    make_cursor,
    parse_cursor,
)
from app.services.dispatch import ParseTimeoutError, RobotsDisallowedError, ServerBusyError, extract
from app.services.fetcher import SSRFError, TooManyRedirectsError
from app.services.limiter import limiter
from app.services.page_fetcher import ContentTypeError, ResponseTooLargeError
from app.utils.responses import error_response

router = APIRouter()
logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health/live")
async def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    """Readiness check — returns 503 if in-process dependencies are unhealthy.

    For the MVP (in-process cache/rate-limiter only) this is always healthy.
    When Redis or a DB is added, check connectivity here before returning ok.
    """
    checks: dict[str, str] = {}
    healthy = True

    # Placeholder: verify robots cache dict is accessible
    try:
        from app.services.robots import _cache  # noqa: F401
        checks["robots_cache"] = "ok"
    except Exception as exc:
        checks["robots_cache"] = f"error: {exc}"
        healthy = False

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )


# ---------------------------------------------------------------------------
# Extraction types enum
# ---------------------------------------------------------------------------

@router.get("/extract/types")
async def get_extraction_types():
    """Return the canonical list of supported extraction type identifiers."""
    return {"types": [t.value for t in ExtractionType]}


# ---------------------------------------------------------------------------
# Main extraction endpoint
# ---------------------------------------------------------------------------

@router.post("/extract", response_model=ExtractResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_IP_PER_MINUTE}/minute")
async def run_extraction(body: ExtractRequest, request: Request):
    cursor_offset = parse_cursor(request.query_params.get("cursor"))

    try:
        data, warnings = await extract(body.url, body.extract)
    except ServerBusyError as exc:
        return error_response(request, 503, "INTERNAL_ERROR", str(exc))
    except RobotsDisallowedError as exc:
        return error_response(request, 403, "ROBOTS_DISALLOWED", str(exc))
    except SSRFError as exc:
        return error_response(request, 400, "SSRF_BLOCKED", str(exc))
    except TooManyRedirectsError as exc:
        return error_response(request, 400, "UPSTREAM_HTTP_ERROR", str(exc))
    except ContentTypeError as exc:
        return error_response(request, 422, "CONTENT_TYPE_UNSUPPORTED", str(exc))
    except ResponseTooLargeError as exc:
        return error_response(request, 413, "RESPONSE_TOO_LARGE", str(exc))
    except ParseTimeoutError as exc:
        return error_response(request, 504, "PARSE_ERROR", str(exc))
    except httpx.TimeoutException:
        return error_response(request, 504, "TIMEOUT", "The request to the target URL timed out.")
    except Exception as exc:
        logger.error("extraction_error", url=body.url, error=str(exc))
        return error_response(request, 500, "INTERNAL_ERROR", "An unexpected error occurred.")

    # Paginate using the shared MAX_RESULT_ROWS limit
    page = data[cursor_offset: cursor_offset + settings.MAX_RESULT_ROWS]
    next_offset = cursor_offset + settings.MAX_RESULT_ROWS
    next_cursor = make_cursor(next_offset) if next_offset < len(data) else None

    logger.info(
        "extraction_complete",
        url=body.url,
        fields=[t.value for t in body.extract],
        total_records=len(data),
        page_records=len(page),
        warning_count=len(warnings),
        request_id=getattr(request.state, "request_id", ""),
    )

    return ExtractResponse(
        success=True,
        url=body.url,
        data=page,
        warnings=warnings,
        next_cursor=next_cursor,
    )
