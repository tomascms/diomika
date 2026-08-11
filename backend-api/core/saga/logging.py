"""Persistência de estado de sagas."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.database import get_db

logger = logging.getLogger("diomika-saga")


def saga_log(saga_id: str, saga_type: str, step: str, status: str, context: dict | None = None) -> None:
    try:
        get_db().table("saga_instances").upsert(
            {
                "id": saga_id,
                "saga_type": saga_type,
                "current_step": step,
                "status": status,
                "context": context or {},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception as exc:
        logger.debug("saga_instances indisponível: %s", exc)
