-- Tipo de catálogo na categoria (almofada | assento)
ALTER TABLE categories ADD COLUMN IF NOT EXISTS tipo_catalogo text NOT NULL DEFAULT 'almofada';

UPDATE categories SET tipo_catalogo = 'assento' WHERE slug IN ('assentos', 'assento');
UPDATE categories SET tipo_catalogo = 'almofada' WHERE tipo_catalogo IS NULL;

ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_tipo_catalogo_check;
-- Validação via API (CATALOG_TYPES) — sem CHECK estático

-- Regras de carrinho por tipo (se ainda genéricas)
UPDATE categories SET carrinho_step = 12, carrinho_min = 12 WHERE tipo_catalogo = 'assento';
UPDATE categories SET carrinho_step = COALESCE(NULLIF(carrinho_step, 0), 6), carrinho_min = COALESCE(NULLIF(carrinho_min, 0), 6)
WHERE tipo_catalogo = 'almofada';
