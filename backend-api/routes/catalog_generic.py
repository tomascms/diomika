"""Rotas genéricas de catálogo — uma URL por tipo registado em CATALOG_TYPES."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from core.auth import require_catalog_role
from core.local_only import admin_must_be_local
from core.cache import catalog_cache_ttl, get_or_set
from core.catalog_service import catalogue_for_category, model_detail_for_slugs, model_detail_for_tipo
from core.database import get_db
from models.catalog_registry import (
    CATALOG_TYPES,
    admin_merged_select_query,
    all_model_tables,
    all_product_tables,
    catalog_metadata,
    is_valid_storefront_tipo,
    is_valid_tipo,
    list_select_query,
    model_table_for_tipo,
    product_table_for_tipo,
    tipo_for_table,
    tipo_label,
)
from models.catalog_views import is_catalog_view
from models.schemas import aggregated_tipos_for_tipo

logger = logging.getLogger("diomika-api")

router = APIRouter(prefix="/catalogo", tags=["Catálogo"])


@router.get("/meta")
async def get_catalog_meta():
    """Tipos, tabelas e modos de vitrine — derivado de CATALOG_TYPES."""
    ttl = catalog_cache_ttl()
    return await asyncio.to_thread(get_or_set, "catalog:meta", float(ttl), catalog_metadata)


def _require_tipo(tipo: str) -> dict:
    if not is_valid_storefront_tipo(tipo):
        raise HTTPException(status_code=404, detail=f"Tipo «{tipo}» não registado.")
    if is_valid_tipo(tipo):
        return CATALOG_TYPES[tipo]
    return {"label": tipo, "storefront_mode": "aggregado"}


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
async def list_storefront_catalog(tipo: str, id_categoria: str, request: Request, filter_tipo: str | None = None):
    """Lista modelos para a loja (vitrine) — visível apenas."""
    _require_tipo(tipo)
    query_filters = {
        key[7:]: value
        for key, value in request.query_params.items()
        if key.startswith("filter_") and value
    }
    filter_key = "|".join(f"{k}={v}" for k, v in sorted(query_filters.items()))
    ttl = catalog_cache_ttl()
    cache_key = f"catalog:list:{tipo}:{id_categoria}:{filter_tipo or ''}:{filter_key}"

    def load():
        return catalogue_for_category(
            tipo,
            id_categoria,
            filters=query_filters or None,
            tipo_filter=filter_tipo,
        )

    try:
        return await asyncio.to_thread(get_or_set, cache_key, float(ttl), load)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Catálogo %s/%s: %s", tipo, id_categoria, exc)
        raise HTTPException(status_code=500, detail="Erro ao carregar catálogo") from exc


@router.get("/{tipo}/modelo-detalhe/slug/{category_slug}/{model_slug}")
async def get_storefront_model_detail_by_slug(tipo: str, category_slug: str, model_slug: str):
    _require_tipo(tipo)
    ttl = catalog_cache_ttl()
    cache_key = f"catalog:modelo-slug:{tipo}:{category_slug}:{model_slug}"

    def load():
        data = model_detail_for_slugs(tipo, category_slug, model_slug)
        if not data:
            raise HTTPException(status_code=404, detail="Modelo não encontrado")
        return data

    try:
        return await asyncio.to_thread(get_or_set, cache_key, float(ttl), load)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Detalhe modelo slug %s/%s/%s: %s", tipo, category_slug, model_slug, exc)
        raise HTTPException(status_code=500, detail="Erro ao carregar modelo") from exc


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


def _fetch_merged_table_page(
    *,
    view_key: str,
    ptable: str,
    visible_only: bool,
    per_table: int,
    categoria_id: str | None,
    modelo_id: str | None,
) -> list[dict]:
    db = get_db()
    query = db.table(ptable).select(admin_merged_select_query(ptable))
    if visible_only:
        query = query.eq("visibilidade", True)
    if categoria_id and view_key == "modelos":
        query = query.eq("id_categoria", categoria_id)
    if categoria_id and view_key == "produtos":
        mt = model_table_for_tipo(tipo_for_table(ptable))
        if mt:
            model_rows = (
                db.table(mt)
                .select("id")
                .eq("id_categoria", categoria_id)
                .execute()
                .data
                or []
            )
            model_ids = [str(row["id"]) for row in model_rows if row.get("id")]
            if not model_ids:
                return []
            query = query.in_("id_modelo", model_ids)
    if modelo_id and view_key == "produtos":
        query = query.eq("id_modelo", modelo_id)
    try:
        try:
            res = query.order("created_at", desc=True).limit(per_table).execute()
        except TypeError:
            res = query.order("created_at", ascending=False).limit(per_table).execute()
    except Exception as exc:
        logger.error("Merged list %s/%s: %s", view_key, ptable, exc)
        return []
    familia = tipo_label(tipo_for_table(ptable))
    mt = model_table_for_tipo(tipo_for_table(ptable))
    out: list[dict] = []
    for item in res.data or []:
        item["_ptable"] = ptable
        item["_tipo_catalogo"] = tipo_for_table(ptable)
        item["_familia_label"] = familia
        cat_nome = None
        if isinstance(item.get("categories"), dict):
            cat_nome = item["categories"].get("nome")
        elif mt and isinstance(item.get(mt), dict):
            emb_cat = item[mt].get("categories")
            if isinstance(emb_cat, dict):
                cat_nome = emb_cat.get("nome")
        item["_categoria_label"] = cat_nome or familia
        out.append(item)
    return out


@router.get(
    "/admin/merged/{view_key}",
    dependencies=[Depends(admin_must_be_local), Depends(require_catalog_role)],
)
async def admin_merged_list(
    view_key: str,
    visible_only: bool = False,
    limit: int = 80,
    offset: int = 0,
    categoria_id: str | None = None,
    modelo_id: str | None = None,
    tipo_catalogo: str | None = None,
):
    """Lista merged para backoffice (modelos ou produtos) — paginada."""
    if not is_catalog_view(view_key):
        raise HTTPException(status_code=400, detail="Vista inválida")
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    # Página pequena: cada tabela só precisa de `limit` linhas mais recentes para o merge.
    per_table = min(max(limit, 20), 60) if offset == 0 else min(limit + offset, 100)

    if tipo_catalogo and aggregated_tipos_for_tipo(tipo_catalogo):
        tables = (
            [model_table_for_tipo(t) for t in aggregated_tipos_for_tipo(tipo_catalogo) or []]
            if view_key == "modelos"
            else [product_table_for_tipo(t) for t in aggregated_tipos_for_tipo(tipo_catalogo) or []]
        )
        tables = [t for t in tables if t]
    elif tipo_catalogo and is_valid_tipo(tipo_catalogo):
        physical = model_table_for_tipo(tipo_catalogo) if view_key == "modelos" else product_table_for_tipo(tipo_catalogo)
        tables = [physical] if physical else []
    else:
        tables = all_model_tables() if view_key == "modelos" else all_product_tables()

    tables = [t for t in tables if t]
    tasks = [
        asyncio.to_thread(
            _fetch_merged_table_page,
            view_key=view_key,
            ptable=ptable,
            visible_only=visible_only,
            per_table=per_table,
            categoria_id=categoria_id,
            modelo_id=modelo_id,
        )
        for ptable in tables
    ]
    chunks = await asyncio.gather(*tasks)
    rows: list[dict] = []
    for chunk in chunks:
        rows.extend(chunk)
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    page = rows[offset : offset + limit]
    return {"items": page, "limit": limit, "offset": offset, "count": len(page), "total_approx": len(rows)}
