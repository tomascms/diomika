#!/usr/bin/env python3
"""Gera sitemap.xml com categorias públicas da API."""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend-web" / "public" / "sitemap.xml"
SITE = os.getenv("SITE_ORIGIN", "https://www.diomika.com").rstrip("/")
API = os.getenv("API_ORIGIN", "https://api.diomika.com").rstrip("/")

STATIC = [
    ("/", "weekly", "1.0"),
    ("/categorias", "weekly", "0.9"),
    ("/pesquisa", "weekly", "0.7"),
    ("/sobre", "monthly", "0.6"),
    ("/contacto", "monthly", "0.6"),
    ("/carrinho", "monthly", "0.4"),
    ("/privacidade", "yearly", "0.3"),
    ("/termos", "yearly", "0.3"),
    ("/cookies", "yearly", "0.3"),
]


def fetch_categories() -> list[dict]:
    req = urllib.request.Request(
        f"{API}/categorias",
        headers={"User-Agent": "DiomikaSitemap/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    today = date.today().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, freq, pri in STATIC:
        lines.append(
            f"  <url><loc>{SITE}{path}</loc><lastmod>{today}</lastmod>"
            f"<changefreq>{freq}</changefreq><priority>{pri}</priority></url>"
        )
    try:
        for cat in fetch_categories():
            slug = (cat.get("slug") or "").strip()
            if slug:
                lines.append(
                    f"  <url><loc>{SITE}/categoria/{slug}</loc><lastmod>{today}</lastmod>"
                    f"<changefreq>weekly</changefreq><priority>0.8</priority></url>"
                )
    except Exception as exc:
        print(f"AVISO: categorias API — {exc}", file=sys.stderr)
    lines.append("</urlset>")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK — {OUT} ({len(lines) - 2} URLs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
