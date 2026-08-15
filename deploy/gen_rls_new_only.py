from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-api"))
from models.catalog_registry import CATALOG_TYPES

OLD = {
    "modelos_almofadas",
    "almofada",
    "modelo_almofada_cores",
    "modelos_assentos",
    "assento",
    "modelo_assento_cores",
}
lines = []
for _tipo, cfg in sorted(CATALOG_TYPES.items()):
    for tbl in (cfg["model_table"], cfg["product_table"], cfg.get("colors_table")):
        if not tbl or tbl in OLD:
            continue
        lines += [
            f"ALTER TABLE IF EXISTS {tbl} ENABLE ROW LEVEL SECURITY;",
            f'DROP POLICY IF EXISTS "{tbl}_public_read" ON {tbl};',
            f'CREATE POLICY "{tbl}_public_read" ON {tbl} FOR SELECT TO anon USING (visibilidade = true);',
            f'DROP POLICY IF EXISTS "{tbl}_deny_anon_insert" ON {tbl};',
            f'CREATE POLICY "{tbl}_deny_anon_insert" ON {tbl} FOR INSERT TO anon WITH CHECK (false);',
            f'DROP POLICY IF EXISTS "{tbl}_deny_anon_update" ON {tbl};',
            f'CREATE POLICY "{tbl}_deny_anon_update" ON {tbl} FOR UPDATE TO anon USING (false) WITH CHECK (false);',
            f'DROP POLICY IF EXISTS "{tbl}_deny_anon_delete" ON {tbl};',
            f'CREATE POLICY "{tbl}_deny_anon_delete" ON {tbl} FOR DELETE TO anon USING (false);',
            "",
        ]
(ROOT / "deploy/_rls_new_only.sql").write_text("\n".join(lines), encoding="utf-8")
print(len(lines))
