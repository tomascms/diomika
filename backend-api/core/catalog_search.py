"""Pesquisa unificada no catálogo público."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.catalog_storefront import models_detail_map_for_tipo
from core.database import get_db
from core.visibility import is_visible
from models.catalog_registry import CATALOG_TYPES

logger = logging.getLogger("diomika-api")


def _model_cover_path(model: dict) -> str:
    cores = [c for c in (model.get("modelo_cores") or []) if is_visible(c)]
    cores.sort(key=lambda c: c.get("numero", 0))
    return str((cores[0] or {}).get("imagem") or "")


def _search_models_by_name(q: str, *, limit: int) -> list[dict]:
    needle = q.strip()
    if len(needle) < 2:
        return []

    db = get_db()
    per_table = max(8, limit // max(len(CATALOG_TYPES), 1) + 1)
    out: list[dict] = []

    def _query_tipo(tipo: str, cfg: dict) -> list[dict]:
        mt = cfg["model_table"]
        try:
            res = (
                db.table(mt)
                .select("id, nome, slug, visibilidade, id_categoria, categories(id, nome, slug, tipo_catalogo)")
                .eq("visibilidade", True)
                .or_(f"nome.ilike.%{needle}%,slug.ilike.%{needle}%")
                .limit(per_table)
                .execute()
            )
        except Exception as exc:
            logger.debug("Search %s: %s", mt, exc)
            return []
        rows: list[dict] = []
        ids = [str(row["id"]) for row in (res.data or []) if row.get("id")]
        details = models_detail_map_for_tipo(tipo, ids)
        for row in res.data or []:
            cat = row.get("categories") or {}
            if not cat.get("id"):
                continue
            detail = details.get(str(row["id"]))
            if not detail:
                continue
            rows.append(
                {
                    "model": detail,
                    "category": cat,
                    "cover_path": _model_cover_path(detail),
                    "_tipo_catalogo": tipo,
                }
            )
        return rows

    with ThreadPoolExecutor(max_workers=min(5, len(CATALOG_TYPES))) as pool:
        futures = [pool.submit(_query_tipo, tipo, cfg) for tipo, cfg in CATALOG_TYPES.items()]
        for fut in as_completed(futures):
            out.extend(fut.result())

    out.sort(key=lambda r: str((r.get("model") or {}).get("nome") or ""))
    return out[:limit]


def _search_by_ean(q: str, *, limit: int) -> list[dict]:
    needle = q.strip()
    if len(needle) < 3:
        return []
    db = get_db()
    try:
        res = (
            db.table("catalog_ean_lookup")
            .select("tipo, id_modelo, ean, product_visivel, model_visivel")
            .ilike("ean", f"%{needle}%")
            .limit(limit)
            .execute()
        )
    except Exception:
        return []

    out: list[dict] = []
    seen: set[str] = set()
    hits: list[tuple[str, str]] = []
    for row in res.data or []:
        if not row.get("product_visivel") or not row.get("model_visivel"):
            continue
        tipo = str(row.get("tipo") or "")
        mid = str(row.get("id_modelo") or "")
        key = f"{tipo}:{mid}"
        if not mid or key in seen:
            continue
        seen.add(key)
        hits.append((tipo, mid))

    by_tipo: dict[str, list[str]] = {}
    for tipo, mid in hits:
        by_tipo.setdefault(tipo, []).append(mid)
    details: dict[str, dict] = {}
    for tipo, ids in by_tipo.items():
        details.update({f"{tipo}:{k}": v for k, v in models_detail_map_for_tipo(tipo, ids).items()})

    for tipo, mid in hits:
        detail = details.get(f"{tipo}:{mid}")
        if not detail:
            continue
        cat = detail.get("categories") or {}
        out.append(
            {
                "model": detail,
                "category": cat,
                "cover_path": _model_cover_path(detail),
                "_tipo_catalogo": tipo,
            }
        )
    return out


def search_storefront(q: str, *, limit: int = 40) -> list[dict]:
    limit = min(max(limit, 1), 80)
    q = (q or "").strip()
    if not q:
        return []

    if q.isdigit() or any(c.isdigit() for c in q):
        ean_hits = _search_by_ean(q, limit=limit)
        if ean_hits:
            return ean_hits

    name_hits = _search_models_by_name(q, limit=limit)
    if name_hits:
        return name_hits

    return _search_by_ean(q, limit=limit)
