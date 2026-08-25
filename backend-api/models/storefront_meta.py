"""Metadados de vitrine derivados automaticamente dos schemas Pydantic."""
from __future__ import annotations
import json
from typing import Any
from models.ui_schema import field_label, field_widget, is_field_hidden

_STOREFRONT_SKIP = frozenset({"id", "id_categoria", "slug", "nome", "descricao", "visibilidade"})

def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return sorted(str(v).strip() for v in value if v and str(v).strip())
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return sorted(str(v).strip() for v in parsed if v and str(v).strip())
        except json.JSONDecodeError:
            pass
        return [value.strip()] if value.strip() else []
    return []

def _first_string_list_field(model_schema) -> str | None:
    for fname, fdef in model_schema.model_fields.items():
        if field_widget(fdef, fname) == "string_list":
            return fname
    return None

def _variant_picker_field(product_schema) -> str:
    if "dimensoes" in product_schema.model_fields:
        return "dimensoes"
    for fname, fdef in product_schema.model_fields.items():
        if field_widget(fdef, fname) == "dimensions":
            return fname
    for fname, fdef in product_schema.model_fields.items():
        w = field_widget(fdef, fname)
        if w in ("text", "dimensions") and fname not in _STOREFRONT_SKIP:
            return fname
    return "dimensoes"

def storefront_picker_for_type(cfg: dict) -> dict | None:
    """Configuração do selector na página de produto (tamanho, altura, etc.)."""
    mode = cfg.get("storefront_mode") or "variantes"
    if mode == "unico":
        return None
    if cfg.get("storefront_picker"):
        return dict(cfg["storefront_picker"])
    model_schema = cfg["model_schema"]
    product_schema = cfg["product_schema"]
    if mode == "assento":
        field = cfg.get("model_discriminator_field") or _first_string_list_field(model_schema) or "alturas"
        fdef = model_schema.model_fields.get(field)
        return {
            "source": "model",
            "field": field,
            "label": field_label(field, fdef) if fdef else "Variante",
            "format": "plain",
        }
    field = _variant_picker_field(product_schema)
    fdef = product_schema.model_fields.get(field)
    fmt = "dimensions" if field == "dimensoes" or field_widget(fdef, field) == "dimensions" else "plain"
    return {
        "source": "products",
        "field": field,
        "label": field_label(field, fdef) if fdef else "Tamanho",
        "format": fmt,
        "suffix": " cm" if fmt == "dimensions" else "",
    }

def storefront_specs_for_model(model_schema, picker: dict | None = None, badge: dict | None = None) -> list[dict]:
    """Campos do modelo a mostrar na ficha de produto da loja."""
    picker_field = picker.get("field") if picker and picker.get("source") == "model" else None
    badge_field = badge.get("field") if badge else None
    specs: list[dict] = []
    for fname, fdef in model_schema.model_fields.items():
        extra = fdef.json_schema_extra or {}
        if is_field_hidden(fname, fdef, {}) and fname not in _STOREFRONT_SKIP:
            if extra.get("ui_hidden"):
                continue
        if fname in _STOREFRONT_SKIP:
            continue
        if fname.startswith("id_") or extra.get("ui_relation"):
            continue
        if fname == picker_field or fname == badge_field:
            continue
        if extra.get("ui_storefront") is False:
            continue
        widget = field_widget(fdef, fname)
        if widget in ("relation", "image", "multi_image"):
            continue
        if widget == "string_list":
            continue
        specs.append(
            {
                "field": fname,
                "label": field_label(fname, fdef),
                "widget": widget,
                "enum_labels": dict(extra.get("ui_labels") or {}),
            }
        )
    return specs

def storefront_badge_for_model(model_schema) -> dict | None:
    """Primeiro campo enum do modelo — badge na grelha de produtos."""
    for fname, fdef in model_schema.model_fields.items():
        extra = fdef.json_schema_extra or {}
        if extra.get("ui_widget") != "enum":
            continue
        if extra.get("ui_storefront_badge") is False:
            continue
        return {
            "field": fname,
            "labels": dict(extra.get("ui_labels") or {}),
        }
    return None

def storefront_filters_for_model(model_schema) -> list[dict]:
    out: list[dict] = []
    for fname, fdef in model_schema.model_fields.items():
        extra = fdef.json_schema_extra or {}
        if extra.get("ui_widget") != "enum":
            continue
        out.append(
            {
                "field": fname,
                "label": field_label(fname, fdef),
                "options": list(extra.get("ui_options") or []),
                "labels": dict(extra.get("ui_labels") or {}),
            }
        )
    return out

def storefront_context_for_tipo(cfg: dict) -> dict:
    picker = storefront_picker_for_type(cfg)
    badge = storefront_badge_for_model(cfg["model_schema"])
    return {
        "mode": cfg.get("storefront_mode") or "variantes",
        "product_table": cfg["product_table"],
        "picker": picker,
        "specs": storefront_specs_for_model(cfg["model_schema"], picker, badge),
        "badge": badge,
    }

def attach_storefront_fields(data: dict, cfg: dict) -> dict:
    """Normaliza campos usados pelo picker (ex.: listas JSON de alturas)."""
    picker = storefront_picker_for_type(cfg)
    if picker and picker.get("source") == "model":
        field = picker.get("field")
        if field and field in data:
            data[field] = _normalize_string_list(data[field])
    return data
