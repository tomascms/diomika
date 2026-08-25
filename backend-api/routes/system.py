from fastapi import APIRouter, HTTPException, Depends, Request
import logging

from core.audit import audit_request
from core.auth import (
    CRUD_INFRA_BLOCKED,
    assert_table_action,
    filter_sidebar_for_role,
    require_admin,
    require_catalog_role,
    require_ops,
    require_pedidos,
    role_can_access_table,
)
from core.config import get_settings
from core.database import get_db
from core.local_only import admin_must_be_local
from core.schema_engine import sync_schema
from models.catalog_registry import catalog_metadata
from models.catalog_views import CATALOG_VIEWS
from models.schemas import TABLE_MAP, sidebar_tables
from models.ui_schema import build_schema_snapshot, get_form_fields, snapshot_hash

logger = logging.getLogger("diomika-api")

router = APIRouter(
    prefix="/system",
    tags=["System"],
    dependencies=[Depends(admin_must_be_local)],
)


@router.get("/workspace")
def workspace_config(request: Request, role=Depends(require_admin)):
    """Config completa do backoffice — sidebar, vistas, schemas (filtrado por role)."""
    sidebar = {}
    for key, cfg in sidebar_tables().items():
        sidebar[key] = {
            "label": cfg.get("label", key),
            "icon": cfg.get("icon", "folder"),
            "ui_mode": cfg.get("ui_mode"),
            "ui_catalog_merged_list": cfg.get("ui_catalog_merged_list") or key in CATALOG_VIEWS,
            "ui_filters": list(cfg.get("ui_filters") or cfg.get("ui_filters_base") or []),
        }
    sidebar = filter_sidebar_for_role(sidebar, str(role))
    tables = {}
    for name, cfg in TABLE_MAP.items():
        if name in CRUD_INFRA_BLOCKED or cfg.get("ui_hidden_infra"):
            continue
        if not role_can_access_table(str(role), name):
            continue
        schema = cfg.get("schema")
        if not schema:
            continue
        tables[name] = {
            "label": cfg.get("label", name),
            "fields": get_form_fields(schema, cfg, name),
            "ui_embed_colors": bool(cfg.get("ui_embed_colors")),
            "ui_list_formatter": cfg.get("ui_list_formatter"),
            "list_label_fields": cfg.get("list_label_fields"),
        }
    for view_key in CATALOG_VIEWS:
        if not role_can_access_table(str(role), view_key):
            continue
        tables[view_key] = {
            "label": CATALOG_VIEWS[view_key]["label"],
            "ui_catalog_merged_list": True,
            "list_label_fields": ["nome"],
        }

    return {
        "sidebar": sidebar,
        "tables": tables,
        "catalog": catalog_metadata(),
        "schema_hash": snapshot_hash(build_schema_snapshot(TABLE_MAP)),
        "actor": getattr(request.state, "api_actor", None),
        "role": role,
    }


@router.get("/schema/form/{table_name}")
def form_schema(request: Request, table_name: str, role=Depends(require_admin)):
    if table_name not in TABLE_MAP or table_name in CRUD_INFRA_BLOCKED:
        raise HTTPException(status_code=404, detail="Categoria não mapeada")
    assert_table_action(table_name, "read", role)
    cfg = TABLE_MAP[table_name]
    schema = cfg.get("schema")
    if not schema:
        raise HTTPException(status_code=404, detail="Sem schema")
    # Não expor metadados internos/callable
    safe_config = {
        k: v
        for k, v in cfg.items()
        if k != "schema" and not callable(v) and not str(k).startswith("_")
    }
    return {
        "table": table_name,
        "label": cfg.get("label", table_name),
        "fields": get_form_fields(schema, cfg, table_name),
        "config": safe_config,
    }


@router.post("/schema/sync")
def run_schema_sync(request: Request, dry_run: bool = False, role=Depends(require_ops)):
    """Sincroniza TABLE_MAP (Pydantic) com a base de dados Supabase — chave ops."""
    try:
        report = sync_schema(supabase=get_db(), apply=not dry_run, dry_run=dry_run)
        audit_request(request, action="schema_sync", resource="system", detail={"dry_run": dry_run})
        return {
            "status": "ok",
            "applied": report.applied,
            "message": report.message,
            "created_tables": report.created_tables,
            "added_columns": report.added_columns,
            "sql_executed": report.sql_executed,
            "sql_pending": report.sql_pending,
            "seeded_categories": report.seeded_categories,
            "new_field_warnings": report.new_field_warnings,
            "incomplete_records": report.incomplete_records,
            "schema_hash": report.schema_hash,
        }
    except Exception as e:
        logger.exception("Schema sync failed")
        raise HTTPException(status_code=500, detail="Erro ao sincronizar schema") from e


@router.post("/apply-deploy-sql")
def apply_deploy_sql(request: Request, role=Depends(require_ops)):
    """Aplica deploy/supabase_pre_deploy.sql (dev local — desactivado em producao)."""
    if get_settings().is_production:
        raise HTTPException(status_code=403, detail="Endpoint desactivado em producao")

    from core.sql_runner import apply_sql_file
    from paths import PROJECT_ROOT

    sql_path = PROJECT_ROOT / "deploy" / "supabase_pre_deploy.sql"
    try:
        via = apply_sql_file(sql_path, interactive=False)
        audit_request(request, action="apply_deploy_sql", resource="system", detail={"via": str(via)})
        return {"status": "ok", "via": via}
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Não foi possível aplicar SQL.") from exc


@router.get("/schema/status", dependencies=[Depends(require_ops)])
def schema_status():
    """Estado do schema sem aplicar alterações."""
    report = sync_schema(supabase=get_db(), apply=False, dry_run=True)
    return {
        "message": report.message,
        "created_tables": report.created_tables,
        "added_columns": report.added_columns,
        "sql_pending": report.sql_pending,
        "seeded_categories": report.seeded_categories,
        "new_field_warnings": report.new_field_warnings,
        "incomplete_records": report.incomplete_records,
        "schema_hash": report.schema_hash,
    }


@router.get("/categories/plan", dependencies=[Depends(require_catalog_role)])
def categories_creation_plan():
    from core.category_flow import build_category_creation_plan

    rows = get_db().table("categories").select("*").execute().data or []
    return build_category_creation_plan(rows)


@router.post("/categories/create")
def create_category_from_form(request: Request, body: dict, role=Depends(require_catalog_role)):
    """Cria categoria pendente — com imagem e regras de carrinho (como backoffice legado)."""
    from core.category_flow import build_category_creation_plan
    from core.cqrs.commands.catalog import CreateCategoryCommand, create_category
    from models.schemas import CATEGORY_DEFINITIONS, Categoria, generate_slug

    slug_key = str(body.get("definition_slug") or body.get("slug") or "").strip().lower()
    definition = CATEGORY_DEFINITIONS.get(slug_key)
    if not definition:
        raise HTTPException(status_code=404, detail="Slug não definido em CATEGORY_DEFINITIONS")

    rows = get_db().table("categories").select("*").execute().data or []
    plan = build_category_creation_plan(rows)
    if not plan.get("can_create"):
        raise HTTPException(status_code=400, detail="Todas as categorias do schema já existem.")
    allowed = {item["slug"] for item in plan.get("missing", [])}
    if slug_key not in allowed:
        raise HTTPException(status_code=400, detail="Esta categoria já existe ou não pode ser criada.")

    nome = str(body.get("nome") or definition.get("nome") or "").strip()
    slug_override = str(body.get("slug_override") or slug_key).strip().lower()
    imagem = str(body.get("imagem") or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Nome é obrigatório.")
    if not imagem:
        raise HTTPException(status_code=400, detail="Imagem é obrigatória — escolha um ficheiro.")

    from utils.image_urls import is_http_url, resolve_image_value

    if not is_http_url(imagem):
        imagem = resolve_image_value(imagem, "categories", "imagem")

    try:
        step = int(body["carrinho_step"]) if body.get("carrinho_step") not in (None, "") else definition.get("carrinho_step")
        min_val = int(body["carrinho_min"]) if body.get("carrinho_min") not in (None, "") else definition.get("carrinho_min")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Passo e mínimo devem ser números válidos.") from exc

    payload = Categoria(
        nome=nome,
        slug=generate_slug(slug_override or nome),
        imagem=imagem,
        tipo_catalogo=definition.get("tipo_catalogo"),
        carrinho_step=step,
        carrinho_min=min_val,
    )
    result = create_category(CreateCategoryCommand(payload=payload.model_dump()))
    audit_request(
        request,
        action="create",
        resource="categories",
        resource_id=str((result or {}).get("id") or ""),
        detail={"slug": slug_key},
    )
    return result


@router.post("/categories/seed/{slug}")
def seed_category_from_definition(request: Request, slug: str, role=Depends(require_catalog_role)):
    from models.schemas import CATEGORY_DEFINITIONS, Categoria

    settings = get_settings()
    if settings.is_production and not settings.is_beta:
        raise HTTPException(
            status_code=403,
            detail="Seed com placeholder desactivado em produção final — use /categories/create.",
        )
    definition = CATEGORY_DEFINITIONS.get(slug)
    if not definition:
        raise HTTPException(status_code=404, detail="Slug não definido em CATEGORY_DEFINITIONS")
    payload = Categoria(
        nome=definition["nome"],
        slug=slug,
        imagem="https://via.placeholder.com/800x200?text=Categoria",
        tipo_catalogo=definition.get("tipo_catalogo"),
        carrinho_step=definition.get("carrinho_step"),
        carrinho_min=definition.get("carrinho_min"),
    )
    from core.cqrs.commands.catalog import CreateCategoryCommand, create_category

    result = create_category(CreateCategoryCommand(payload=payload.model_dump()))
    audit_request(
        request,
        action="seed",
        resource="categories",
        resource_id=str((result or {}).get("id") or ""),
        detail={"slug": slug},
    )
    return result


@router.get("/order-picker/{category_id}", dependencies=[Depends(require_pedidos)])
def order_picker_for_category(category_id: str):
    """Dados para criar linhas de encomenda — genérico por tipo de catálogo."""
    from models.catalog_registry import CATALOG_TYPES, storefront_mode_for_tipo

    cat_res = get_db().table("categories").select("*").eq("id", category_id).execute()
    if not cat_res.data:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    cat = cat_res.data[0]
    tipo = cat.get("tipo_catalogo")
    if not tipo or tipo not in CATALOG_TYPES:
        raise HTTPException(status_code=400, detail="Categoria sem tipo de catálogo válido")
    cfg = CATALOG_TYPES[tipo]
    mode = storefront_mode_for_tipo(tipo)
    step = cat.get("carrinho_step") or 6
    min_q = cat.get("carrinho_min") or step

    db = get_db()
    if mode == "assento":
        mt = cfg["model_table"]
        pt = cfg["product_table"]
        models_res = db.table(mt).select("id, nome, alturas").eq("id_categoria", category_id).execute()
        lines = []
        for m in models_res.data or []:
            prod = (
                db.table(pt).select("ean").eq("id_modelo", m["id"]).limit(1).execute().data
                or [{}]
            )[0]
            cores = (
                db.table("modelo_cores")
                .select("numero, nome")
                .eq("id_modelo", m["id"])
                .eq("visibilidade", True)
                .execute()
                .data
                or []
            )
            lines.append(
                {
                    "modelo_id": m["id"],
                    "modelo_nome": m["nome"],
                    "ean": prod.get("ean"),
                    "alturas": m.get("alturas") or [],
                    "cores": cores,
                }
            )
        return {"mode": "assento", "tipo": tipo, "carrinho_step": step, "carrinho_min": min_q, "models": lines}

    pt = cfg["product_table"]
    mt = cfg["model_table"]
    models = (
        db.table(mt)
        .select("id, nome")
        .eq("id_categoria", category_id)
        .eq("visibilidade", True)
        .execute()
        .data
        or []
    )
    model_by_id = {str(m["id"]): m for m in models}
    model_ids = list(model_by_id.keys())
    if not model_ids:
        return {"mode": "variantes", "tipo": tipo, "carrinho_step": step, "carrinho_min": min_q, "products": []}

    products = (
        db.table(pt)
        .select("ean, dimensoes, id_modelo")
        .in_("id_modelo", model_ids)
        .eq("visibilidade", True)
        .execute()
        .data
        or []
    )
    cores_map: dict[str, list] = {}
    cores_res = (
        db.table("modelo_cores")
        .select("id_modelo, numero, nome")
        .in_("id_modelo", model_ids)
        .eq("visibilidade", True)
        .execute()
    )
    for c in cores_res.data or []:
        mid = str(c["id_modelo"])
        cores_map.setdefault(mid, []).append({"numero": c["numero"], "nome": c.get("nome") or ""})

    enriched = []
    for p in products:
        mid = str(p.get("id_modelo") or "")
        modelo = model_by_id.get(mid) or {}
        enriched.append(
            {
                "ean": p["ean"],
                "dimensoes": p.get("dimensoes"),
                "modelo_nome": modelo.get("nome") or "",
                "cores": cores_map.get(mid, []),
            }
        )
    return {"mode": "variantes", "tipo": tipo, "carrinho_step": step, "carrinho_min": min_q, "products": enriched}
