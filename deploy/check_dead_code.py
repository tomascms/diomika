#!/usr/bin/env python3
"""Scan leve de código morto (Python). Exit 0 sempre em CI soft; --strict falha.

Uso:
  python deploy/check_dead_code.py
  python deploy/check_dead_code.py --strict
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        import vulture  # noqa: F401
    except ImportError:
        print("vulture não instalado — pip install vulture (opcional)")
        return 0 if not args.strict else 1

    cmd = [
        sys.executable,
        "-m",
        "vulture",
        "backend-api",
        "--min-confidence",
        "80",
        "--exclude",
        "*test*,*__pycache__*",
    ]
    print(">>>", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0 and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
