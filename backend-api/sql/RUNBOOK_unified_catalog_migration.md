# Runbook — migração para o catálogo unificado

Contexto: o catálogo passou de 13 famílias de tabelas quase-idênticas
(`modelos_almofadas`+`almofada`+`modelo_almofada_cores`, etc.) para 3 tabelas
partilhadas (`product_models`, `product_variants`, `product_model_colors`),
discriminadas por `tipo_catalogo`. O código da API já está adaptado a este
esquema novo neste branch. **A base de dados ainda não foi migrada.**

## Antes de começar

- **Backup.** No Supabase: Database → Backups → cria um backup manual (ou
  confirma que o backup automático diário está ativo e tens o ponto de
  restauro de hoje). Isto é mais importante do que qualquer passo abaixo.
- Este script **não foi corrido contra a tua base de dados real** — foi
  escrito a partir do código. Em particular, não sei com certeza se a tua BD
  ainda tem a tabela de cores partilhada legada `modelo_cores` (almofada +
  assento) ou se já foi dividida em `modelo_almofada_cores` /
  `modelo_assento_cores` — o script tenta as duas hipóteses, mas confirma no
  passo de verificação.

## Passo 1 — confirmar o esquema real (opcional mas recomendado)

No SQL Editor do Supabase:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name LIKE 'modelo%' OR table_name LIKE '%_cores'
ORDER BY table_name;
```

Compara com os nomes assumidos em `0002_migrate_catalog_data.sql`. Se algo
não bater (nome de coluna diferente, tabela em falta), ajusta o script antes
de correr — ou pede para eu o fazer, se me deres acesso de leitura à BD
(`DATABASE_URL` nos secrets do ambiente).

## Passo 2 — aplicar o esquema novo

No SQL Editor do Supabase, corre `0001_unified_catalog_schema.sql` completo.
É idempotente (`IF NOT EXISTS` / `DROP POLICY IF EXISTS` + `CREATE`) — podes
correr mais do que uma vez sem problema.

## Passo 3 — migrar os dados, dentro de uma transação

```sql
BEGIN;
```

Cola e corre o conteúdo de `0002_migrate_catalog_data.sql`.

Depois, confirma os números (adapta à lista real de tabelas que existem na
tua BD):

```sql
SELECT 'product_models' AS t, count(*) FROM product_models
UNION ALL SELECT 'product_variants', count(*) FROM product_variants
UNION ALL SELECT 'product_model_colors', count(*) FROM product_model_colors;

-- compara com a soma das tabelas antigas, por família, ex.:
SELECT count(*) FROM modelos_almofadas;  -- deve bater com:
SELECT count(*) FROM product_models WHERE tipo_catalogo = 'almofada';
```

Se os números baterem certo em todas as famílias:

```sql
COMMIT;
```

Se algo parecer errado (contagens não batem, `attributes` com valores
estranhos):

```sql
ROLLBACK;
```

...e avisa-me — ajusto o script e tentamos outra vez. Nada foi destruído: o
`ROLLBACK` desfaz tudo o que o passo 3 fez, as tabelas antigas continuam
intactas.

## Passo 4 — publicar o código novo

O código deste branch já lê/escreve nas tabelas novas. Faz deploy normal
(o fluxo habitual do projeto). **Não** definas `SCHEMA_BOOTSTRAP` — essa
variável deixou de ter efeito (o motor de auto-migração no arranque foi
removido; ver commit "Unify catalog schema").

## Passo 5 — confirmar em produção

Durante alguns dias, verifica:
- A loja mostra o catálogo correctamente (modelos, cores, variantes, filtros).
- O backoffice cria/edita categorias, modelos e produtos sem erros.
- Orçamentos e encomendas resolvem as linhas (EAN → nome/cor) correctamente.

## Passo 6 — limpeza (só depois do passo 5 correr bem por uns dias)

Corre `0003_cleanup_legacy_tables_TEMPLATE.sql` — renomeia (não apaga) as 13
famílias de tabelas antigas com o prefixo `legacy_`. Reversível: se precisares
de voltar atrás, é só renomear de volta. Passados uns meses, se nunca
precisares, podes fazer `DROP TABLE legacy_*` à mão.

## Se alguma coisa correr mal depois do deploy

O `ROLLBACK` do passo 3 só cobre a migração de dados. Se o problema aparecer
só depois do deploy (código novo + dados migrados, mas algo no comportamento
está errado), as tabelas antigas continuam lá, intactas — podes:
1. Reverter o deploy para o commit anterior a este branch (código antigo
   volta a ler as tabelas antigas, que não foram tocadas).
2. Investigar com calma, sem pressão de produção partida.
