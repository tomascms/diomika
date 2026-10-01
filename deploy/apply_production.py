#!/usr/bin/env python3
"""
Aplica SQL de produção (infra + catálogo) e seed demo opcional.

ESQUEMA UNIFICADO (ver backend-api/sql/RUNBOOK_unified_catalog_migration.md):
o catálogo passou de 13 famílias de tabelas para 3 tabelas partilhadas
(product_models/product_variants/product_model_colors). O sync automático
Pydantic→BD (core.schema_engine.bootstrap_database_schema) tratava cada
"tabela virtual" do catálogo (modelos_almofadas, almofada, ...) como uma
tabela física própria — sob o esquema novo isso tentaria criar tabelas com
esses nomes, que já não existem na BD real. Por isso este script deixou de
o chamar por omissão.

Uso (na raiz do repo):
  python deploy/apply_production.py                  # instruções + (opcional) seed demo
  python deploy/apply_production.py --seed-demo
  python deploy/apply_production.py --images-only
  python deploy/apply_production.py --legacy-schema-sync   # só tabelas operacionais (não-catálogo); ver aviso abaixo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-api"))

from core.env_loader import load_project_env  # noqa: E402

load_project_env()

RUNBOOK = ROOT / "backend-api" / "sql" / "RUNBOOK_unified_catalog_migration.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="SQL produção Supabase + seed demo")
    parser.add_argument("--interactive", action="store_true", help="Pedir password DB se necessário")
    parser.add_argument("--seed-demo", action="store_true", help="Correr deploy/seed_catalog_demo.py")
    parser.add_argument("--images-only", action="store_true", help="Só refrescar imagens demo [TESTE]")
    parser.add_argument(
        "--legacy-schema-sync",
        action="store_true",
        help=(
            "Corre o sync automático Pydantic→BD antigo. Só devia ainda ser preciso para as tabelas "
            "operacionais (pedidos_orcamento, encomendas_internas, contact_messages, idempotency_keys, "
            "outbox_events, saga_instances) — vai tentar (incorrectamente) criar tabelas de catálogo com "
            "nomes antigos (modelos_almofadas, ...). Não uses isto sem reveres core/schema_engine.py primeiro."
        ),
    )
    args = parser.parse_args()

    if args.images_only:
        import subprocess

        cmd = [sys.executable, str(ROOT / "deploy" / "seed_catalog_demo.py"), "--images-only"]
        return subprocess.call(cmd, cwd=ROOT)

    if args.legacy_schema_sync:
        from core.schema_engine import bootstrap_database_schema

        print("\n=== Schema sync + SQL infra (legado — ver aviso em --help) ===\n")
        bootstrap_database_schema()
        print("OK schema bootstrap")
    else:
        print(
            "\nEsquema do catálogo: aplica backend-api/sql/0001_unified_catalog_schema.sql e "
            "0002_migrate_catalog_data.sql manualmente, seguindo o runbook:\n"
            f"  {RUNBOOK}\n"
            "(--legacy-schema-sync corre o sync automático antigo, só recomendado para as tabelas "
            "operacionais — ver --help.)\n"
        )

    if args.seed_demo:
        import subprocess

        cmd = [sys.executable, str(ROOT / "deploy" / "seed_catalog_demo.py")]
        return subprocess.call(cmd, cwd=ROOT)

    print("\nOK.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
