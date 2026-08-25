"""CRUD genérico para backoffice web — validação via TABLE_MAP."""
from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from core.audit import log_admin_action
from core.auth import Role, assert_table_action, require_admin
from core.cache import invalidate_prefix
from core.config import get_settings
from core.cqrs.commands.catalog import soft_delete
from core.database import get_db
from core.local_only import admin_must_be_local
from core.rate_limit import get_client_ip
from models.catalog_registry import apply_barcode_on_save, list_select_query
from models.schemas import TABLE_MAP
from models.ui_schema import get_form_fields
from utils.barcode_gen import apply_barcode_url
from utils.image_urls import content_type_for_path, resolve_image_value
from utils.image_validation import validate_upload_bytes
from utils.storage import upload_bytes

logger = logging.getLogger("diomika-api")

router = APIRouter(
    prefix="/admin/crud",
    tags=["Admin CRUD"],
    dependencies=[Depends(admin_must_be_local), Depends(require_admin)],
)


def _client_error(exc: Exception) -> str:
    return "Dados inválidos ou em conflito."


def _schema_for(table: str):
    if table not in TABLE_MAP:
        raise HTTPException(status_code=404, detail="Categoria não mapeada")
    schema = TABLE_MAP[table].get("schema")
    if not schema:
        raise HTTPException(status_code=404, detail="Sem schema")
    return schema


def _role(request: Request) -> Role:
    return getattr(request.state, "api_role", "admin")  # type: ignore[return-value]


def _normalize_payload(payload: dict) -> dict:
    out = dict(payload)
    for k, v in list(out.items()):
        if isinstance(v, UUID):
            out[k] = str(v)
    return out


def _audit(request: Request, action: str, resource: str, resource_id: str | None = None, **detail):
    role = getattr(request.state, "api_role", "admin")
    log_admin_action(
        action=action,
        resource=resource,
        resource_id=resource_id,
        role=str(role),
        actor=getattr(request.state, "api_actor", None),
        request_id=getattr(request.state, "request_id", None),
        client_ip=get_client_ip(request),
        detail=detail or None,
    )


def _invalidate_catalog_cache() -> None:
    invalidate_prefix("categories:")
    invalidate_prefix("catalog:")


def _resolve_image_fields(table_name: str, payload: dict) -> dict:
    """Upload de caminhos locais (backoffice no PC admin) antes de validar schema."""
    out = dict(payload)
    cfg = TABLE_MAP.get(table_name, {})
    schema = cfg.get("schema")
    if not schema:
        return out

    for field_def in get_form_fields(schema, cfg):
        name = field_def["name"]
        if name not in out or out[name] in (None, ""):
            continue
        widget = field_def.get("widget")
        if widget == "image":
            val = str(out[name]).strip()
            if val and not val.startswith(("http://", "https://")):
                out[name] = resolve_image_value(val, table_name, name)
        elif widget == "multi_image":
            raw = out[name]
            if isinstance(raw, str):
                raw = [p.strip() for p in raw.split(";") if p.strip()]
            if isinstance(raw, list):
                from utils.image_urls import resolve_image_list

                out[name] = resolve_image_list([str(v) for v in raw], table_name, name)
    return out


def _allowed_upload_field(table: str, field: str) -> bool:
    if table not in TABLE_MAP:
        return False
    cfg = TABLE_MAP[table]
    schema = cfg.get("schema")
    if not schema:
        return False
    for field_def in get_form_fields(schema, cfg, table):
        if field_def["name"] == field and field_def.get("widget") in ("image", "multi_image"):
            return True
    return False


@router.post("/upload-image")
async def upload_image(
    request: Request,
    table: str,
    field: str,
    file: UploadFile = File(...),
    role: Role = Depends(require_admin),
):
    """Upload multipart — para backoffice Vue (browser não envia paths locais)."""
    if not _allowed_upload_field(table, field):
        raise HTTPException(status_code=400, detail="Campo de imagem inválido para esta categoria.")
    assert_table_action(table, "upload", role)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Ficheiro em falta")
    ext = Path(file.filename).suffix.lower() or ".png"
    dest = f"{table}/{field}/{uuid4().hex}{ext}"
    data = await file.read()
    try:
        validate_upload_bytes(data, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ctype = file.content_type or content_type_for_path(file.filename)
    url = upload_bytes(data, dest, ctype)
    _audit(request, "upload", table, detail={"field": field, "bytes": len(data)})
    return {"url": url}


@router.get("/{table_name}")
def list_records(
    request: Request,
    table_name: str,
    visible_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    id_modelo: str | None = None,
):
    _schema_for(table_name)
    assert_table_action(table_name, "read", _role(request))
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    query = get_db().table(table_name).select(list_select_query(table_name))
    if visible_only:
        query = query.eq("visibilidade", True)
    if id_modelo and table_name == "modelo_cores":
        query = query.eq("id_modelo", id_modelo)
    try:
        res = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    except TypeError:
        try:
            res = query.order("created_at", ascending=False).range(offset, offset + limit - 1).execute()
        except Exception:
            res = query.limit(limit).offset(offset).execute()
    except Exception:
        res = query.limit(limit).execute()
    rows = res.data or []
    return {"items": rows, "limit": limit, "offset": offset, "count": len(rows)}


@router.get("/{table_name}/{record_id}")
def get_record(request: Request, table_name: str, record_id: str):
    _schema_for(table_name)
    assert_table_action(table_name, "read", _role(request))
    res = (
        get_db()
        .table(table_name)
        .select(list_select_query(table_name))
        .eq("id", record_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Registo não encontrado")
    return res.data[0]


@router.post("/{table_name}")
def create_record(request: Request, table_name: str, body: dict):
    schema_class = _schema_for(table_name)
    assert_table_action(table_name, "create", _role(request))
    try:
        body = _resolve_image_fields(table_name, body)
        validated = schema_class(**body)
        payload = _normalize_payload(validated.model_dump())
        if apply_barcode_on_save(table_name) and payload.get("ean"):
            apply_barcode_url(payload)
        ins = get_db().table(table_name).insert(payload).execute()
        row = (ins.data or [{}])[0]
        _invalidate_catalog_cache()
        _audit(request, "create", table_name, resource_id=str(row.get("id") or ""))
        return row
    except Exception as exc:
        logger.error("Create %s: %s", table_name, exc)
        raise HTTPException(status_code=400, detail=_client_error(exc)) from exc


@router.put("/{table_name}/{record_id}")
def update_record(request: Request, table_name: str, record_id: str, body: dict):
    schema_class = _schema_for(table_name)
    assert_table_action(table_name, "update", _role(request))
    try:
        body = {**body, "id": record_id}
        body = _resolve_image_fields(table_name, body)
        validated = schema_class(**body)
        payload = _normalize_payload(validated.model_dump())
        payload.pop("id", None)
        payload.pop("created_at", None)
        if apply_barcode_on_save(table_name) and payload.get("ean"):
            apply_barcode_url(payload)
        res = get_db().table(table_name).update(payload).eq("id", record_id).execute()
        _invalidate_catalog_cache()
        _audit(request, "update", table_name, resource_id=record_id)
        return (res.data or [{}])[0] if res.data else {"id": record_id, **payload}
    except Exception as exc:
        logger.error("Update %s/%s: %s", table_name, record_id, exc)
        raise HTTPException(status_code=400, detail=_client_error(exc)) from exc


@router.patch("/{table_name}/{record_id}/visibility")
def patch_visibility(request: Request, table_name: str, record_id: str, body: dict):
    """Alterna visibilidade sem revalidar o registo completo."""
    _schema_for(table_name)
    assert_table_action(table_name, "update", _role(request))
    if "visibilidade" not in body:
        raise HTTPException(status_code=400, detail="Campo visibilidade em falta")
    vis = bool(body["visibilidade"])
    res = get_db().table(table_name).update({"visibilidade": vis}).eq("id", record_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registo não encontrado")
    _invalidate_catalog_cache()
    _audit(request, "visibility", table_name, resource_id=record_id, visibilidade=vis)
    return (res.data or [{"id": record_id, "visibilidade": vis}])[0]


@router.patch("/{table_name}/{record_id}/lida")
def patch_lida(request: Request, table_name: str, record_id: str, body: dict):
    """Marca orçamento/mensagem como lida ou não lida."""
    _schema_for(table_name)
    assert_table_action(table_name, "update", _role(request))
    if table_name not in ("pedidos_orcamento", "contact_messages"):
        raise HTTPException(status_code=400, detail="Campo lida não aplicável a esta tabela")
    if "lida" not in body:
        raise HTTPException(status_code=400, detail="Campo lida em falta")
    lida = bool(body["lida"])
    res = get_db().table(table_name).update({"lida": lida}).eq("id", record_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registo não encontrado")
    _audit(request, "mark_read", table_name, resource_id=record_id, lida=lida)
    return (res.data or [{"id": record_id, "lida": lida}])[0]


@router.delete("/{table_name}/{record_id}")
def delete_record(request: Request, table_name: str, record_id: str, hard: bool = False):
    _schema_for(table_name)
    settings = get_settings()
    action = "hard_delete" if hard else "delete"
    assert_table_action(table_name, action, _role(request))
    if hard and settings.is_production and not settings.is_beta:
        raise HTTPException(status_code=403, detail="Hard delete desactivado em produção.")
    try:
        if hard:
            if table_name in ("modelos_almofadas", "modelos_assentos"):
                # modelo_cores sem FK polimórfica — limpar cores do modelo
                get_db().table("modelo_cores").delete().eq("id_modelo", record_id).execute()
            get_db().table(table_name).delete().eq("id", record_id).execute()
            _invalidate_catalog_cache()
            _audit(request, "hard_delete", table_name, resource_id=record_id)
            return {"status": "deleted", "hard": True}
        result = soft_delete(table_name, record_id)
        _invalidate_catalog_cache()
        _audit(request, "soft_delete", table_name, resource_id=record_id)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Delete %s/%s: %s", table_name, record_id, exc)
        raise HTTPException(status_code=400, detail="Não foi possível apagar o registo.") from exc
