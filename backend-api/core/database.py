"""Cliente Supabase — TLS com certifi por defeito; verify=False nunca é auto-activado."""
from __future__ import annotations

import logging
import os
import ssl
import sys

import certifi
import httpx
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from core.env_loader import load_project_env

load_project_env()

logger = logging.getLogger("diomika-api")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

_env = (os.getenv("DIOMIKA_ENV") or "development").strip().lower()
_is_production = _env == "production"
_is_beta = (os.getenv("DIOMIKA_BETA") or "").strip().lower() in ("1", "true", "yes")
_ssl_flag = (os.getenv("DIOMIKA_SSL_INSECURE") or "").strip().lower() in ("1", "true", "yes")

# Nunca default por beta. Só flag explícita, e nunca em produção final.
_is_final_production = _is_production and not _is_beta
if _ssl_flag and _is_final_production:
    print(
        "ERRO: DIOMIKA_SSL_INSECURE=1 em producao final — abortar.\n"
        "  Remova DIOMIKA_SSL_INSECURE do .env (API usa certifi).",
        file=sys.stderr,
    )
    sys.exit(1)

_ssl_insecure = _ssl_flag and not _is_final_production

_http_limits = httpx.Limits(max_connections=80, max_keepalive_connections=25, keepalive_expiry=30.0)
_http_timeout = httpx.Timeout(12.0, connect=3.0)

if _ssl_insecure:
    print(
        "AVISO: DIOMIKA_SSL_INSECURE=1 — TLS desactivado (flag explícita; nunca auto).\n"
        "  Remova antes do domain day / VM producao.",
        file=sys.stderr,
    )
    _http = httpx.Client(verify=False, timeout=_http_timeout, limits=_http_limits)
else:
    _ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    _http = httpx.Client(verify=_ssl_ctx, timeout=_http_timeout, limits=_http_limits)

_options = SyncClientOptions(httpx_client=_http)
supabase: Client = create_client(url or "", key or "", options=_options)


def get_db() -> Client:
    return supabase
