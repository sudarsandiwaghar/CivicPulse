"""
CivicPulse FastAPI Application Factory

Creates and configures the FastAPI application instance. This is the
entry point for the ASGI server (Uvicorn).

Responsibilities:
    - Create the FastAPI app with metadata for OpenAPI documentation.
    - Register the lifespan handler for startup/shutdown tasks.
    - Mount the versioned API router under the configured prefix.
    - Register middleware (request logging, CORS in future).
    - Register global exception handlers that translate domain
      exceptions into consistent JSON error responses.

Running the application:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import sys
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolationError,
    CivicPulseError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    FileUploadError,
    InvalidStateTransitionError,
    RateLimitExceededError,
)
from app.core.middleware import RequestLoggingMiddleware
from app.api.v1.router import router as v1_router


# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    """
    Configure application-wide logging.

    Sets up a consistent log format with timestamps and module names.
    The log level is controlled by the LOG_LEVEL setting, defaulting
    to INFO. DEBUG mode enables SQLAlchemy query logging via the
    engine's echo parameter (see db/session.py).
    """
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


# ---------------------------------------------------------------------------
# Application Lifespan (Startup / Shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manages application startup and shutdown tasks.

    Startup:
        1. Configure logging.
        2. Initialise the database engine and session factory.
        3. Create the uploads directory if it doesn't exist.

    Shutdown:
        1. Dispose of the database engine (closes all pooled connections).
    """
    import os
    from app.db.session import init_engine, get_engine

    # --- Startup ---
    _configure_logging()
    logger = logging.getLogger("civicpulse.startup")

    settings = get_settings()
    logger.info(
        "Starting %s v%s", settings.APP_NAME, settings.APP_VERSION
    )

    # Initialise database connection pool
    init_engine()

    # Ensure the three core authorization roles exist in the database
    try:
        from app.db.session import _SessionFactory
        if _SessionFactory:
            with _SessionFactory() as session:
                from app.services.auth_service import init_roles
                init_roles(session)
                logger.info("Application roles verified / initialised")

                from app.services.category_service import init_categories
                init_categories(session)
                logger.info("Default categories and departments verified / initialised")
    except Exception as exc:
        logger.warning("Auto-initialisation skipped or failed during startup: %s", exc)

    # Ensure the upload directory exists for local file storage
    upload_dir = settings.UPLOAD_DIR
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, exist_ok=True)
        logger.info("Created upload directory: %s", upload_dir)

    logger.info("Application startup complete")

    yield  # Application runs here

    # --- Shutdown ---
    logger.info("Shutting down %s", settings.APP_NAME)
    try:
        engine = get_engine()
        engine.dispose()
        logger.info("Database connections closed")
    except RuntimeError:
        # Engine was never initialised (e.g. during testing)
        pass

    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI Application Instance
# ---------------------------------------------------------------------------

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    # OpenAPI docs available at /docs (Swagger UI) and /redoc when enabled
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware Registration
# ---------------------------------------------------------------------------

app.add_middleware(RequestLoggingMiddleware)

# CORS middleware supporting environment-configured trusted origins
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API Router Mounting
# ---------------------------------------------------------------------------

app.include_router(v1_router, prefix=settings.API_V1_PREFIX)


# ---------------------------------------------------------------------------
# Global Exception Handlers
#
# Each handler catches a specific domain exception and returns a
# consistent JSON error body. This keeps HTTP concerns out of the
# service layer while ensuring the frontend receives predictable
# error structures.
# ---------------------------------------------------------------------------

@app.exception_handler(AuthenticationError)
async def authentication_error_handler(
    request: Request, exc: AuthenticationError
) -> JSONResponse:
    """Map authentication failures to 401 Unauthorized with standard Bearer challenge header."""
    return JSONResponse(
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
        content={
            "success": False,
            "message": "Authentication failed",
            "detail": exc.message,
        },
    )


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(
    request: Request, exc: AuthorizationError
) -> JSONResponse:
    """Map authorisation failures to 403 Forbidden."""
    return JSONResponse(
        status_code=403,
        content={
            "success": False,
            "message": "Forbidden",
            "detail": exc.message,
        },
    )


@app.exception_handler(EntityNotFoundError)
async def entity_not_found_handler(
    request: Request, exc: EntityNotFoundError
) -> JSONResponse:
    """Map missing entity lookups to 404 Not Found."""
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": "Not found",
            "detail": exc.message,
        },
    )


@app.exception_handler(EntityAlreadyExistsError)
async def entity_already_exists_handler(
    request: Request, exc: EntityAlreadyExistsError
) -> JSONResponse:
    """Map duplicate entity creation to 409 Conflict."""
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "message": "Conflict",
            "detail": exc.message,
        },
    )


@app.exception_handler(InvalidStateTransitionError)
async def invalid_state_transition_handler(
    request: Request, exc: InvalidStateTransitionError
) -> JSONResponse:
    """Map invalid complaint status transitions to 422 Unprocessable Entity."""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Invalid state transition",
            "detail": exc.message,
        },
    )


@app.exception_handler(BusinessRuleViolationError)
async def business_rule_violation_handler(
    request: Request, exc: BusinessRuleViolationError
) -> JSONResponse:
    """Map business rule violations to 422 Unprocessable Entity."""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Business rule violation",
            "detail": exc.message,
        },
    )


@app.exception_handler(FileUploadError)
async def file_upload_error_handler(
    request: Request, exc: FileUploadError
) -> JSONResponse:
    """Map file upload failures to 400 Bad Request."""
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": "File upload error",
            "detail": exc.message,
        },
    )


@app.exception_handler(RateLimitExceededError)
async def rate_limit_error_handler(
    request: Request, exc: RateLimitExceededError
) -> JSONResponse:
    """Map rate limit violations to 429 Too Many Requests."""
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": "Rate limit exceeded",
            "detail": exc.message,
        },
    )


@app.exception_handler(CivicPulseError)
async def generic_civicpulse_error_handler(
    request: Request, exc: CivicPulseError
) -> JSONResponse:
    """
    Catch-all for any CivicPulseError not handled by a more specific
    handler above. Returns 500 to avoid leaking internal details.
    """
    logging.getLogger("civicpulse.error").error(
        "Unhandled application error: %s", exc.message
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": "An unexpected error occurred",
        },
    )


@app.exception_handler(Exception)
async def unhandled_server_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Catch-all for any unexpected Python exceptions.
    Logs full exception and traceback server-side and returns sanitized JSON.
    Never exposes internal paths, database schemas, or stack traces in production.
    """
    logging.getLogger("civicpulse.unhandled").exception(
        "Unhandled unexpected server exception: %s", exc
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": "An unexpected server error occurred. Please contact system administration.",
        },
    )
