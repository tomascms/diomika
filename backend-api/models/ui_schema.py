"""
Utilitários para extrair metadados UI e validação a partir dos modelos Pydantic.
Fonte única para o backoffice schema-driven.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo


def field_extra(field: FieldInfo | None) -> dict:
    if field is None:
        return {}
    extra = field.json_schema_extra
    return extra if isinstance(extra, dict) else {}


def is_field_required(field: FieldInfo) -> bool:
    if field.is_required():
        return True
    extra = field_extra(field)
    return extra.get("ui_required", False)


def is_field_hidden(field_name: str, field: FieldInfo, table_config: dict) -> bool:
    extra = field_extra(field)
    if extra.get("ui_hidden"):
        return True
    hidden_defaults = {"id", "slug", "barcode_url", "created_at", "updated_at", "last_sender"}
    if field_name in hidden_defaults:
        return True
    if field_name == "visibilidade" and not table_config.get("ui_show_visibility_field"):
        return True
    return False


def is_field_readonly(field: FieldInfo) -> bool:
    return bool(field_extra(field).get("ui_readonly"))


def field_widget(field: FieldInfo | None, field_name: str) -> str:
    if field is None:
        if field_name == "dimensoes":
            return "dimensions"
        return "text"
    extra = field_extra(field)
    if extra.get("ui_widget"):
        return extra["ui_widget"]
    if field_name in ("imagem", "imagem_capa"):
        return "image"
    if field_name == "galeria":
        return "multi_image"
    if field_name == "dimensoes":
        return "dimensions"
    if field_name == "mensagem":
        return "textarea"
    if field_name == "cor":
        return "text"
    if field_name.startswith("id_"):
        return "relation"
    origin = get_origin(field.annotation)
    if origin is list:
        args = get_args(field.annotation)
        if args and args[0] is str:
            return "string_list"
        return "json_list"
    if origin is dict:
        return "json_dict"
    ann = field.annotation
    args = get_args(ann)
    if args and all(isinstance(a, str) for a in args):
        return "enum"
    if ann is bool:
        return "boolean"
    return "text"


def field_label(field_name: str, field: FieldInfo) -> str:
    extra = field_extra(field)
    if extra.get("description"):
        return extra["description"]
    if extra.get("ui_label"):
        return extra["ui_label"]
    return field_name.replace("id_", "").replace("_", " ").title()


def relation_table(field_name: str, field: FieldInfo, table_config: dict | None = None) -> Optional[str]:
    extra = field_extra(field)
    if extra.get("ui_relation"):
        return extra["ui_relation"]
    if field_name == "id_categoria":
        return "categories"
    if field_name == "id_modelo" and table_config:
        from models.catalog_registry import tipo_for_table
        from models.schemas import CATALOG_TYPES

        ptable = table_config.get("_table_name")
        if ptable:
            tipo = tipo_for_table(ptable)
            if tipo and tipo in CATALOG_TYPES:
                return CATALOG_TYPES[tipo]["model_table"]
    if field_name == "id_modelo":
        return "modelos_almofadas"
    return None


def get_form_fields(schema_class: type[BaseModel], table_config: dict, table_name: str | None = None) -> List[dict]:
    """Lista de campos para renderizar no formulário do backoffice."""
    ctx = {**table_config, "_table_name": table_name}
    fields = []
    for name, field in schema_class.model_fields.items():
        if is_field_hidden(name, field, table_config):
            continue
        fields.append(
            {
                "name": name,
                "label": field_label(name, field),
                "widget": field_widget(field, name),
                "required": is_field_required(field),
                "readonly": is_field_readonly(field),
                "relation": relation_table(name, field, ctx),
                "enum_options": field_extra(field).get("ui_options"),
                "enum_labels": field_extra(field).get("ui_labels", {}),
                "lock_on_edit": field_extra(field).get("ui_lock_on_edit", False),
            }
        )
    return fields


def get_list_display(item: dict, table_config: dict) -> str:
    """Gera texto de exibição na lista lateral."""
    if table_config.get("ui_list_formatter") == "contact":
        return item.get("email") or "—"
    if table_config.get("ui_list_formatter") == "order_cliente":
        return item.get("referencia_cliente") or item.get("nome") or "—"
    if table_config.get("ui_list_formatter") in ("produto", "assento"):
        from models.catalog_registry import model_table_for_tipo

        mt = model_table_for_tipo(table_config.get("ui_catalog_tipo")) or ""
        modelo = item.get(mt) if mt else None
        if isinstance(modelo, list) and modelo:
            modelo = modelo[0]
        if not isinstance(modelo, dict):
            modelo = {}
        nome = (modelo.get("nome") or "").strip()
        ean = (item.get("ean") or "").strip()
        if ean and nome:
            return f"{ean} · {nome}"
        if ean:
            return ean
        return nome or "—"

    label_fields = table_config.get("list_label_fields", ["nome", "ean", "id"])
    enum_labels = table_config.get("schema", None)
    parts = []
    for f in label_fields:
        val = item.get(f)
        if val:
            if f == "tipo":
                from models.schemas import TIPO_ALMOFADA_LABELS
                parts.append(TIPO_ALMOFADA_LABELS.get(val, val))
            elif f == "tipo_catalogo":
                from models.schemas import TIPO_CATALOGO_LABELS
                parts.append(TIPO_CATALOGO_LABELS.get(val, val))
            else:
                parts.append(str(val))
    return " | ".join(parts) if parts else str(item.get("id", "Sem Nome"))


def record_missing_fields(
    item: dict, schema_class: type[BaseModel], table_config: dict
) -> List[str]:
    """Devolve nomes de campos obrigatórios em falta num registo."""
    missing = []
    for name, field in schema_class.model_fields.items():
        if is_field_hidden(name, field, table_config):
            continue
        if not is_field_required(field):
            continue
        if is_field_readonly(field) and table_config.get("ui_mode") == "conversation":
            continue

        value = item.get(name)
        if value is None:
            missing.append(field_label(name, field))
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(field_label(name, field))
            continue
        if isinstance(value, (list, dict)) and not value:
            missing.append(field_label(name, field))
    return missing


def build_schema_snapshot(table_map: dict) -> dict:
    """Snapshot serializável do schema atual para diff."""
    snapshot: dict[str, Any] = {}
    for table_name, info in table_map.items():
        schema = info["schema"]
        columns = {}
        for fname, field in schema.model_fields.items():
            columns[fname] = {
                "type": str(field.annotation),
                "required": is_field_required(field),
                "widget": field_widget(field, fname),
            }
        snapshot[table_name] = {
            "label": info.get("label", table_name),
            "schema_class": schema.__name__,
            "columns": columns,
            "config": {k: v for k, v in info.items() if k != "schema"},
        }
    return snapshot


def list_catalog_model_schemas() -> list[dict]:
    """Resumo legível: tipo de catálogo → classe Pydantic de modelo."""
    from models.catalog_registry import CATALOGO_TIPOS

    rows = []
    for tipo, cfg in CATALOGO_TIPOS.items():
        schema = cfg["model_schema"]
        fields = [
            field_label(n, f)
            for n, f in schema.model_fields.items()
            if not is_field_hidden(n, f, {})
        ]
        rows.append(
            {
                "tipo": tipo,
                "label": cfg["label"],
                "schema_class": schema.__name__,
                "table": cfg["model_table"],
                "fields": fields,
            }
        )
    return rows


def snapshot_hash(snapshot: dict) -> str:
    return str(abs(hash(json.dumps(snapshot, sort_keys=True, default=str))))
