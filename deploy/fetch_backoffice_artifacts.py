#!/usr/bin/env python3
"""Descarrega artifacts do workflow Backoffice release e copia para cliente-backoffice."""
from __future__ import annotations

import io
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-api"))
from core.env_loader import load_project_env  # noqa: E402

load_project_env()
RUN_ID = 31914695733
ARTIFACTS = {
    "mac": 9254608296,
    "linux": 9254603132,
}
NAMES = {
    "mac": "Diomika-Backoffice-1.0.0-mac.dmg",
    "linux": "Diomika-Backoffice-1.0.0-linux.AppImage",
}
DEST_DIRS = [
    ROOT / "cliente-backoffice",
    ROOT.parent / "cliente-backoffice",
]


def github_token() -> str:
    import os

    for key in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git credential fill falhou")
    creds: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            creds[k.strip()] = v.strip()
    token = creds.get("password") or creds.get("username") or ""
    if not token:
        raise RuntimeError("Sem token GitHub — faz login git ou define GITHUB_TOKEN")
    return token


def download_artifact(artifact_id: int, token: str) -> bytes:
    url = f"https://api.github.com/repos/tomascms/diomika/actions/artifacts/{artifact_id}/zip"
    req = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "diomika-fetch-artifacts",
    })
    with urlopen(req, timeout=300) as resp:
        return resp.read()


def extract_named(data: bytes, expected_name: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            base = Path(info.filename).name
            if base == expected_name:
                return zf.read(info.filename)
    raise FileNotFoundError(f"{expected_name} não encontrado no zip")


def main() -> int:
    token = github_token()
    for key, artifact_id in ARTIFACTS.items():
        name = NAMES[key]
        print(f"Descarregar {name} …")
        blob = download_artifact(artifact_id, token)
        payload = extract_named(blob, name)
        for dest in DEST_DIRS:
            dest.mkdir(parents=True, exist_ok=True)
            out = dest / name
            out.write_bytes(payload)
            print(f"  OK {out} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
