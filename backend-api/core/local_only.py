"""Garante que rotas admin/system não ficam na API pública de produção final."""
from __future__ import annotations

from fastapi import HTTPException, Request

from core.config import get_settings

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def peer_is_loopback(request: Request) -> bool:
    """IP do peer TCP — não usar X-Forwarded-For (fácil de forjar)."""
    if request.client and request.client.host:
        peer = request.client.host.strip().lower()
        return peer in _LOOPBACK or peer.startswith("127.")
    return False


def admin_must_be_local(request: Request) -> None:
    """Em produção final (sem beta), /admin e /system só via loopback.

    Sem escape remoto: ADMIN_ALLOW_REMOTE foi removido.
    Dev e beta (tunnel local) continuam a permitir.
    Middleware PrivilegedPathMiddleware reforça o mesmo em todas as rotas.
    """
    settings = get_settings()
    if not settings.is_production or settings.is_beta:
        return
    if peer_is_loopback(request):
        return
    raise HTTPException(
        status_code=403,
        detail="Admin/system só disponível em localhost na produção final.",
    )
