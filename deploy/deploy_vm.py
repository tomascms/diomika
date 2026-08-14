#!/usr/bin/env python3
"""
Deploy API permanente para VM remota via SSH (GCP e2-micro Always Free).

Requisitos no .env local:
  REMOTE_VM_SSH=USER@IP_PUBLICO
  CLOUDFLARE_TUNNEL_TOKEN=...

Uso:
  python deploy/deploy_vm.py
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.is_file():
        raise SystemExit("ERRO: .env em falta na raiz do repo")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def update_tunnel_origin(env: dict[str, str], origin: str) -> None:
    token = env.get("CLOUDFLARE_API_TOKEN", "")
    account = env.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not token or not account:
        print("! Sem CLOUDFLARE_API_TOKEN/ACCOUNT_ID — actualiza o origin no Zero Trust manualmente")
        return
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/cfd_tunnel?is_deleted=false",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        tunnels = json.load(r).get("result") or []
    tunnel = next((t for t in tunnels if t.get("name") == "diomika-api"), tunnels[0] if tunnels else None)
    if not tunnel:
        raise SystemExit("ERRO: tunnel diomika-api nao encontrado")
    tid = tunnel["id"]
    body = {
        "config": {
            "ingress": [
                {"hostname": "api.diomika.com", "service": origin, "originRequest": {}},
                {"service": "http_status:404"},
            ]
        }
    }
    data = json.dumps(body).encode()
    req2 = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/cfd_tunnel/{tid}/configurations",
        data=data,
        method="PUT",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req2, timeout=30) as r2:
        ok = json.load(r2).get("success")
    print(f"OK tunnel origin -> {origin} (success={ok})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-tunnel-origin", default="http://127.0.0.1:8000")
    parser.add_argument("--skip-tunnel-update", action="store_true")
    args = parser.parse_args()

    env = load_env()
    ssh = (env.get("REMOTE_VM_SSH") or "").strip()
    if not ssh:
        print("ERRO: define REMOTE_VM_SSH no .env (ex: tomas@34.x.x.x)")
        print("  GCP Always Free: e2-micro em us-central1 — docs/FREE_STACK.md")
        return 1

    if not (env.get("CLOUDFLARE_TUNNEL_TOKEN") or "").strip():
        print("ERRO: CLOUDFLARE_TUNNEL_TOKEN em falta")
        return 1

    required = [
        "DIOMIKA_ENV=production",
        "TRUST_PROXY=1",
        "SUPABASE_STORAGE_PRIVATE=1",
        "API_BASE_URL=https://api.diomika.com",
        "ALLOWED_HOSTS=api.diomika.com",
    ]
    text = (ROOT / ".env").read_text(encoding="utf-8")
    for item in required:
        key = item.split("=", 1)[0]
        if f"{key}=" not in text:
            text += f"\n{item}\n"

    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=accept-new", ssh]
    scp_base = ["scp", "-o", "StrictHostKeyChecking=accept-new"]

    print("\n=== 1) Bootstrap Docker + swap na VM ===\n")
    bootstrap = (
        "set -euo pipefail; "
        "if ! swapon --show | grep -q .; then "
        "  sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048; "
        "  sudo chmod 600 /swapfile; sudo mkswap /swapfile; sudo swapon /swapfile; "
        "  grep -q swapfile /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab; "
        "fi; "
        "if ! command -v docker >/dev/null 2>&1; then curl -fsSL https://get.docker.com | sh; "
        "sudo usermod -aG docker $USER || true; fi; "
        "mkdir -p $HOME/diomika"
    )
    if subprocess.run([*ssh_base, bootstrap], cwd=ROOT).returncode != 0:
        print("ERRO bootstrap SSH")
        return 1

    print("\n=== 2) Enviar codigo local (repo privado — sem git clone) ===\n")
    with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".tar") as tmp_tar:
        tar_path = tmp_tar.name
    try:
        excludes = [
            "--exclude=.git",
            "--exclude=node_modules",
            "--exclude=frontend-web/node_modules",
            "--exclude=backoffice-desktop/node_modules",
            "--exclude=backoffice-desktop/release",
            "--exclude=__pycache__",
            "--exclude=.venv",
            "--exclude=*.pyc",
            "--exclude=.env",
        ]
        tar_cmd = ["tar", "-cf", tar_path, *excludes, "-C", str(ROOT), "."]
        if subprocess.run(tar_cmd, cwd=ROOT).returncode != 0:
            print("ERRO a criar tarball local")
            return 1
        if subprocess.run([*scp_base, tar_path, f"{ssh}:/tmp/diomika-deploy.tar"], cwd=ROOT).returncode != 0:
            print("ERRO scp tarball")
            return 1
        unpack = (
            "set -euo pipefail; "
            "mkdir -p $HOME/diomika; "
            "tar -xf /tmp/diomika-deploy.tar -C $HOME/diomika; "
            "rm -f /tmp/diomika-deploy.tar"
        )
        if subprocess.run([*ssh_base, unpack], cwd=ROOT).returncode != 0:
            print("ERRO unpack na VM")
            return 1
    finally:
        try:
            os.unlink(tar_path)
        except OSError:
            pass

    print("\n=== 3) Enviar .env de producao ===\n")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".env") as tmp:
        tmp.write(text)
        tmp_path = tmp.name
    try:
        ok_scp = subprocess.run([*scp_base, tmp_path, f"{ssh}:~/diomika/.env"], cwd=ROOT).returncode == 0
    finally:
        os.unlink(tmp_path)
    if not ok_scp:
        print("ERRO scp .env")
        return 1

    if not args.skip_tunnel_update:
        print("\n=== 4) Tunnel origin para Docker host :8000 ===\n")
        update_tunnel_origin(env, args.update_tunnel_origin)

    print("\n=== 5) docker compose --profile tunnel ===\n")
    up = (
        "set -euo pipefail; cd $HOME/diomika; "
        "sudo docker compose --env-file .env -f deploy/docker-compose.free.yml --profile tunnel up -d --build; "
        "sleep 8; curl -sf http://127.0.0.1:8000/health; echo"
    )
    if subprocess.run([*ssh_base, up], cwd=ROOT).returncode != 0:
        print("ERRO compose na VM")
        return 1

    print("\n=== 6) Smoke publico ===\n")
    try:
        req = urllib.request.Request(
            "https://api.diomika.com/health",
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; DiomikaDeploy/1.0)",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            print("live", r.status, r.read().decode("utf-8", errors="replace"))
            ok = r.status == 200
    except Exception as exc:
        print("live FAIL", exc)
        ok = False

    if ok:
        print("\nOK API permanente na VM.")
        return 0
    print("\nTunnel pode estar a propagar — retesta: curl https://api.diomika.com/health")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
