import logging
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import router
from app.config import settings
from app.services.limiter import limiter

# Per-request ID accessible anywhere in the call stack
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Configure stdlib logging to JSON via structlog
logging.basicConfig(level=settings.LOG_LEVEL.upper())
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.database import init_db
    await init_db()
    logger.info("startup", env=settings.APP_ENV)
    yield
    logger.info("shutdown")


app = FastAPI(title="Universal Web Data Extractor", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": {"code": "RATE_LIMITED", "message": "Too many requests. Please slow down."},
            "request_id": getattr(request.state, "request_id", ""),
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request_id_var.set(request_id)
    request.state.request_id = request_id
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


app.include_router(router, prefix="/api/v1")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    message = first.get("msg", "Invalid request.")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {"code": "VALIDATION_ERROR", "message": message},
            "request_id": getattr(request.state, "request_id", ""),
        },
    )
