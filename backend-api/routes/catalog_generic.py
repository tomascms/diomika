"""Rotas genéricas de catálogo — uma URL por tipo registado em CATALOG_TYPES."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from core.auth import require_catalog_role
from core.local_only import admin_must_be_local
from core.cache import catalog_cache_ttl, get_or_set
from core.catalog_service import catalogue_for_category, model_detail_for_tipo
from core.database import get_db
from models.catalog_registry import (
    CATALOG_TYPES,
    all_model_tables,
    all_product_tables,
    catalog_metadata,
    is_valid_tipo,
    list_select_query,
    tipo_for_table,
    tipo_label,
)
from models.catalog_views import is_catalog_view

logger = logging.getLogger("diomika-api")

router = APIRouter(prefix="/catalogo", tags=["Catálogo"])


@router.get("/meta")
async def get_catalog_meta():
    """Tipos, tabelas e modos de vitrine — derivado de CATALOG_TYPES."""
    ttl = catalog_cache_ttl()
    return await asyncio.to_thread(get_or_set, "catalog:meta", float(ttl), catalog_metadata)


def _require_tipo(tipo: str) -> dict:
    if not is_valid_tipo(tipo):
        raise HTTPException(status_code=404, detail=f"Tipo «{tipo}» não registado.")
    return CATALOG_TYPES[tipo]


@router.get("/modelo-detalhe/{id_modelo}")
async def get_storefront_model_detail_auto(id_modelo: str):
    """Detalhe de modelo — deteta o tipo automaticamente (URLs legadas da loja)."""
    ttl = catalog_cache_ttl()
    cache_key = f"catalog:modelo-auto:{id_modelo}"

    def load():
        for tipo in CATALOG_TYPES:
            try:
                data = model_detail_for_tipo(tipo, id_modelo)
                if data:
                    data["_tipo_catalogo"] = tipo
                    data["_storefront_mode"] = CATALOG_TYPES[tipo].get("storefront_mode") or "variantes"
                    return data
            except HTTPException:
                continue
        raise HTTPException(status_code=404, detail="Modelo não encontrado")

    try:
        return await asyncio.to_thread(get_or_set, cache_key, float(ttl), load)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Detalhe modelo auto %s: %s", id_modelo, exc)
        raise HTTPException(status_code=500, detail="Erro ao carregar modelo") from exc


@router.get("/{tipo}/modelos-catalogo/{id_categoria}")
async def list_storefront_catalog(tipo: str, id_categoria: str, filter_tipo: str | None = None):
    """Lista modelos para a loja (vitrine) — visível apenas."""
    _require_tipo(tipo)
    ttl = catalog_cache_ttl()
    cache_key = f"catalog:list:{tipo}:{id_categoria}:{filter_tipo or ''}"

    def load():
        return catalogue_for_category(tipo, id_categoria, tipo_filter=filter_tipo)

    try:
        return await asyncio.to_thread(get_or_set, cache_key, float(ttl), load)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Catálogo %s/%s: %s", tipo, id_categoria, exc)
        raise HTTPException(status_code=500, detail="Erro ao carregar catálogo") from exc


@router.get("/{tipo}/modelo-detalhe/{id_modelo}")
async def get_storefront_model_detail(tipo: str, id_modelo: str):
    _require_tipo(tipo)
    ttl = catalog_cache_ttl()
    cache_key = f"catalog:modelo:{tipo}:{id_modelo}"

    def load():
        data = model_detail_for_tipo(tipo, id_modelo)
        if not data:
            raise HTTPException(status_code=404, detail="Modelo não encontrado")
        return data

    try:
        return await asyncio.to_thread(get_or_set, cache_key, float(ttl), load)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Detalhe modelo %s/%s: %s", tipo, id_modelo, exc)
        raise HTTPException(status_code=500, detail="Erro ao carregar modelo") from exc


@router.get(
    "/admin/merged/{view_key}",
    dependencies=[Depends(admin_must_be_local), Depends(require_catalog_role)],
)
def admin_merged_list(
    view_key: str,
    visible_only: bool = False,
    limit: int = 200,
    offset: int = 0,
):
    """Lista merged para backoffice (modelos ou produtos) — paginada."""
    if not is_catalog_view(view_key):
        raise HTTPException(status_code=400, detail="Vista inválida")
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)
    tables = all_model_tables() if view_key == "modelos" else all_product_tables()
    db = get_db()
    rows: list[dict] = []
    for ptable in tables:
        query = db.table(ptable).select(list_select_query(ptable))
        if visible_only:
            query = query.eq("visibilidade", True)
        try:
            try:
                res = query.order("created_at", desc=True).limit(limit + offset).execute()
            except TypeError:
                res = query.order("created_at", ascending=False).limit(limit + offset).execute()
        except Exception as exc:
            logger.error("Merged list %s/%s: %s", view_key, ptable, exc)
            continue
        categoria_label = tipo_label(tipo_for_table(ptable))
        for item in res.data or []:
            item["_ptable"] = ptable
            item["_categoria_label"] = categoria_label
            rows.append(item)
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    page = rows[offset : offset + limit]
    return {"items": page, "limit": limit, "offset": offset, "count": len(page), "total_approx": len(rows)}
