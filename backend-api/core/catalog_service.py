"""Operações de catálogo genéricas — dispatch por CATALOG_TYPES."""
from __future__ import annotations

from fastapi import HTTPException

from core.catalog_storefront import catalogue_models_for_tipo, model_detail_for_tipo_query
from models.catalog_registry import is_valid_tipo, storefront_filters_for_model_tipo


def catalogue_for_category(tipo: str, id_categoria: str, *, tipo_filter: str | None = None) -> list:
    if not is_valid_tipo(tipo):
        raise HTTPException(status_code=404, detail=f"Tipo de catálogo «{tipo}» desconhecido.")
    filter_field = None
    if tipo_filter:
        filters = storefront_filters_for_model_tipo(tipo)
        if filters:
            filter_field = filters[0]["field"]
    return catalogue_models_for_tipo(
        tipo,
        id_categoria,
        filter_field=filter_field,
        filter_value=tipo_filter or None,
    )


def model_detail_for_tipo(tipo: str, id_modelo: str) -> dict | None:
    if not is_valid_tipo(tipo):
        raise HTTPException(status_code=404, detail=f"Tipo de catálogo «{tipo}» desconhecido.")
    return model_detail_for_tipo_query(tipo, id_modelo)
