from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-api"))
from models.catalog_registry import CATALOG_TYPES

lines = []
for _tipo, cfg in sorted(CATALOG_TYPES.items()):
    for tbl in (cfg["model_table"], cfg["product_table"], cfg.get("colors_table")):
        if not tbl:
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
        if tbl == cfg["model_table"]:
            lines.append(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_categoria ON {tbl} (id_categoria);")
        if tbl == cfg["product_table"]:
            lines += [
                f"CREATE INDEX IF NOT EXISTS idx_{tbl}_modelo ON {tbl} (id_modelo);",
                f"CREATE INDEX IF NOT EXISTS idx_{tbl}_ean ON {tbl} (ean);",
            ]
        if tbl == cfg.get("colors_table"):
            lines.append(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_modelo ON {tbl} (id_modelo);")
        lines.append("")

extra = (ROOT / "backend-api/sql/migration_almofada_dimensoes_modelo.sql").read_text(encoding="utf-8")
(ROOT / "deploy/_rls_compact.sql").write_text(extra + "\n\n" + "\n".join(lines), encoding="utf-8")
print("written", len("\n".join(lines)), "chars")
