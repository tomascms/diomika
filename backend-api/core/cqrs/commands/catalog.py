"""Comandos CQRS — escritas com soft-delete."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from core.database import get_db
from core.resilience import log_idempotency
from models.schemas import category_definition_for_slug
from utils.barcode_gen import apply_barcode_url


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
class CreateAlmofadaCommand:
    payload: dict[str, Any]


@dataclass
class UpdateAlmofadaCommand:
    id: str
    payload: dict[str, Any]


def create_almofada(cmd: CreateAlmofadaCommand):
    db = get_db()
    data = _serialize(dict(cmd.payload))
    ean = data.get("ean")
    existing = db.table("almofada").select("id").eq("ean", ean).execute()
    if existing.data:
        log_idempotency("CREATE_ALMOFADA", ean)
        return {"message": "Já existe", "data": existing.data[0], "status": "already_exists"}
    apply_barcode_url(data)
    res = db.table("almofada").insert(data).execute()
    return {"message": "Almofada criada", "data": res.data[0]}


def update_almofada(cmd: UpdateAlmofadaCommand):
    db = get_db()
    data = _serialize(dict(cmd.payload))
    data.pop("id", None)
    data.pop("created_at", None)
    conflict = db.table("almofada").select("id").eq("ean", data.get("ean", "")).neq("id", cmd.id).execute()
    if conflict.data:
        raise HTTPException(status_code=409, detail="EAN já em uso.")
    apply_barcode_url(data)
    res = db.table("almofada").update(data).eq("id", cmd.id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Almofada não encontrada.")
    return {"message": "Almofada atualizada", "data": res.data[0]}


@dataclass
class CreateModeloCorCommand:
    payload: dict[str, Any]


@dataclass
class UpdateModeloCorCommand:
    id: str
    payload: dict[str, Any]


def create_modelo_cor(cmd: CreateModeloCorCommand):
    db = get_db()
    data = _serialize(dict(cmd.payload))
    res = db.table("modelo_cores").insert(data).execute()
    return {"message": "Cor criada", "data": res.data[0]}


def update_modelo_cor(cmd: UpdateModeloCorCommand):
    db = get_db()
    data = _serialize(dict(cmd.payload))
    data.pop("id", None)
    data.pop("created_at", None)
    res = db.table("modelo_cores").update(data).eq("id", cmd.id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Cor não encontrada.")
    return {"message": "Cor atualizada", "data": res.data[0]}


@dataclass
class CreateCategoryCommand:
    payload: dict[str, Any]


@dataclass
class UpdateCategoryCommand:
    id: str
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
        data["tipo_catalogo"] = "almofada"

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


def update_category(cmd: UpdateCategoryCommand):
    db = get_db()
    data = _serialize(dict(cmd.payload))
    data.pop("id", None)
    data.pop("created_at", None)
    slug = (data.get("slug") or "").strip()
    definition = category_definition_for_slug(slug)
    if definition:
        data["tipo_catalogo"] = definition["tipo_catalogo"]
        if data.get("carrinho_step") is None:
            data["carrinho_step"] = definition.get("carrinho_step")
        if data.get("carrinho_min") is None:
            data["carrinho_min"] = definition.get("carrinho_min")
    elif data.get("tipo_catalogo") is None:
        data["tipo_catalogo"] = "almofada"
    if data.get("carrinho_step") is None:
        data["carrinho_step"] = 6
    if data.get("carrinho_min") is None:
        data["carrinho_min"] = data["carrinho_step"]
    res = db.table("categories").update(data).eq("id", cmd.id).execute()
    return {"message": "Atualizada", "data": res.data[0]}


@dataclass
class CreateModelCommand:
    payload: dict[str, Any]


@dataclass
class UpdateModelCommand:
    id: str
    payload: dict[str, Any]


def create_model(cmd: CreateModelCommand):
    db = get_db()
    data = _serialize(dict(cmd.payload))
    res = db.table("modelos_almofadas").insert(data).execute()
    return {"message": "Modelo criado", "data": res.data[0]}


def update_model(cmd: UpdateModelCommand):
    db = get_db()
    data = _serialize(dict(cmd.payload))
    data.pop("id", None)
    data.pop("created_at", None)
    res = db.table("modelos_almofadas").update(data).eq("id", cmd.id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    return {"message": "Modelo atualizado", "data": res.data[0]}


create_product = create_almofada
update_product = update_almofada
CreateProductCommand = CreateAlmofadaCommand
UpdateProductCommand = UpdateAlmofadaCommand
