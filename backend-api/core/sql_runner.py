"""Aplica ficheiros SQL à base Supabase (PostgreSQL directo ou Management API)."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from getpass import getpass
from pathlib import Path

from core.database_url import _supabase_project_ref, iter_database_urls

MGMT_API = "https://api.supabase.com/v1"


def split_sql_statements(sql: str) -> list[str]:
    """Divide SQL em statements, respeitando blocos $$ ... $$."""
    statements: list[str] = []
    buf: list[str] = []
    dollar_tag: str | None = None
    i = 0
    n = len(sql)

    while i < n:
        if dollar_tag is None and sql.startswith("--", i):
            end = sql.find("\n", i)
            if end == -1:
                break
            i = end + 1
            continue

        if dollar_tag is None:
            match = re.match(r"\$([A-Za-z0-9_]*)\$", sql[i:])
            if match:
                tag = match.group(0)
                buf.append(tag)
                i += len(tag)
                dollar_tag = tag
                continue

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(sql[i])
            i += 1
            continue

        ch = sql[i]
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _with_sslmode(url: str) -> str:
    if "sslmode=" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}sslmode=require"


def apply_via_postgres(sql: str, urls: list[str] | None = None) -> str:
    import psycopg2

    candidates = [_with_sslmode(u) for u in (urls or iter_database_urls())]
    if not candidates:
        raise RuntimeError("Sem URLs PostgreSQL — defina SUPABASE_DB_PASSWORD ou DATABASE_URL")

    statements = split_sql_statements(sql)
    last_error: Exception | None = None

    for url in candidates:
        host_hint = url.split("@")[-1].split("/")[0]
        conn = None
        try:
            conn = psycopg2.connect(url, connect_timeout=15)
            conn.autocommit = True
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
            return host_hint
        except Exception as exc:
            last_error = exc
        finally:
            if conn:
                conn.close()

    raise RuntimeError(f"PostgreSQL falhou: {last_error}")


def apply_via_management_api(sql: str) -> str:
    token = (os.getenv("SUPABASE_ACCESS_TOKEN") or "").strip()
    ref = _supabase_project_ref()
    if not token:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN em falta")
    if not ref:
        raise RuntimeError("SUPABASE_URL invalido — nao foi possivel obter project ref")

    url = f"{MGMT_API}/projects/{ref}/database/query"
    body = json.dumps({"query": sql}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Management API HTTP {exc.code}: {detail}") from exc

    return f"Management API ({ref})"


def apply_sql_file(path: Path, *, interactive: bool = False) -> str:
    """Aplica SQL. Tenta Management API, depois PostgreSQL, depois password interactiva."""
    if not path.is_file():
        raise FileNotFoundError(path)

    sql = path.read_text(encoding="utf-8")
    errors: list[str] = []

    if (os.getenv("SUPABASE_ACCESS_TOKEN") or "").strip():
        try:
            return apply_via_management_api(sql)
        except Exception as exc:
            errors.append(f"Management API: {exc}")

    if iter_database_urls():
        try:
            return apply_via_postgres(sql)
        except Exception as exc:
            errors.append(f"PostgreSQL: {exc}")

    if interactive:
        pwd = getpass("Password PostgreSQL Supabase (Settings > Database): ")
        if pwd.strip():
            os.environ["SUPABASE_DB_PASSWORD"] = pwd.strip()
            try:
                return apply_via_postgres(sql)
            except Exception as exc:
                errors.append(f"PostgreSQL (interactivo): {exc}")

    hint = (
        "Opcoes:\n"
        "  1. SUPABASE_ACCESS_TOKEN no .env (Dashboard > Account > Access Tokens)\n"
        "  2. SUPABASE_DB_PASSWORD correcto (Dashboard > Project Settings > Database)\n"
        "  3. python deploy/apply_production.py --interactive"
    )
    raise RuntimeError("\n".join(errors + [hint]))
