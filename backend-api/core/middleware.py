"""Middleware: segurança, request-id, rate limit global."""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.config import get_settings
from core.rate_limit import check_global_rate_limit

ALLOWED_CORS_HEADERS = [
    "Accept",
    "Accept-Language",
    "Content-Language",
    "Content-Type",
    "Authorization",
    "X-API-Key",
    "Idempotency-Key",
    "X-Request-Id",
]

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        if get_settings().is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response


class CatalogCacheHeadersMiddleware(BaseHTTPMiddleware):
    """Cache-Control para leituras públicas de catálogo."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.method != "GET" or response.status_code != 200:
            return response
        path = request.url.path
        if path == "/categorias" or path.startswith("/categorias/"):
            response.headers.setdefault("Cache-Control", "public, max-age=60, stale-while-revalidate=120")
        elif path == "/catalogo/meta" or (
            path.startswith("/catalogo/") and "/admin/" not in path and response.status_code == 200
        ):
            response.headers.setdefault("Cache-Control", "public, max-age=60, stale-while-revalidate=120")
        return response


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit tiered — catálogo 600/min, global 120/min, admin 300/min (loopback isento)."""

    async def dispatch(self, request: Request, call_next):
        blocked = check_global_rate_limit(request)
        if blocked is not None:
            return blocked
        return await call_next(request)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejeita bodies demasiado grandes (DoS) — Content-Length e stream."""

    MAX_BYTES = int(__import__("os").getenv("MAX_REQUEST_BODY_BYTES") or str(2 * 1024 * 1024))

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl:
            try:
                if int(cl) > self.MAX_BYTES:
                    return Response("Payload demasiado grande", status_code=413)
            except ValueError:
                return Response("Content-Length inválido", status_code=400)

        if request.method in ("POST", "PUT", "PATCH"):
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > self.MAX_BYTES:
                    return Response("Payload demasiado grande", status_code=413)
            payload = bytes(body)

            async def receive():
                return {"type": "http.request", "body": payload, "more_body": False}

            request = Request(request.scope, receive)

        return await call_next(request)
