-- Migração: dimensões no modelo de almofadas (variantes no produto)
-- Agrega dimensões existentes dos produtos para jsonb no modelo.

ALTER TABLE modelos_almofadas
    ADD COLUMN IF NOT EXISTS dimensoes jsonb DEFAULT '[]'::jsonb;

UPDATE modelos_almofadas m
SET dimensoes = COALESCE(
    (
        SELECT jsonb_agg(DISTINCT to_jsonb(a.dimensoes))
        FROM almofada a
        WHERE a.id_modelo = m.id
          AND a.dimensoes IS NOT NULL
          AND trim(a.dimensoes) <> ''
    ),
    '[]'::jsonb
)
WHERE m.dimensoes IS NULL OR m.dimensoes = '[]'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS idx_almofada_modelo_dimensoes
    ON almofada (id_modelo, dimensoes);
