"""Queries — catálogo de assentos (detalhe de modelo para encomendas)."""
from __future__ import annotations

import json

from core.database import get_db
from core.visibility import is_visible


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
    assento_rows = [
        a
        for a in (data.get("assento") or [])
        if a.get("visibilidade", True) and str(a.get("ean") or "").strip()
    ]
    assento_rows.sort(key=lambda a: str(a.get("altura") or ""))
    data["assento"] = assento_rows
    data["modelo_cores"] = _modelo_cores(data)
    if not assento_rows or not data["modelo_cores"]:
        return None
    alturas = data.get("alturas") or []
    if isinstance(alturas, str):
        try:
            alturas = json.loads(alturas)
        except Exception:
            alturas = []
    data["alturas"] = sorted(alturas)
    return data
