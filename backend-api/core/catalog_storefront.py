"""Queries genéricas de catálogo para a loja — derivadas de CATALOG_TYPES."""



from __future__ import annotations



from core.database import get_db

from core.visibility import is_visible

from models.catalog_registry import CATALOG_TYPES, colors_table_for_tipo, is_valid_tipo

from models.storefront_meta import attach_storefront_fields, storefront_context_for_tipo





def _visible_products(rows: list[dict] | None) -> list[dict]:

    return [row for row in (rows or []) if is_visible(row)]





def _modelo_cores(data: dict) -> list[dict]:

    cores = [c for c in (data.get("modelo_cores") or []) if is_visible(c)]

    cores.sort(key=lambda c: c.get("numero", 0))

    return cores





def _product_select_fields(product_schema) -> str:
    fields = ["id", "ean", "barcode_url", "visibilidade"]
    for fname in product_schema.model_fields:
        if fname in fields or fname in ("id", "id_modelo", "barcode_url", "visibilidade"):
            continue
        if fname in ("dimensoes", "altura", "segmento"):
            fields.append(fname)
    return ", ".join(fields)





def _category_select() -> str:

    return "id, nome, carrinho_step, carrinho_min, slug, tipo_catalogo"





def _attach_modelo_cores(rows: list[dict], *, tipo: str | None = None) -> None:

    """Cores do modelo — tabela dedicada por família de catálogo."""

    if not rows:

        return



    colors_table = colors_table_for_tipo(tipo) if tipo else None

    if not colors_table:

        return



    db = get_db()

    model_ids = [str(row["id"]) for row in rows if row.get("id")]

    cores_by_model: dict[str, list[dict]] = {mid: [] for mid in model_ids}



    if model_ids:

        direct = (

            db.table(colors_table)

            .select("id_modelo, numero, nome, imagem, visibilidade")

            .in_("id_modelo", model_ids)

            .execute()

            .data

            or []

        )

        for cor in direct:

            mid = str(cor.get("id_modelo") or "")

            if mid in cores_by_model:

                cores_by_model[mid].append(cor)



    for row in rows:

        mid = str(row.get("id") or "")

        row["modelo_cores"] = _modelo_cores({"modelo_cores": cores_by_model.get(mid, [])})





def _lookup_cor_nome(db, *, id_modelo: str | None, numero_cor: int, tipo: str | None = None) -> str:

    cor_nome = f"Cor {numero_cor}"

    if not id_modelo:

        return cor_nome

    colors_table = colors_table_for_tipo(tipo)

    if not colors_table:

        for t in CATALOG_TYPES:

            colors_table = colors_table_for_tipo(t)

            if not colors_table:

                continue

            cr = (

                db.table(colors_table)

                .select("nome, numero")

                .eq("id_modelo", str(id_modelo))

                .eq("numero", numero_cor)

                .limit(1)

                .execute()

            )

            if cr.data:

                return cr.data[0].get("nome") or cor_nome

        return cor_nome

    cr = (

        db.table(colors_table)

        .select("nome, numero")

        .eq("id_modelo", str(id_modelo))

        .eq("numero", numero_cor)

        .limit(1)

        .execute()

    )

    if cr.data:

        return cr.data[0].get("nome") or cor_nome

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





def _finalize_model_products(row: dict, cfg: dict, pt: str, mode: str) -> bool:
    """Ordena variantes visíveis; devolve False se não houver produto publicável."""
    products = _visible_products(row.get(pt) if isinstance(row.get(pt), list) else [row.get(pt)] if row.get(pt) else [])

    if mode == "unico":
        if not products:
            return False
        row[pt] = products[0] if len(products) == 1 else products
        return True

    if mode == "assento":
        if not products:
            return False
        products.sort(key=lambda p: str(p.get("altura") or ""))
        row[pt] = products
        return True

    if not products:
        return False
    products.sort(key=lambda p: str(p.get("dimensoes") or p.get("segmento") or ""))
    row[pt] = products
    return True


def catalogue_models_for_tipo(
    tipo: str,
    id_categoria: str,
    *,
    filters: dict[str, str] | None = None,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> list[dict]:

    if not is_valid_tipo(tipo):

        return []

    if not _require_public_category(id_categoria):

        return []



    cfg = CATALOG_TYPES[tipo]

    mode = cfg.get("storefront_mode") or "variantes"

    mt = cfg["model_table"]

    pt = cfg["product_table"]

    product_fields = _product_select_fields(cfg["product_schema"])



    active_filters = dict(filters or {})
    if filter_field and filter_value:
        active_filters[filter_field] = filter_value

    query = (
        get_db()
        .table(mt)
        .select(f"*, categories({_category_select()}), {pt}({product_fields})")
        .eq("id_categoria", id_categoria)
        .eq("visibilidade", True)
    )

    for field, value in active_filters.items():
        if field and value:
            query = query.eq(field, value)

    rows = query.order("nome").execute().data or []
    _attach_modelo_cores(rows, tipo=tipo)
    out: list[dict] = []

    for row in rows:
        row = attach_storefront_fields(dict(row), cfg)
        row["modelo_cores"] = _modelo_cores(row)
        if not _finalize_model_products(row, cfg, pt, mode):
            continue

        row["_tipo_catalogo"] = tipo
        row["_storefront"] = storefront_context_for_tipo(cfg)
        row["_storefront_mode"] = mode
        out.append(row)

    return out


def catalogue_models_aggregated(
    virtual_tipo: str,
    id_categoria: str,
    *,
    filters: dict[str, str] | None = None,
) -> list[dict]:
    from models.schemas import aggregated_tipos_for_tipo

    if not _require_public_category(id_categoria):
        return []

    tipos = aggregated_tipos_for_tipo(virtual_tipo) or []
    family = (filters or {}).get("_tipo_catalogo")
    db_filters = {k: v for k, v in (filters or {}).items() if not k.startswith("_")}
    out: list[dict] = []

    for physical in tipos:
        if family and physical != family:
            continue
        rows = catalogue_models_for_tipo(physical, id_categoria, filters=db_filters)
        for row in rows:
            row["_tipo_catalogo"] = physical
            row["_category_tipo"] = virtual_tipo
            row["_familia_label"] = CATALOG_TYPES[physical]["label"]
            out.append(row)

    out.sort(key=lambda r: str(r.get("nome") or ""))
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

            for k in ("id", "nome", "carrinho_step", "carrinho_min", "slug", "tipo_catalogo")

        }



    _attach_modelo_cores([data], tipo=tipo)

    data = attach_storefront_fields(dict(data), cfg)

    data["modelo_cores"] = _modelo_cores(data)



    raw_products = data.get(pt)
    if isinstance(raw_products, dict):
        raw_products = [raw_products]
    products = _visible_products(raw_products)

    if not _finalize_model_products(data, cfg, pt, mode):
        return None

    ctx = storefront_context_for_tipo(cfg)
    data["_tipo_catalogo"] = tipo
    data["_storefront"] = ctx
    data["_storefront_mode"] = mode
    return data


def _resolve_public_category_id(category_slug: str) -> str | None:
    db = get_db()
    key = (category_slug or "").strip()
    if not key:
        return None
    query = db.table("categories").select("id,visibilidade,slug").eq("visibilidade", True)
    if len(key) == 36 and key.count("-") == 4:
        query = query.eq("id", key)
    else:
        query = query.eq("slug", key)
    row = query.limit(1).execute().data
    if not row:
        return None
    return str(row[0]["id"])


def model_detail_for_slugs_query(tipo: str, category_slug: str, model_slug: str) -> dict | None:
    from models.schemas import aggregated_tipos_for_tipo

    if aggregated_tipos_for_tipo(tipo):
        category_id = _resolve_public_category_id(category_slug)
        if not category_id:
            return None
        model_key = (model_slug or "").strip()
        if not model_key:
            return None
        for physical in aggregated_tipos_for_tipo(tipo) or []:
            cfg = CATALOG_TYPES[physical]
            mt = cfg["model_table"]
            query = (
                get_db()
                .table(mt)
                .select("id")
                .eq("id_categoria", category_id)
                .eq("visibilidade", True)
            )
            if len(model_key) == 36 and model_key.count("-") == 4:
                query = query.eq("id", model_key)
            else:
                query = query.eq("slug", model_key)
            res = query.limit(1).execute()
            row = (res.data or [None])[0]
            if not row and not (len(model_key) == 36 and model_key.count("-") == 4):
                res = (
                    get_db()
                    .table(mt)
                    .select("id")
                    .eq("id_categoria", category_id)
                    .eq("visibilidade", True)
                    .ilike("nome", model_key)
                    .limit(1)
                    .execute()
                )
                row = (res.data or [None])[0]
            if row:
                data = model_detail_for_tipo_query(physical, str(row["id"]))
                if data:
                    data["_tipo_catalogo"] = physical
                    data["_category_tipo"] = tipo
                    data["_familia_label"] = cfg["label"]
                    return data
        return None

    if not is_valid_tipo(tipo):
        return None
    category_id = _resolve_public_category_id(category_slug)
    if not category_id:
        return None

    cfg = CATALOG_TYPES[tipo]
    mt = cfg["model_table"]
    model_key = (model_slug or "").strip()
    if not model_key:
        return None

    query = (
        get_db()
        .table(mt)
        .select(f"*, categories(*), {cfg['product_table']}(*)")
        .eq("id_categoria", category_id)
        .eq("visibilidade", True)
    )
    if len(model_key) == 36 and model_key.count("-") == 4:
        query = query.eq("id", model_key)
    else:
        query = query.eq("slug", model_key)

    res = query.limit(1).execute()
    data = (res.data or [None])[0]
    if not data and not (len(model_key) == 36 and model_key.count("-") == 4):
        res = (
            get_db()
            .table(mt)
            .select(f"*, categories(*), {cfg['product_table']}(*)")
            .eq("id_categoria", category_id)
            .eq("visibilidade", True)
            .ilike("nome", model_key)
            .limit(1)
            .execute()
        )
        data = (res.data or [None])[0]
    if not data:
        return None
    return model_detail_for_tipo_query(tipo, str(data["id"]))


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

            numero_cor=numero_cor,

            tipo=tipo,

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

