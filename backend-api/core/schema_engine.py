"""
Motor de schema: Pydantic TABLE_MAP → SQL PostgreSQL → diff → migração.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, get_args, get_origin

from models.schemas import TABLE_MAP, CATEGORY_DEFINITIONS
from models.ui_schema import build_schema_snapshot, field_label, is_field_required, snapshot_hash
from core.env_loader import get_database_url

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / ".schema_snapshot.json"
SQL_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "sql"
SQL_PATH = SQL_OUTPUT_DIR / "create_messages_tables.sql"
DB_CONNECT_TIMEOUT = int(os.getenv("SUPABASE_DB_CONNECT_TIMEOUT", "5"))


def _connect_pg():
    import psycopg2

    database_url = get_database_url()
    if not database_url:
        return None
    return psycopg2.connect(database_url, connect_timeout=DB_CONNECT_TIMEOUT)


def _db_reachable() -> bool:
    conn = None
    try:
        conn = _connect_pg()
        return conn is not None
    except Exception:
        return False
    finally:
        if conn:
            conn.close()


def _pytype_to_sql(field_name: str, annotation) -> str:
    if field_name == "id":
        return "uuid"

    origin = get_origin(annotation)
    if origin is list or origin is dict:
        return "jsonb"

    if origin is not None:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if args:
            annotation = args[0]
            origin = get_origin(annotation)

    name = getattr(annotation, "__name__", str(annotation))
    mapping = {
        "str": "text",
        "int": "integer",
        "bool": "boolean",
        "UUID": "uuid",
        "float": "double precision",
    }
    return mapping.get(name, "text")


def generate_create_table_sql(table_name: str, schema_class) -> str:
    if table_name == "idempotency_keys":
        return """
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key text PRIMARY KEY,
    operation text NOT NULL,
    response jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now(),
    expires_at timestamptz
);""".strip()

    lines = []
    for fname, fdef in schema_class.model_fields.items():
        sql_type = _pytype_to_sql(fname, fdef.annotation)
        if fname == "id":
            lines.append(f"{fname} {sql_type} PRIMARY KEY DEFAULT gen_random_uuid()")
        else:
            nullable = "" if is_field_required(fdef) else ""
            default = ""
            if fdef.default is not None and not callable(fdef.default):
                if sql_type == "boolean":
                    default = f" DEFAULT {str(fdef.default).lower()}"
                elif sql_type == "text" and isinstance(fdef.default, str):
                    default = f" DEFAULT '{fdef.default}'"
            lines.append(f"{fname} {sql_type}{nullable}{default}")

    if "created_at" not in schema_class.model_fields:
        lines.append("created_at timestamptz DEFAULT now()")
    if "updated_at" not in schema_class.model_fields and table_name == "contact_messages":
        lines.append("updated_at timestamptz DEFAULT now()")

    body = ",\n    ".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n    {body}\n);"


def generate_add_column_sql(table_name: str, col_name: str, schema_class) -> str:
    fdef = schema_class.model_fields[col_name]
    sql_type = _pytype_to_sql(col_name, fdef.annotation)
    default = ""
    if col_name == "tipo":
        default = " DEFAULT 'decorativa'"
    return f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_name} {sql_type}{default};"


def load_snapshot() -> dict:
    if SNAPSHOT_PATH.exists():
        try:
            return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _supabase_tables_ready(supabase) -> bool:
    """True se todas as tabelas do TABLE_MAP existem na Supabase."""
    for table_name in TABLE_MAP:
        try:
            supabase.table(table_name).select("id").limit(1).execute()
        except Exception:
            return False
    return True


def save_snapshot(snapshot: dict) -> None:
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")


def diff_snapshots(old: dict, new: dict) -> tuple[list[str], dict[str, list[str]]]:
    new_tables = [t for t in new if t not in old]
    added_columns: dict[str, list[str]] = {}

    for table, info in new.items():
        old_cols = set(old.get(table, {}).get("columns", {}).keys())
        new_cols = set(info.get("columns", {}).keys())
        diff_cols = sorted(new_cols - old_cols)
        if diff_cols and table not in new_tables:
            added_columns[table] = diff_cols

    return new_tables, added_columns


@dataclass
class SyncReport:
    created_tables: List[str] = field(default_factory=list)
    added_columns: Dict[str, List[str]] = field(default_factory=dict)
    sql_executed: List[str] = field(default_factory=list)
    sql_pending: List[str] = field(default_factory=list)
    seeded_categories: List[str] = field(default_factory=list)
    new_field_warnings: List[dict] = field(default_factory=list)
    incomplete_records: Dict[str, List[dict]] = field(default_factory=dict)
    schema_hash: str = ""
    applied: bool = False
    message: str = ""


def _execute_sql_statements(statements: List[str]) -> tuple[List[str], List[str]]:
    if not get_database_url():
        return [], statements

    executed = []
    conn = None
    try:
        conn = _connect_pg()
        if not conn:
            return [], statements
        conn.autocommit = True
        with conn.cursor() as cur:
            for sql in statements:
                cur.execute(sql)
                executed.append(sql)
        return executed, []
    except Exception as e:
        raise RuntimeError(f"Erro ao aplicar SQL: {e}") from e
    finally:
        if conn:
            conn.close()


def _introspect_columns(table_name: str) -> set[str]:
    conn = None
    try:
        conn = _connect_pg()
        if not conn:
            return set()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (table_name,),
            )
            return {row[0] for row in cur.fetchall()}
    except Exception:
        return set()
    finally:
        if conn:
            conn.close()


MESSAGING_SQL = """
CREATE TABLE IF NOT EXISTS message_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id uuid REFERENCES contact_messages(id) ON DELETE CASCADE,
    sender_email text,
    body text,
    created_at timestamptz DEFAULT now()
);
"""


def build_migration_sql(new_tables: list[str], added_columns: dict[str, list[str]]) -> list[str]:
    statements = []
    for table in new_tables:
        schema = TABLE_MAP[table]["schema"]
        statements.append(generate_create_table_sql(table, schema))
        if table == "contact_messages":
            statements.append(MESSAGING_SQL.strip())

    for table, columns in added_columns.items():
        schema = TABLE_MAP[table]["schema"]
        for col in columns:
            if col == "id":
                continue
            statements.append(generate_add_column_sql(table, col, schema))

    return statements


def _seed_categories(supabase) -> list[str]:
    """Não criar categorias por defeito; apenas devolve uma lista vazia."""
    return []


def find_incomplete_records(supabase, table_map: dict = TABLE_MAP) -> dict[str, list[dict]]:
    incomplete: dict[str, list[dict]] = {}
    for table_name, info in table_map.items():
        if info.get("ui_mode") == "conversation":
            continue
        schema = info["schema"]
        try:
            rows = supabase.table(table_name).select("*").execute().data or []
        except Exception:
            continue

        bad = []
        for row in rows:
            from models.ui_schema import record_missing_fields

            missing = record_missing_fields(row, schema, info)
            if missing:
                bad.append({"id": row.get("id"), "missing": missing, "label": get_list_display_safe(row, info)})
        if bad:
            incomplete[table_name] = bad
    return incomplete


def get_list_display_safe(item, table_config):
    from models.ui_schema import get_list_display

    return get_list_display(item, table_config)


def sync_schema(supabase=None, apply: bool = True, dry_run: bool = False) -> SyncReport:
    report = SyncReport()
    old_snapshot = load_snapshot()
    new_snapshot = build_schema_snapshot(TABLE_MAP)
    report.schema_hash = snapshot_hash(new_snapshot)

    if not old_snapshot and supabase and _supabase_tables_ready(supabase):
        save_snapshot(new_snapshot)
        old_snapshot = new_snapshot

    new_tables, added_columns = diff_snapshots(old_snapshot, new_snapshot)

    # Introspecção directa à BD (só se PostgreSQL responder em poucos segundos)
    if get_database_url() and _db_reachable():
        for table_name in list(TABLE_MAP.keys()):
            db_cols = _introspect_columns(table_name)
            if not db_cols:
                if table_name not in new_tables:
                    new_tables.append(table_name)
            else:
                schema_cols = set(TABLE_MAP[table_name]["schema"].model_fields.keys())
                pk_skip = {"id", "key"}
                missing_in_db = sorted(schema_cols - db_cols - pk_skip)
                if missing_in_db:
                    added_columns[table_name] = sorted(
                        set(added_columns.get(table_name, []) + missing_in_db)
                    )
    elif get_database_url():
        report.message = (
            "Ligação directa à BD indisponível (timeout) — schema via Supabase API. "
            "Migrações SQL: Supabase SQL Editor ou quando a rede permitir."
        )

    report.created_tables = new_tables
    report.added_columns = added_columns

    statements = build_migration_sql(new_tables, added_columns)

    # Gerar ficheiros SQL
    SQL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for table_name, info in TABLE_MAP.items():
        sql = generate_create_table_sql(table_name, info["schema"])
        (SQL_OUTPUT_DIR / f"generated_{table_name}.sql").write_text(sql, encoding="utf-8")

    if dry_run:
        report.sql_pending = statements
        report.message = "Dry-run: SQL gerado mas não aplicado."
        return report

    if apply and statements:
        try:
            executed, pending = _execute_sql_statements(statements)
            report.sql_executed = executed
            report.sql_pending = pending
            report.applied = bool(executed)
        except RuntimeError as e:
            report.sql_pending = statements
            report.message = str(e)
    elif statements:
        report.sql_pending = statements

    # Avisos de novos campos
    for table, cols in added_columns.items():
        schema = TABLE_MAP[table]["schema"]
        for col in cols:
            if col in ("created_at", "updated_at"):
                continue
            fdef = schema.model_fields.get(col)
            if not fdef:
                continue
            warning = {
                "table": table,
                "table_label": TABLE_MAP[table].get("label", table),
                "field": col,
                "label": field_label(col, fdef),
                "required": is_field_required(fdef),
            }
            report.new_field_warnings.append(warning)

    if supabase:
        report.incomplete_records = find_incomplete_records(supabase)

    if supabase and apply:
        try:
            report.seeded_categories = _seed_categories(supabase)
        except Exception:
            report.seeded_categories = []

    if not report.message:
        if report.applied:
            report.message = "Schema sincronizado com sucesso."
        elif report.sql_pending:
            report.message = (
                "SQL gerado. Defina SUPABASE_DB_PASSWORD (ou DATABASE_URL) no .env para aplicar automaticamente, "
                "ou execute o SQL no Supabase SQL Editor."
            )
        else:
            report.message = "Schema já está atualizado."

    if apply and (report.applied or not statements):
        save_snapshot(new_snapshot)

    return report


def ensure_deploy_sql(log=None) -> bool:
    """Aplica deploy SQL (base + infra gerada de CATALOG_TYPES) se houver credenciais."""
    from paths import PROJECT_ROOT
    from core.catalog_deploy_sql import write_catalog_infra_sql
    from core.sql_runner import apply_sql_file

    sql_path = PROJECT_ROOT / "deploy" / "supabase_pre_deploy.sql"
    if not sql_path.is_file():
        return False
    try:
        write_catalog_infra_sql()
        via = apply_sql_file(sql_path, interactive=False)
        if log:
            log.info("SQL de deploy aplicado via %s", via)
        catalog_sql = PROJECT_ROOT / "deploy" / "generated_catalog_infra.sql"
        if catalog_sql.is_file():
            via2 = apply_sql_file(catalog_sql, interactive=False)
            if log:
                log.info("SQL catalogo (CATALOG_TYPES) aplicado via %s", via2)
        return True
    except Exception as exc:
        if log:
            log.warning("SQL de deploy nao aplicado: %s", exc)
        return False


def bootstrap_database_schema(log=None) -> None:
    """Sync Pydantic → BD + SQL infra (melhor esforço no arranque)."""
    try:
        from core.database import get_db

        ensure_deploy_sql(log)
        sync_schema(supabase=get_db(), apply=True, dry_run=False)
    except Exception as exc:
        if log:
            log.warning("Bootstrap schema: %s", exc)
