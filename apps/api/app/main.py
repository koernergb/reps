import time
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
from app.db import create_database_engine, create_session_factory, database_is_ready
from app.errors import ApiError, api_error_handler
from app.llm.provider import set_runtime_choice
from app.llm.runtime import refresh as refresh_llm_choice
from app.local_mode import LOCAL_USER_ID
from app.logging import configure_logging
from app.metrics import request_metrics
from app.routes.drills import router as drills_router
from app.routes.executions import router as executions_router
from app.routes.interviews import router as interviews_router
from app.routes.learner import router as learner_router
from app.routes.local_data import router as local_data_router
from app.routes.problems import router as problems_router
from app.routes.reports import router as reports_router
from app.routes.reviews import router as reviews_router
from app.routes.settings import router as settings_router
from app.routes.solutions import router as solutions_router
from app.routes.system import router as system_router
from app.schemas import ErrorDetail, ErrorResponse, HealthResponse

logger = structlog.get_logger()


def create_app(engine_factory: Callable[[], Engine] = create_database_engine) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database_engine = engine_factory()
        app.state.session_factory = create_session_factory(app.state.database_engine)
        with app.state.session_factory() as session:
            refresh_llm_choice(session, LOCAL_USER_ID)
        yield
        set_runtime_choice(None)
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
        allow_origins=sorted(
            {settings.web_origin, settings.web_origin.replace("localhost", "127.0.0.1")}
        ),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "Idempotency-Key"],
    )
    application.include_router(problems_router)
    application.include_router(local_data_router)
    application.include_router(executions_router)
    application.include_router(interviews_router)
    application.include_router(reports_router)
    application.include_router(reviews_router)
    application.include_router(drills_router)
    application.include_router(learner_router)
    application.include_router(solutions_router)
    application.include_router(settings_router)
    application.include_router(system_router)
    application.add_exception_handler(ApiError, api_error_handler)

    @application.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            route = request.scope.get("route")
            request_metrics.record(
                request.method,
                getattr(route, "path", "unmatched"),
                (time.perf_counter() - started) * 1000,
                status,
            )
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
            request_id=request.state.request_id,
        )

    @application.get(
        "/ready",
        response_model=HealthResponse,
        responses={503: {"model": ErrorResponse}},
    )
    async def ready(request: Request) -> HealthResponse | JSONResponse:
        request_id = request.state.request_id
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
