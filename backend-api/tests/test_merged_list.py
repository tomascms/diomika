"""Testes da lista merged do admin (filtro categoria/modelo)."""

from unittest.mock import MagicMock, patch

from routes.catalog_generic import _fetch_merged_table_page, _model_ids_by_table_for_category


def test_fetch_merged_produtos_empty_model_ids_returns_list_not_crash():
    """Família sem modelos na categoria deve devolver [] sem AttributeError."""
    with patch("routes.catalog_generic.get_db"):
        out = _fetch_merged_table_page(
            view_key="produtos",
            ptable="toalha_mesa",
            visible_only=False,
            per_table=40,
            categoria_id="cat-123",
            modelo_id=None,
            model_ids_by_mt={"modelos_toalhas_mesa": []},
        )
    assert out == []


def test_fetch_merged_produtos_skips_table_without_models():
    with patch("routes.catalog_generic.get_db") as mock_db:
        out = _fetch_merged_table_page(
            view_key="produtos",
            ptable="almofada",
            visible_only=False,
            per_table=40,
            categoria_id="cat-123",
            modelo_id=None,
            model_ids_by_mt={"modelos_toalha_mesa": ["m1"]},
        )
    assert out == []
    mock_db.assert_not_called()


def test_model_ids_by_table_for_category_groups_by_model_table():
    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.data = [{"id": "m1"}, {"id": "m2"}]
    chain = mock_db.table.return_value.select.return_value.eq.return_value
    chain.execute.return_value = mock_execute

    with patch("routes.catalog_generic.get_db", return_value=mock_db):
        with patch("routes.catalog_generic.CATALOG_TYPES", {
            "toalha_mesa": {"model_table": "modelos_toalha_mesa"},
            "almofada": {"model_table": "modelos_almofada"},
        }):
            out = _model_ids_by_table_for_category("cat-1")

    assert "modelos_toalha_mesa" in out or "modelos_almofada" in out
