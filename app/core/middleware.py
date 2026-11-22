"""
CivicPulse Middleware

Request-level middleware for cross-cutting concerns such as rate
limiting and audit logging. Middleware components are registered
with the FastAPI application in main.py.

Phase 1 scope:
    - Request ID injection for traceability
    - Request/response logging

Future phases will add:
    - Rate limiting (Phase 13)
    - Detailed audit logging for sensitive operations (Phase 13)

Design note:
    Middleware runs on every request, so implementations must be
    lightweight. Heavy operations (like writing audit logs to a
    database) should be offloaded to background tasks.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("civicpulse.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs each incoming request and its response time.

    Assigns a unique request ID to every request via the
    X-Request-ID response header for end-to-end traceability
    across logs and error reports.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate a unique request ID for log correlation
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        logger.info(
            "Request started | id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )

        response: Response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Request completed | id=%s status=%d duration=%.1fms",
            request_id,
            response.status_code,
            elapsed_ms,
        )

        # Attach the request ID to the response for client-side correlation
        response.headers["X-Request-ID"] = request_id
        return response
