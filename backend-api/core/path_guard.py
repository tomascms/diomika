"""Middleware de fronteira de segurança — aplica-se a TODAS as rotas, sem Depends.

Fecha gaps de “rota nova sem guard”: /admin e /system nunca ficam públicos
em produção final, mesmo se alguém esquecer Depends(admin_must_be_local).
"""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.config import get_settings
from core.local_only import peer_is_loopback

# Prefixos sempre sensíveis
_PRIVILEGED_PREFIXES = ("/admin", "/system", "/health/detail")

# Mutações públicas (podem ser bloqueadas em lockdown)
_PUBLIC_MUTATE_PREFIXES = ("/contacto", "/orcamentos")


def lockdown_active() -> bool:
    return (os.getenv("SECURITY_LOCKDOWN") or "").strip().lower() in ("1", "true", "yes")


class PrivilegedPathMiddleware(BaseHTTPMiddleware):
    """Fail-closed para caminhos privilegiados + lockdown global."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        settings = get_settings()

        if lockdown_active():
            # Health básico continua (load balancer / uptime)
            if path in ("/health", "/health/ready") and request.method == "GET":
                return await call_next(request)
            # Bloqueia mutações públicas e tudo privilegiado
            if path.startswith(_PRIVILEGED_PREFIXES) or any(
                path.startswith(p) for p in _PUBLIC_MUTATE_PREFIXES
            ):
                return JSONResponse(
                    status_code=503,
                    content={"detail": "SECURITY_LOCKDOWN activo — operações suspensas."},
                )

        if settings.is_production and not settings.is_beta:
            if any(path.startswith(p) for p in _PRIVILEGED_PREFIXES):
                if not peer_is_loopback(request):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "Admin/system só disponível em localhost na produção final."
                        },
                    )

        return await call_next(request)
