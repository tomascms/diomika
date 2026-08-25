"""Testes do plano de criação de categorias."""

from core.category_flow import build_category_creation_plan


def test_returns_no_missing_when_all_categories_exist():
    existing_rows = [{"slug": "almofadas"}, {"slug": "assentos"}]
    plan = build_category_creation_plan(existing_rows)
    assert plan["can_create"] is False
    assert plan["missing"] == []


def test_returns_only_missing_categories_when_some_are_absent():
    existing_rows = [{"slug": "almofadas"}]
    plan = build_category_creation_plan(existing_rows)
    assert plan["can_create"] is True
    assert [item["slug"] for item in plan["missing"]] == ["assentos"]


def test_matches_by_tipo_catalogo_when_slug_differs():
    existing_rows = [
        {"nome": "Almofadas Premium", "slug": "almofadas-premium", "tipo_catalogo": "almofada"},
    ]
    plan = build_category_creation_plan(existing_rows)
    assert plan["can_create"] is True
    assert [item["slug"] for item in plan["missing"]] == ["assentos"]


def test_should_show_creation_when_no_categories_exist():
    plan = build_category_creation_plan([])
    assert plan["can_create"] is True
    assert len(plan["missing"]) >= 1
