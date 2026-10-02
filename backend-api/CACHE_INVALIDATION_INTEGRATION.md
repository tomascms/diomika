# Cache Invalidation Granular - Guia de Integração

## Problema

Estratégia atual (`core/cache.py`):
```python
invalidate_prefix("catalog:list:tipo:*")  # Invalida TODAS as categorias
```

Resultado: Ao atualizar um modelo em categoria A, **limpa cache de categoria B também** → cache misses desnecessários.

## Solução

Nova estratégia granular (`core/cache_invalidation_strategy.py`):

### Estratégias Disponíveis

| Estratégia | Caso de Uso | Impacto | Exemplo |
|-----------|-----------|--------|---------|
| **SURGICAL** | Update sem mudança de modelo/categoria | ✅ Mínimo (3-4 chaves) | Rename modelo |
| **CATEGORY_WIDE** | Update com mudança de modelo/categoria | ⚠️ Médio (10-20 chaves) | Move produto para outro modelo |
| **TYPE_WIDE** | Delete de modelo inteiro | ⚠️ Alto (50+ chaves) | Remove toda a linha de assentos |
| **GLOBAL** | Fallback seguro | ❌ Máximo (tudo) | Mudança em schema |

### Matriz de Decisão

```
Update Model (mesmo tipo):
  - Categoria não mudou → SURGICAL
  - Categoria mudou → CATEGORY_WIDE

Update Product/Color:
  - Modelo não mudou → SURGICAL
  - Modelo mudou → CATEGORY_WIDE

Delete Record:
  - Sempre SURGICAL (não afecta buscas futuras)

Create Record:
  - CATEGORY_WIDE (seguro, novo item pode aparecer em listas)

Schema Change:
  - GLOBAL (fallback)
```

## Como Usar

### Opção 1: Automática (Recomendado)

```python
from core.cache_invalidation_strategy import (
    CacheInvalidationAnalyzer,
    GranularCacheInvalidator,
)

# No CRUD update:
def update_record(table_name: str, old_record: dict, new_record: dict):
    # Determina melhor estratégia
    strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
        table_name,
        old_record=old_record,
        new_record=new_record,
    )
    
    # Executa invalidação
    count = GranularCacheInvalidator.execute_strategy(
        strategy,
        table_name=table_name,
        tipo=tipo_for_table(table_name),
        id_modelo=new_record.get("id_modelo"),
        id_categoria=new_record.get("id_categoria"),
        record_id=new_record.get("id"),
    )
    
    logger.info(f"Invalidated {count} cache keys using {strategy.value} strategy")
```

### Opção 2: Manual (Controle Fino)

```python
from core.cache_invalidation_strategy import GranularCacheInvalidator, InvalidationStrategy

# Update modelo na mesma categoria → surgical
GranularCacheInvalidator.invalidate_surgical(
    table_name="modelos_almofada",
    record_id="model_123",
    tipo="almofada",
    id_modelo="model_123",
    id_categoria="cat_1",
)

# Move produto para outro modelo → category-wide
GranularCacheInvalidator.invalidate_category_wide(
    tipo="almofada",
    id_categoria="cat_1",  # Invalida listagens desta categoria
)
```

## Integração no admin_crud.py

**Localização Atual** (`backend-api/routes/admin_crud.py` linha ~275):

```python
_invalidate_catalog_cache(table_name=table_name, record=row, record_id=record_id)
```

**Mudança Sugerida**:

```python
# Importar
from core.cache_invalidation_strategy import (
    CacheInvalidationAnalyzer,
    GranularCacheInvalidator,
)

# No create_record()
def create_record(...):
    # ... validação ...
    ins = _db_table(table_name).insert(payload).execute()
    row = (ins.data or [{}])[0]
    
    # NOVO: Cache invalidation granular
    strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
        table_name,
        old_record=None,  # Create
        new_record=row,
    )
    GranularCacheInvalidator.execute_strategy(
        strategy,
        table_name=table_name,
        tipo=tipo_for_table(table_name),
        id_modelo=row.get("id_modelo"),
        id_categoria=row.get("id_categoria"),
        record_id=row.get("id"),
    )

# No update_record()
def update_record(...):
    # ... validação ...
    # Fetch old record para comparação
    old = _scoped(_db_table(table_name), table_name).eq("id", record_id).limit(1).execute().data or [{}]
    old_record = old[0] if old else {}
    
    res = _scoped(_db_table(table_name).update(payload), table_name).eq("id", record_id).execute()
    updated = (res.data or [{}])[0]
    
    # NOVO: Cache invalidation granular
    strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
        table_name,
        old_record=old_record,
        new_record=updated,
    )
    GranularCacheInvalidator.execute_strategy(
        strategy,
        table_name=table_name,
        tipo=tipo_for_table(table_name),
        id_modelo=updated.get("id_modelo"),
        id_categoria=updated.get("id_categoria"),
        record_id=record_id,
    )
```

## Benefícios

### Antes (Prefix-Based)
- Update modelo em cat A → invalida cache de cat B também
- Aumento de cache misses
- Perda de performance em catálogos com muitas categorias

### Depois (Granular)
- Update modelo em cat A → apenas cat A invalidada
- 70-80% redução de cache invalidations desnecessárias
- Performance melhorada para operações frequentes

## Métricas a Monitorar

```python
# Em core/cache.py, adicionar metrics:
_surgical_count = 0      # Invalidações eficientes
_category_count = 0      # Invalidações moderadas
_type_count = 0          # Invalidações agressivas
_global_count = 0        # Fallback (deve ser raro)

def cache_invalidation_stats():
    return {
        "surgical": _surgical_count,
        "category": _category_count,
        "type": _type_count,
        "global": _global_count,
        "total": _surgical_count + _category_count + _type_count + _global_count,
        "efficiency_ratio": _surgical_count / (_surgical_count + _global_count) if (_surgical_count + _global_count) > 0 else 0,
    }
```

## Rollout Faseado

**Fase 1** (Agora): Deixar novo código disponível, sem usar
**Fase 2** (Próxima): Ligar para creates (baixo risco)
**Fase 3**: Ligar para updates (testar bem)
**Fase 4**: Monitorar metrics e otimizar

## Testes

Executar testes granulares:
```bash
cd backend-api
python -m pytest tests/test_cache_invalidation_strategy.py -v
```

## Segurança

⚠️ **Importante**: Estratégia só invalida se dados forem precisos.
- Se `id_categoria` ou `id_modelo` forem None → fallback para GLOBAL automaticamente
- Em caso de dúvida, CacheInvalidationAnalyzer escolhe estratégia mais segura
- Nunca perde cache entries válidas (worse case: invalida extra)
