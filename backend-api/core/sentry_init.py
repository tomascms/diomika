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
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
    )
    logger.info("Sentry activo (env=%s, traces=%.2f)", env, sample)
    return True
