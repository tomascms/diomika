"""Queries genéricas de catálogo para a loja — derivadas de CATALOG_TYPES."""

from __future__ import annotations

from core.database import get_db
from core.visibility import is_visible
from models.catalog_registry import CATALOG_TYPES, is_valid_tipo
from models.storefront_meta import attach_storefront_fields, storefront_context_for_tipo


def _visible_products(rows: list[dict] | None) -> list[dict]:
    return [row for row in (rows or []) if is_visible(row)]


def _modelo_cores(data: dict) -> list[dict]:
    cores = [c for c in (data.get("modelo_cores") or []) if is_visible(c)]
    cores.sort(key=lambda c: c.get("numero", 0))
    return cores


def _product_select_fields(product_schema) -> str:
    fields = ["id", "ean", "barcode_url", "visibilidade"]
    for fname in ("dimensoes",):
        if fname in product_schema.model_fields and fname not in fields:
            fields.append(fname)
    return ", ".join(fields)


def _category_select() -> str:
    return "nome, carrinho_step, carrinho_min, slug, tipo_catalogo"


def _attach_modelo_cores(rows: list[dict]) -> None:
    """Cores por modelo ou paleta — query separada (sem embed PostgREST)."""
    if not rows:
        return

    db = get_db()
    model_ids = [str(row["id"]) for row in rows if row.get("id")]
    cores_by_model: dict[str, list[dict]] = {mid: [] for mid in model_ids}

    if model_ids:
        direct = (
            db.table("modelo_cores")
            .select("id_modelo, numero, nome, imagem, visibilidade, template_modelo")
            .in_("id_modelo", model_ids)
            .execute()
            .data
            or []
        )
        for cor in direct:
            mid = str(cor.get("id_modelo") or "")
            if mid in cores_by_model:
                cores_by_model[mid].append(cor)

    palette_ids = list({str(row["id_paleta"]) for row in rows if row.get("id_paleta")})
    palette_cores: dict[str, list[dict]] = {}
    if palette_ids:
        palette_rows = (
            db.table("modelo_cores")
            .select("id_paleta, template_modelo, numero, nome, imagem, visibilidade")
            .in_("id_paleta", palette_ids)
            .execute()
            .data
            or []
        )
        for cor in palette_rows:
            pid = str(cor.get("id_paleta") or "")
            palette_cores.setdefault(pid, []).append(cor)

    for row in rows:
        mid = str(row.get("id") or "")
        cores = list(cores_by_model.get(mid, []))
        if not cores and row.get("id_paleta"):
            model_name = (row.get("nome") or "").strip()
            for cor in palette_cores.get(str(row["id_paleta"]), []):
                template = (cor.get("template_modelo") or "").strip()
                if template and template != model_name:
                    continue
                cores.append(cor)
        row["modelo_cores"] = _modelo_cores({"modelo_cores": cores})


def _lookup_cor_nome(db, *, id_modelo: str | None, id_paleta: str | None, model_name: str, numero_cor: int) -> str:
    cor_nome = f"Cor {numero_cor}"
    if id_modelo:
        cr = (
            db.table("modelo_cores")
            .select("nome, numero, template_modelo")
            .eq("id_modelo", str(id_modelo))
            .eq("numero", numero_cor)
            .limit(1)
            .execute()
        )
        if cr.data:
            return cr.data[0].get("nome") or cor_nome

    if id_paleta:
        rows = (
            db.table("modelo_cores")
            .select("nome, numero, template_modelo")
            .eq("id_paleta", str(id_paleta))
            .eq("numero", numero_cor)
            .execute()
            .data
            or []
        )
        for row in rows:
            template = (row.get("template_modelo") or "").strip()
            if template and template != model_name:
                continue
            return row.get("nome") or cor_nome
    return cor_nome


def _require_public_category(id_categoria: str) -> bool:
    """Categoria tem de existir e estar visível na loja (anti-IDOR por UUID oculto)."""
    try:
        res = (
            get_db()
            .table("categories")
            .select("id,visibilidade")
            .eq("id", id_categoria)
            .limit(1)
            .execute()
        )
    except Exception:
        return False
    rows = res.data or []
    if not rows:
        return False
    return is_visible(rows[0])


def catalogue_models_for_tipo(tipo: str, id_categoria: str, *, filter_field: str | None = None, filter_value: str | None = None) -> list[dict]:
    if not is_valid_tipo(tipo):
        return []
    if not _require_public_category(id_categoria):
        return []

    cfg = CATALOG_TYPES[tipo]
    mode = cfg.get("storefront_mode") or "variantes"
    mt = cfg["model_table"]
    pt = cfg["product_table"]
    product_fields = _product_select_fields(cfg["product_schema"])

    query = (
        get_db()
        .table(mt)
        .select(f"*, categories({_category_select()}), {pt}({product_fields})")
        .eq("id_categoria", id_categoria)
        .eq("visibilidade", True)
    )

    if filter_field and filter_value:
        query = query.eq(filter_field, filter_value)

    rows = query.order("nome").execute().data or []
    _attach_modelo_cores(rows)
    out: list[dict] = []

    for row in rows:
        row = attach_storefront_fields(dict(row), cfg)
        row["modelo_cores"] = _modelo_cores(row)
        products = _visible_products(row.get(pt) if isinstance(row.get(pt), list) else [row.get(pt)] if row.get(pt) else [])

        if mode == "assento":
            if not products:
                continue
            row[pt] = products[0]
        else:
            if not products:
                continue
            products.sort(key=lambda p: str(p.get("dimensoes") or ""))
            row[pt] = products

        row["_tipo_catalogo"] = tipo
        row["_storefront"] = storefront_context_for_tipo(cfg)
        row["_storefront_mode"] = mode
        out.append(row)

    return out


def model_detail_for_tipo_query(tipo: str, id_modelo: str) -> dict | None:
    if not is_valid_tipo(tipo):
        return None

    cfg = CATALOG_TYPES[tipo]
    mode = cfg.get("storefront_mode") or "variantes"
    mt = cfg["model_table"]
    pt = cfg["product_table"]

    res = (
        get_db()
        .table(mt)
        .select(f"*, categories(*), {pt}(*)")
        .eq("id", id_modelo)
        .single()
        .execute()
    )
    data = res.data
    if not data or not is_visible(data):
        return None

    # Não expor detalhe se a categoria-mãe estiver oculta
    parent = data.get("categories") if isinstance(data.get("categories"), dict) else None
    if parent is not None and not is_visible(parent):
        return None
    if parent is None and data.get("id_categoria") and not _require_public_category(str(data["id_categoria"])):
        return None

    # Só campos públicos da categoria (evita vazar metadata interna)
    if isinstance(data.get("categories"), dict):
        cat = data["categories"]
        data["categories"] = {
            k: cat.get(k)
            for k in ("nome", "carrinho_step", "carrinho_min", "slug", "tipo_catalogo")
        }

    _attach_modelo_cores([data])
    data = attach_storefront_fields(dict(data), cfg)
    data["modelo_cores"] = _modelo_cores(data)

    raw_products = data.get(pt)
    if isinstance(raw_products, dict):
        raw_products = [raw_products]
    products = _visible_products(raw_products)

    if mode == "assento":
        data[pt] = products[0] if products else None
    else:
        products.sort(key=lambda p: str(p.get("dimensoes") or ""))
        data[pt] = products

    ctx = storefront_context_for_tipo(cfg)
    data["_tipo_catalogo"] = tipo
    data["_storefront"] = ctx
    data["_storefront_mode"] = mode
    return data


def resolve_product_line(ean: str, numero_cor: int, altura: str | None = None) -> dict:
    """Resolve EAN + cor (+ altura) para qualquer tipo registado."""
    db = get_db()

    for tipo, cfg in CATALOG_TYPES.items():
        pt = cfg["product_table"]
        mt = cfg["model_table"]
        mode = cfg.get("storefront_mode") or "variantes"

        row = db.table(pt).select(f"*, {mt}(*)").eq("ean", ean).limit(1).execute()
        item = (row.data or [None])[0]
        if not item:
            continue

        modelo = item.get(mt) or {}
        if isinstance(modelo, list) and modelo:
            modelo = modelo[0]
        if not isinstance(modelo, dict):
            modelo = {}

        id_modelo = item.get("id_modelo")
        model_name = modelo.get("nome") or ""
        cor_nome = _lookup_cor_nome(
            db,
            id_modelo=str(id_modelo) if id_modelo else None,
            id_paleta=str(modelo.get("id_paleta")) if modelo.get("id_paleta") else None,
            model_name=model_name,
            numero_cor=numero_cor,
        )

        dim = altura or item.get("dimensoes") or ""
        if mode == "assento" and altura:
            dim = altura

        return {
            "ean": ean,
            "numero_cor": numero_cor,
            "altura": altura or "",
            "modelo": model_name,
            "dimensoes": dim,
            "cor_nome": cor_nome,
            "tipo_produto": tipo,
        }

    return {
        "ean": ean,
        "numero_cor": numero_cor,
        "modelo": "?",
        "dimensoes": "?",
        "cor_nome": f"Cor {numero_cor}",
    }
