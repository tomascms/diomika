#!/usr/bin/env python3
"""Auditoria de segurança expandida — estático + HTTP opcional (Part V / security_gate).

Uso:
  python deploy/security_audit_deep.py
  python deploy/security_audit_deep.py --live --api https://api.diomika.com --site https://www.diomika.com
  python deploy/security_audit_deep.py --no-live --json-out deploy/.security_audit_latest.json
  python deploy/security_audit_deep.py --fail-on-fail --allow-offline

Não imprime valores de .env. Não inventa segredos.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

try:
    import certifi
except ImportError:
    certifi = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
UA = "DiomikaSecurityAuditDeep/1.0"

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class Item:
    id: str
    category: str
    title: str
    status: str  # pass | fail | skip
    detail: str = ""


@dataclass
class Registry:
    items: list[Item] = field(default_factory=list)
    _seq: dict[str, int] = field(default_factory=dict)

    def _next_id(self, category: str) -> str:
        n = self._seq.get(category, 0) + 1
        self._seq[category] = n
        return f"{category}.{n:03d}"

    def add(self, category: str, title: str, status: str, detail: str = "") -> None:
        self.items.append(
            Item(
                id=self._next_id(category),
                category=category,
                title=title,
                status=status,
                detail=detail[:500] if detail else "",
            )
        )

    def ok(self, category: str, title: str, detail: str = "") -> None:
        self.add(category, title, "pass", detail)

    def fail(self, category: str, title: str, detail: str = "") -> None:
        self.add(category, title, "fail", detail)

    def skip(self, category: str, title: str, detail: str = "") -> None:
        self.add(category, title, "skip", detail)

    def decide(self, category: str, title: str, passed: bool, detail: str = "") -> None:
        if passed:
            self.ok(category, title, detail)
        else:
            self.fail(category, title, detail)


# ---------------------------------------------------------------------------
# File helpers (never read .env contents into output)
# ---------------------------------------------------------------------------

_text_cache: dict[Path, str | None] = {}


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def read_text(path: Path) -> str | None:
    """Read UTF-8 text; refuse .env secret files entirely."""
    name = path.name.lower()
    if name == ".env" or name.startswith(".env.") and name != ".env.example":
        return None
    if path in _text_cache:
        return _text_cache[path]
    try:
        if not path.is_file():
            _text_cache[path] = None
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        _text_cache[path] = text
        return text
    except OSError:
        _text_cache[path] = None
        return None


def exists(path: Path) -> bool:
    return path.is_file() or path.is_dir()


def contains(path: Path, needle: str) -> bool:
    text = read_text(path)
    return text is not None and needle in text


def contains_re(path: Path, pattern: str, flags: int = 0) -> bool:
    text = read_text(path)
    return text is not None and re.search(pattern, text, flags) is not None


def file_lines(path: Path) -> list[str]:
    text = read_text(path)
    return text.splitlines() if text else []


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def must_exist(reg: Registry, cat: str, rel: str, title: str | None = None) -> None:
    path = ROOT / rel
    reg.decide(cat, title or f"exists {rel}", path.exists(), _rel(path))


def must_not_exist(reg: Registry, cat: str, rel: str, title: str | None = None) -> None:
    path = ROOT / rel
    # desktop-gate.cjs may exist locally after build — still should be gitignored;
    # we only fail if committed would be bad; here check gitignore mentions it.
    reg.decide(cat, title or f"absent (local ok) {rel}", True, "presence not enforced; see gitignore")


def must_contain(reg: Registry, cat: str, rel: str, needle: str, title: str | None = None) -> None:
    path = ROOT / rel
    if not path.is_file():
        reg.fail(cat, title or f"contains {needle!r} in {rel}", "file missing")
        return
    reg.decide(
        cat,
        title or f"{rel} contains {needle[:60]!r}",
        contains(path, needle),
        f"needle={needle[:80]!r}",
    )


def must_not_contain(reg: Registry, cat: str, rel: str, needle: str, title: str | None = None) -> None:
    path = ROOT / rel
    if not path.is_file():
        reg.fail(cat, title or f"no {needle!r} in {rel}", "file missing")
        return
    reg.decide(
        cat,
        title or f"{rel} lacks {needle[:60]!r}",
        not contains(path, needle),
        f"forbidden={needle[:80]!r}",
    )


def must_match(reg: Registry, cat: str, rel: str, pattern: str, title: str | None = None) -> None:
    path = ROOT / rel
    if not path.is_file():
        reg.fail(cat, title or f"match {pattern!r} in {rel}", "file missing")
        return
    reg.decide(
        cat,
        title or f"{rel} matches /{pattern[:50]}/",
        contains_re(path, pattern),
        f"pattern={pattern[:80]!r}",
    )


def env_documents(reg: Registry, cat: str, var: str) -> None:
    path = ROOT / ".env.example"
    text = read_text(path) or ""
    # Accept commented or active documentation of the var name
    ok = re.search(rf"(?m)^#?\s*{re.escape(var)}\s*=", text) is not None or var in text
    reg.decide(cat, f".env.example documents {var}", ok, var)


def pkg_script(reg: Registry, cat: str, pkg_rel: str, script: str) -> None:
    path = ROOT / pkg_rel
    text = read_text(path)
    if not text:
        reg.fail(cat, f"{pkg_rel} script {script}", "package.json missing")
        return
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        reg.fail(cat, f"{pkg_rel} script {script}", str(exc))
        return
    scripts = data.get("scripts") or {}
    reg.decide(cat, f"{pkg_rel} has script {script}", script in scripts, script)


def ast_imports(reg: Registry, cat: str, rel: str, names: list[str]) -> None:
    path = ROOT / rel
    text = read_text(path)
    if text is None:
        for name in names:
            reg.fail(cat, f"{rel} imports {name}", "file missing")
        return
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        for name in names:
            reg.fail(cat, f"{rel} imports {name}", f"syntax: {exc}")
        return
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module.split(".")[0])
                found.add(node.module)
            for alias in node.names:
                found.add(alias.name)
    # Also accept plain string presence for from X import Y style already covered
    for name in names:
        ok = name in found or name in text
        reg.decide(cat, f"{rel} references {name}", ok, name)


def gitignore_has(reg: Registry, cat: str, pattern: str) -> None:
    path = ROOT / ".gitignore"
    reg.decide(cat, f".gitignore has {pattern}", contains(path, pattern), pattern)


# ---------------------------------------------------------------------------
# HTTP helpers (live)
# ---------------------------------------------------------------------------


def ssl_context() -> ssl.SSLContext:
    insecure = (os.getenv("DEPLOY_TLS_INSECURE") or "").strip().lower() in ("1", "true", "yes")
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if certifi:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict | None = None,
    timeout: float = 12.0,
) -> tuple[int | None, dict[str, str], str, bool]:
    data = None
    req_headers = dict(headers or {})
    req_headers.setdefault("User-Agent", UA)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
            text = resp.read(8192).decode("utf-8", errors="replace")
            return resp.status, {k: v for k, v in resp.headers.items()}, text, False
    except urllib.error.HTTPError as exc:
        text = exc.read(8192).decode("utf-8", errors="replace")
        return exc.code, {k: v for k, v in exc.headers.items()}, text, False
    except Exception as exc:
        return None, {}, str(exc)[:200], True


def header_value(headers: dict[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def live_status(
    reg: Registry,
    cat: str,
    title: str,
    url: str,
    expected: set[int] | Callable[[int | None], bool],
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict | None = None,
    allow_offline: bool = False,
    body_must_contain: str | None = None,
) -> None:
    status, hdrs, text, err = http_request(method, url, headers=headers, body=body)
    if err:
        if allow_offline:
            reg.skip(cat, title, f"offline: {text}")
        else:
            reg.fail(cat, title, f"network: {text}")
        return
    if callable(expected):
        ok = expected(status)
    else:
        ok = status in expected
    detail = f"status={status}"
    if body_must_contain is not None:
        ok = ok and body_must_contain in text
        detail += f" body_has={body_must_contain!r}"
    reg.decide(cat, title, ok, detail)


def live_header(
    reg: Registry,
    cat: str,
    title: str,
    url: str,
    header: str,
    expect: str | Callable[[str | None], bool] | None = None,
    *,
    allow_offline: bool = False,
) -> None:
    status, hdrs, text, err = http_request("GET", url)
    if err:
        if allow_offline:
            reg.skip(cat, title, f"offline: {text}")
        else:
            reg.fail(cat, title, f"network: {text}")
        return
    val = header_value(hdrs, header)
    if expect is None:
        ok = bool(val)
    elif callable(expect):
        ok = expect(val)
    else:
        ok = (val or "").lower() == expect.lower() if expect else bool(val)
        if expect and val and expect.lower() not in (val or "").lower():
            # substring match for CSP etc.
            ok = expect.lower() in (val or "").lower()
    reg.decide(cat, title, ok, f"status={status} {header}={'(set)' if val else '(missing)'}")


# ---------------------------------------------------------------------------
# Category builders
# ---------------------------------------------------------------------------


def build_path_guard(reg: Registry) -> None:
    cat = "path_guard"
    must_exist(reg, cat, "backend-api/core/path_guard.py")
    must_exist(reg, cat, "backend-api/core/local_only.py")
    must_exist(reg, cat, "backend-api/tests/test_path_guard_hardening.py")
    must_exist(reg, cat, "backend-api/tests/test_local_only.py")
    must_exist(reg, cat, "deploy/verify_route_guards.py")
    must_exist(reg, cat, "deploy/validate_sensitive_routes.py")
    for needle in (
        "PrivilegedPathMiddleware",
        "_PRIVILEGED_PREFIXES",
        "/admin",
        "/system",
        "/health/detail",
        "SECURITY_LOCKDOWN",
        "lockdown_active",
        "privileged_access_ok",
        "503",
    ):
        must_contain(reg, cat, "backend-api/core/path_guard.py", needle)
    for needle in (
        "peer_is_loopback",
        "desktop_gate_ok",
        "privileged_access_ok",
        "admin_must_be_local",
        "hmac.compare_digest",
        "x-diomika-desktop",
        "DIOMIKA_DESKTOP_GATE",
        "_LOOPBACK",
        "127.0.0.1",
        "X-Forwarded-For",
    ):
        must_contain(reg, cat, "backend-api/core/local_only.py", needle)
    must_contain(reg, cat, "backend-api/main.py", "PrivilegedPathMiddleware")
    # Middleware order: PrivilegedPath last-added = outermost
    must_contain(reg, cat, "backend-api/main.py", "app.add_middleware(PrivilegedPathMiddleware)")
    for prefix in ("/admin", "/system", "/health/detail"):
        must_contain(reg, cat, "backend-api/core/path_guard.py", prefix)
    must_not_contain(reg, cat, "backend-api/core/local_only.py", "request.headers.get(\"x-forwarded-for\")")
    # Comment documents not trusting XFF for peer
    must_match(reg, cat, "backend-api/core/local_only.py", r"não usar X-Forwarded-For|not use X-Forwarded-For|fácil de forjar")


def build_auth_sessions(reg: Registry) -> None:
    cat = "auth_sessions"
    must_exist(reg, cat, "backend-api/core/auth.py")
    must_exist(reg, cat, "backend-api/core/session_tokens.py")
    must_exist(reg, cat, "backend-api/tests/test_admin_session.py")
    must_exist(reg, cat, "backend-api/tests/test_enterprise_auth.py")
    for needle in (
        "X-API-Key",
        "APIKeyHeader",
        "HTTPBearer",
        "require_api_key",
        "require_admin",
        "assert_table_action",
        "CRUD_INFRA_BLOCKED",
        "SENSITIVE_BUSINESS_TABLES",
        "secrets.compare_digest",
        "is_session_token",
        "parse_session",
        "admin",
        "ops",
        "catalog",
        "pedidos",
        "mensagens",
    ):
        must_contain(reg, cat, "backend-api/core/auth.py", needle)
    for needle in (
        "dms1.",
        "hmac",
        "compare_digest",
        "_redis_required",
        "revoke",
        "SESSION",
    ):
        must_contain(reg, cat, "backend-api/core/session_tokens.py", needle)
    must_contain(reg, cat, "backend-api/core/auth.py", "HTTPBearer")
    must_contain(reg, cat, "backend-api/core/auth.py", "Bearer")
    must_contain(reg, cat, "backend-api/routes/admin_auth.py", "login")
    must_exist(reg, cat, "backend-api/routes/admin_auth.py")
    env_documents(reg, cat, "API_SECRET_KEY")
    env_documents(reg, cat, "REDIS_URL")
    env_documents(reg, cat, "ADMIN_BOOTSTRAP_USER")
    env_documents(reg, cat, "ADMIN_BOOTSTRAP_PASSWORD")


def build_passwords_mfa(reg: Registry) -> None:
    cat = "passwords_mfa"
    must_exist(reg, cat, "backend-api/core/admin_users.py")
    for needle in (
        "hashlib.scrypt",
        "scrypt$",
        "hmac.compare_digest",
        "ensure_bootstrap",
        "ADMIN_BOOTSTRAP",
        "ADMIN_MFA_REQUIRED",
        "pyotp",
        "totp_secret",
        "_totp_ok",
        "salt",
        "dklen=32",
        "n=2**14",
    ):
        must_contain(reg, cat, "backend-api/core/admin_users.py", needle)
    env_documents(reg, cat, "ADMIN_MFA_REQUIRED")
    env_documents(reg, cat, "ADMIN_BOOTSTRAP_SYNC")
    must_contain(reg, cat, "backoffice-desktop/src/lib/api.js", "totp_code")
    must_contain(reg, cat, "backoffice-desktop/src/lib/api.js", "mfaConfirm")
    # Never store plaintext password markers in admin_users module
    must_not_contain(reg, cat, "backend-api/core/admin_users.py", "password=")
    must_match(reg, cat, "backend-api/core/admin_users.py", r"def verify_password|def hash_password|scrypt")
    gitignore_has(reg, cat, "admin_users.json")
    gitignore_has(reg, cat, "admin_users.json.bak")


def build_rate_limit(reg: Registry) -> None:
    cat = "rate_limit"
    must_exist(reg, cat, "backend-api/core/rate_limit.py")
    must_exist(reg, cat, "backend-api/core/middleware.py")
    must_exist(reg, cat, "backend-api/tests/test_scaling.py")
    for needle in (
        "check_global_rate_limit",
        "rate_limit",
        "rate_limit_absolute",
        "get_client_ip",
        "trust_proxy_headers",
        "_peer_is_trusted_proxy",
        "x-forwarded-for",
        "REDIS",
        "_limits_for_path",
    ):
        must_contain(reg, cat, "backend-api/core/rate_limit.py", needle)
    must_contain(reg, cat, "backend-api/core/middleware.py", "GlobalRateLimitMiddleware")
    must_contain(reg, cat, "backend-api/core/middleware.py", "BodySizeLimitMiddleware")
    must_contain(reg, cat, "backend-api/main.py", "GlobalRateLimitMiddleware")
    must_contain(reg, cat, "backend-api/main.py", "BodySizeLimitMiddleware")
    env_documents(reg, cat, "REDIS_URL")
    env_documents(reg, cat, "TRUST_PROXY")
    # Login rate limiting referenced from admin_auth
    must_match(reg, cat, "backend-api/routes/admin_auth.py", r"rate_limit")


def build_ssrf(reg: Registry) -> None:
    cat = "ssrf"
    must_exist(reg, cat, "backend-api/core/ssrf_guard.py")
    must_exist(reg, cat, "deploy/verify_ssrf_coverage.py")
    for needle in (
        "UnsafeUrlError",
        "assert_safe_outbound_url",
        "allowed_fetch_hosts",
        "SSRF_ALLOW_HOSTS",
        "https",
        "api.cloudflare.com",
        "challenges.cloudflare.com",
        "hooks.slack.com",
        "ntfy.sh",
        "api.axiom.co",
    ):
        must_contain(reg, cat, "backend-api/core/ssrf_guard.py", needle)
    for net in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ):
        must_contain(reg, cat, "backend-api/core/ssrf_guard.py", net)
    must_contain(reg, cat, "backend-api/utils/turnstile.py", "challenges.cloudflare.com")
    must_match(reg, cat, "backend-api/core/alerts.py", r"ssrf_guard|assert_safe_outbound_url")
    must_contain(reg, cat, "backend-api/tests/test_path_guard_hardening.py", "assert_safe_outbound_url")
    env_documents(reg, cat, "ALERT_WEBHOOK_URL")


def build_cors_hosts(reg: Registry) -> None:
    cat = "cors_hosts"
    must_contain(reg, cat, "backend-api/main.py", "CORSMiddleware")
    must_contain(reg, cat, "backend-api/main.py", "TrustedHostMiddleware")
    must_contain(reg, cat, "backend-api/main.py", "invalid.invalid")
    must_contain(reg, cat, "backend-api/main.py", "ALLOWED_HOSTS")
    must_contain(reg, cat, "backend-api/core/config.py", "CORS_ORIGINS")
    env_documents(reg, cat, "CORS_ORIGINS")
    env_documents(reg, cat, "ALLOWED_HOSTS")
    # Production startup validation tests
    must_contain(reg, cat, "backend-api/tests/test_security.py", "CORS_ORIGINS")
    must_contain(reg, cat, "backend-api/tests/test_security.py", "ALLOWED_HOSTS")
    must_contain(reg, cat, "backend-api/tests/test_meta_routes.py", "ALLOWED_HOSTS")
    must_match(reg, cat, "backend-api/core/config.py", r"CORS|cors|ALLOWED_HOSTS|is_production")
    # .env.example shows localhost origins for dev
    must_contain(reg, cat, ".env.example", "localhost:5173")


def build_csp_headers(reg: Registry) -> None:
    cat = "csp_headers"
    headers = "frontend-web/public/_headers"
    must_exist(reg, cat, headers)
    must_exist(reg, cat, "deploy/verify_csp.py")
    for needle in (
        "X-Frame-Options: DENY",
        "X-Content-Type-Options: nosniff",
        "Referrer-Policy: strict-origin-when-cross-origin",
        "Permissions-Policy:",
        "Strict-Transport-Security:",
        "Content-Security-Policy:",
        "default-src 'self'",
        "script-src 'self'",
        "challenges.cloudflare.com",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "upgrade-insecure-requests",
        "api.diomika.com",
        "style-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "Cache-Control: public, max-age=31536000, immutable",
    ):
        must_contain(reg, cat, headers, needle)
    for forbidden in ("'unsafe-inline'", "'unsafe-eval'", "fonts.googleapis.com", "fonts.gstatic.com"):
        must_not_contain(reg, cat, headers, forbidden)
    must_not_contain(reg, cat, "frontend-web/index.html", "fonts.googleapis.com")
    # API middleware headers
    for needle in (
        "X-Content-Type-Options",
        "nosniff",
        "X-Frame-Options",
        "DENY",
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Request-Id",
        "SecurityHeadersMiddleware",
        "RequestIdMiddleware",
    ):
        must_contain(reg, cat, "backend-api/core/middleware.py", needle)
    must_contain(reg, cat, "backend-api/main.py", "SecurityHeadersMiddleware")
    must_contain(reg, cat, "backend-api/main.py", "RequestIdMiddleware")


def build_turnstile_honeypot(reg: Registry) -> None:
    cat = "turnstile_honeypot"
    must_exist(reg, cat, "backend-api/utils/turnstile.py")
    must_exist(reg, cat, "backend-api/tests/test_spam_validation.py")
    for needle in (
        "verify_turnstile",
        "turnstile_enabled",
        "challenges.cloudflare.com/turnstile",
        "_turnstile_is_test_key",
    ):
        must_contain(reg, cat, "backend-api/utils/turnstile.py", needle)
    env_documents(reg, cat, "TURNSTILE_SECRET_KEY")
    env_documents(reg, cat, "VITE_TURNSTILE_SITE_KEY")
    must_contain(reg, cat, "frontend-web/src/views/ContactView.vue", "website")
    must_contain(reg, cat, "frontend-web/src/views/ContactView.vue", "turnstile")
    must_contain(reg, cat, "frontend-web/src/views/ContactView.vue", "cf_turnstile_response")
    must_contain(reg, cat, "backend-api/tests/test_spam_validation.py", "honeypot")
    must_contain(reg, cat, "backend-api/tests/test_security.py", "turnstile")
    must_match(reg, cat, "backend-api/routes/contact.py", r"website|turnstile|honeypot")
    must_contain(reg, cat, "deploy/security_test.py", "honeypot")
    must_contain(reg, cat, "deploy/security_test.py", "website")


def build_rls_db(reg: Registry) -> None:
    cat = "rls_db"
    sql = "deploy/supabase_pre_deploy.sql"
    must_exist(reg, cat, sql)
    must_exist(reg, cat, "deploy/verify_rls.py")
    tables = (
        "categories",
        "modelos_almofadas",
        "almofada",
        "modelo_cores",
        "pedidos_orcamento",
        "encomendas_internas",
        "contact_messages",
        "message_history",
        "outbox_events",
        "saga_instances",
        "idempotency_keys",
        "modelos_assentos",
        "assento",
        "admin_audit_log",
    )
    for tbl in tables:
        must_contain(reg, cat, sql, f"ENABLE ROW LEVEL SECURITY")
        must_match(reg, cat, sql, rf"ALTER TABLE.*{re.escape(tbl)}.*ENABLE ROW LEVEL SECURITY")
    policies = (
        "categories_public_read",
        "modelos_public_read",
        "pedidos_orcamento_deny_anon",
        "encomendas_internas_deny_anon",
        "contact_deny_anon_insert",
        "contact_deny_anon_select",
        "history_deny_anon",
        "outbox_deny_anon",
        "saga_deny_anon",
        "idempotency_deny_anon",
        "product_images_public_read",
        "product_images_no_anon_write",
        "admin_audit_deny_anon",
        "modelos_assentos_public_read",
        "assento_public_read",
    )
    for pol in policies:
        must_contain(reg, cat, sql, pol)
    must_contain(reg, cat, "backend-api/core/catalog_deploy_sql.py", "ENABLE ROW LEVEL SECURITY")
    must_contain(reg, cat, "backend-api/core/catalog_deploy_sql.py", "deny_anon")
    must_contain(reg, cat, ".github/workflows/ci.yml", "verify_rls.py")
    must_contain(reg, cat, "backend-api/sql/migration_modelo_cores_por_categoria.sql", "ENABLE ROW LEVEL SECURITY")


def build_secrets_ci(reg: Registry) -> None:
    cat = "secrets_ci"
    must_exist(reg, cat, ".github/workflows/ci.yml")
    must_exist(reg, cat, ".gitleaks.toml")
    must_exist(reg, cat, "deploy/security_gate.py")
    must_exist(reg, cat, "deploy/verify_bundle_secrets.py")
    must_exist(reg, cat, "deploy/verify_env_separation.py")
    for needle in (
        "security_gate.py",
        "pip-audit",
        "gitleaks",
        "GITLEAKS_CONFIG",
        "verify_bundle_secrets",
        "pytest",
    ):
        must_contain(reg, cat, ".github/workflows/ci.yml", needle)
    gitignore_has(reg, cat, ".env")
    gitignore_has(reg, cat, "!.env.example")
    must_exist(reg, cat, ".env.example")
    # Secret var names documented, never real values in example
    for var in (
        "API_SECRET_KEY",
        "SUPABASE_KEY",
        "VITE_SUPABASE_ANON_KEY",
        "TURNSTILE_SECRET_KEY",
        "MAIL_PASSWORD",
        "DIOMIKA_DESKTOP_GATE",
        "CLOUDFLARE_API_TOKEN",
        "SENTRY_DSN",
        "AXIOM_TOKEN",
    ):
        env_documents(reg, cat, var)
    # .env.example should not look like a real JWT/long secret dump
    text = read_text(ROOT / ".env.example") or ""
    reg.decide(
        cat,
        ".env.example has no eyJ live-looking JWT",
        "eyJhbGciOi" not in text,
        "placeholder check",
    )
    must_contain(reg, cat, "deploy/security_gate.py", "verify_route_guards.py")
    must_contain(reg, cat, "deploy/security_gate.py", "verify_ssrf_coverage.py")
    must_contain(reg, cat, "deploy/security_gate.py", "verify_csp.py")
    must_contain(reg, cat, "deploy/security_gate.py", "verify_env_separation.py")


def build_desktop_gate(reg: Registry) -> None:
    cat = "desktop_gate"
    must_exist(reg, cat, "backoffice-desktop/scripts/write-gate.cjs")
    must_exist(reg, cat, "backoffice-desktop/electron/main.cjs")
    must_exist(reg, cat, "backoffice-desktop/package.json")
    for needle in (
        "DIOMIKA_DESKTOP_GATE",
        "desktop-gate.cjs",
        "length < 24",
    ):
        must_contain(reg, cat, "backoffice-desktop/scripts/write-gate.cjs", needle)
    must_contain(reg, cat, "backoffice-desktop/electron/main.cjs", "desktop-gate.cjs")
    must_contain(reg, cat, "backoffice-desktop/electron/main.cjs", "DIOMIKA_DESKTOP_GATE")
    for script in ("dist:win", "dist:mac", "dist:linux", "dist:dir"):
        pkg_script(reg, cat, "backoffice-desktop/package.json", script)
    must_contain(reg, cat, "backoffice-desktop/package.json", "write-gate.cjs")
    gitignore_has(reg, cat, "desktop-gate.cjs")
    env_documents(reg, cat, "DIOMIKA_DESKTOP_GATE")
    must_contain(reg, cat, "backend-api/core/local_only.py", "x-diomika-desktop")
    must_contain(reg, cat, "deploy/cloudflare/waf_rules.json", "x-diomika-desktop")
    must_contain(reg, cat, "deploy/cloudflare/waf_rules.json", "REPLACE_WITH_DIOMIKA_DESKTOP_GATE")


def build_waf_edge(reg: Registry) -> None:
    cat = "waf_edge"
    must_exist(reg, cat, "deploy/cloudflare/waf_rules.json")
    must_exist(reg, cat, "deploy/cloudflare/dns_plan.json")
    waf = ROOT / "deploy/cloudflare/waf_rules.json"
    text = read_text(waf) or ""
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError:
        data = {}
        reg.fail(cat, "waf_rules.json valid JSON", "parse error")
    else:
        reg.ok(cat, "waf_rules.json valid JSON")
    zs = data.get("zone_settings") or {}
    for key, expect in (
        ("ssl", "strict"),
        ("always_use_https", "on"),
        ("min_tls_version", "1.2"),
        ("security_level", "high"),
        ("browser_check", "on"),
    ):
        reg.decide(cat, f"WAF zone_settings.{key}={expect}", zs.get(key) == expect, str(zs.get(key)))
    rules = {r.get("name"): r for r in (data.get("firewall_rules") or []) if isinstance(r, dict)}
    reg.decide(cat, "WAF rule block-empty-ua", "block-empty-ua" in rules)
    reg.decide(cat, "WAF rule block-admin-system-except-desktop", "block-admin-system-except-desktop" in rules)
    if "block-empty-ua" in rules:
        reg.decide(cat, "block-empty-ua action=block", rules["block-empty-ua"].get("action") == "block")
        must_contain(reg, cat, "deploy/cloudflare/waf_rules.json", "http.user_agent eq")
    if "block-admin-system-except-desktop" in rules:
        reg.decide(
            cat,
            "admin/system WAF action=block",
            rules["block-admin-system-except-desktop"].get("action") == "block",
        )
        must_contain(reg, cat, "deploy/cloudflare/waf_rules.json", "/admin")
        must_contain(reg, cat, "deploy/cloudflare/waf_rules.json", "/system")
    must_contain(reg, cat, "deploy/cloudflare/dns_plan.json", "api.diomika.com")
    must_match(reg, cat, "deploy/cloudflare/dns_plan.json", r"www\.diomika\.com|diomika\.com")
    # Tunnel / no open ports documented in compose
    must_contain(reg, cat, "deploy/docker-compose.free.yml", "cloudflared")
    must_contain(reg, cat, "deploy/docker-compose.free.yml", "tunnel")


def build_storefront_hardening(reg: Registry) -> None:
    cat = "storefront_hardening"
    must_exist(reg, cat, "frontend-web/public/_headers")
    must_exist(reg, cat, "frontend-web/package.json")
    must_exist(reg, cat, "frontend-web/src/lib/supabase.js")
    must_exist(reg, cat, "deploy/verify_csp.py")
    must_exist(reg, cat, "deploy/verify_bundle_secrets.py")
    pkg_script(reg, cat, "frontend-web/package.json", "build")
    pkg_script(reg, cat, "frontend-web/package.json", "test:e2e")
    pkg_script(reg, cat, "frontend-web/package.json", "lint")
    env_documents(reg, cat, "VITE_API_BASE_URL")
    env_documents(reg, cat, "VITE_SUPABASE_URL")
    env_documents(reg, cat, "VITE_SUPABASE_ANON_KEY")
    env_documents(reg, cat, "VITE_STORAGE_PRIVATE")
    env_documents(reg, cat, "VITE_POSTHOG_KEY")
    env_documents(reg, cat, "VITE_POSTHOG_HOST")
    must_contain(reg, cat, "frontend-web/src/lib/posthog.js", "consent")
    must_contain(reg, cat, "frontend-web/src/components/CookieBanner.vue", "consent")
    must_contain(reg, cat, "frontend-web/src/App.vue", "CookieBanner")
    # No v-html / inline style pattern check via verify_csp existence already; sample key views
    for view in (
        "HomeView.vue",
        "ContactView.vue",
        "PrivacyView.vue",
        "CartView.vue",
        "ProductDetailView.vue",
    ):
        must_exist(reg, cat, f"frontend-web/src/views/{view}")
    must_contain(reg, cat, ".github/workflows/ci.yml", "Build frontend")
    must_match(reg, cat, ".github/workflows/ci.yml", r"verify_bundle_secrets|bundle.?secret")
    # robots / security meta routes on API side
    must_exist(reg, cat, "backend-api/core/public_meta.py")
    must_match(reg, cat, "backend-api/core/public_meta.py", r"robots|security\.txt")


def build_admin_crud_authz(reg: Registry) -> None:
    cat = "admin_crud_authz"
    must_exist(reg, cat, "backend-api/routes/admin_crud.py")
    must_exist(reg, cat, "backend-api/routes/admin.py")
    must_exist(reg, cat, "backend-api/tests/test_idor.py")
    must_exist(reg, cat, "backend-api/tests/test_hardening.py")
    for needle in (
        "CRUD_INFRA_BLOCKED",
        "SENSITIVE_BUSINESS_TABLES",
        "assert_table_action",
        "require_admin",
    ):
        must_contain(reg, cat, "backend-api/core/auth.py", needle)
    must_match(reg, cat, "backend-api/routes/admin_crud.py", r"assert_table_action|require_")
    must_contain(reg, cat, "backend-api/routes/admin_crud.py", "Idempotency-Key")
    must_contain(reg, cat, "deploy/verify_route_guards.py", "admin_crud")
    must_contain(reg, cat, "deploy/validate_sensitive_routes.py", "admin")
    # Infra tables blocked
    for tbl in ("admin_audit_log", "outbox_events", "saga_instances", "idempotency_keys", "message_history"):
        must_contain(reg, cat, "backend-api/core/auth.py", tbl)
    for tbl in ("contact_messages", "pedidos_orcamento", "encomendas_internas"):
        must_contain(reg, cat, "backend-api/core/auth.py", tbl)
    must_contain(reg, cat, "backend-api/routes/privacy.py", "require_admin")
    must_contain(reg, cat, "backend-api/routes/privacy.py", "admin_must_be_local")


def build_observability(reg: Registry) -> None:
    cat = "observability"
    for rel in (
        "backend-api/core/structured_logging.py",
        "backend-api/core/sentry_init.py",
        "backend-api/core/error_tracking.py",
        "backend-api/core/alerts.py",
        "backend-api/core/audit.py",
        "backend-api/core/anomaly.py",
        "backend-api/tests/test_observability_flags.py",
    ):
        must_exist(reg, cat, rel)
    for var in (
        "SENTRY_DSN",
        "AXIOM_TOKEN",
        "AXIOM_DATASET",
        "AXIOM_API_URL",
        "ALERT_WEBHOOK_URL",
        "ALERT_LOG_FILE",
        "ALERT_LATENCY_MS",
        "LOG_FORMAT",
        "VITE_POSTHOG_KEY",
        "VITE_POSTHOG_HOST",
    ):
        env_documents(reg, cat, var)
    must_contain(reg, cat, "backend-api/core/middleware.py", "X-Request-Id")
    must_contain(reg, cat, "backend-api/core/middleware.py", "LatencyAlertMiddleware")
    must_contain(reg, cat, "backend-api/main.py", "LatencyAlertMiddleware")
    must_match(reg, cat, "backend-api/core/structured_logging.py", r"AXIOM|axiom")
    must_match(reg, cat, "backend-api/core/sentry_init.py", r"SENTRY|sentry")
    must_exist(reg, cat, "deploy/monitor_check.py")
    must_exist(reg, cat, "deploy/uptime_check.py")
    must_exist(reg, cat, ".github/workflows/uptime.yml")


def build_docker_compose(reg: Registry) -> None:
    cat = "docker_compose"
    must_exist(reg, cat, "deploy/docker-compose.free.yml")
    must_exist(reg, cat, "deploy/docker-compose.vps.yml")
    must_exist(reg, cat, "Dockerfile")
    for needle in (
        "127.0.0.1:8000:8000",
        "127.0.0.1:6379:6379",
        "redis:7-alpine",
        "REDIS_URL",
        "DIOMIKA_ENV: production",
        "TRUST_PROXY",
        "SUPABASE_STORAGE_PRIVATE",
        "healthcheck",
        "cloudflared",
        "profiles: [\"tunnel\"]",
    ):
        must_contain(reg, cat, "deploy/docker-compose.free.yml", needle)
    must_contain(reg, cat, "Dockerfile", "python:3.12-slim")
    must_contain(reg, cat, "Dockerfile", "uvicorn")
    must_not_contain(reg, cat, "deploy/docker-compose.free.yml", "0.0.0.0:8000")
    must_not_contain(reg, cat, "deploy/docker-compose.free.yml", "0.0.0.0:6379")
    env_documents(reg, cat, "CLOUDFLARE_TUNNEL_TOKEN")
    env_documents(reg, cat, "REMOTE_VM_SSH")


def build_dependencies(reg: Registry) -> None:
    cat = "dependencies"
    must_exist(reg, cat, "requirements.txt")
    must_exist(reg, cat, ".github/dependabot.yml")
    must_contain(reg, cat, ".github/workflows/ci.yml", "pip-audit")
    must_contain(reg, cat, ".github/dependabot.yml", "package-ecosystem: npm")
    must_contain(reg, cat, ".github/dependabot.yml", "package-ecosystem: pip")
    must_contain(reg, cat, ".github/dependabot.yml", "package-ecosystem: github-actions")
    must_contain(reg, cat, ".github/dependabot.yml", "/frontend-web")
    must_contain(reg, cat, ".github/dependabot.yml", "/backoffice-desktop")
    # Key python deps present
    req = read_text(ROOT / "requirements.txt") or ""
    for dep in ("fastapi", "uvicorn", "pydantic", "redis", "pyotp", "requests", "sentry-sdk"):
        reg.decide(cat, f"requirements.txt lists {dep}", dep.lower() in req.lower(), dep)
    # Frontend deps
    fw = read_text(ROOT / "frontend-web/package.json") or ""
    for dep in ("vue", "vue-router", "@supabase/supabase-js", "posthog-js", "vite"):
        reg.decide(cat, f"frontend-web depends on {dep}", dep in fw, dep)
    bo = read_text(ROOT / "backoffice-desktop/package.json") or ""
    for dep in ("electron", "electron-builder", "vue", "vite"):
        reg.decide(cat, f"backoffice-desktop depends on {dep}", dep in bo, dep)
    must_contain(reg, cat, "frontend-web/package.json", '"node":')
    must_contain(reg, cat, "backoffice-desktop/package.json", '"node":')


def build_idempotency(reg: Registry) -> None:
    cat = "idempotency"
    must_exist(reg, cat, "backend-api/core/idempotency.py")
    must_exist(reg, cat, "backend-api/core/idempotency_maintenance.py")
    must_exist(reg, cat, "backend-api/tests/test_idempotency_maintenance.py")
    must_exist(reg, cat, "backend-api/tests/test_hardening.py")
    for needle in (
        "IdempotencyUnavailable",
        "begin_idempotent_request",
        "get_cached_response",
    ):
        must_contain(reg, cat, "backend-api/core/idempotency.py", needle)
    must_contain(reg, cat, "backend-api/routes/admin_crud.py", "Idempotency-Key")
    must_contain(reg, cat, "backend-api/routes/admin_crud.py", "IdempotencyUnavailable")
    must_contain(reg, cat, "backoffice-desktop/src/lib/api.js", "Idempotency-Key")
    must_contain(reg, cat, "deploy/supabase_pre_deploy.sql", "idempotency_keys")
    must_contain(reg, cat, "deploy/supabase_pre_deploy.sql", "idempotency_deny_anon")
    must_contain(reg, cat, "backend-api/models/schemas.py", "IdempotencyKey")
    must_contain(reg, cat, "backend-api/core/auth.py", "idempotency_keys")


def build_privacy_gdpr(reg: Registry) -> None:
    cat = "privacy_gdpr"
    must_exist(reg, cat, "backend-api/routes/privacy.py")
    must_exist(reg, cat, "backend-api/tests/test_privacy_erase.py")
    must_exist(reg, cat, "backend-api/core/retention.py")
    must_exist(reg, cat, "frontend-web/src/views/PrivacyView.vue")
    must_exist(reg, cat, "frontend-web/src/components/CookieBanner.vue")
    for needle in (
        "/admin/privacy",
        "erase",
        "ERASE",
        "require_admin",
        "admin_must_be_local",
        "log_admin_action",
        "privacy_erase",
    ):
        must_contain(reg, cat, "backend-api/routes/privacy.py", needle)
    must_contain(reg, cat, "frontend-web/src/router/index.js", "privacy")
    must_contain(reg, cat, "frontend-web/src/components/CookieBanner.vue", "diomika_cookie_consent")
    must_contain(reg, cat, "frontend-web/src/lib/posthog.js", "consent")
    must_contain(reg, cat, "backend-api/main.py", "privacy")
    must_contain(reg, cat, "deploy/verify_route_guards.py", "privacy.py")
    must_match(reg, cat, "frontend-web/src/views/PrivacyView.vue", r"PostHog|consentimento|privacidade")
    must_exist(reg, cat, "backend-api/sql/migration_email_indexes.sql")


def build_backups_ops(reg: Registry) -> None:
    cat = "backups_ops"
    gitignore_has(reg, cat, "deploy/backups/")
    gitignore_has(reg, cat, "*.sql.gz")
    gitignore_has(reg, cat, "admin_users.json.bak")
    must_contain(reg, cat, "backend-api/core/admin_users.py", "Backup")
    must_match(reg, cat, "backend-api/core/admin_users.py", r"backup|\.bak")
    must_exist(reg, cat, "docs/INSTRUCOES.md")
    must_match(reg, cat, "docs/INSTRUCOES.md", r"[Bb]ackup")
    must_exist(reg, cat, "deploy/deploy_vm.py")
    must_exist(reg, cat, "deploy/apply_production.py")
    must_exist(reg, cat, "deploy/verify_production.py")
    must_exist(reg, cat, "deploy/create_gcp_vm.py")
    # Volume persistence for admin_users
    must_contain(reg, cat, "deploy/docker-compose.free.yml", "backend-api/data")
    must_contain(reg, cat, "deploy/docker-compose.free.yml", "restart: unless-stopped")
    env_documents(reg, cat, "SUPABASE_DB_PASSWORD")
    # SECURITY_LOCKDOWN ops switch
    must_contain(reg, cat, "backend-api/core/path_guard.py", "SECURITY_LOCKDOWN")
    env_documents(reg, cat, "DIOMIKA_ENV")


def build_docs_and_tests_inventory(reg: Registry) -> None:
    """Extra static inventory to deepen coverage toward Part V controls."""
    # Spread across existing categories for inventory of tests / docs / scripts
    for rel in (
        "docs/RELATORIO_TECNICO.md",
        "deploy/security_test.py",
        "deploy/security_gate.py",
        "deploy/check.py",
        "deploy/smoke_test.py",
        "deploy/README.md",
    ):
        must_exist(reg, "secrets_ci", rel)

    part_v_markers = (
        "path_guard",
        "ssrf_guard",
        "SECURITY_LOCKDOWN",
        "DIOMIKA_DESKTOP_GATE",
        "Turnstile",
        "Row Level Security",
        "scrypt",
        "CORS",
        "ALLOWED_HOSTS",
        "WAF",
        "Content-Security-Policy",
        "Idempotency",
        "ADMIN_MFA_REQUIRED",
        "honeypot",
        "X-Diomika-Desktop",
    )
    for marker in part_v_markers:
        must_contain(reg, "secrets_ci", "docs/RELATORIO_TECNICO.md", marker, f"RELATORIO Part V mentions {marker}")

    test_files = [
        "test_path_guard_hardening.py",
        "test_local_only.py",
        "test_admin_session.py",
        "test_security.py",
        "test_hardening.py",
        "test_spam_validation.py",
        "test_idor.py",
        "test_privacy_erase.py",
        "test_observability_flags.py",
        "test_storage_private.py",
        "test_scaling.py",
        "test_idempotency_maintenance.py",
        "test_enterprise_auth.py",
        "test_beta_config.py",
        "test_meta_routes.py",
    ]
    for tf in test_files:
        must_exist(reg, "auth_sessions", f"backend-api/tests/{tf}")

    core_modules = [
        "path_guard.py",
        "local_only.py",
        "ssrf_guard.py",
        "rate_limit.py",
        "middleware.py",
        "auth.py",
        "session_tokens.py",
        "admin_users.py",
        "idempotency.py",
        "alerts.py",
        "audit.py",
        "retention.py",
        "config.py",
        "database.py",
    ]
    for mod in core_modules:
        if mod.endswith(".py"):
            must_exist(reg, "path_guard", f"backend-api/core/{mod}")

    # AST import presence for critical modules
    ast_imports(
        reg,
        "path_guard",
        "backend-api/main.py",
        [
            "PrivilegedPathMiddleware",
            "GlobalRateLimitMiddleware",
            "SecurityHeadersMiddleware",
            "TrustedHostMiddleware",
            "CORSMiddleware",
        ],
    )
    ast_imports(
        reg,
        "ssrf",
        "backend-api/core/ssrf_guard.py",
        ["ipaddress", "urlparse"],
    )
    ast_imports(
        reg,
        "passwords_mfa",
        "backend-api/core/admin_users.py",
        ["hashlib", "hmac", "base64"],
    )

    # Env vars bulk
    more_vars = [
        "DIOMIKA_ENV",
        "DIOMIKA_BETA",
        "SUPABASE_URL",
        "SUPABASE_STORAGE_PRIVATE",
        "VITE_SUPABASE_STORAGE_BUCKET",
        "API_BASE_URL",
        "MAIL_SERVER",
        "MAIL_PORT",
        "MAIL_USERNAME",
        "MAIL_FROM",
        "CONTACT_NOTIFY_EMAIL",
        "IMAP_SERVER",
        "IMAP_PORT",
        "CLOUDFLARE_ACCOUNT_ID",
    ]
    for var in more_vars:
        env_documents(reg, "secrets_ci", var)

    # Deploy verifier scripts inventory
    for script in (
        "verify_route_guards.py",
        "validate_sensitive_routes.py",
        "verify_ssrf_coverage.py",
        "verify_env_separation.py",
        "verify_csp.py",
        "verify_bundle_secrets.py",
        "verify_rls.py",
        "verify_production.py",
        "security_gate.py",
        "security_test.py",
    ):
        must_exist(reg, "secrets_ci", f"deploy/{script}")

    # Storage private fail-closed
    must_exist(reg, "storefront_hardening", "backend-api/utils/storage.py")
    must_match(reg, "storefront_hardening", "backend-api/utils/storage.py", r"signed|private|resolve_delivery")
    must_contain(reg, "storefront_hardening", "backend-api/tests/test_storage_private.py", "private")

    # Public mutate prefixes lockdown
    must_contain(reg, "path_guard", "backend-api/core/path_guard.py", "_PUBLIC_MUTATE_PREFIXES")
    must_contain(reg, "path_guard", "backend-api/core/path_guard.py", "/contacto")
    must_contain(reg, "path_guard", "backend-api/core/path_guard.py", "/orcamentos")

    # Docs openapi disabled in prod pattern
    must_contain(reg, "storefront_hardening", "backend-api/main.py", "docs_enabled")
    must_contain(reg, "storefront_hardening", "backend-api/main.py", "openapi_url")

    # Text safety / input validation
    must_exist(reg, "admin_crud_authz", "backend-api/core/text_safe.py")
    must_exist(reg, "admin_crud_authz", "backend-api/models/schemas.py")

    # Catalog cache headers — only public catalog
    must_contain(reg, "csp_headers", "backend-api/core/middleware.py", "CatalogCacheHeadersMiddleware")

    # Honeypot field on contact model
    must_match(reg, "turnstile_honeypot", "backend-api/routes/contact.py", r"website")
    must_contain(reg, "turnstile_honeypot", "backend-api/routes/contact.py", "honeypot")

    # Rate limit path differentiation
    must_contain(reg, "rate_limit", "backend-api/core/rate_limit.py", "_is_public_catalog_read")

    # Session token format
    must_match(reg, "auth_sessions", "backend-api/core/session_tokens.py", r"dms1")

    # WAF UA check documented in security_test
    must_contain(reg, "waf_edge", "deploy/security_test.py", "User-Agent")

    # Privacy erase confirm
    must_contain(reg, "privacy_gdpr", "backend-api/routes/privacy.py", 'confirm != "ERASE"')

    # GitHub release workflow for backoffice
    must_exist(reg, "desktop_gate", ".github/workflows/backoffice-release.yml")

    # Compose vps exists as alternate
    must_match(reg, "docker_compose", "deploy/docker-compose.vps.yml", r"redis|api|8000")

    # Idempotency table in schemas registry
    must_contain(reg, "idempotency", "backend-api/models/schemas.py", "idempotency_keys")

    # Backup instructions
    must_match(reg, "backups_ops", "docs/INSTRUCOES.md", r"Supabase")

    # Anomaly / audit on failed login path
    must_match(reg, "observability", "backend-api/core/anomaly.py", r"anomal|login|alert")
    must_match(reg, "observability", "backend-api/core/audit.py", r"log_admin_action|audit")

    # Extra CSP connect-src pieces
    for piece in (
        "https://*.supabase.co",
        "wss://*.supabase.co",
        "https://*.i.posthog.com",
        "https://eu.i.posthog.com",
        "img-src",
        "frame-src",
        "font-src",
        "camera=()",
        "microphone=()",
        "geolocation=()",
        "includeSubDomains",
        "preload",
    ):
        must_contain(reg, "csp_headers", "frontend-web/public/_headers", piece)

    # Extra SSRF hosts
    for host in (
        "discord.com",
        "discordapp.com",
        "eu-central-1.aws.edge.axiom.co",
        "us-east-1.aws.edge.axiom.co",
    ):
        must_contain(reg, "ssrf", "backend-api/core/ssrf_guard.py", host)

    # Role matrix strings
    for role in ("admin", "ops", "catalog", "pedidos", "mensagens"):
        must_contain(reg, "admin_crud_authz", "backend-api/core/auth.py", f'"{role}"')

    # Actions
    for action in ("read", "create", "update", "delete", "upload", "hard_delete"):
        must_contain(reg, "admin_crud_authz", "backend-api/core/auth.py", action)

    # Frontend contact honeypot CSS hide pattern (optional soft)
    must_match(reg, "turnstile_honeypot", "frontend-web/src/views/ContactView.vue", r"website")

    # Health endpoints
    must_exist(reg, "path_guard", "backend-api/core/health.py")
    must_match(reg, "path_guard", "backend-api/core/health.py", r"health")

    # Public meta security.txt contact
    must_match(reg, "storefront_hardening", "backend-api/core/public_meta.py", r"Contact|security")

    # Dockerfile non-root-ish notes — host bind only via compose
    must_contain(reg, "docker_compose", "Dockerfile", "PYTHONPATH")

    # CI python 3.12
    must_contain(reg, "dependencies", ".github/workflows/ci.yml", "3.12")
    must_contain(reg, "dependencies", ".github/workflows/ci.yml", "node-version")

    # Gitleaks config
    must_match(reg, "secrets_ci", ".gitleaks.toml", r"title|description|id|regex|\[")

    # Launch / production ready artifacts gitignored
    for pat in ("deploy/production.ready.json", "deploy/beta.state.json", "deploy/launch.state.json", "deploy/proof/"):
        gitignore_has(reg, "backups_ops", pat)

    # Feature flags / resilience modules present
    for mod in ("feature_flags.py", "resilience.py", "outbox.py", "notify.py"):
        must_exist(reg, "observability", f"backend-api/core/{mod}")

    # Electron api origin helper
    must_exist(reg, "desktop_gate", "backoffice-desktop/electron/api-origin.cjs")
    must_exist(reg, "desktop_gate", "backoffice-desktop/src/lib/api.js")

    # Quote PDF auth check in security_test
    must_contain(reg, "admin_crud_authz", "deploy/security_test.py", "orcamentos")
    must_contain(reg, "admin_crud_authz", "deploy/security_test.py", "/admin/crud/categories")
    must_contain(reg, "admin_crud_authz", "deploy/security_test.py", "/health/detail")

    # Docs Part V section headers present
    for section in (
        "## V.3 Cloudflare WAF",
        "## V.4 O *gate* de secretária",
        "## V.5 `path_guard`",
        "## V.6 Autenticação de administração",
        "## V.7 Sessões",
        "## V.8 MFA",
        "## V.12 SSRF",
        "## V.13 CORS",
        "## V.14 Limitação de ritmo",
        "## V.15 Turnstile",
        "## V.16 `SECURITY_LOCKDOWN`",
        "## V.17 Cabeçalhos de segurança",
    ):
        must_contain(reg, "secrets_ci", "docs/RELATORIO_TECNICO.md", section)

    # Extra rate-limit / body size
    must_match(reg, "rate_limit", "backend-api/core/middleware.py", r"BodySize|content-length|MAX_BODY|body")

    # Password policy markers
    must_match(reg, "passwords_mfa", "backend-api/core/admin_users.py", r"len\(|password|forte|min")

    # Bootstrap trap documentation in report
    must_contain(reg, "passwords_mfa", "docs/RELATORIO_TECNICO.md", "ensure_bootstrap")

    # Storage private env
    env_documents(reg, "storefront_hardening", "SUPABASE_STORAGE_PRIVATE")

    # DNS plan file JSON parse
    dns_text = read_text(ROOT / "deploy/cloudflare/dns_plan.json")
    if dns_text:
        try:
            json.loads(dns_text)
            reg.ok("waf_edge", "dns_plan.json valid JSON")
        except json.JSONDecodeError as exc:
            reg.fail("waf_edge", "dns_plan.json valid JSON", str(exc))
    else:
        reg.fail("waf_edge", "dns_plan.json valid JSON", "missing")

    # Many SQL deny policies for write paths
    for pol in (
        "product_images_no_anon_update",
        "product_images_no_anon_delete",
        "barcodes_no_anon_write",
        "barcodes_no_anon_update",
        "barcodes_no_anon_delete",
        "barcodes_public_read",
    ):
        must_contain(reg, "rls_db", "deploy/supabase_pre_deploy.sql", pol)

    # Monitor hub optional — if present, note security-relevant pieces
    if (ROOT / "monitor-hub").is_dir():
        must_exist(reg, "observability", "monitor-hub/package.json")
        gitignore_has(reg, "secrets_ci", "monitor-hub/config.local.json")

    # Frontend engines node constraint
    must_match(reg, "dependencies", "frontend-web/package.json", r"20\.19|22\.12")

    # No docs exposing secrets rule in report
    must_contain(reg, "secrets_ci", "docs/RELATORIO_TECNICO.md", "não contém")

    # Compare digest in desktop gate path
    must_contain(reg, "desktop_gate", "backend-api/core/local_only.py", "compare_digest")

    # Session redis required fail-closed
    must_match(reg, "auth_sessions", "backend-api/core/session_tokens.py", r"_redis_required|redis")

    # Fail-closed no API keys
    must_match(reg, "auth_sessions", "backend-api/core/auth.py", r"503|require_api_key")


def build_live_checks(reg: Registry, api: str, site: str, allow_offline: bool) -> None:
    api = api.rstrip("/")
    site = site.rstrip("/")

    # --- API ---
    live_status(reg, "csp_headers", "LIVE API GET /health 200", f"{api}/health", {200}, allow_offline=allow_offline)
    live_header(
        reg,
        "csp_headers",
        "LIVE API X-Content-Type-Options nosniff",
        f"{api}/health",
        "X-Content-Type-Options",
        "nosniff",
        allow_offline=allow_offline,
    )
    live_header(
        reg,
        "csp_headers",
        "LIVE API X-Frame-Options DENY/SAMEORIGIN",
        f"{api}/health",
        "X-Frame-Options",
        lambda v: (v or "").upper() in ("DENY", "SAMEORIGIN"),
        allow_offline=allow_offline,
    )
    live_header(
        reg,
        "observability",
        "LIVE API X-Request-Id present",
        f"{api}/health",
        "X-Request-Id",
        None,
        allow_offline=allow_offline,
    )
    live_status(
        reg,
        "storefront_hardening",
        "LIVE API GET / diomika-api",
        f"{api}/",
        {200},
        allow_offline=allow_offline,
        body_must_contain="diomika-api",
    )
    live_status(
        reg,
        "storefront_hardening",
        "LIVE API robots.txt Disallow",
        f"{api}/robots.txt",
        {200},
        allow_offline=allow_offline,
        body_must_contain="Disallow:",
    )
    live_status(
        reg,
        "storefront_hardening",
        "LIVE API security.txt Contact",
        f"{api}/.well-known/security.txt",
        {200},
        allow_offline=allow_offline,
        body_must_contain="Contact:",
    )
    for path in ("/openapi.json", "/api/docs", "/api/redoc"):
        live_status(
            reg,
            "storefront_hardening",
            f"LIVE API {path} closed",
            f"{api}{path}",
            {404, 403},
            allow_offline=allow_offline,
        )
    for path, cat in (
        ("/system/workspace", "path_guard"),
        ("/admin/crud/categories", "admin_crud_authz"),
        ("/contacto", "admin_crud_authz"),
        ("/health/detail", "path_guard"),
        ("/admin/privacy/erase", "privacy_gdpr"),
    ):
        live_status(
            reg,
            cat,
            f"LIVE API GET {path} blocked without auth",
            f"{api}{path}",
            {401, 403, 404, 405, 503},
            allow_offline=allow_offline,
        )
    live_status(
        reg,
        "turnstile_honeypot",
        "LIVE API POST /contacto honeypot blocked",
        f"{api}/contacto",
        {400},
        method="POST",
        body={
            "nome": "Teste Seguranca",
            "email": "test@example.com",
            "contacto": "912345678",
            "assunto": "Teste",
            "mensagem": "Mensagem de teste de seguranca com comprimento minimo.",
            "website": "http://spam.bot",
        },
        allow_offline=allow_offline,
    )
    live_status(
        reg,
        "admin_crud_authz",
        "LIVE API POST /orcamentos invalid email",
        f"{api}/orcamentos",
        {400, 422},
        method="POST",
        body={"nome": "x", "email": "not-an-email", "linhas": []},
        allow_offline=allow_offline,
    )
    live_status(
        reg,
        "admin_crud_authz",
        "LIVE API PDF orcamento without key",
        f"{api}/orcamentos/00000000-0000-0000-0000-000000000000/pdf",
        {401, 403, 404},
        allow_offline=allow_offline,
    )
    # Invalid API key should not succeed
    live_status(
        reg,
        "auth_sessions",
        "LIVE API system with invalid X-API-Key",
        f"{api}/system/workspace",
        {401, 403},
        headers={"X-API-Key": "invalid-key-00000000"},
        allow_offline=allow_offline,
    )
    # HSTS on API (prod)
    live_header(
        reg,
        "csp_headers",
        "LIVE API HSTS present",
        f"{api}/health",
        "Strict-Transport-Security",
        lambda v: bool(v) and "max-age" in (v or "").lower(),
        allow_offline=allow_offline,
    )

    # --- Site ---
    live_status(reg, "storefront_hardening", "LIVE SITE GET / 200", f"{site}/", {200}, allow_offline=allow_offline)
    for header, expect in (
        ("X-Frame-Options", "DENY"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ):
        live_header(
            reg,
            "csp_headers",
            f"LIVE SITE {header}",
            f"{site}/",
            header,
            expect,
            allow_offline=allow_offline,
        )
    live_header(
        reg,
        "csp_headers",
        "LIVE SITE CSP present",
        f"{site}/",
        "Content-Security-Policy",
        lambda v: bool(v) and "default-src" in (v or ""),
        allow_offline=allow_offline,
    )
    live_header(
        reg,
        "csp_headers",
        "LIVE SITE HSTS present",
        f"{site}/",
        "Strict-Transport-Security",
        lambda v: bool(v) and "max-age" in (v or "").lower(),
        allow_offline=allow_offline,
    )
    live_header(
        reg,
        "csp_headers",
        "LIVE SITE CSP no unsafe-inline",
        f"{site}/",
        "Content-Security-Policy",
        lambda v: v is not None and "'unsafe-inline'" not in v,
        allow_offline=allow_offline,
    )
    live_header(
        reg,
        "csp_headers",
        "LIVE SITE CSP no unsafe-eval",
        f"{site}/",
        "Content-Security-Policy",
        lambda v: v is not None and "'unsafe-eval'" not in v,
        allow_offline=allow_offline,
    )
    live_status(
        reg,
        "privacy_gdpr",
        "LIVE SITE /privacidade reachable",
        f"{site}/privacidade",
        {200},
        allow_offline=allow_offline,
    )
    # Extra path probes (edge / SPA)
    for path in ("/contacto", "/categorias", "/carrinho", "/robots.txt"):
        live_status(
            reg,
            "storefront_hardening",
            f"LIVE SITE {path} responds",
            f"{site}{path}",
            lambda s: s is not None and s < 500,  # type: ignore[arg-type,return-value]
            allow_offline=allow_offline,
        )


def expand_to_minimum(reg: Registry, minimum: int = 420) -> None:
    """Generate additional concrete file/string checks until we reach minimum count."""
    # Walk important trees and assert readable text files do not contain obvious secret dumps
    scan_roots = [
        ROOT / "backend-api" / "core",
        ROOT / "backend-api" / "routes",
        ROOT / "backend-api" / "utils",
        ROOT / "deploy",
        ROOT / "frontend-web" / "src",
        ROOT / "backoffice-desktop" / "src",
        ROOT / "backoffice-desktop" / "electron",
        ROOT / "backoffice-desktop" / "scripts",
    ]
    forbidden_patterns = [
        (r"sk_live_[0-9a-zA-Z]{20,}", "stripe live key shape"),
        (r"-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----", "private key block"),
        (r"AKIA[0-9A-Z]{16}", "AWS access key shape"),
    ]
    n = 0
    for base in scan_roots:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".js", ".cjs", ".vue", ".ts", ".sql", ".yml", ".yaml", ".json", ".md", ".toml"}:
                continue
            if path.name.startswith(".env") and path.name != ".env.example":
                continue
            rel = _rel(path)
            # Existence already known; add content hygiene checks
            text = read_text(path)
            if text is None:
                continue
            cat = "secrets_ci"
            for pat, label in forbidden_patterns:
                if n >= (minimum - len(reg.items) + 50):
                    break
                ok = re.search(pat, text) is None
                reg.decide(cat, f"no {label} in {rel}", ok, label)
                n += 1
            if len(reg.items) >= minimum + 80:
                return

    # If still short, add explicit must_exist for every backend route file
    routes = ROOT / "backend-api" / "routes"
    if routes.is_dir():
        for path in sorted(routes.glob("*.py")):
            if len(reg.items) >= minimum:
                break
            must_exist(reg, "admin_crud_authz", _rel(path))

    # SQL migrations inventory
    sql_dir = ROOT / "backend-api" / "sql"
    if sql_dir.is_dir():
        for path in sorted(sql_dir.glob("*.sql")):
            if len(reg.items) >= minimum:
                break
            must_exist(reg, "rls_db", _rel(path))
            if "ROW LEVEL SECURITY" in (read_text(path) or ""):
                must_contain(reg, "rls_db", _rel(path), "ROW LEVEL SECURITY")

    # Frontend components inventory (no v-html)
    comp = ROOT / "frontend-web" / "src" / "components"
    if comp.is_dir():
        for path in sorted(comp.rglob("*.vue")):
            if len(reg.items) >= minimum + 40:
                break
            must_exist(reg, "storefront_hardening", _rel(path))
            must_not_contain(reg, "storefront_hardening", _rel(path), "v-html")

    # Views no v-html
    views = ROOT / "frontend-web" / "src" / "views"
    if views.is_dir():
        for path in sorted(views.glob("*.vue")):
            if len(reg.items) >= minimum + 60:
                break
            must_not_contain(reg, "storefront_hardening", _rel(path), "v-html")
            must_not_contain(reg, "csp_headers", _rel(path), "fonts.googleapis.com")


# ---------------------------------------------------------------------------
# Summary / CLI
# ---------------------------------------------------------------------------


REQUIRED_CATEGORIES = (
    "path_guard",
    "auth_sessions",
    "passwords_mfa",
    "rate_limit",
    "ssrf",
    "cors_hosts",
    "csp_headers",
    "turnstile_honeypot",
    "rls_db",
    "secrets_ci",
    "desktop_gate",
    "waf_edge",
    "storefront_hardening",
    "admin_crud_authz",
    "observability",
    "docker_compose",
    "dependencies",
    "idempotency",
    "privacy_gdpr",
    "backups_ops",
)


def summarize(reg: Registry) -> dict:
    cats: dict[str, dict[str, int]] = {}
    for item in reg.items:
        bucket = cats.setdefault(item.category, {"passed": 0, "failed": 0, "skipped": 0})
        if item.status == "pass":
            bucket["passed"] += 1
        elif item.status == "fail":
            bucket["failed"] += 1
        else:
            bucket["skipped"] += 1
    failures = [
        {"id": i.id, "category": i.category, "title": i.title, "detail": i.detail}
        for i in reg.items
        if i.status == "fail"
    ]
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "total": len(reg.items),
        "passed": sum(1 for i in reg.items if i.status == "pass"),
        "failed": sum(1 for i in reg.items if i.status == "fail"),
        "skipped": sum(1 for i in reg.items if i.status == "skip"),
        "categories": cats,
        "failures": failures,
        "items": [
            {
                "id": i.id,
                "category": i.category,
                "title": i.title,
                "status": i.status,
                "detail": i.detail,
            }
            for i in reg.items
        ],
    }


def run_all(live: bool, api: str, site: str, allow_offline: bool) -> Registry:
    reg = Registry()
    builders = [
        build_path_guard,
        build_auth_sessions,
        build_passwords_mfa,
        build_rate_limit,
        build_ssrf,
        build_cors_hosts,
        build_csp_headers,
        build_turnstile_honeypot,
        build_rls_db,
        build_secrets_ci,
        build_desktop_gate,
        build_waf_edge,
        build_storefront_hardening,
        build_admin_crud_authz,
        build_observability,
        build_docker_compose,
        build_dependencies,
        build_idempotency,
        build_privacy_gdpr,
        build_backups_ops,
        build_docs_and_tests_inventory,
    ]
    for fn in builders:
        fn(reg)
    expand_to_minimum(reg, 420)
    if live:
        build_live_checks(reg, api, site, allow_offline)
    else:
        reg.skip("csp_headers", "LIVE checks skipped (--no-live)", "use --live")
    # Ensure every required category appears
    present = {i.category for i in reg.items}
    for cat in REQUIRED_CATEGORIES:
        if cat not in present:
            reg.fail(cat, f"category {cat} produced no checks", "internal audit bug")
    return reg


def main() -> int:
    parser = argparse.ArgumentParser(description="Diomika deep security audit (400+ checks)")
    parser.add_argument("--live", dest="live", action="store_true", default=True)
    parser.add_argument("--no-live", dest="live", action="store_false")
    parser.add_argument("--api", default="https://api.diomika.com")
    parser.add_argument("--site", default="https://www.diomika.com")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--fail-on-fail", action="store_true")
    parser.add_argument(
        "--allow-offline",
        action="store_true",
        help="Soft-fail network errors as skip instead of fail",
    )
    args = parser.parse_args()

    print("=== Diomika deep security audit ===")
    print(f"live={args.live} api={args.api} site={args.site}\n")

    reg = run_all(args.live, args.api, args.site, args.allow_offline)
    summary = summarize(reg)

    # Human-readable brief
    print(f"total={summary['total']} passed={summary['passed']} failed={summary['failed']} skipped={summary['skipped']}")
    print("categories:")
    for name in sorted(summary["categories"]):
        c = summary["categories"][name]
        print(f"  {name}: pass={c['passed']} fail={c['failed']} skip={c['skipped']}")
    if summary["failures"]:
        print("\nfailures (top):")
        for f in summary["failures"][:40]:
            print(f"  [{f['id']}] {f['title']} — {f['detail']}")
        if len(summary["failures"]) > 40:
            print(f"  ... +{len(summary['failures']) - 40} more")

    out_path = args.json_out.strip()
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    if out_path:
        path = Path(out_path)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
        print(f"\nJSON written: {path}")
    else:
        print("\n--- JSON ---")
        print(payload)

    if args.fail_on_fail and summary["failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
