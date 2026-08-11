"""Enriquecer linhas de pedido para PDF (EAN → nome modelo/cor)."""
from __future__ import annotations

from core.cqrs.queries.catalog import resolve_line_display


def enrich_order_lines(linhas: list[dict]) -> list[dict]:
    out = []
    for linha in linhas:
        info = resolve_line_display(linha["ean"], linha["numero_cor"], linha.get("altura"))
        out.append({**linha, **info})
    return out
