"""Health check endpoints for readiness and liveness probes."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from core.database import get_db

logger = logging.getLogger("diomika-api")

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("/live")
async def liveness() -> dict:
    """Liveness probe — is the service running?

    Used by Kubernetes to determine if container should be restarted.
    Returns 200 if service is alive, 503 if shutting down.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "diomika-backend",
    }


@router.get("/ready")
async def readiness(db=Depends(get_db)) -> dict:
    """Readiness probe — is the service ready for traffic?

    Used by Kubernetes to determine if traffic should be sent.
    Checks: database connection, critical services.
    Returns 200 if ready, 503 if not.
    """
    checks = {
        "database": False,
        "cache": False,
    }

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
        logger.debug("Health check: database OK")
    except Exception as e:
        logger.warning(f"Health check: database FAILED - {e}")
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Check cache (Redis) — optional, don't fail if unavailable
    try:
        # Will implement after cache layer
        checks["cache"] = True
    except Exception as e:
        logger.warning(f"Health check: cache FAILED - {e}")
        checks["cache"] = False

    ready = all(checks.values())
    status_code = 200 if ready else 503

    return {
        "status": "ready" if ready else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "service": "diomika-backend",
    }


@router.get("")
async def health(db=Depends(get_db)) -> dict:
    """General health endpoint — combines liveness + readiness.

    Simpler endpoint for basic health monitoring.
    """
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "diomika-backend",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")
