"""Correlation (request) id: per-request contextvar + middleware.

Each request gets an id (inbound X-Request-ID or a fresh uuid). It is bound to a
contextvar so structlog injects it into every log line, echoed in the response
header, and propagated to Celery tasks (see services.dispatch).
"""
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

HEADER = "X-Request-ID"


def get_request_id() -> str | None:
    return request_id_var.get()


def bind_request_id(rid: str | None) -> None:
    request_id_var.set(rid)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(HEADER) or uuid.uuid4().hex
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[HEADER] = rid
        return response
