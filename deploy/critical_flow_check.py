#!/usr/bin/env python3
"""Alias — usa verify_production.py (entrypoint único)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call([sys.executable, str(ROOT / "deploy" / "verify_production.py"), *sys.argv[1:]]))
