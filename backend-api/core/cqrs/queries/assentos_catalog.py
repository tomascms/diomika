"""Queries — catálogo de assentos."""
from __future__ import annotations

import json
from dataclasses import dataclass

from core.database import get_db
from core.visibility import is_visible


@dataclass
class AssentoCatalogueQuery:
    id_categoria: str


def _modelo_cores(data: dict) -> list[dict]:
    """Cores próprias do modelo (sempre id_modelo)."""
    cores = [c for c in (data.get("modelo_cores") or []) if c.get("visibilidade", True)]
    cores.sort(key=lambda c: c.get("numero", 0))
    return cores


def _attach_cores(rows: list[dict]) -> None:
    if not rows:
        return
    db = get_db()
    model_ids = [str(r["id"]) for r in rows if r.get("id")]
    by_model: dict[str, list] = {mid: [] for mid in model_ids}
    if model_ids:
        for cor in (
            db.table("modelo_assento_cores")
            .select("id_modelo, numero, nome, imagem, visibilidade")
            .in_("id_modelo", model_ids)
            .execute()
            .data
            or []
        ):
            mid = str(cor.get("id_modelo") or "")
            if mid in by_model:
                by_model[mid].append(cor)
    for row in rows:
        row["modelo_cores"] = _modelo_cores({"modelo_cores": by_model.get(str(row.get("id") or ""), [])})


def catalogue_assento_models(q: AssentoCatalogueQuery):
    db = get_db()
    res = (
        db.table("modelos_assentos")
        .select(
            "*, categories(nome, carrinho_step, carrinho_min, slug, tipo_catalogo), "
            "assento(ean, barcode_url, visibilidade, altura)"
        )
        .eq("id_categoria", q.id_categoria)
        .eq("visibilidade", True)
        .order("nome")
        .execute()
    )
    rows = res.data or []
    _attach_cores(rows)
    out = []
    for row in rows:
        assento_rows = [a for a in (row.get("assento") or []) if a.get("visibilidade", True)]
        if not assento_rows:
            continue
        assento_rows.sort(key=lambda a: str(a.get("altura") or ""))
        row["assento"] = assento_rows
        row["modelo_cores"] = _modelo_cores(row)
        out.append(row)
    return out


def assento_model_detail(id_modelo: str):
    db = get_db()
    res = (
        db.table("modelos_assentos")
        .select("*, categories(*), assento(*)")
        .eq("id", id_modelo)
        .single()
        .execute()
    )
    data = res.data
    if not data:
        return None
    if not is_visible(data):
        return None
    _attach_cores([data])
    assento_rows = [a for a in (data.get("assento") or []) if a.get("visibilidade", True)]
    assento_rows.sort(key=lambda a: str(a.get("altura") or ""))
    data["assento"] = assento_rows
    data["modelo_cores"] = _modelo_cores(data)
    alturas = data.get("alturas") or []
    if isinstance(alturas, str):
        try:
            alturas = json.loads(alturas)
        except Exception:
            alturas = []
    data["alturas"] = sorted(alturas)
    return data


def resolve_assento_line(ean: str, numero_cor: int, altura: str | None = None) -> dict:
    db = get_db()
    row = db.table("assento").select("*, modelos_assentos(*)").eq("ean", ean).limit(1).execute()
    item = (row.data or [None])[0]
    if not item:
        return {}
    modelo = item.get("modelos_assentos") or {}
    if isinstance(modelo, list) and modelo:
        modelo = modelo[0]
    detail = assento_model_detail(str(item["id_modelo"])) or {}
    cor_nome = f"Cor {numero_cor}"
    for c in detail.get("modelo_cores") or []:
        if int(c.get("numero", 0)) == int(numero_cor):
            cor_nome = c.get("nome") or cor_nome
            break
    return {
        "ean": ean,
        "numero_cor": numero_cor,
        "altura": altura or "",
        "modelo": modelo.get("nome", ""),
        "dimensoes": altura or "",
        "cor_nome": cor_nome,
        "tipo_produto": "assento",
    }
