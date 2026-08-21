from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine
from starlette.middleware.base import RequestResponseEndpoint

from app.config import get_settings
from app.db import create_database_engine, database_is_ready
from app.logging import configure_logging
from app.schemas import ErrorDetail, ErrorResponse, HealthResponse

logger = structlog.get_logger()


def create_app(engine_factory: Callable[[], Engine] = create_database_engine) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database_engine = engine_factory()
        yield
        app.state.database_engine.dispose()

    application = FastAPI(
        title="Reps API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )

    @application.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @application.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception(
            "unhandled_request_error",
            path=request.url.path,
            error_type=type(exc).__name__,
        )
        payload = ErrorResponse(
            error=ErrorDetail(
                code="internal_error",
                message="The request could not be completed.",
                request_id=request_id,
            )
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

    @application.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        return HealthResponse(
            status="ok",
            request_id=request.headers.get("x-request-id") or "unknown",
        )

    @application.get(
        "/ready",
        response_model=HealthResponse,
        responses={503: {"model": ErrorResponse}},
    )
    async def ready(request: Request) -> HealthResponse | JSONResponse:
        request_id = request.headers.get("x-request-id") or "unknown"
        if not database_is_ready(request.app.state.database_engine):
            payload = ErrorResponse(
                error=ErrorDetail(
                    code="database_unavailable",
                    message="The API is waiting for its database.",
                    request_id=request_id,
                )
            )
            return JSONResponse(status_code=503, content=payload.model_dump())
        return HealthResponse(status="ok", request_id=request_id)

    return application


app = create_app()
