"""Utilidades para ler/escrever .env sem expor valores."""
from __future__ import annotations

from pathlib import Path


def load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def update_env_file(path: Path, updates: dict[str, str]) -> list[str]:
    """Actualiza chaves no .env. Devolve lista de chaves alteradas."""
    if not path.is_file():
        path.write_text("", encoding="utf-8")
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    out: list[str] = []
    changed: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_val = updates[key]
                if not line.startswith(f"{key}=") or line.split("=", 1)[1].strip().strip('"').strip("'") != new_val:
                    changed.append(key)
                out.append(f"{key}={new_val}")
                seen.add(key)
                continue
        out.append(line)

    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
            changed.append(key)

    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return changed
