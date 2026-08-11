"""Plano de criação de categorias — lê CATEGORY_DEFINITIONS."""
from __future__ import annotations

from models.schemas import CATEGORY_DEFINITIONS, generate_slug


def _existing_category_keys(existing_rows: list[dict]) -> tuple[set[str], set[str]]:
    existing_slugs: set[str] = set()
    existing_tipos: set[str] = set()
    for row in existing_rows:
        slug = str((row.get("slug") or "")).strip().lower()
        if slug:
            existing_slugs.add(slug)
        nome = str((row.get("nome") or "")).strip()
        if nome:
            existing_slugs.add(generate_slug(nome).lower())
        tipo = str((row.get("tipo_catalogo") or "")).strip().lower()
        if tipo:
            existing_tipos.add(tipo)
    return existing_slugs, existing_tipos


def _definition_item(slug: str, definition: dict) -> dict:
    return {
        "slug": slug,
        "nome": definition.get("nome") or slug.replace("-", " ").title(),
        "tipo_catalogo": definition.get("tipo_catalogo"),
        "carrinho_step": definition.get("carrinho_step"),
        "carrinho_min": definition.get("carrinho_min"),
    }


def build_category_creation_plan(existing_rows: list[dict]) -> dict:
    existing_slugs, existing_tipos = _existing_category_keys(existing_rows)
    missing = []
    for slug, definition in CATEGORY_DEFINITIONS.items():
        tipo = str(definition.get("tipo_catalogo") or "").strip().lower()
        if slug.lower() in existing_slugs or (tipo and tipo in existing_tipos):
            continue
        missing.append(_definition_item(slug, definition))

    if not missing:
        return {
            "can_create": False,
            "missing": [],
            "message": "Já existem todas as categorias definidas no schema.",
        }
    return {
        "can_create": True,
        "missing": missing,
        "message": "Escolhe uma categoria para criar, ou cria só as que ainda não existem.",
    }
