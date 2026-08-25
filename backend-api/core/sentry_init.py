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
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("SENTRY_DSN definido mas sentry-sdk não instalado")
        return False

    env = (os.getenv("DIOMIKA_ENV") or "development").strip().lower()
    sample = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE") or ("0.05" if env == "production" else "0.0"))
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
        ],
    )
    logger.info("Sentry activo (env=%s, traces=%.2f)", env, sample)
    return True


def _before_send(event, hint):
    """Filtra ruído operacional que não é bug de código."""
    exc_info = hint.get("exc_info") if hint else None
    if exc_info and len(exc_info) >= 2:
        exc = exc_info[1]
        name = type(exc).__name__
        msg = str(exc).lower()
        # Conflitos de dados / 4xx esperados
        if name == "HTTPException":
            status = getattr(exc, "status_code", None)
            if status and 400 <= int(status) < 500:
                return None
        if "duplicate key" in msg or "23505" in msg:
            return None
        if "socket error" in msg or ("eof" in msg and ("imap" in msg or "socket" in msg)):
            return None
    log_entry = event.get("logentry") or {}
    message = (log_entry.get("message") or event.get("message") or "").lower()
    if "imap ligação perdida" in message:
        return None
    if "duplicate key" in message or "já existe" in message:
        return None
    return event


# Keep module load side-effects none; init_sentry calls _before_send by name above.