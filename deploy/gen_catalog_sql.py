#!/usr/bin/env python3
"""
OBSOLETO — esquema de catálogo unificado.

Isto gerava SQL de infra (RLS, índices, triggers, FKs) por-família a partir
de CATALOG_TYPES, quando havia 13 famílias de tabelas de catálogo. Desde o
refactor para 3 tabelas partilhadas (product_models/product_variants/
product_model_colors), essa SQL é escrita à mão em
backend-api/sql/0001_unified_catalog_schema.sql — não há mais nada para
gerar por categoria. Usa --force só se souberes que ainda precisas da
infra SQL antiga (ex.: tabelas por-família que ainda não foram migradas).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-api"))


def main() -> int:
    if "--force" not in sys.argv:
        print(
            "\nOBSOLETO: este script gera SQL de infra para as 13 famílias de tabelas "
            "antigas. O catálogo já usa 3 tabelas partilhadas — ver "
            "backend-api/sql/0001_unified_catalog_schema.sql e "
            "backend-api/sql/RUNBOOK_unified_catalog_migration.md.\n"
            "Usa --force se tens mesmo a certeza que precisas da infra antiga.\n"
        )
        return 1

    sys.path.insert(0, str(ROOT / "backend-api"))
    from core.catalog_deploy_sql import write_catalog_infra_sql

    path = write_catalog_infra_sql()
    print(f"OK {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
