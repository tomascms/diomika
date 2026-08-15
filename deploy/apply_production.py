#!/usr/bin/env python3
"""
Aplica SQL de produção (schema sync + infra catálogo) e seed demo opcional.

Uso (na raiz do repo):
  python deploy/apply_production.py
  python deploy/apply_production.py --interactive
  python deploy/apply_production.py --skip-schema --seed-demo
  python deploy/apply_production.py --images-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-api"))

from core.env_loader import load_project_env  # noqa: E402

load_project_env()


def main() -> int:
    parser = argparse.ArgumentParser(description="SQL produção Supabase + seed demo")
    parser.add_argument("--interactive", action="store_true", help="Pedir password DB se necessário")
    parser.add_argument("--skip-schema", action="store_true", help="Não correr sync Pydantic → BD")
    parser.add_argument("--seed-demo", action="store_true", help="Correr deploy/seed_catalog_demo.py")
    parser.add_argument("--images-only", action="store_true", help="Só refrescar imagens demo [TESTE]")
    args = parser.parse_args()

    if args.images_only:
        import subprocess

        cmd = [sys.executable, str(ROOT / "deploy" / "seed_catalog_demo.py"), "--images-only"]
        return subprocess.call(cmd, cwd=ROOT)

    if not args.skip_schema:
        from core.schema_engine import bootstrap_database_schema

        print("\n=== Schema sync + SQL infra ===\n")
        bootstrap_database_schema()
        print("OK schema bootstrap")

    if args.seed_demo:
        import subprocess

        cmd = [sys.executable, str(ROOT / "deploy" / "seed_catalog_demo.py"), "--skip-schema"]
        return subprocess.call(cmd, cwd=ROOT)

    print("\nOK SQL produção (usa --seed-demo ou --images-only se precisares).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
