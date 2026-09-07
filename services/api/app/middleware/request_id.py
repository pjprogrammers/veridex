"""Request ID middleware — propagates X-Request-ID across the request lifecycle.

If the client supplies an ``X-Request-ID`` header it is echoed back;
otherwise a UUID4 is generated.  The ID is injected into the structlog
context so every log line emitted during the request carries it, and it
is returned as a response header.
"""
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_CTXVAR = "request_id"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(**{REQUEST_ID_CTXVAR: request_id})

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
