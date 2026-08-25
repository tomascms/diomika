"""Gera TABLE_MAP a partir de CATALOG_TYPES — não editar tipos aqui."""
from __future__ import annotations

from typing import Any

from models.ui_schema import field_label


def _enum_filters_from_schema(schema) -> list[dict]:
    out: list[dict] = []
    for fname, fdef in schema.model_fields.items():
        extra = fdef.json_schema_extra or {}
        if extra.get("ui_widget") != "enum":
            continue
        out.append(
            {
                "field": fname,
                "type": "enum",
                "label": field_label(fname, fdef),
                "options": list(extra.get("ui_options") or []),
                "labels": dict(extra.get("ui_labels") or {}),
            }
        )
    return out


def build_catalog_table_map(catalog_types: dict) -> dict[str, dict]:
    """Entradas model_table + product_table derivadas de CATALOG_TYPES."""
    out: dict[str, dict] = {}
    for tipo, cfg in catalog_types.items():
        label = cfg.get("label") or tipo.title()
        mt = cfg["model_table"]
        pt = cfg["product_table"]
        model_schema = cfg["model_schema"]
        product_schema = cfg["product_schema"]
        embed = cfg.get("ui_embed_colors", True)

        model_filters: list[dict] = [
            {"field": "id_categoria", "relation": "categories", "label": "Categoria"},
        ]
        model_filters.extend(_enum_filters_from_schema(model_schema))

        out[mt] = {
            "schema": model_schema,
            "label": cfg.get("model_label") or f"Modelos {label}",
            "icon": "layers",
            "ui_sidebar": False,
            "list_label_fields": cfg.get("model_list_fields") or ["nome"],
            "ui_embed_colors": embed,
            "ui_filters": model_filters,
            "ui_catalog_tipo": tipo,
        }

        product_filters: list[dict] = [
            {"field": "id_modelo", "relation": mt, "label": "Modelo"},
            {"field": "ean", "type": "search", "label": "EAN"},
        ]
        mode = cfg.get("storefront_mode") or "variantes"
        out[pt] = {
            "schema": product_schema,
            "label": cfg.get("product_label") or f"Produtos {label}",
            "icon": "shopping_cart",
            "ui_sidebar": False,
            "ui_list_formatter": "assento" if mode == "assento" else "produto",
            "ui_filters": product_filters,
            "ui_catalog_tipo": tipo,
        }

        ct = cfg.get("colors_table")
        cs = cfg.get("colors_schema")
        if ct and cs:
            out[ct] = {
                "schema": cs,
                "label": f"Cores — {label}",
                "icon": "palette",
                "ui_sidebar": False,
                "list_label_fields": ["numero", "nome"],
                "ui_catalog_tipo": tipo,
            }
            out[mt]["ui_colors_table"] = ct
    return out


def build_operations_table_map(
    *,
    categoria_schema,
    pedido_schema,
    encomenda_schema,
    contact_schema,
    infra_schemas: dict[str, Any],
) -> dict[str, dict]:
    """Tabelas fixas: categorias, operações, infra."""
    out = {
        "categories": {
            "schema": categoria_schema,
            "label": "Categorias",
            "icon": "folder",
            "list_label_fields": ["nome", "tipo_catalogo"],
            "ui_no_filters": True,
        },
        "pedidos_orcamento": {
            "schema": pedido_schema,
            "label": "Orçamentos",
            "icon": "receipt",
            "ui_mode": "order_view",
            "ui_no_create": True,
            "ui_no_filters": True,
            "ui_list_formatter": "order_cliente",
        },
        "encomendas_internas": {
            "schema": encomenda_schema,
            "label": "Encomendas",
            "icon": "clipboard",
            "ui_mode": "order_create",
            "ui_no_filters": True,
            "ui_list_formatter": "order_cliente",
            "list_label_fields": ["referencia_cliente"],
        },
        "contact_messages": {
            "schema": contact_schema,
            "label": "Mensagens",
            "icon": "mail",
            "ui_mode": "conversation",
            "ui_no_create": True,
            "ui_no_filters": True,
            "ui_list_formatter": "contact",
        },
    }
    for table_name, schema in infra_schemas.items():
        out[table_name] = {
            "schema": schema,
            "label": table_name.replace("_", " ").title(),
            "icon": "database",
            "ui_sidebar": False,
            "ui_hidden_infra": True,
        }
    return out


def merge_table_map(catalog_types: dict, operations: dict) -> dict[str, dict]:
    return {**operations, **build_catalog_table_map(catalog_types)}
