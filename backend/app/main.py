from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.observability_routes import router as observability_router
from app.config import settings

from app.services.observability import reset_trace_context, set_trace_context, store, utc_now

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    store.initialize()
    store.cleanup(settings.observability_retention_days)
    yield


app = FastAPI(title="Retail Supplier Delay Risk Classification", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(observability_router)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    endpoint = request.url.path
    started_at = utc_now()
    started = time.perf_counter()
    trace_context = {
        "request_id": request_id,
        "trace_id": trace_id,
        "session_id": session_id,
        "endpoint": endpoint,
    }
    context_token = set_trace_context(trace_context)
    request.state.request_id = request_id
    request.state.trace_id = trace_id
    request.state.session_id = session_id
    try:
        trace_context["parent_span_id"] = store.start_request(
            request_id, trace_id, session_id, endpoint, request.method, started_at
        )
        store.maybe_cleanup(settings.observability_retention_days)
    except Exception:
        logger.exception("Could not start observability trace")

    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Session-ID"] = session_id
        return response
    except Exception as error:
        store.record_error(
            type(error).__name__, "Unhandled request failure.", endpoint,
            request_id, trace_id, session_id,
        )
        logger.exception("Unhandled API request failure")
        raise
    finally:
        latency_ms = (time.perf_counter() - started) * 1000
        try:
            store.end_request(
                request_id, trace_id, session_id, endpoint, request.method,
                status_code, latency_ms, started_at,
            )
        except Exception:
            logger.exception("Could not persist completed request metrics")
        reset_trace_context(context_token)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "retail-supplier-risk"}
