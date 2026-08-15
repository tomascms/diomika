"""Queries de listagem do catálogo."""
from __future__ import annotations


def test_list_select_query_product_joins_category_via_model():
    from models.catalog_registry import list_select_query

    assert list_select_query("almofada") == "*, modelos_almofadas(nome, categories(nome))"
    assert list_select_query("assento") == "*, modelos_assentos(nome, alturas, categories(nome))"


def test_list_select_query_model_joins_category_directly():
    from models.catalog_registry import list_select_query

    assert list_select_query("modelos_almofadas") == "*, categories(nome)"
