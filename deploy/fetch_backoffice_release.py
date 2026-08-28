#!/usr/bin/env python3
"""Descarrega instaladores mac/linux/windows do GitHub Release publico cliente."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TAG = "backoffice-cliente-latest"
BASE = f"https://github.com/tomascms/diomika/releases/download/{TAG}"
# Windows passa a ZIP (menos falsos positivos de antivirus que o .exe portatil).
FILES = [
    "Diomika-Backoffice-1.0.0-windows.zip",
    "Diomika-Backoffice-1.0.0-mac.dmg",
    "Diomika-Backoffice-1.0.0-linux.AppImage",
]
HELPERS = [
    ROOT / "backoffice-desktop" / "packaging" / "Abrir-Windows.cmd",
    ROOT / "backoffice-desktop" / "packaging" / "Abrir-Windows.ps1",
    ROOT / "backoffice-desktop" / "packaging" / "LEIA-ME.txt",
]
DEST_DIRS = [
    ROOT / "cliente-backoffice",
    ROOT.parent / "cliente-backoffice",
]


def download(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "diomika-fetch-release"})
    with urlopen(req, timeout=300) as resp:
        return resp.read()


def main() -> int:
    ok = 0
    for name in FILES:
        url = f"{BASE}/{name}"
        print(f"Descarregar {name} …")
        try:
            data = download(url)
        except Exception as exc:
            print(f"  AVISO: {exc}")
            continue
        for dest in DEST_DIRS:
            dest.mkdir(parents=True, exist_ok=True)
            out = dest / name
            out.write_bytes(data)
            print(f"  OK {out} ({len(data)} bytes)")
        ok += 1
    if ok == 0:
        print("ERRO: nenhum ficheiro descarregado — aguarda o workflow Backoffice release terminar.")
        return 1

    for dest in DEST_DIRS:
        dest.mkdir(parents=True, exist_ok=True)
        for helper in HELPERS:
            if helper.is_file():
                shutil.copy2(helper, dest / helper.name)
                print(f"  Helper {dest / helper.name}")
        for old in dest.glob("Diomika-Backoffice-*-windows.exe"):
            try:
                old.unlink()
                print(f"  Removido legado: {old}")
            except OSError as exc:
                print(f"  AVISO ao remover {old}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
