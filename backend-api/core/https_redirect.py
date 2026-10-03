"""HTTPS redirect and protocol enforcement middleware.

Garantir que TODO o tráfego use HTTPS em produção.
"""
from __future__ import annotations

import logging
from fastapi import Request
from starlette.responses import RedirectResponse

logger = logging.getLogger("diomika-api")


class HTTPSRedirectMiddleware:
    """Redirect HTTP requests to HTTPS in production."""

    def __init__(self, app, enabled: bool = True, allowed_paths: list[str] | None = None):
        self.app = app
        self.enabled = enabled
        # Paths that should not redirect (e.g., health checks, ACME challenges)
        self.allowed_paths = allowed_paths or [
            "/.well-known/acme-challenge/",
            "/health",
            "/health/",
            "/health/ready",
        ]

    async def __call__(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        # Skip redirect for whitelisted paths
        for allowed in self.allowed_paths:
            if request.url.path.startswith(allowed):
                return await call_next(request)

        # Check if request is HTTP (not HTTPS)
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        if scheme == "http":
            # Redirect to HTTPS
            url = request.url.replace(scheme="https")
            logger.debug(f"Redirecting HTTP -> HTTPS: {request.url.path}")
            return RedirectResponse(url=url, status_code=301)

        return await call_next(request)


class StrictSecureMiddleware:
    """Enforce strict security policies (HTTPS, HSTS, etc)."""

    def __init__(self, app, is_production: bool = False):
        self.app = app
        self.is_production = is_production

    async def __call__(self, request: Request, call_next):
        response = await call_next(request)

        if self.is_production:
            # In production, ensure all responses have security headers
            scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
            if scheme != "https":
                logger.warning(f"Non-HTTPS request in production: {request.url}")

            # Add HSTS header
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

            # Enforce secure cookies
            if "set-cookie" in response.headers:
                cookies = response.headers.get_list("set-cookie")
                for cookie in cookies:
                    if "Secure" not in cookie and "secure" not in cookie.lower():
                        cookie += "; Secure"
                    if "HttpOnly" not in cookie:
                        cookie += "; HttpOnly"
                    if "SameSite" not in cookie:
                        cookie += "; SameSite=Strict"

        return response
