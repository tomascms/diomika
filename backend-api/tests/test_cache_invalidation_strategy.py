"""Testes para estratégia de cache invalidation granular."""
import pytest

from core.cache_invalidation_strategy import (
    InvalidationStrategy,
    CacheInvalidationAnalyzer,
)


class TestInvalidationStrategySelection:
    """Testes de seleção automática de estratégia."""

    def test_delete_uses_surgical(self):
        """Deletar um record usa surgical (apenas este record)."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "almofada",
            old_record={"id": "123", "id_modelo": "m1"},
            new_record=None,  # Deleted
        )
        assert strategy == InvalidationStrategy.SURGICAL

    def test_model_update_same_category_surgical(self):
        """Update modelo na mesma categoria usa surgical."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "modelos_almofada",
            old_record={"id": "m1", "id_categoria": "c1", "nome": "Model A"},
            new_record={"id": "m1", "id_categoria": "c1", "nome": "Model B"},
        )
        assert strategy == InvalidationStrategy.SURGICAL

    def test_model_category_change_is_category_wide(self):
        """Update modelo mudando categoria usa category-wide."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "modelos_almofada",
            old_record={"id": "m1", "id_categoria": "c1"},
            new_record={"id": "m1", "id_categoria": "c2"},  # Categoria mudou
        )
        assert strategy == InvalidationStrategy.CATEGORY_WIDE

    def test_product_update_same_model_surgical(self):
        """Update produto no mesmo modelo usa surgical."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "almofada",
            old_record={"id": "p1", "id_modelo": "m1", "ean": "111"},
            new_record={"id": "p1", "id_modelo": "m1", "ean": "222"},
        )
        assert strategy == InvalidationStrategy.SURGICAL

    def test_product_model_change_is_category_wide(self):
        """Update produto mudando modelo usa category-wide."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "almofada",
            old_record={"id": "p1", "id_modelo": "m1"},
            new_record={"id": "p1", "id_modelo": "m2"},  # Modelo mudou
        )
        assert strategy == InvalidationStrategy.CATEGORY_WIDE

    def test_color_update_same_model_surgical(self):
        """Update cor no mesmo modelo usa surgical."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "cores_almofada",
            old_record={"id": "c1", "id_modelo": "m1", "nome": "Red"},
            new_record={"id": "c1", "id_modelo": "m1", "nome": "Blue"},
        )
        assert strategy == InvalidationStrategy.SURGICAL

    def test_create_defaults_to_category_wide(self):
        """Create (old_record=None) usa category-wide por segurança."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "almofada",
            old_record=None,  # Created
            new_record={"id": "p1", "id_modelo": "m1"},
        )
        assert strategy == InvalidationStrategy.CATEGORY_WIDE

    def test_unknown_table_uses_global(self):
        """Table desconhecida usa global (fallback seguro)."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "unknown_table",
            old_record=None,
            new_record={"id": "123"},
        )
        assert strategy == InvalidationStrategy.GLOBAL

    def test_empty_table_name_uses_global(self):
        """Table vazio usa global."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "",
            old_record=None,
            new_record={"id": "123"},
        )
        assert strategy == InvalidationStrategy.GLOBAL

    def test_chair_product_update(self):
        """Teste com cadeira (não almofada)."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "cadeira",
            old_record={"id": "p1", "id_modelo": "m1"},
            new_record={"id": "p1", "id_modelo": "m1"},
        )
        assert strategy == InvalidationStrategy.SURGICAL

    def test_oculos_color_update(self):
        """Teste com óculos."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "cores_oculo",
            old_record={"id": "c1", "id_modelo": "m1"},
            new_record={"id": "c1", "id_modelo": "m1"},
        )
        assert strategy == InvalidationStrategy.SURGICAL

    def test_regional_product_update(self):
        """Teste com produtos regionais."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "regional",
            old_record={"id": "p1", "id_modelo": "m1"},
            new_record={"id": "p1", "id_modelo": "m2"},  # Modelo mudou
        )
        assert strategy == InvalidationStrategy.CATEGORY_WIDE


class TestStrategyComparison:
    """Comparação entre estratégias (impacto de cache)."""

    def test_surgical_vs_category_wide_efficiency(self):
        """Surgical deve ser mais eficiente que category-wide."""
        # Surgical invalida ~3-4 chaves
        surgical_strategy = InvalidationStrategy.SURGICAL

        # Category-wide invalida ~10-20 chaves (todas as páginas/filtros)
        category_strategy = InvalidationStrategy.CATEGORY_WIDE

        # Para um update em modelo específico, surgical é melhor
        chosen = CacheInvalidationAnalyzer.get_strategy_for_change(
            "modelos_almofada",
            old_record={"id": "m1", "id_categoria": "c1", "nome": "A"},
            new_record={"id": "m1", "id_categoria": "c1", "nome": "B"},
        )
        assert chosen == surgical_strategy

    def test_fallback_to_global_on_uncertainty(self):
        """Em caso de dúvida, fallback para global (seguro)."""
        strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
            "mystery_table",
            old_record={"unknown": "fields"},
            new_record={"unknown": "fields"},
        )
        assert strategy == InvalidationStrategy.GLOBAL
