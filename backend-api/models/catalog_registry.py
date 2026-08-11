"""
Registo de tipos de catálogo — lê CATALOG_TYPES de schemas.py.

Não dupliques tipos aqui: edita models/schemas.py (CATALOG_TYPES + TABLE_MAP + CATEGORY_DEFINITIONS).
"""
from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from models.schemas import CATALOG_TYPES, TIPO_CATALOGO_LABELS

CATALOGO_TIPOS = CATALOG_TYPES


def is_valid_tipo(tipo: str | None) -> bool:
    return bool(tipo and tipo in CATALOG_TYPES)


def tipo_label(tipo: str | None) -> str:
    if not tipo:
        return ""
    return CATALOG_TYPES.get(tipo, {}).get("label") or TIPO_CATALOGO_LABELS.get(tipo, tipo)


def model_table_for_tipo(tipo: str | None) -> str | None:
    if not is_valid_tipo(tipo):
        return None
    return CATALOG_TYPES[tipo]["model_table"]


def product_table_for_tipo(tipo: str | None) -> str | None:
    if not is_valid_tipo(tipo):
        return None
    return CATALOG_TYPES[tipo]["product_table"]


def model_schema_for_tipo(tipo: str | None) -> Type[BaseModel] | None:
    if not is_valid_tipo(tipo):
        return None
    return CATALOG_TYPES[tipo]["model_schema"]


def product_schema_for_tipo(tipo: str | None) -> Type[BaseModel] | None:
    if not is_valid_tipo(tipo):
        return None
    return CATALOG_TYPES[tipo]["product_schema"]


def tipo_for_table(ptable: str | None) -> str | None:
    if not ptable:
        return None
    for tipo, cfg in CATALOG_TYPES.items():
        if ptable in (cfg["model_table"], cfg["product_table"]):
            return tipo
    return None


def all_model_tables() -> list[str]:
    return [cfg["model_table"] for cfg in CATALOG_TYPES.values()]


def all_product_tables() -> list[str]:
    return [cfg["product_table"] for cfg in CATALOG_TYPES.values()]


def all_catalog_tables() -> list[str]:
    out: list[str] = []
    for cfg in CATALOG_TYPES.values():
        out.append(cfg["model_table"])
        out.append(cfg["product_table"])
    return out


def is_model_table(ptable: str | None) -> bool:
    return ptable in all_model_tables()


def is_product_table(ptable: str | None) -> bool:
    return ptable in all_product_tables()


def product_readonly_on_edit(ptable: str | None) -> bool:
    tipo = tipo_for_table(ptable)
    if not tipo:
        return False
    return bool(CATALOG_TYPES[tipo].get("product_readonly_on_edit"))


def apply_barcode_on_save(ptable: str | None) -> bool:
    tipo = tipo_for_table(ptable)
    if not tipo:
        return False
    return bool(CATALOG_TYPES[tipo].get("apply_barcode_on_save"))


def storefront_mode_for_tipo(tipo: str | None) -> str:
    if not is_valid_tipo(tipo):
        return "variantes"
    return CATALOG_TYPES[tipo].get("storefront_mode") or "variantes"


def is_assento_tipo(tipo: str | None) -> bool:
    return storefront_mode_for_tipo(tipo) == "assento"


def list_select_query(table: str) -> str:
    """Query Supabase para listas do backoffice — derivada do registo."""
    tipo = tipo_for_table(table)
    if not tipo:
        return "*"
    cfg = CATALOG_TYPES[tipo]
    mt = cfg["model_table"]
    if table == cfg["product_table"]:
        model_fields = ["nome"]
        disc = cfg.get("model_discriminator_field")
        if disc:
            model_fields.append(disc)
        return f"*, {mt}({', '.join(model_fields)}), categories(nome)"
    if table == mt:
        return "*, categories(nome)"
    return "*"


def infer_model_ptable(item: dict) -> str | None:
    if item.get("_ptable") in all_model_tables():
        return item["_ptable"]
    for cfg in CATALOG_TYPES.values():
        field = cfg.get("model_discriminator_field")
        if field and item.get(field) is not None:
            return cfg["model_table"]
    return None


def infer_product_ptable(item: dict) -> str | None:
    if item.get("_ptable") in all_product_tables():
        return item["_ptable"]
    for cfg in CATALOG_TYPES.values():
        rel = cfg["model_table"]
        if item.get(rel) is not None:
            return cfg["product_table"]
    return None


def embedded_model_keys(item: dict) -> list[str]:
    return [cfg["model_table"] for cfg in CATALOG_TYPES.values() if item.get(cfg["model_table"]) is not None]


def storefront_filters_for_model_tipo(tipo: str | None) -> list[dict]:
    if not is_valid_tipo(tipo):
        return []
    cfg = CATALOG_TYPES[tipo]
    if cfg.get("storefront_filters"):
        return list(cfg["storefront_filters"])
    from models.storefront_meta import storefront_filters_for_model

    return storefront_filters_for_model(cfg["model_schema"])


def catalog_metadata() -> dict:
    """Metadados para API/loja — tipos, tabelas, modos de vitrine."""
    from models.schemas import CATEGORY_DEFINITIONS
    from models.storefront_meta import storefront_context_for_tipo

    tipos = []
    for key, cfg in CATALOG_TYPES.items():
        ctx = storefront_context_for_tipo(cfg)
        tipos.append(
            {
                "tipo": key,
                "label": cfg.get("label") or key,
                "model_table": cfg["model_table"],
                "product_table": cfg["product_table"],
                "storefront_mode": ctx["mode"],
                "storefront_filters": storefront_filters_for_model_tipo(key),
                "storefront_picker": ctx["picker"],
                "storefront_specs": ctx["specs"],
                "storefront_badge": ctx["badge"],
                "order_picker_mode": ctx["mode"],
            }
        )

    return {
        "catalog_types": tipos,
        "category_definitions": CATEGORY_DEFINITIONS,
    }
