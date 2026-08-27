"""Sentry opcional — só activa com SENTRY_DSN."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("diomika-sentry")


def init_sentry() -> bool:
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("SENTRY_DSN definido mas sentry-sdk não instalado")
        return False

    env = (os.getenv("DIOMIKA_ENV") or "development").strip().lower()
    sample = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE") or ("0.05" if env == "production" else "0.0"))
    # Só ERROR+; WARNING IMAP/health não devem criar issues
    logging_integration = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        traces_sample_rate=max(0.0, min(1.0, sample)),
        send_default_pii=False,
        ignore_errors=[
            KeyboardInterrupt,
            SystemExit,
        ],
        before_send=_before_send,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            logging_integration,
        ],
    )
    logger.info("Sentry activo (env=%s, traces=%.2f)", env, sample)
    return True


def _transaction_name(event: dict) -> str:
    tx = event.get("transaction") or ""
    req = (event.get("request") or {}).get("url") or ""
    return f"{tx} {req}".lower()


def _before_send(event, hint):
    """Filtra ruído operacional que não é bug de código."""
    tx = _transaction_name(event)
    log_entry = event.get("logentry") or {}
    message = (log_entry.get("message") or event.get("message") or "").lower()
    exc_info = hint.get("exc_info") if hint else None
    exc_name = ""
    msg = ""
    status = None
    if exc_info and len(exc_info) >= 2:
        exc = exc_info[1]
        exc_name = type(exc).__name__
        msg = str(exc).lower()
        status = getattr(exc, "status_code", None)

    # Probes / health — 503 degraded não é bug
    if "/health" in tx or "health_ready" in tx or "health_check" in tx:
        return None
    if status == 503 and ("degraded" in msg or "database" in msg):
        return None

    # HTTP 4xx esperados (validação, auth, conflitos)
    if exc_name == "HTTPException" and status and 400 <= int(status) < 500:
        return None

    # Conflitos Postgres / PostgREST
    if "duplicate key" in msg or "23505" in msg or "já existe" in msg:
        return None
    if "pgrst200" in msg or "could not find a relationship" in msg:
        return None

    # IMAP / email transitório
    if "socket error" in msg or ("eof" in msg and ("imap" in msg or "socket" in msg or "fetch" in msg)):
        return None
    if "imap ligação perdida" in message:
        return None
    if "erro ao processar email" in message and (
        "socket" in message or "eof" in message or "fetch" in message or "broken pipe" in message
    ):
        return None

    # Boot / config transitória (já fail-closed com 503 no código actual)
    if "redis_url" in msg and ("obrigat" in msg or "required" in msg):
        return None

    if "duplicate key" in message or "já existe" in message:
        return None
    if "pgrst200" in message or "could not find a relationship" in message:
        return None

    return event
