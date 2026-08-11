"""Queries CQRS — leituras do catálogo."""
from __future__ import annotations

from dataclasses import dataclass

from core.database import get_db


@dataclass
class ListCategoriesQuery:
    visible_only: bool = True


@dataclass
class ListAlmofadasQuery:
    id_categoria: str | None = None
    visible_only: bool = True


@dataclass
class CatalogueModelsQuery:
    id_categoria: str
    tipo: str | None = None


def list_categories(q: ListCategoriesQuery):
    from core.public_api import PUBLIC_CATEGORY_FIELDS, public_category

    db = get_db()
    query = db.table("categories").select(PUBLIC_CATEGORY_FIELDS)
    if q.visible_only:
        query = query.eq("visibilidade", True)
    rows = query.order("nome").execute().data or []
    return [public_category(r) for r in rows]


def list_almofadas(q: ListAlmofadasQuery):
    db = get_db()
    query = db.table("almofada").select("*")
    if q.id_categoria:
        query = query.eq("id_categoria", q.id_categoria)
    if q.visible_only:
        query = query.eq("visibilidade", True)
    return query.execute().data


def catalogue_models(q: CatalogueModelsQuery):
    db = get_db()
    query = (
        db.table("modelos_almofadas")
        .select("*, categories(nome, carrinho_step, carrinho_min)")
        .eq("id_categoria", q.id_categoria)
        .eq("visibilidade", True)
    )
    if q.tipo in ("decorativa", "dormir"):
        query = query.eq("tipo", q.tipo)
    models = query.execute().data or []
    if not models:
        return []

    model_ids = [str(model.get("id")) for model in models if model.get("id")]
    cores_by_model: dict[str, list[dict]] = {model_id: [] for model_id in model_ids}

    if model_ids:
        cores = (
            db.table("modelo_cores")
            .select("id_modelo, numero, nome, imagem, visibilidade")
            .in_("id_modelo", model_ids)
            .execute()
            .data
            or []
        )
        for cor in cores:
            model_id = str(cor.get("id_modelo") or "")
            if model_id in cores_by_model:
                cores_by_model[model_id].append(cor)

    for model in models:
        model_id = str(model.get("id") or "")
        cores = cores_by_model.get(model_id, [])
        cores.sort(key=lambda c: c.get("numero", 0))
        model["modelo_cores"] = cores

    return models


def model_detail(id_modelo: str):
    db = get_db()
    res = (
        db.table("modelos_almofadas")
        .select("*, categories(*), almofada(*)")
        .eq("id", id_modelo)
        .single()
        .execute()
    )
    data = res.data
    if not data:
        return None
    from core.visibility import is_visible

    if not is_visible(data):
        return None
    cores = (
        db.table("modelo_cores")
        .select("*")
        .eq("id_modelo", id_modelo)
        .execute()
        .data
        or []
    )
    cores = [c for c in cores if c.get("visibilidade", True)]
    cores.sort(key=lambda c: c.get("numero", 0))
    data["modelo_cores"] = cores
    almofadas = [a for a in (data.get("almofada") or []) if a.get("visibilidade", True)]
    almofadas.sort(key=lambda a: a.get("dimensoes", ""))
    data["almofada"] = almofadas
    return data


def resolve_line_display(ean: str, numero_cor: int, altura: str | None = None) -> dict:
    """Resolve EAN + numero_cor (+ altura) para labels no email/PDF."""
    from core.catalog_storefront import resolve_product_line

    return resolve_product_line(ean, numero_cor, altura)
