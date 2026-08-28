"""Queries de listagem do catálogo."""
from __future__ import annotations


def test_list_select_query_product_joins_category_via_model():
    from models.catalog_registry import list_select_query

    assert list_select_query("almofada") == "*, modelos_almofadas(nome, dimensoes, categories(nome))"
    assert list_select_query("assento") == "*, modelos_assentos(nome, alturas, categories(nome))"


def test_list_select_query_model_joins_category_directly():
    from models.catalog_registry import list_select_query

    assert list_select_query("modelos_almofadas") == "*, categories(nome)"


def test_storefront_tipo_includes_aggregated():
    from models.catalog_registry import is_valid_storefront_tipo, storefront_filters_for_category_tipo

    assert is_valid_storefront_tipo("material_cozinha")
    assert not is_valid_storefront_tipo("unknown")
    filters = storefront_filters_for_category_tipo("material_cozinha")
    assert filters[0]["field"] == "_tipo_catalogo"
    assert "avental" in filters[0]["options"]


def test_catalog_types_registered():
    from models.schemas import CATALOG_TYPES

    expected = {
        "almofada",
        "assento",
        "guarda_chuva",
        "oculo",
        "toalha_mesa",
        "avental",
        "luva",
        "pega",
        "pano_cozinha",
        "protetor_colchao",
        "passadeira",
        "regional",
    }
    assert set(CATALOG_TYPES) == expected
    assert CATALOG_TYPES["almofada"]["model_discriminator_field"] == "dimensoes"
