"""Cache invalidation strategy — granular vs broad invalidation.

Problema atual: invalidate_prefix("catalog:list:tipo:*") invalida TODAS as categorias.
Solução: Invalidar apenas chaves afectadas (categoria específica, modelo específico).

Estratégias:
1. Surgical: Invalida chaves específicas (modelo X, categoria Y)
2. Category-wide: Invalida todas as variantes de uma categoria
3. Type-wide: Invalida toda uma família de produtos
4. Global: Invalida tudo (fallback seguro)
"""
from enum import Enum
from typing import Optional


class InvalidationStrategy(str, Enum):
    """Estratégias de invalidação disponíveis."""

    SURGICAL = "surgical"          # Apenas chaves afectadas (modelo/cor/produto específico)
    CATEGORY_WIDE = "category"     # Todas variantes de uma categoria
    TYPE_WIDE = "type"             # Toda a família de produtos
    GLOBAL = "global"              # Tudo (fallback seguro, caro)


class CacheInvalidationAnalyzer:
    """Analisa mudanças e determina melhor estratégia de invalidação."""

    @staticmethod
    def get_strategy_for_change(
        table_name: str,
        old_record: Optional[dict] = None,
        new_record: Optional[dict] = None,
    ) -> InvalidationStrategy:
        """
        Determina estratégia baseada no tipo de mudança.

        Args:
        - table_name: Nome da tabela (modelos_almofada, almofada, cores_almofada, etc)
        - old_record: Valor anterior (None em creates)
        - new_record: Valor novo (None em deletes)

        Returns:
        - InvalidationStrategy recomendada
        """
        if not table_name:
            return InvalidationStrategy.GLOBAL

        table_lower = table_name.lower()
        old = old_record or {}
        new = new_record or {}

        # Deleted records: surgical (não afectam buscas futuras de novo)
        if old and not new:
            return InvalidationStrategy.SURGICAL

        # Model updates: check se categoria mudou
        if "modelos_" in table_lower and old and new:
            old_cat = str(old.get("id_categoria") or "")
            new_cat = str(new.get("id_categoria") or "")
            if old_cat != new_cat:
                # Categoria mudou → category-wide em AMBAS categorias
                return InvalidationStrategy.CATEGORY_WIDE
            # Categoria mantém-se → surgical
            return InvalidationStrategy.SURGICAL

        # Product/Color updates: check se modelo mudou
        if table_lower in ("almofada", "cadeira", "mesas", "oculo", "regional",
                          "cores_almofada", "cores_cadeira", "cores_mesas",
                          "cores_oculo", "cores_regional"):
            old_modelo = str(old.get("id_modelo") or "")
            new_modelo = str(new.get("id_modelo") or "")
            if old_modelo != new_modelo:
                # Modelo mudou → category-wide
                return InvalidationStrategy.CATEGORY_WIDE
            # Modelo mantém-se → surgical
            return InvalidationStrategy.SURGICAL

        # Default: usar category-wide para segurança
        return InvalidationStrategy.CATEGORY_WIDE

    @staticmethod
    def should_invalidate_prefix_search() -> bool:
        """Verifica se deve invalidar buscas de slug (sempre que nome/slug muda)."""
        return True  # Sempre invalida slug cache (relativamente rápido recompilar)


class GranularCacheInvalidator:
    """Executa invalidação granular usando estratégia determinada."""

    @staticmethod
    def invalidate_surgical(
        table_name: str,
        record_id: str,
        tipo: Optional[str] = None,
        id_modelo: Optional[str] = None,
        id_categoria: Optional[str] = None,
    ) -> int:
        """
        Invalida apenas chaves diretamente afectadas.

        Returns: Número de chaves invalidadas
        """
        from core.cache import invalidate_key

        count = 0

        # Sempre invalida meta
        count += invalidate_key("catalog:meta")

        # Se é modelo: invalida apenas este modelo
        if tipo and id_modelo:
            count += invalidate_key(f"catalog:modelo-auto:{id_modelo}")
            count += invalidate_key(f"catalog:modelo:{tipo}:{id_modelo}")

        # Se é produto/cor: invalida apenas este item (via modelo)
        if tipo and id_modelo:
            count += invalidate_key(f"catalog:modelo-auto:{id_modelo}")

        # Se tem categoria: invalida apenas listagens de esta categoria
        if tipo and id_categoria:
            count += invalidate_key(f"catalog:list:{tipo}:{id_categoria}")

        return count

    @staticmethod
    def invalidate_category_wide(
        tipo: Optional[str] = None,
        id_categoria: Optional[str] = None,
    ) -> int:
        """
        Invalida todas variantes de uma categoria.

        Returns: Número de chaves invalidadas
        """
        from core.cache import invalidate_prefix, invalidate_key

        count = 0
        count += invalidate_key("catalog:meta")

        # Invalida todas as páginas/filtros desta categoria
        if tipo and id_categoria:
            count += invalidate_prefix(f"catalog:list:{tipo}:{id_categoria}:")

        # Invalida slug cache (pode ter mudado nome)
        count += invalidate_prefix("catalog:modelo-slug:")

        return count

    @staticmethod
    def invalidate_type_wide(tipo: Optional[str] = None) -> int:
        """
        Invalida toda uma família de produtos.

        Returns: Número de chaves invalidadas
        """
        from core.cache import invalidate_prefix, invalidate_key

        count = 0
        count += invalidate_key("catalog:meta")

        if tipo:
            count += invalidate_prefix(f"catalog:list:{tipo}:")
            count += invalidate_prefix(f"catalog:modelo:{tipo}:")

        count += invalidate_prefix("catalog:modelo-slug:")

        return count

    @staticmethod
    def invalidate_global() -> int:
        """
        Invalida tudo (fallback seguro, caro).

        Returns: Número de chaves invalidadas
        """
        from core.cache import invalidate_prefix, invalidate_key

        count = 0
        count += invalidate_prefix("admin:merged:")
        count += invalidate_key("catalog:meta")
        count += invalidate_prefix("categories:")
        count += invalidate_prefix("catalog:")

        return count

    @staticmethod
    def execute_strategy(
        strategy: InvalidationStrategy,
        table_name: str,
        tipo: Optional[str] = None,
        id_modelo: Optional[str] = None,
        id_categoria: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> int:
        """
        Executa invalidação de acordo com estratégia.

        Returns: Número de chaves invalidadas
        """
        if strategy == InvalidationStrategy.SURGICAL:
            return GranularCacheInvalidator.invalidate_surgical(
                table_name, record_id or "", tipo, id_modelo, id_categoria
            )
        elif strategy == InvalidationStrategy.CATEGORY_WIDE:
            return GranularCacheInvalidator.invalidate_category_wide(tipo, id_categoria)
        elif strategy == InvalidationStrategy.TYPE_WIDE:
            return GranularCacheInvalidator.invalidate_type_wide(tipo)
        else:  # GLOBAL
            return GranularCacheInvalidator.invalidate_global()
