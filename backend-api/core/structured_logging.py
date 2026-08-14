"""Logging estruturado (JSON) — activo em produção; Axiom se AXIOM_TOKEN."""
from __future__ import annotations

import json
import logging
import os
import threading
import urllib.request
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key in ("request_id", "path", "method", "status", "ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


_axiom_lock = threading.Lock()
_axiom_queue: list[dict[str, Any]] = []


class AxiomHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        token = (os.getenv("AXIOM_TOKEN") or "").strip()
        dataset = (os.getenv("AXIOM_DATASET") or "diomika").strip()
        if not token:
            return
        try:
            body = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
        except Exception:
            return
        with _axiom_lock:
            _axiom_queue.append(body)
            batch = list(_axiom_queue) if len(_axiom_queue) >= 5 else None
            if batch:
                _axiom_queue.clear()
        if not batch:
            return
        try:
            from core.ssrf_guard import assert_safe_outbound_url

            # EU org: edge ingest (https://eu-central-1.aws.edge.axiom.co/v1/ingest/{dataset})
            # US legacy: https://api.axiom.co/v1/datasets/{dataset}/ingest
            base = (os.getenv("AXIOM_API_URL") or "https://api.axiom.co").rstrip("/")
            if "edge.axiom.co" in base:
                url = f"{base}/v1/ingest/{dataset}"
            else:
                url = f"{base}/v1/datasets/{dataset}/ingest"
            assert_safe_outbound_url(url)
            req = urllib.request.Request(
                url,
                data=json.dumps(batch).encode("utf-8"),
                method="POST",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "DiomikaAxiom/1.0",
                },
            )
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:
            pass


def configure_structured_logging() -> None:
    root = logging.getLogger()
    fmt = (os.getenv("LOG_FORMAT") or "").strip().lower()
    if fmt == "json":
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    else:
        if not root.handlers:
            logging.basicConfig(level=logging.INFO)
    if (os.getenv("AXIOM_TOKEN") or "").strip():
        ax = AxiomHandler()
        ax.setLevel(logging.INFO)
        root.addHandler(ax)
