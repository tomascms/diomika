"""Prometheus metrics endpoint."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from core.metrics import registry

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
)


@router.get("", response_class=None)
async def metrics():
    """Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format.
    Accessible at /metrics for scraping by Prometheus.
    """
    return Response(
        generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )
