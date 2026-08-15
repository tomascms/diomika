#!/usr/bin/env python3
"""
Aplica schema, infra SQL, categorias em falta e produtos de demonstração.

Uso (na raiz do repo):
  python deploy/seed_catalog_demo.py
  python deploy/seed_catalog_demo.py --skip-schema
"""
from __future__ import annotations

import argparse
import sys
from io import BytesIO
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-api"))

from core.env_loader import load_project_env  # noqa: E402

load_project_env()

from core.category_flow import build_category_creation_plan  # noqa: E402
from core.cqrs.commands.catalog import CreateCategoryCommand, create_category  # noqa: E402
from core.database import get_db  # noqa: E402
from core.schema_engine import bootstrap_database_schema, sync_schema  # noqa: E402
from core.sql_runner import apply_sql_file  # noqa: E402
from models.catalog_registry import CATALOG_TYPES  # noqa: E402
from models.schemas import CATEGORY_DEFINITIONS, generate_slug  # noqa: E402
from utils.barcode_gen import apply_barcode_url  # noqa: E402
from utils.storage import upload_bytes  # noqa: E402

LOGO_SVG = ROOT / "frontend-web" / "public" / "brand" / "logo.svg"
EAN_SEQ = 590700000000


def make_ean(n: int) -> str:
    base = str(EAN_SEQ + n).zfill(12)
    digits = [int(d) for d in base]
    check = (10 - (sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10)) % 10
    return base + str(check)


def logo_png_url() -> str:
    if not LOGO_SVG.is_file():
        raise FileNotFoundError(LOGO_SVG)
    svg = LOGO_SVG.read_bytes()
    png: bytes | None = None
    try:
        import cairosvg

        png = cairosvg.svg2png(bytestring=svg, output_width=640)
    except Exception:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGBA", (640, 114), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 48)
        except OSError:
            font = ImageFont.load_default()
        draw.text((24, 32), "DIOMIKA", fill=(20, 20, 20, 255), font=font)
        buf = BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()
    dest = "seed/demo/diomika-logo.png"
    return upload_bytes(png, dest, "image/png")


def apply_extra_sql() -> None:
    sql_dir = ROOT / "backend-api" / "sql"
    deploy_dir = ROOT / "deploy"
    from core.catalog_deploy_sql import write_catalog_infra_sql

    write_catalog_infra_sql()
    for rel in (
        sql_dir / "migration_almofada_dimensoes_modelo.sql",
        sql_dir / "migration_material_to_composicao.sql",
        deploy_dir / "generated_catalog_infra.sql",
        sql_dir / "realtime_publication.sql",
    ):
        if rel.is_file():
            via = apply_sql_file(rel, interactive=False)
            print(f"  SQL {rel.name} via {via}")


def refresh_demo_images(logo_url: str) -> None:
    """Garante logo Diomika em todas as cores dos modelos [TESTE]."""
    db = get_db()
    updated = 0
    for tipo, cfg in CATALOG_TYPES.items():
        mt = cfg["model_table"]
        ct = cfg.get("colors_table")
        if not ct:
            continue
        models = (
            db.table(mt)
            .select("id, nome")
            .ilike("nome", "[TESTE]%")
            .execute()
            .data
            or []
        )
        for model in models:
            mid = str(model["id"])
            cores = (
                db.table(ct)
                .select("id, numero, nome, imagem")
                .eq("id_modelo", mid)
                .order("numero")
                .execute()
                .data
                or []
            )
            if not cores:
                upsert_color(db, ct, mid, 1, "Teste", logo_url)
                upsert_color(db, ct, mid, 2, "Teste 2", logo_url)
                updated += 2
                continue
            for cor in cores:
                if cor.get("imagem") != logo_url or cor.get("visibilidade") is not True:
                    db.table(ct).update({"imagem": logo_url, "visibilidade": True}).eq("id", cor["id"]).execute()
                    updated += 1
            nums = {int(c.get("numero") or 0) for c in cores}
            if 2 not in nums:
                upsert_color(db, ct, mid, 2, "Teste 2", logo_url)
                updated += 1
    print(f"  imagens demo actualizadas: {updated} cor(es)")


def ensure_categories(logo_url: str) -> dict[str, dict]:
    db = get_db()
    rows = db.table("categories").select("*").execute().data or []
    by_tipo = {str(r.get("tipo_catalogo")): r for r in rows if r.get("tipo_catalogo")}
    plan = build_category_creation_plan(rows)
    defaults = {
        "guarda-chuvas": {"carrinho_step": 12, "carrinho_min": 12},
        "oculos": {"carrinho_step": 12, "carrinho_min": 12},
        "toalhas-mesa": {"carrinho_step": 6, "carrinho_min": 6},
        "material-cozinha": {"carrinho_step": 12, "carrinho_min": 12},
        "regional": {"carrinho_step": 6, "carrinho_min": 6},
    }
    for slug, definition in CATEGORY_DEFINITIONS.items():
        tipo = definition["tipo_catalogo"]
        if tipo in by_tipo:
            continue
        extra = defaults.get(slug, {"carrinho_step": 6, "carrinho_min": 6})
        payload = {
            "nome": definition["nome"],
            "slug": slug,
            "imagem": logo_url,
            "tipo_catalogo": tipo,
            "visibilidade": True,
            **extra,
        }
        res = create_category(CreateCategoryCommand(payload=payload))
        row = (res or {}).get("data") or res
        if isinstance(row, dict) and row.get("id"):
            by_tipo[tipo] = row
            print(f"  categoria criada: {definition['nome']} ({tipo})")
    rows = db.table("categories").select("*").execute().data or []
    return {str(r.get("tipo_catalogo")): r for r in rows if r.get("tipo_catalogo")}


def upsert_model(db, table: str, payload: dict) -> dict:
    nome = payload["nome"]
    cat = payload["id_categoria"]
    existing = (
        db.table(table)
        .select("*")
        .eq("id_categoria", cat)
        .eq("nome", nome)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        row = existing[0]
        db.table(table).update({k: v for k, v in payload.items() if k != "id"}).eq("id", row["id"]).execute()
        return row
    ins = db.table(table).insert(payload).execute().data[0]
    return ins


def upsert_color(db, table: str, id_modelo: str, numero: int, nome: str, imagem: str) -> None:
    existing = (
        db.table(table)
        .select("id")
        .eq("id_modelo", id_modelo)
        .eq("numero", numero)
        .limit(1)
        .execute()
        .data
        or []
    )
    payload = {
        "id_modelo": id_modelo,
        "numero": numero,
        "nome": nome,
        "imagem": imagem,
        "visibilidade": True,
    }
    if existing:
        db.table(table).update(payload).eq("id", existing[0]["id"]).execute()
    else:
        db.table(table).insert(payload).execute()


def upsert_product(db, table: str, payload: dict) -> None:
    q = db.table(table).select("id").eq("id_modelo", payload["id_modelo"])
    for key in ("dimensoes", "altura", "segmento"):
        if key in payload and payload[key] is not None:
            q = q.eq(key, payload[key])
    existing = q.limit(1).execute().data or []
    data = dict(payload)
    apply_barcode_url(data)
    if existing:
        db.table(table).update(data).eq("id", existing[0]["id"]).execute()
    else:
        db.table(table).insert(data).execute()


def seed_demo(categories: dict[str, dict], logo_url: str) -> None:
    db = get_db()
    ean_i = 0

    def next_ean() -> str:
        nonlocal ean_i
        ean_i += 1
        return make_ean(ean_i)

    def seed_family(tipo: str, model_payload: dict, products: list[dict], color_name: str = "Teste") -> None:
        cfg = CATALOG_TYPES[tipo]
        mt, pt, ct = cfg["model_table"], cfg["product_table"], cfg["colors_table"]
        cat = categories.get(tipo)
        if not cat:
            print(f"  ! categoria em falta para {tipo}")
            return
        model_payload = {
            **model_payload,
            "id_categoria": cat["id"],
            "visibilidade": True,
            "slug": generate_slug(model_payload["nome"]),
        }
        model = upsert_model(db, mt, model_payload)
        mid = str(model["id"])
        upsert_color(db, ct, mid, 1, color_name, logo_url)
        upsert_color(db, ct, mid, 2, f"{color_name} 2", logo_url)
        for prod in products:
            upsert_product(
                db,
                pt,
                {
                    "id_modelo": mid,
                    "ean": next_ean(),
                    "visibilidade": True,
                    **prod,
                },
            )
        print(f"  demo OK: {tipo} — {model_payload['nome']}")

    # Almofada
    seed_family(
        "almofada",
        {
            "nome": "[TESTE] Almofada decorativa",
            "descricao": "Modelo de teste com composição e dimensões.",
            "tipo": "decorativa",
            "composicao": {"algodao": 60, "poliester": 40},
            "dimensoes": ["40x40", "50x50"],
        },
        [{"dimensoes": "40x40"}, {"dimensoes": "50x50"}],
        "Estampa teste",
    )

    # Assento
    seed_family(
        "assento",
        {
            "nome": "[TESTE] Assento conforto",
            "descricao": "Assento demo com alturas múltiplas.",
            "material_forro": "Napa sintética",
            "material_enchimento": "Espuma HR",
            "alturas": ["8cm", "10cm"],
        },
        [{"altura": "8cm"}, {"altura": "10cm"}],
    )

    # Guarda-chuva
    seed_family(
        "guarda_chuva",
        {
            "nome": "[TESTE] Guarda-chuva Grande",
            "descricao": "Guarda-chuva de teste — modelo grande.",
        },
        [{}],
    )

    # Óculos sol + leitura
    seed_family(
        "oculo",
        {
            "nome": "[TESTE] Óculos sol clássico",
            "descricao": "Óculos de sol demo.",
            "tipo_oculo": "sol",
        },
        [
            {"segmento": "homem"},
            {"segmento": "mulher"},
            {"segmento": "crianca"},
        ],
    )
    seed_family(
        "oculo",
        {
            "nome": "[TESTE] Óculos leitura sortido",
            "descricao": "Óculos de leitura — produto sortido.",
            "tipo_oculo": "leitura",
        },
        [{}],
    )

    # Toalha mesa
    seed_family(
        "toalha_mesa",
        {
            "nome": "[TESTE] Toalha PVC floral",
            "descricao": "Toalha de mesa demo.",
            "tipo_produto": "toalha",
            "material": "pvc",
            "composicao": {"pvc": 100},
            "dimensoes": ["140x140", "160x160"],
        },
        [{"dimensoes": "140x140"}, {"dimensoes": "160x160"}],
    )

    # Material cozinha (categoria agregada — mesma id_categoria)
    cozinha_cat = categories.get("material_cozinha")
    if cozinha_cat:
        cid = cozinha_cat["id"]
        for tipo, model_data, prods in [
            (
                "avental",
                {"nome": "[TESTE] Avental chef", "descricao": "Avental demo.", "composicao": {"Algodão": 100}},
                [{}],
            ),
            (
                "luva",
                {"nome": "[TESTE] Luva forno", "descricao": "Luva demo.", "composicao": {"Silicone": 100}},
                [{}],
            ),
            (
                "pega",
                {"nome": "[TESTE] Pega silicone", "descricao": "Pega demo.", "composicao": {"Silicone": 100}},
                [{}],
            ),
            (
                "pano_cozinha",
                {
                    "nome": "[TESTE] Pano multi-uso",
                    "descricao": "Pano demo.",
                    "composicao": {"Microfibra": 100},
                    "dimensoes": ["30x30", "40x40"],
                },
                [{"dimensoes": "30x30"}, {"dimensoes": "40x40"}],
            ),
        ]:
            cfg = CATALOG_TYPES[tipo]
            model = upsert_model(
                db,
                cfg["model_table"],
                {
                    **model_data,
                    "id_categoria": cid,
                    "visibilidade": True,
                    "slug": generate_slug(model_data["nome"]),
                },
            )
            mid = str(model["id"])
            upsert_color(db, cfg["colors_table"], mid, 1, "Teste", logo_url)
            upsert_color(db, cfg["colors_table"], mid, 2, "Teste 2", logo_url)
            for p in prods:
                upsert_product(
                    db,
                    cfg["product_table"],
                    {"id_modelo": mid, "ean": next_ean(), "visibilidade": True, **p},
                )
            print(f"  demo OK: {tipo} (cozinha) — {model_data['nome']}")

    # Regional
    seed_family(
        "regional",
        {
            "nome": "[TESTE] Regional azulejo",
            "descricao": "Produto regional demo.",
            "subtipo": "toalha",
            "composicao": {"pvc": 100},
            "dimensoes": ["140x140"],
        },
        [{"dimensoes": "140x140"}],
        "Azulejo teste",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-schema", action="store_true")
    parser.add_argument("--images-only", action="store_true", help="Só upload logo + imagens [TESTE]")
    args = parser.parse_args()

    print("\n=== 1) Logo Diomika -> storage ===\n")
    logo_url = logo_png_url()
    print(f"  {logo_url[:80]}...")

    if args.images_only:
        print("\n=== Imagens demo [TESTE] ===\n")
        refresh_demo_images(logo_url)
        print("\nOK imagens demo.\n")
        return 0

    if not args.skip_schema:
        print("\n=== 2) Schema sync + SQL infra ===\n")
        bootstrap_database_schema()
        report = sync_schema(supabase=get_db(), apply=True, dry_run=False)
        print(f"  {report.message}")
        if report.created_tables:
            print(f"  tabelas novas: {len(report.created_tables)}")
        apply_extra_sql()

    print("\n=== 3) Categorias ===\n")
    categories = ensure_categories(logo_url)

    print("\n=== 4) Produtos demo ===\n")
    seed_demo(categories, logo_url)

    print("\n=== 5) Imagens demo (logo em todas as cores) ===\n")
    refresh_demo_images(logo_url)

    print("\nOK seed concluído.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
