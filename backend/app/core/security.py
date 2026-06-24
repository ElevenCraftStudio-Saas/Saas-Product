"""Security-headers middleware.

Adds standard hardening headers to every response. HSTS is only meaningful over
HTTPS but is harmless on plain HTTP (browsers ignore it there), so it's always
sent. The CSP is intentionally strict for an API (no inline scripts/styles); the
Next.js frontend ships its own CSP for its document responses.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for k, v in _HEADERS.items():
            response.headers.setdefault(k, v)
        return response
