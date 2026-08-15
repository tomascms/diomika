#!/usr/bin/env python3
"""Alias — regenera deploy/generated_catalog_infra.sql (RLS + FKs)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call([sys.executable, str(ROOT / "deploy" / "gen_catalog_sql.py")]))
