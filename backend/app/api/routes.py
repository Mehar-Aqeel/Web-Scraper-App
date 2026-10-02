import asyncio
import time
import httpx
import structlog
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import settings
from app.schemas.extraction import (
    BatchExtractRequest,
    BatchExtractResponse,
    BatchResultItem,
    CsvExportRequest,
    ExportRequest,
    ExtractionType,
    ExtractRequest,
    ExtractResponse,
    JobResponse,
    JobStatusResponse,
    make_cursor,
    parse_cursor,
)
from app.services.csv_exporter import generate_csv
from app.services.deduplicator import deduplicate
from app.services.dispatch import ParseTimeoutError, RobotsDisallowedError, ServerBusyError, batch_extract, extract, extract_js_async
from app.services.exporter import generate_excel, generate_json
from app.services.fetcher import SSRFError, TooManyRedirectsError
from app.services.history_store import get_dashboard_stats, get_job_records, list_jobs, save_job
from app.services.job_store import create_job, get_job
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
# Batch extraction (TICKET-025)
# ---------------------------------------------------------------------------

@router.post("/extract/batch", response_model=BatchExtractResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_IP_PER_MINUTE}/minute")
async def run_batch_extraction(body: BatchExtractRequest, request: Request):
    results = await batch_extract(body.urls, body.extract)
    return BatchExtractResponse(
        results=[BatchResultItem(**r) for r in results]
    )


# ---------------------------------------------------------------------------
# JSON export (TICKET-026)
# ---------------------------------------------------------------------------

@router.post("/export/json")
async def export_json_endpoint(body: ExportRequest, request: Request):
    try:
        data = generate_json(body.data)
    except Exception as exc:
        logger.error("json_export_error", error=str(exc))
        return error_response(request, 500, "INTERNAL_ERROR", "JSON export failed.")
    return StreamingResponse(
        iter([data]),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="extraction.json"',
            "Content-Length": str(len(data)),
        },
    )


# ---------------------------------------------------------------------------
# Excel export (TICKET-026)
# ---------------------------------------------------------------------------

@router.post("/export/excel")
async def export_excel_endpoint(body: ExportRequest, request: Request):
    try:
        data = generate_excel(body.data)
    except Exception as exc:
        logger.error("excel_export_error", error=str(exc))
        return error_response(request, 500, "INTERNAL_ERROR", "Excel export failed.")
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="extraction.xlsx"',
            "Content-Length": str(len(data)),
        },
    )


# ---------------------------------------------------------------------------
# Scraping history (TICKET-027)
# ---------------------------------------------------------------------------

@router.get("/history")
async def get_history(limit: int = 50):
    jobs = await list_jobs(limit=min(limit, 200))
    return {"jobs": jobs}


@router.get("/history/{job_id}/records")
async def get_history_records(job_id: int, request: Request):
    records = await get_job_records(job_id)
    if not records:
        return error_response(request, 404, "INTERNAL_ERROR", "Job not found or has no records.")
    return {"job_id": job_id, "records": records}


# ---------------------------------------------------------------------------
# Dashboard stats (TICKET-029)
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def dashboard():
    return await get_dashboard_stats()


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

@router.post("/export/csv")
async def export_csv(body: CsvExportRequest, request: Request):
    try:
        csv_bytes = generate_csv(body.data)
    except Exception as exc:
        logger.error("csv_export_error", error=str(exc))
        return error_response(request, 500, "INTERNAL_ERROR", "CSV generation failed.")

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="extraction.csv"',
            "Content-Length": str(len(csv_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# JS rendering endpoint (Playwright async job)
# ---------------------------------------------------------------------------

@router.post("/extract/js", response_model=JobResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_IP_PER_MINUTE}/minute")
async def run_js_extraction(body: ExtractRequest, request: Request):
    """Start a Playwright extraction job. Returns job_id immediately."""
    job = create_job(body.url)
    asyncio.create_task(extract_js_async(job.job_id, body.url, body.extract))
    return JobResponse(job_id=job.job_id, status=job.status, url=job.url)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, request: Request):
    """Poll job status and result."""
    job = get_job(job_id)
    if job is None:
        return error_response(request, 404, "INTERNAL_ERROR", "Job not found.")

    page = job.data[:settings.MAX_RESULT_ROWS]
    next_offset = settings.MAX_RESULT_ROWS
    next_cursor = make_cursor(next_offset) if next_offset < len(job.data) else None

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        data=page,
        warnings=job.warnings,
        error=job.error,
        next_cursor=next_cursor,
    )


@router.websocket("/jobs/{job_id}/ws")
async def job_progress_ws(websocket: WebSocket, job_id: str):
    """WebSocket stream of {stage, progress, status} events for a job."""
    await websocket.accept()
    job = get_job(job_id)
    if job is None:
        await websocket.send_json({"error": "Job not found"})
        await websocket.close()
        return

    # If already finished, send final state immediately
    if job.status in ("done", "error"):
        await websocket.send_json({
            "stage": job.stage,
            "progress": job.progress,
            "status": job.status,
        })
        await websocket.close()
        return

    queue = job.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"ping": True})
                continue
            await websocket.send_json(event)
            if event.get("status") in ("done", "error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        job.unsubscribe(queue)
    await websocket.close()


# ---------------------------------------------------------------------------
# Main extraction endpoint
# ---------------------------------------------------------------------------

@router.post("/extract", response_model=ExtractResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_IP_PER_MINUTE}/minute")
async def run_extraction(body: ExtractRequest, request: Request):
    _start = time.perf_counter()
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

    # TICKET-029a: server-side dedup before pagination
    data = deduplicate(data)

    # Paginate using the shared MAX_RESULT_ROWS limit
    page = data[cursor_offset: cursor_offset + settings.MAX_RESULT_ROWS]
    next_offset = cursor_offset + settings.MAX_RESULT_ROWS
    next_cursor = make_cursor(next_offset) if next_offset < len(data) else None

    duration_ms = round((time.perf_counter() - _start) * 1000, 2)

    # TICKET-027/028: persist to history
    asyncio.create_task(save_job(
        url=body.url,
        fields=[t.value for t in body.extract],
        records=data,
        warnings=warnings,
        duration_ms=duration_ms,
    ))

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
