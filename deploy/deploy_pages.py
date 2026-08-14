#!/usr/bin/env python3
"""
Deploy beta privada — stack 100% grátis (Cloudflare Tunnel + Pages).

Uso:
  python deploy/deploy_pages.py --deploy          # tunnel API + build + Pages (se token)
  python deploy/deploy_pages.py --build --api-url URL
  python deploy/deploy_pages.py --deploy --pages-only

Requisitos:
  - cloudflared (winget install Cloudflare.cloudflared)
  - API local ou Docker
  - CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID (opcional, para Pages automático)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE = ROOT / "frontend-web"
DIST = FE / "dist"
STATE = ROOT / "deploy" / "beta.state.json"
CLOUDFLARED = Path(os.getenv("CLOUDFLARED_PATH", "cloudflared"))


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    dotenv = ROOT / ".env"
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def save_state(data: dict) -> None:
    STATE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK estado beta: {STATE}")


def build_frontend(env: dict[str, str], api_url: str, *, beta: bool = True) -> bool:
    build_env = {
        **env,
        "VITE_API_BASE_URL": api_url.rstrip("/"),
    }
    if beta:
        build_env["VITE_BETA_MODE"] = "1"
        # Turnstile: usa VITE_TURNSTILE_SITE_KEY real do .env (widget inclui *.pages.dev)
    elif not build_env.get("VITE_TURNSTILE_SITE_KEY"):
        print("ERRO: VITE_TURNSTILE_SITE_KEY em falta para build producao")
        return False
    for key in ("VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY"):
        if not build_env.get(key):
            print(f"ERRO: {key} em falta no .env")
            return False

    print("\n=== Build loja {} ===\n".format("beta (noindex)" if beta else "producao"))
    if not (FE / "node_modules").is_dir():
        subprocess.run(["npm", "ci"], cwd=FE, check=True, shell=os.name == "nt")
    subprocess.run(["npm", "run", "build"], cwd=FE, check=True, env=build_env, shell=os.name == "nt")

    beta_robots = FE / "public" / "robots-beta.txt"
    if beta and beta_robots.is_file() and DIST.is_dir():
        shutil.copy(beta_robots, DIST / "robots.txt")
    headers_prod = FE / "public" / "_headers.production"
    headers_beta = FE / "public" / "_headers"
    if DIST.is_dir():
        if beta and headers_beta.is_file():
            shutil.copy(headers_beta, DIST / "_headers")
        elif not beta and headers_prod.is_file():
            shutil.copy(headers_prod, DIST / "_headers")
    noindex = DIST / "index.html"
    if beta and noindex.is_file():
        html = noindex.read_text(encoding="utf-8")
        if "noindex" not in html:
            html = html.replace(
                "<head>",
                '<head>\n    <meta name="robots" content="noindex, nofollow">',
                1,
            )
            noindex.write_text(html, encoding="utf-8")

    verify = subprocess.run(
        [sys.executable, str(ROOT / "deploy" / "verify_bundle_secrets.py")],
        cwd=ROOT,
    )
    if verify.returncode != 0:
        return False
    return True


def deploy_cloudflare_pages(dist: Path, project: str, env: dict[str, str]) -> str | None:
    token = (env.get("CLOUDFLARE_API_TOKEN") or "").strip()
    account = (env.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    if not token or not account:
        print("! Pages manual: Cloudflare Dashboard -> Upload dist/ ou Connect GitHub")
        return env.get("BETA_PAGES_URL") or None
    branch = (env.get("PAGES_BRANCH") or "production").strip()
    # Deploy from frontend-web so sibling `functions/` (path probes 404) is included.
    dist_arg = "dist" if dist.resolve() == DIST.resolve() else str(dist.resolve())
    cmd = [
        "npx",
        "--yes",
        "wrangler@3",
        "pages",
        "deploy",
        dist_arg,
        f"--project-name={project}",
        f"--branch={branch}",
        "--commit-dirty=true",
    ]
    run_env = {
        **os.environ,
        **env,
        "CLOUDFLARE_API_TOKEN": token,
        "CLOUDFLARE_ACCOUNT_ID": account,
        "NODE_OPTIONS": os.environ.get("NODE_OPTIONS", "--use-system-ca"),
    }
    print("\n=== Deploy Cloudflare Pages ===\n")
    proc = subprocess.run(cmd, cwd=FE, capture_output=True, text=True, env=run_env, shell=os.name == "nt")
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        print(out[:2000])
        return None
    match = re.search(r"https://[a-z0-9-]+\.pages\.dev", out)
    url = match.group(0) if match else env.get("BETA_PAGES_URL")
    if url:
        print(f"OK Pages: {url}")
    return url


API_PORT = int(os.getenv("BETA_API_PORT", "8001"))


def api_local_url() -> str:
    return f"http://127.0.0.1:{API_PORT}"


def api_healthy(base: str | None = None, timeout: float = 2.0) -> bool:
    base = base or api_local_url()
    try:
        with urllib.request.urlopen(f"{base.rstrip('/')}/health", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_api(env: dict[str, str], *, detach: bool = False) -> subprocess.Popen | None:
    local = api_local_url()
    if api_healthy(local):
        print(f"OK API ja online em {local}")
        return None
    run_env = {
        **os.environ,
        **env,
        "DIOMIKA_ENV": "production",
        "DIOMIKA_BETA": "1",
        "TRUST_PROXY": "1",
        "TRUSTED_PROXY_IPS": env.get("TRUSTED_PROXY_IPS") or "127.0.0.1,::1",
        "RUN_EMBEDDED_WORKERS": "true",
        "PYTHONPATH": str(ROOT / "backend-api"),
    }
    # Nunca auto-definir DIOMIKA_SSL_INSECURE — so herda se o .env tiver flag explicita
    print(f"\n=== A arrancar API beta em {local} ===\n")
    if detach and os.name == "nt":
        api_log = ROOT / "deploy" / "beta-api.log"
        env_parts = " ".join(f"$env:{k}='{v}'" for k, v in run_env.items() if k.startswith(("DIOMIKA_", "TRUST_", "RUN_", "PYTHON", "SUPABASE", "API_", "MAIL", "TURNSTILE", "IMAP", "OUTBOX", "EMAIL")))
        ps = (
            f"{env_parts}; "
            f"$p = Start-Process -FilePath '{sys.executable}' "
            f"-ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','{API_PORT}' "
            f"-WorkingDirectory '{ROOT / 'backend-api'}' "
            f"-RedirectStandardOutput '{api_log}' -RedirectStandardError '{api_log}' "
            f"-PassThru -WindowStyle Hidden; $p.Id"
        )
        proc_id = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps], text=True).strip()
        print(f"OK API pid={proc_id}")
    else:
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
            cwd=ROOT / "backend-api",
            env=run_env,
        )
    for _ in range(45):
        if api_healthy(local):
            print(f"OK API {local}/health")
            return None
        time.sleep(1)
    raise RuntimeError("API nao arrancou — ve deploy/beta-api.log")


def _popen_kwargs(detach: bool) -> dict:
    if detach and os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
    return {}


def start_quick_tunnel(local_url: str, label: str, *, detach: bool = False) -> tuple[subprocess.Popen | None, str]:
    log = ROOT / "deploy" / f"cloudflared-{label}.log"
    log.write_text("", encoding="utf-8")
    pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    cf = str(CLOUDFLARED)

    if detach and os.name == "nt":
        ps = (
            f"$p = Start-Process -FilePath '{cf}' "
            f"-ArgumentList 'tunnel','--url','{local_url}','--no-autoupdate' "
            f"-RedirectStandardOutput '{log}' -RedirectStandardError '{log}' "
            f"-PassThru -WindowStyle Hidden; $p.Id"
        )
        proc_id = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps], text=True).strip()
        print(f"OK cloudflared {label} pid={proc_id}")
        deadline = time.time() + 45
        while time.time() < deadline:
            text = log.read_text(encoding="utf-8", errors="replace")
            match = pattern.search(text)
            if match:
                print(f"OK tunnel {label}: {match.group(0)}")
                return None, match.group(0)
            time.sleep(0.5)
        raise RuntimeError(f"Tunnel {label} falhou — ve {log}")

    log_handle = open(log, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [cf, "tunnel", "--url", local_url, "--no-autoupdate"],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 45
    while time.time() < deadline:
        text = log.read_text(encoding="utf-8", errors="replace")
        match = pattern.search(text)
        if match:
            url = match.group(0)
            print(f"OK tunnel {label}: {url}")
            return proc, url
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    log_handle.close()
    raise RuntimeError(f"Tunnel {label} falhou — ve {log}")


def start_static_server(port: int = 8788, *, detach: bool = False) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(ROOT / "deploy" / "static_server_secure.py"), "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **_popen_kwargs(detach),
    )


def ensure_cloudflared() -> None:
    if shutil.which(str(CLOUDFLARED)):
        return
    print("A instalar cloudflared (winget)…")
    subprocess.run(
        ["winget", "install", "--id", "Cloudflare.cloudflared", "-e", "--accept-package-agreements", "--accept-source-agreements"],
        check=False,
    )
    if not shutil.which("cloudflared"):
        raise RuntimeError("cloudflared em falta — winget install Cloudflare.cloudflared")


def deploy_full(env: dict[str, str], pages_project: str, *, detach: bool = False) -> int:
    ensure_cloudflared()
    api_proc = start_api(env, detach=detach)
    tunnel_api_proc, api_public = start_quick_tunnel(api_local_url(), "api", detach=detach)

    if not build_frontend(env, api_public):
        return 1

    pages_url = deploy_cloudflare_pages(DIST, pages_project, env)
    static_proc = None
    tunnel_web_proc = None
    if not pages_url:
        static_proc = start_static_server(8788, detach=detach)
        time.sleep(2)
        tunnel_web_proc, pages_url = start_quick_tunnel("http://127.0.0.1:8788", "loja", detach=detach)

    state = {
        "api_url": api_public,
        "pages_url": pages_url,
        "mode": "pages" if "pages.dev" in (pages_url or "") else "tunnel",
        "private": True,
        "noindex": True,
    }
    save_state(state)

    print(
        f"""
=== Beta privada online (grátis) ===

  Loja:  {pages_url}
  API:   {api_public}

  Testes:
    python deploy/security_test.py --url {api_public}
    python deploy/check.py --production

  Backoffice PC:
    API_BASE_URL={api_public}

  Nota: URLs trycloudflare/pages.dev — não partilhar publicamente.
  Endgame produção: docs/FREE_STACK.md

  Tunnels activos — mantém este terminal/processo. Ctrl+C para parar.
"""
    )
    if detach:
        return 0
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        for p in (tunnel_api_proc, tunnel_web_proc, static_proc, api_proc):
            if p and p.poll() is None:
                p.terminate()
    return 0


def pages_deploy_only(env: dict[str, str], project: str, api_url: str) -> int:
    if not DIST.is_dir() or not (DIST / "index.html").is_file():
        print("ERRO: dist/ em falta — corre primeiro: python deploy/deploy_pages.py --build --api-url URL")
        return 1
    pages_url = deploy_cloudflare_pages(DIST, project, env)
    if not pages_url:
        return 1
    pages_url = pages_url.rstrip("/")
    state = {
        "api_url": api_url.rstrip("/"),
        "pages_url": pages_url,
        "mode": "pages+beta",
        "private": False,
        "noindex": True,
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_state(state)
    print(f"\nOK loja: {pages_url}\nOK API no bundle: {api_url}\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy beta privada Diomika (grátis)")
    parser.add_argument("--deploy", action="store_true", help="Tunnel + build + Pages")
    parser.add_argument("--pages-deploy", action="store_true", help="Deploy dist/ para Cloudflare Pages")
    parser.add_argument("--detach", action="store_true", help="Sair após deploy (tunnels ficam activos)")
    parser.add_argument("--build", action="store_true", help="Só build frontend")
    parser.add_argument("--api-url", default=os.getenv("BETA_API_URL", ""))
    parser.add_argument(
        "--pages-project",
        default=os.getenv("PAGES_PROJECT") or os.getenv("BETA_PAGES_PROJECT") or "diomika-loja",
    )
    args = parser.parse_args()
    env = load_env()

    if args.pages_deploy:
        api = args.api_url or env.get("BETA_API_URL") or ""
        if not api:
            print("ERRO: --api-url ou BETA_API_URL em falta")
            return 1
        return pages_deploy_only(env, args.pages_project, api)

    if args.deploy:
        if os.name == "nt":
            print("\n=== Beta Windows (recomendado): deploy/beta_pages.ps1 ===\n")
            ps1 = ROOT / "deploy" / "beta_pages.ps1"
            if not ps1.is_file():
                ps1 = ROOT / "deploy" / "beta_run.ps1"
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                cwd=ROOT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            )
            print(f"OK beta_run.ps1 pid={proc.pid}")
            print("Aguarda ~20s e abre deploy/beta.state.json")
            for _ in range(45):
                if STATE.is_file():
                    try:
                        data = json.loads(STATE.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        data = {}
                    if data.get("api_url") and data.get("pages_url"):
                        print(f"\n  Loja: {data['pages_url']}\n  API:  {data['api_url']}\n")
                        return 0
                time.sleep(2)
            print("URLs ainda a propagar — corre: type deploy\\beta.state.json")
            return 0
        return deploy_full(env, args.pages_project, detach=args.detach)
    if args.build:
        api = args.api_url or env.get("BETA_API_URL") or "https://api.diomika.com"
        return 0 if build_frontend(env, api) else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
