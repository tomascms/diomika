"""Gera SQL de infra (RLS, índices, triggers) a partir de CATALOG_TYPES."""

from __future__ import annotations

from pathlib import Path

from models.catalog_registry import CATALOG_TYPES

GENERATED_PATH = Path(__file__).resolve().parents[2] / "deploy" / "generated_catalog_infra.sql"

SHARED_CATALOG_TABLES = frozenset(
    {
        "categories",
        "modelo_almofada_cores",
        "modelo_assento_cores",
    }
)


def generate_catalog_infra_sql() -> str:
    lines = [
        "-- Gerado automaticamente a partir de CATALOG_TYPES (schemas.py)",
        "-- Aplicado via ensure_deploy_sql / deploy/apply_production.py",
        "",
    ]

    trigger_tables: list[str] = []

    for tipo, cfg in sorted(CATALOG_TYPES.items()):
        mt = cfg["model_table"]
        pt = cfg["product_table"]
        lines.append(f"-- === {tipo} ({mt} + {pt}) ===")

        for tbl in (mt, pt):
            if tbl in SHARED_CATALOG_TABLES:
                continue
            trigger_tables.append(tbl)
            lines.extend(
                [
                    f"ALTER TABLE IF EXISTS {tbl} ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();",
                    f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;",
                    f'DROP POLICY IF EXISTS "{tbl}_public_read" ON {tbl};',
                    f'CREATE POLICY "{tbl}_public_read" ON {tbl} FOR SELECT TO anon USING (visibilidade = true);',
                    f'DROP POLICY IF EXISTS "{tbl}_deny_anon_insert" ON {tbl};',
                    f'CREATE POLICY "{tbl}_deny_anon_insert" ON {tbl} FOR INSERT TO anon WITH CHECK (false);',
                    f'DROP POLICY IF EXISTS "{tbl}_deny_anon_update" ON {tbl};',
                    f'CREATE POLICY "{tbl}_deny_anon_update" ON {tbl} FOR UPDATE TO anon USING (false) WITH CHECK (false);',
                    f'DROP POLICY IF EXISTS "{tbl}_deny_anon_delete" ON {tbl};',
                    f'CREATE POLICY "{tbl}_deny_anon_delete" ON {tbl} FOR DELETE TO anon USING (false);',
                ]
            )
            if tbl == mt:
                lines.append(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_categoria ON {tbl} (id_categoria);")

        ct = cfg.get("colors_table")
        if ct and ct not in SHARED_CATALOG_TABLES:
            trigger_tables.append(ct)
            lines.extend(
                [
                    f"ALTER TABLE IF EXISTS {ct} ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();",
                    f"ALTER TABLE {ct} ENABLE ROW LEVEL SECURITY;",
                    f'DROP POLICY IF EXISTS "{ct}_public_read" ON {ct};',
                    f'CREATE POLICY "{ct}_public_read" ON {ct} FOR SELECT TO anon USING (visibilidade = true);',
                    f"CREATE INDEX IF NOT EXISTS idx_{ct}_modelo ON {ct} (id_modelo);",
                ]
            )

        lines.extend(
            [
                f"CREATE INDEX IF NOT EXISTS idx_{pt}_modelo ON {pt} (id_modelo);",
                f"CREATE INDEX IF NOT EXISTS idx_{pt}_ean ON {pt} (ean);",
                "",
            ]
        )

    if trigger_tables:
        unique_tables = sorted(set(trigger_tables))
        tbl_array = ", ".join(f"'{t}'" for t in unique_tables)
        lines.extend(
            [
                "CREATE OR REPLACE FUNCTION diomika_set_updated_at()",
                "RETURNS trigger AS $$",
                "BEGIN",
                "  NEW.updated_at = now();",
                "  RETURN NEW;",
                "END;",
                "$$ LANGUAGE plpgsql SET search_path = '';",
                "",
                "DO $$",
                "DECLARE tbl text;",
                "BEGIN",
                f"  FOREACH tbl IN ARRAY ARRAY[{tbl_array}]",
                "  LOOP",
                "    EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_updated_at ON %I', tbl, tbl);",
                "    EXECUTE format(",
                "      'CREATE TRIGGER trg_%I_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION diomika_set_updated_at()',",
                "      tbl, tbl",
                "    );",
                "  END LOOP;",
                "END $$;",
            ]
        )

    return "\n".join(lines) + "\n"


def write_catalog_infra_sql(path: Path | None = None) -> Path:
    target = path or GENERATED_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate_catalog_infra_sql(), encoding="utf-8")
    return target
