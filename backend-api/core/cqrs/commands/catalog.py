"""Comandos CQRS — escritas de categoria + soft-delete.

CRUD de modelos/produtos/cores: usar admin_crud (TABLE_MAP + validação).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from core.database import get_db
from core.resilience import log_idempotency
from models.schemas import category_definition_for_slug


def soft_delete(table: str, record_id: str) -> dict:
    db = get_db()
    res = db.table(table).update({"visibilidade": False}).eq("id", record_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registo não encontrado")
    return {"status": "soft_deleted", "id": record_id}


def _serialize(data: dict) -> dict:
    for k, v in list(data.items()):
        if isinstance(v, UUID):
            data[k] = str(v)
    return data


@dataclass
class CreateCategoryCommand:
    payload: dict[str, Any]


def create_category(cmd: CreateCategoryCommand):
    db = get_db()
    data = _serialize(dict(cmd.payload))
    slug = (data.get("slug") or "").strip()
    definition = category_definition_for_slug(slug)

    if definition:
        data["tipo_catalogo"] = definition["tipo_catalogo"]
        if data.get("carrinho_step") is None:
            data["carrinho_step"] = definition.get("carrinho_step")
        if data.get("carrinho_min") is None:
            data["carrinho_min"] = definition.get("carrinho_min")
    elif data.get("tipo_catalogo") is None:
        raise HTTPException(
            status_code=400,
            detail="Categoria sem tipo_catalogo — use uma definição do schema.",
        )

    if data.get("carrinho_step") is None:
        data["carrinho_step"] = 6
    if data.get("carrinho_min") is None:
        data["carrinho_min"] = data["carrinho_step"]

    existing = db.table("categories").select("id").eq("slug", slug).execute()
    if existing.data:
        log_idempotency("CREATE_CATEGORY", slug)
        return {"message": "Já existe", "data": existing.data[0], "status": "already_exists"}
    res = db.table("categories").insert(data).execute()
    return {"message": "Criada", "data": res.data[0]}
