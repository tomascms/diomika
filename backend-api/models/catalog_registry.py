"""
Registo de tipos de catálogo — lê CATALOG_TYPES de schemas.py.

Não dupliques tipos aqui: edita models/schemas.py (CATALOG_TYPES + TABLE_MAP + CATEGORY_DEFINITIONS).
"""
from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from models.schemas import (
    CATALOG_TYPES,
    TIPO_CATALOGO_LABELS,
    aggregated_tipos_for_tipo,
    is_registered_tipo,
)

CATALOGO_TIPOS = CATALOG_TYPES


def is_valid_tipo(tipo: str | None) -> bool:
    return bool(tipo and tipo in CATALOG_TYPES)


def is_valid_storefront_tipo(tipo: str | None) -> bool:
    return is_registered_tipo(tipo)


def tipo_label(tipo: str | None) -> str:
    if not tipo:
        return ""
    if tipo in CATALOG_TYPES:
        return CATALOG_TYPES[tipo].get("label") or TIPO_CATALOGO_LABELS.get(tipo, tipo)
    # Tipos virtuais (ex.: material_cozinha) — label vem das definições de categoria
    from models.schemas import CATEGORY_DEFINITIONS

    for definition in CATEGORY_DEFINITIONS.values():
        if definition.get("tipo_catalogo") == tipo:
            return str(definition.get("nome") or tipo)
    return TIPO_CATALOGO_LABELS.get(tipo, tipo)


def model_table_for_tipo(tipo: str | None) -> str | None:
    if not is_valid_tipo(tipo):
        return None
    return CATALOG_TYPES[tipo]["model_table"]


def product_table_for_tipo(tipo: str | None) -> str | None:
    if not is_valid_tipo(tipo):
        return None
    return CATALOG_TYPES[tipo]["product_table"]


def colors_table_for_tipo(tipo: str | None) -> str | None:
    if not is_valid_tipo(tipo):
        return None
    return CATALOG_TYPES[tipo].get("colors_table")


def colors_schema_for_tipo(tipo: str | None) -> Type[BaseModel] | None:
    if not is_valid_tipo(tipo):
        return None
    return CATALOG_TYPES[tipo].get("colors_schema")


def all_colors_tables() -> list[str]:
    return [cfg["colors_table"] for cfg in CATALOG_TYPES.values() if cfg.get("colors_table")]


def colors_table_for_model_table(model_table: str | None) -> str | None:
    if not model_table:
        return None
    for cfg in CATALOG_TYPES.values():
        if cfg["model_table"] == model_table:
            return cfg.get("colors_table")
    return None


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
        tables = (cfg["model_table"], cfg["product_table"], cfg.get("colors_table"))
        if ptable in tables:
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
        if cfg.get("colors_table"):
            out.append(cfg["colors_table"])
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
        # Categoria via modelo — produtos não têm FK directo para categories
        return f"*, {mt}({', '.join(model_fields)}, categories(nome))"
    if table == mt:
        return "*, categories(nome)"
    return "*"


def admin_merged_select_query(table: str) -> str:
    """Select leve para listas merged do admin.

    Colunas por família — pedir campos inexistentes (ex.: altura em almofada)
    faz o PostgREST falhar e a lista merged ficar vazia.
    """
    return admin_list_select_query(table, embed_category=True)


def admin_list_select_query(table: str, *, embed_category: bool = False) -> str:
    """Select leve para listagens do backoffice (sem * nem embeds pesados)."""
    if table == "categories":
        return "id, nome, tipo_catalogo, visibilidade, slug, created_at"
    tipo = tipo_for_table(table)
    if not tipo:
        return "id, nome, visibilidade, created_at"
    cfg = CATALOG_TYPES[tipo]
    mt = cfg["model_table"]
    if table == cfg["product_table"]:
        cols = ["id", "ean", "visibilidade", "created_at", "id_modelo"]
        if tipo == "assento":
            cols.append("altura")
        elif tipo == "oculo":
            cols.append("segmento")
        elif tipo in ("almofada", "toalha_mesa", "pano_cozinha", "regional", "protetor_colchao", "passadeira"):
            cols.append("dimensoes")
        if embed_category:
            return f"{', '.join(cols)}, {mt}(nome, categories(nome))"
        return f"{', '.join(cols)}, {mt}(nome)"
    if table == mt:
        cols = ["id", "nome", "visibilidade", "created_at", "id_categoria"]
        disc = cfg.get("model_discriminator_field")
        if disc:
            cols.append(disc)
        if embed_category:
            return f"{', '.join(cols)}, categories(nome)"
        return ", ".join(cols)
    colors = cfg.get("colors_table")
    if colors and table == colors:
        return "id, numero, nome, visibilidade, id_modelo, created_at"
    return "id, visibilidade, created_at"


def relation_options_select_query(table: str) -> str:
    """Mínimo para dropdowns de relação no formulário."""
    if table == "categories":
        return "id, nome, tipo_catalogo"
    tipo = tipo_for_table(table)
    if not tipo:
        return "id, nome"
    cfg = CATALOG_TYPES[tipo]
    if table == cfg["model_table"]:
        return "id, nome"
    if table == cfg["product_table"]:
        return "id, ean, id_modelo"
    colors = cfg.get("colors_table")
    if colors and table == colors:
        return "id, numero, nome, id_modelo"
    return "id, nome"

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


def aggregated_family_filter(tipo: str | None) -> dict | None:
    tipos = aggregated_tipos_for_tipo(tipo)
    if not tipos:
        return None
    return {
        "field": "_tipo_catalogo",
        "label": "Subcategoria",
        "options": tipos,
        "labels": {
            t: CATALOG_TYPES[t]["label"]
            for t in tipos
            if t in CATALOG_TYPES
        },
    }


def storefront_filters_for_model_tipo(tipo: str | None) -> list[dict]:
    if not is_valid_tipo(tipo):
        return []
    cfg = CATALOG_TYPES[tipo]
    if cfg.get("storefront_filters"):
        return list(cfg["storefront_filters"])
    from models.storefront_meta import storefront_filters_for_model

    return storefront_filters_for_model(cfg["model_schema"])


def storefront_filters_for_category_tipo(tipo: str | None) -> list[dict]:
    agg = aggregated_family_filter(tipo)
    if agg:
        return [agg]
    return storefront_filters_for_model_tipo(tipo)


def catalog_metadata() -> dict:
    """Metadados para API/loja — tipos, tabelas, modos de vitrine."""
    from models.schemas import CATEGORY_DEFINITIONS
    from models.storefront_meta import storefront_context_for_tipo

    def _product_select(cfg: dict) -> str:
        fields = ["id", "ean", "barcode_url", "visibilidade"]
        schema = cfg.get("product_schema")
        if schema is not None:
            for fname in schema.model_fields:
                if fname in fields or fname in ("id", "id_modelo", "barcode_url", "visibilidade", "created_at", "updated_at"):
                    continue
                if fname in ("dimensoes", "altura", "segmento"):
                    fields.append(fname)
        return ", ".join(fields)

    tipos = []
    for key, cfg in CATALOG_TYPES.items():
        ctx = storefront_context_for_tipo(cfg)
        tipos.append(
            {
                "tipo": key,
                "label": cfg.get("label") or key,
                "model_table": cfg["model_table"],
                "product_table": cfg["product_table"],
                "colors_table": cfg.get("colors_table"),
                "storefront_mode": ctx["mode"],
                "storefront_filters": storefront_filters_for_model_tipo(key),
                "storefront_picker": ctx["picker"],
                "storefront_specs": ctx["specs"],
                "storefront_badge": ctx["badge"],
                "order_picker_mode": ctx["mode"],
                "product_select": _product_select(cfg),
            }
        )

    aggregated = []
    for _slug, definition in CATEGORY_DEFINITIONS.items():
        virtual = definition.get("tipo_catalogo")
        if virtual and aggregated_tipos_for_tipo(virtual):
            fam = aggregated_family_filter(virtual)
            aggregated.append(
                {
                    "tipo": virtual,
                    "label": definition.get("nome") or virtual,
                    "aggregated_tipos": list(definition["aggregated_tipos"]),
                    "storefront_mode": "aggregado",
                    "storefront_filters": [fam] if fam else [],
                }
            )

    return {
        "catalog_types": tipos,
        "aggregated_categories": aggregated,
        "category_definitions": CATEGORY_DEFINITIONS,
    }
