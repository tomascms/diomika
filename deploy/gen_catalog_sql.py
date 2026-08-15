#!/usr/bin/env python3
"""Regenera SQL de infra do catálogo (RLS, índices, triggers, FKs) a partir de CATALOG_TYPES."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-api"))

from core.catalog_deploy_sql import write_catalog_infra_sql  # noqa: E402


def main() -> int:
    path = write_catalog_infra_sql()
    print(f"OK {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
