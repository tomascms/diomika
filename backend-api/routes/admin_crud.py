"""CRUD genérico para backoffice web — validação via TABLE_MAP."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile

from core.audit import log_admin_action
from core.auth import Role, SENSITIVE_BUSINESS_TABLES, assert_table_action, require_admin
from core.cache import invalidate_prefix
from core.cqrs.commands.catalog import soft_delete
from core.database import get_db
from core.idempotency import (
    IdempotencyUnavailable,
    abort_idempotent_request,
    begin_idempotent_request,
    complete_idempotent_request,
    get_cached_response,
)
from core.local_only import admin_must_be_local
from core.rate_limit import get_client_ip
from models.catalog_registry import (
    CATALOG_TYPES,
    admin_list_select_query,
    all_colors_tables,
    all_model_tables,
    all_product_tables,
    apply_barcode_on_save,
    colors_table_for_model_table,
    colors_table_for_tipo,
    list_select_query,
    relation_options_select_query,
    tipo_for_table,
)
from models.schemas import TABLE_MAP, aggregated_tipos_for_tipo
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


def _schedule_barcode_update(table_name: str, record_id: str, ean: str | None) -> None:
    """Gera barcode em background — evita timeout no guardar (upload storage é lento)."""
    code = (ean or "").strip()
    if not code or not apply_barcode_on_save(table_name):
        return

    def _job() -> None:
        try:
            payload = {"ean": code}
            apply_barcode_url(payload)
            url = payload.get("barcode_url")
            if url:
                get_db().table(table_name).update({"barcode_url": url}).eq("id", record_id).execute()
        except Exception as exc:
            logger.warning("Barcode async %s/%s: %s", table_name, record_id, exc)

    threading.Thread(target=_job, daemon=True).start()


def _client_error(exc: Exception) -> str:
    from pydantic import ValidationError

    if isinstance(exc, ValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        msg = first.get("msg") or str(exc)
        loc = first.get("loc") or ()
        if loc:
            field = ".".join(str(x) for x in loc if x != "__root__")
            if field:
                return f"{field}: {msg}"
        return str(msg)
    text = str(exc).strip()
    if "duplicate key" in text.lower() or "23505" in text:
        if "assento_id_modelo_key" in text or "assento_modelo_altura" in text:
            return "Já existe um assento com esta altura neste modelo."
        if "modelo_cores_model_numero" in text or "modelo_cores" in text.lower():
            return "Já existe esta cor (número) neste modelo."
        if "ean" in text.lower():
            return "Este EAN já existe noutro produto."
        return "Registo duplicado — já existe um com a mesma chave única."
    if text and text not in ("", "None"):
        return text[:240]
    return "Dados inválidos ou em conflito."


def _is_expected_client_conflict(exc: Exception) -> bool:
    text = str(exc).lower()
    return "duplicate key" in text or "23505" in text or "violates unique" in text


def _schema_for(table: str):
    if table not in TABLE_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"Tabela «{table}» não registada no catálogo",
        )
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
    invalidate_prefix("admin:merged:")


def _tipo_for_model_id(model_id: str | None) -> str:
    if not model_id:
        raise ValueError("Modelo em falta.")
    db = get_db()
    for tipo, cfg in CATALOG_TYPES.items():
        mt = cfg["model_table"]
        row = db.table(mt).select("id").eq("id", model_id).limit(1).execute().data
        if row:
            return tipo
    raise ValueError("Modelo não encontrado.")


def _model_discriminator_values(model_id: str, model_table: str, field: str) -> list[str]:
    db = get_db()
    res = db.table(model_table).select(field).eq("id", model_id).limit(1).execute()
    row = (res.data or [None])[0]
    if not row:
        raise ValueError("Modelo não encontrado.")
    values = row.get(field) or []
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except json.JSONDecodeError:
            values = [values]
    return [str(a).strip() for a in values if a and str(a).strip()]


def _validate_model_discriminator(table_name: str, payload: dict, record_id: str | None = None) -> None:
    tipo = tipo_for_table(table_name)
    if not tipo:
        return
    cfg = CATALOG_TYPES.get(tipo) or {}
    model_field = cfg.get("model_discriminator_field")
    if not model_field:
        return

    product_field = "altura" if table_name == "assento" else model_field
    value = (payload.get(product_field) or "").strip()
    if not value:
        raise ValueError(f"Selecione {product_field.replace('_', ' ')} desta variante.")

    id_modelo = payload.get("id_modelo")
    if not id_modelo:
        return

    mt = cfg["model_table"]
    allowed = _model_discriminator_values(str(id_modelo), mt, model_field)
    if value not in allowed:
        raise ValueError(f"«{value}» não está definido no modelo.")

    db = get_db()
    pt = cfg["product_table"]
    q = db.table(pt).select("id").eq("id_modelo", str(id_modelo)).eq(product_field, value)
    if record_id:
        q = q.neq("id", record_id)
    if (q.limit(1).execute().data or []):
        raise ValueError(f"Já existe variante «{value}» neste modelo.")


def _validate_assento_altura(payload: dict, record_id: str | None = None) -> None:
    _validate_model_discriminator("assento", payload, record_id)


def _validate_oculo(payload: dict, record_id: str | None = None) -> None:
    id_modelo = payload.get("id_modelo")
    if not id_modelo:
        return
    db = get_db()
    model = (
        db.table("modelos_oculos")
        .select("tipo_oculo")
        .eq("id", str(id_modelo))
        .limit(1)
        .execute()
        .data
        or [None]
    )[0]
    if not model:
        raise ValueError("Modelo de óculos não encontrado.")
    tipo_oculo = model.get("tipo_oculo")
    segmento = payload.get("segmento")
    if tipo_oculo == "leitura":
        if segmento:
            raise ValueError("Óculos de leitura não têm segmento — use produto sortido.")
        q = db.table("oculo").select("id").eq("id_modelo", str(id_modelo))
        if record_id:
            q = q.neq("id", record_id)
        if (q.limit(1).execute().data or []):
            raise ValueError("Este modelo de leitura já tem produto sortido.")
        return
    if not segmento:
        raise ValueError("Selecione segmento (homem, mulher ou criança).")
    q = db.table("oculo").select("id").eq("id_modelo", str(id_modelo)).eq("segmento", segmento)
    if record_id:
        q = q.neq("id", record_id)
    if (q.limit(1).execute().data or []):
        raise ValueError(f"Já existe produto para segmento «{segmento}» neste modelo.")


def _validate_regional_product(payload: dict, record_id: str | None = None) -> None:
    id_modelo = payload.get("id_modelo")
    if not id_modelo:
        return
    db = get_db()
    model = (
        db.table("modelos_regionais")
        .select("subtipo, dimensoes")
        .eq("id", str(id_modelo))
        .limit(1)
        .execute()
        .data
        or [None]
    )[0]
    if not model:
        raise ValueError("Modelo regional não encontrado.")
    subtipo = model.get("subtipo")
    needs_dim = subtipo in ("pano_cozinha", "toalha", "protetor")
    dim = (payload.get("dimensoes") or "").strip()
    if needs_dim:
        if not dim:
            raise ValueError("Selecione dimensão desta variante.")
        allowed = _model_discriminator_values(str(id_modelo), "modelos_regionais", "dimensoes")
        if dim not in allowed:
            raise ValueError(f"Dimensão «{dim}» não está definida no modelo.")
        q = db.table("regional").select("id").eq("id_modelo", str(id_modelo)).eq("dimensoes", dim)
        if record_id:
            q = q.neq("id", record_id)
        if (q.limit(1).execute().data or []):
            raise ValueError(f"Já existe variante «{dim}» neste modelo.")
    elif dim:
        raise ValueError("Este subtipo não usa dimensão no produto.")


def _product_validation_table(table_name: str) -> bool:
    return table_name in all_product_tables()


def _validate_unico_single_product(table_name: str, payload: dict, record_id: str | None = None) -> None:
    """Modo unico: um único produto por modelo."""
    tipo = tipo_for_table(table_name)
    cfg = CATALOG_TYPES.get(tipo or "") or {}
    if (cfg.get("storefront_mode") or "") != "unico":
        return
    if cfg.get("model_discriminator_field"):
        return
    id_modelo = payload.get("id_modelo")
    if not id_modelo:
        return
    q = get_db().table(table_name).select("id").eq("id_modelo", str(id_modelo))
    if record_id:
        q = q.neq("id", record_id)
    if q.limit(1).execute().data or []:
        raise ValueError("Este modelo já tem um produto (modo único — uma referência por modelo).")


def _assert_model_category_tipo(table_name: str, payload: dict) -> None:
    """Garante que o modelo/cor/produto fica na categoria da família correcta."""
    tipo = tipo_for_table(table_name)
    if not tipo:
        return
    db = get_db()
    id_categoria = payload.get("id_categoria")
    id_modelo = payload.get("id_modelo")

    if table_name in all_model_tables():
        if not id_categoria:
            return
        cat = (
            db.table("categories")
            .select("id,nome,tipo_catalogo")
            .eq("id", str(id_categoria))
            .limit(1)
            .execute()
            .data
            or [None]
        )[0]
        if not cat:
            raise ValueError("Categoria não encontrada.")
        cat_tipo = str(cat.get("tipo_catalogo") or "").strip()
        allowed = {tipo}
        aggregated = aggregated_tipos_for_tipo(cat_tipo) or []
        if aggregated:
            allowed = set(aggregated)
        elif cat_tipo:
            allowed = {cat_tipo}
        if tipo not in allowed:
            raise ValueError(
                f"A categoria «{cat.get('nome') or cat_tipo}» não aceita modelos do tipo «{tipo}»."
            )
        return

    if table_name in all_product_tables() or table_name in all_colors_tables():
        if not id_modelo:
            return
        mt = CATALOG_TYPES.get(tipo, {}).get("model_table")
        if not mt:
            return
        model = (
            db.table(mt)
            .select("id,id_categoria")
            .eq("id", str(id_modelo))
            .limit(1)
            .execute()
            .data
            or [None]
        )[0]
        if not model:
            raise ValueError("Modelo não encontrado.")
        # Reusa a mesma regra via o modelo pai
        _assert_model_category_tipo(mt, {"id_categoria": model.get("id_categoria")})


def _validate_product_payload(table_name: str, payload: dict, record_id: str | None = None) -> None:
    if table_name == "assento":
        _validate_assento_altura(payload, record_id)
    elif table_name == "oculo":
        _validate_oculo(payload, record_id)
    elif table_name == "regional":
        _validate_regional_product(payload, record_id)
    elif _product_validation_table(table_name):
        _validate_model_discriminator(table_name, payload, record_id)
    _validate_unico_single_product(table_name, payload, record_id)


def _publish_catalog_children(table_name: str, record_id: str, *, tipo: str | None = None) -> None:
    """Torna visíveis cores e produtos filhos quando o modelo é publicado."""
    db = get_db()
    if table_name in all_model_tables():
        cfg = CATALOG_TYPES.get(tipo or tipo_for_table(table_name) or "") or {}
        pt = cfg.get("product_table")
        ct = cfg.get("colors_table")
        if pt:
            db.table(pt).update({"visibilidade": True}).eq("id_modelo", record_id).execute()
        if ct:
            db.table(ct).update({"visibilidade": True}).eq("id_modelo", record_id).execute()


def _hide_catalog_children(table_name: str, record_id: str, *, tipo: str | None = None) -> None:
    """Oculta cores e produtos filhos quando o modelo é ocultado."""
    db = get_db()
    if table_name in all_model_tables():
        cfg = CATALOG_TYPES.get(tipo or tipo_for_table(table_name) or "") or {}
        pt = cfg.get("product_table")
        ct = cfg.get("colors_table")
        if pt:
            db.table(pt).update({"visibilidade": False}).eq("id_modelo", record_id).execute()
        if ct:
            db.table(ct).update({"visibilidade": False}).eq("id_modelo", record_id).execute()


def _assert_ean_globally_unique(table_name: str, payload: dict, record_id: str | None = None) -> None:
    """EAN único em todas as tabelas de produto (além do UNIQUE por tabela na BD)."""
    if table_name not in all_product_tables():
        return
    ean = str(payload.get("ean") or "").strip()
    if not ean:
        return
    db = get_db()
    for pt in all_product_tables():
        q = db.table(pt).select("id").eq("ean", ean)
        if record_id and pt == table_name:
            q = q.neq("id", record_id)
        if q.limit(1).execute().data or []:
            if pt == table_name:
                raise ValueError(f"Já existe um produto com EAN {ean} nesta família.")
            raise ValueError(f"EAN {ean} já está registado noutro catálogo ({pt}).")


def _assert_model_publishable(table_name: str, record_id: str) -> None:
    """Loja só mostra modelos com ≥1 cor (imagem) e ≥1 produto com EAN.

    Conta rascunhos — a cascata de publicação torna-os visíveis a seguir.
    """
    if table_name not in all_model_tables():
        return
    tipo = tipo_for_table(table_name)
    cfg = CATALOG_TYPES.get(tipo or "") or {}
    pt = cfg.get("product_table")
    ct = cfg.get("colors_table")
    db = get_db()
    if ct:
        colors = (
            db.table(ct)
            .select("id,imagem")
            .eq("id_modelo", record_id)
            .limit(20)
            .execute()
            .data
            or []
        )
        if not any(str(c.get("imagem") or "").strip() for c in colors):
            raise ValueError("Adicione pelo menos uma cor com imagem antes de publicar na loja.")
    if pt:
        products = (
            db.table(pt)
            .select("id,ean")
            .eq("id_modelo", record_id)
            .limit(50)
            .execute()
            .data
            or []
        )
        if not any(str(p.get("ean") or "").strip() for p in products):
            raise ValueError("Adicione pelo menos um produto com EAN antes de publicar na loja.")


def _cascade_category_visibility(category_id: str, vis: bool) -> None:
    """Ao tornar categoria visível/oculta, propaga para modelos (e produtos/cores)."""
    db = get_db()
    for tipo, cfg in CATALOG_TYPES.items():
        mt = cfg.get("model_table")
        if not mt:
            continue
        models = (
            db.table(mt)
            .select("id")
            .eq("id_categoria", str(category_id))
            .execute()
            .data
            or []
        )
        for row in models:
            mid = str(row.get("id") or "")
            if not mid:
                continue
            db.table(mt).update({"visibilidade": vis}).eq("id", mid).execute()
            if vis:
                _publish_catalog_children(mt, mid, tipo=tipo)
            else:
                _hide_catalog_children(mt, mid, tipo=tipo)


def _enrich_create_payload(table_name: str, payload: dict) -> dict:
    out = dict(payload)
    _assert_model_category_tipo(table_name, out)
    _assert_ean_globally_unique(table_name, out)
    _validate_product_payload(table_name, out)
    # Modelos novos começam sempre como rascunho — publicar só quando cor+EAN existirem
    if table_name in all_model_tables() and out.get("visibilidade"):
        out["visibilidade"] = False
    return out


def _enrich_update_payload(table_name: str, payload: dict, record_id: str) -> dict:
    out = dict(payload)
    db = get_db()
    if table_name in all_model_tables() and not out.get("id_categoria"):
        row = (
            db.table(table_name)
            .select("id_categoria")
            .eq("id", record_id)
            .limit(1)
            .execute()
            .data
            or [None]
        )[0]
        if row:
            out.setdefault("id_categoria", row.get("id_categoria"))
    if _product_validation_table(table_name) or table_name in ("assento", "oculo", "regional"):
        if table_name == "assento" and (not out.get("altura") or not out.get("id_modelo")):
            row = (
                db.table("assento")
                .select("altura, id_modelo")
                .eq("id", record_id)
                .limit(1)
                .execute()
                .data
            )
            if row:
                out.setdefault("altura", row[0].get("altura"))
                out.setdefault("id_modelo", row[0].get("id_modelo"))
        if not out.get("id_modelo"):
            row = (
                db.table(table_name)
                .select("id_modelo")
                .eq("id", record_id)
                .limit(1)
                .execute()
                .data
                or [None]
            )[0]
            if row:
                out.setdefault("id_modelo", row.get("id_modelo"))
        _validate_product_payload(table_name, out, record_id)
        _assert_ean_globally_unique(table_name, out, record_id)
    _assert_model_category_tipo(table_name, out)
    if table_name in all_model_tables() and out.get("visibilidade"):
        _assert_model_publishable(table_name, record_id)
    return out


def _idempotency_op(table_name: str) -> str:
    return f"admin_create:{table_name}"


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


@router.get("/{table_name}/options")
def list_relation_options(
    request: Request,
    table_name: str,
    visible_only: bool = False,
    limit: int = 200,
    id_modelo: str | None = None,
):
    """Dropdowns leves — só id + label, sem embeds pesados."""
    _schema_for(table_name)
    assert_table_action(table_name, "read", _role(request))
    limit = min(max(limit, 1), 300)
    query = get_db().table(table_name).select(relation_options_select_query(table_name))
    if visible_only:
        query = query.eq("visibilidade", True)
    if id_modelo and table_name in all_colors_tables():
        query = query.eq("id_modelo", id_modelo)
    try:
        res = query.order("nome").limit(limit).execute()
    except Exception:
        try:
            res = query.order("created_at", desc=True).limit(limit).execute()
        except Exception:
            res = query.limit(limit).execute()
    rows = res.data or []

    def _label(row: dict) -> str:
        if row.get("nome"):
            return str(row["nome"]).strip()
        if row.get("ean"):
            return str(row["ean"]).strip()
        if row.get("numero") is not None:
            parts = [str(row["numero"]).strip()]
            if row.get("nome"):
                parts.append(str(row["nome"]).strip())
            return " · ".join(p for p in parts if p)
        return str(row.get("id", ""))[:8]

    return {
        "items": [
            {
                "id": r["id"],
                "label": _label(r) or str(r.get("id", ""))[:8],
                **(
                    {"tipo_catalogo": r["tipo_catalogo"]}
                    if table_name == "categories" and r.get("tipo_catalogo")
                    else {}
                ),
            }
            for r in rows
        ],
    }


@router.get("/{table_name}")
def list_records(
    request: Request,
    table_name: str,
    visible_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    id_modelo: str | None = None,
    tipo_catalogo: str | None = None,
):
    _schema_for(table_name)
    assert_table_action(table_name, "read", _role(request))
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    select_q = admin_list_select_query(table_name, embed_category=table_name in all_product_tables())
    query = get_db().table(table_name).select(select_q)
    if visible_only:
        query = query.eq("visibilidade", True)
    if id_modelo and table_name in all_colors_tables():
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
def create_record(
    request: Request,
    table_name: str,
    body: dict,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    schema_class = _schema_for(table_name)
    assert_table_action(table_name, "create", _role(request))
    key = (idempotency_key or "").strip()
    op = _idempotency_op(table_name)
    if key:
        try:
            state = begin_idempotent_request(key, op)
        except IdempotencyUnavailable:
            raise HTTPException(status_code=503, detail="Idempotência indisponível.") from None
        if state == "cached":
            cached = get_cached_response(key, op)
            if cached:
                return cached
        if state == "in_progress":
            raise HTTPException(status_code=409, detail="Pedido em processamento — aguarde.")
        if state == "unavailable":
            raise HTTPException(status_code=503, detail="Idempotência indisponível.")
    try:
        body = _resolve_image_fields(table_name, body)
        body = _enrich_create_payload(table_name, body)
        validated = schema_class(**body)
        payload = _normalize_payload(validated.model_dump())
        ins = get_db().table(table_name).insert(payload).execute()
        row = (ins.data or [{}])[0]
        record_id = str(row.get("id") or "")
        if key:
            complete_idempotent_request(key, op, row)
        _invalidate_catalog_cache()
        _audit(request, "create", table_name, resource_id=record_id or None)
        _schedule_barcode_update(table_name, record_id, payload.get("ean"))
        if payload.get("visibilidade"):
            cfg = TABLE_MAP.get(table_name, {})
            _publish_catalog_children(table_name, record_id, tipo=cfg.get("ui_catalog_tipo"))
        return row
    except HTTPException:
        if key:
            abort_idempotent_request(key, op)
        raise
    except Exception as exc:
        if key:
            abort_idempotent_request(key, op)
        detail = _client_error(exc)
        if _is_expected_client_conflict(exc):
            logger.warning("Create %s: %s", table_name, detail)
            raise HTTPException(status_code=409, detail=detail) from exc
        logger.error("Create %s: %s", table_name, exc)
        raise HTTPException(status_code=400, detail=detail) from exc


@router.put("/{table_name}/{record_id}")
def update_record(request: Request, table_name: str, record_id: str, body: dict):
    schema_class = _schema_for(table_name)
    assert_table_action(table_name, "update", _role(request))
    try:
        body = {**body, "id": record_id}
        body = _resolve_image_fields(table_name, body)
        body = _enrich_update_payload(table_name, body, record_id)
        validated = schema_class(**body)
        payload = _normalize_payload(validated.model_dump())
        payload.pop("id", None)
        payload.pop("created_at", None)
        res = get_db().table(table_name).update(payload).eq("id", record_id).execute()
        _invalidate_catalog_cache()
        _audit(request, "update", table_name, resource_id=record_id)
        _schedule_barcode_update(table_name, record_id, payload.get("ean"))
        if payload.get("visibilidade"):
            cfg = TABLE_MAP.get(table_name, {})
            _publish_catalog_children(table_name, record_id, tipo=cfg.get("ui_catalog_tipo"))
            if table_name == "categories":
                _cascade_category_visibility(record_id, True)
        elif table_name == "categories" and "visibilidade" in payload and not payload.get("visibilidade"):
            _cascade_category_visibility(record_id, False)
        return (res.data or [{}])[0] if res.data else {"id": record_id, **payload}
    except Exception as exc:
        detail = _client_error(exc)
        if _is_expected_client_conflict(exc):
            logger.warning("Update %s/%s: %s", table_name, record_id, detail)
            raise HTTPException(status_code=409, detail=detail) from exc
        logger.error("Update %s/%s: %s", table_name, record_id, exc)
        raise HTTPException(status_code=400, detail=detail) from exc


@router.patch("/{table_name}/{record_id}/visibility")
def patch_visibility(request: Request, table_name: str, record_id: str, body: dict):
    """Alterna visibilidade sem revalidar o registo completo."""
    _schema_for(table_name)
    assert_table_action(table_name, "update", _role(request))
    if "visibilidade" not in body:
        raise HTTPException(status_code=400, detail="Campo visibilidade em falta")
    vis = bool(body["visibilidade"])
    if vis and table_name in all_model_tables():
        try:
            _assert_model_publishable(table_name, record_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    res = get_db().table(table_name).update({"visibilidade": vis}).eq("id", record_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registo não encontrado")
    cfg = TABLE_MAP.get(table_name, {})
    tipo = cfg.get("ui_catalog_tipo") or tipo_for_table(table_name)
    if table_name in all_model_tables():
        if vis:
            _publish_catalog_children(table_name, record_id, tipo=tipo)
        else:
            _hide_catalog_children(table_name, record_id, tipo=tipo)
    elif table_name == "categories":
        _cascade_category_visibility(record_id, vis)
    _invalidate_catalog_cache()
    _audit(request, "visibility", table_name, resource_id=record_id, visibilidade=vis)
    return (res.data or [{"id": record_id, "visibilidade": vis}])[0]


@router.post("/{table_name}/{record_id}/publish")
def publish_record(request: Request, table_name: str, record_id: str):
    """Torna o registo visível na loja (e cores/produtos do modelo, se aplicável)."""
    cfg = TABLE_MAP.get(table_name)
    if not cfg:
        raise HTTPException(
            status_code=404,
            detail=f"Tabela «{table_name}» não registada no catálogo",
        )
    assert_table_action(table_name, "update", _role(request))
    if table_name in all_model_tables():
        try:
            _assert_model_publishable(table_name, record_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    db = get_db()
    res = db.table(table_name).update({"visibilidade": True}).eq("id", record_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registo não encontrado")

    tipo = cfg.get("ui_catalog_tipo")
    if cfg.get("ui_embed_colors") and tipo:
        ct = colors_table_for_tipo(tipo)
        if ct:
            db.table(ct).update({"visibilidade": True}).eq("id_modelo", record_id).execute()

    if table_name in all_model_tables() and tipo:
        _publish_catalog_children(table_name, record_id, tipo=tipo)
    elif table_name == "categories":
        _cascade_category_visibility(record_id, True)

    _invalidate_catalog_cache()
    _audit(request, "publish", table_name, resource_id=record_id)
    return (res.data or [{"id": record_id, "visibilidade": True}])[0]


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
    if hard and table_name in SENSITIVE_BUSINESS_TABLES:
        hard = False
    action = "hard_delete" if hard else "delete"
    assert_table_action(table_name, action, _role(request))
    try:
        if hard:
            db = get_db()
            if table_name in all_model_tables():
                ct = colors_table_for_model_table(table_name)
                if ct:
                    db.table(ct).delete().eq("id_modelo", record_id).execute()
                for t, cfg in CATALOG_TYPES.items():
                    if cfg["model_table"] == table_name:
                        db.table(cfg["product_table"]).delete().eq("id_modelo", record_id).execute()
                        break
            db.table(table_name).delete().eq("id", record_id).execute()
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
        raise HTTPException(status_code=400, detail=_client_error(exc)) from exc
