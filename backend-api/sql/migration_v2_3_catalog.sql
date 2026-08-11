-- Migração v2.3: products → almofada, cores no modelo, orçamentos

ALTER TABLE categories ADD COLUMN IF NOT EXISTS carrinho_step integer DEFAULT 6;
ALTER TABLE categories ADD COLUMN IF NOT EXISTS carrinho_min integer DEFAULT 6;

ALTER TABLE modelos_almofadas ADD COLUMN IF NOT EXISTS composicao jsonb DEFAULT '{}'::jsonb;

UPDATE modelos_almofadas m
SET composicao = sub.composicao
FROM (
  SELECT DISTINCT ON (id_modelo) id_modelo, composicao
  FROM products
  WHERE composicao IS NOT NULL AND composicao != '{}'::jsonb
  ORDER BY id_modelo, created_at NULLS LAST
) sub
WHERE m.id = sub.id_modelo AND (m.composicao IS NULL OR m.composicao = '{}'::jsonb);

CREATE TABLE IF NOT EXISTS modelo_cores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    id_modelo uuid NOT NULL REFERENCES modelos_almofadas(id) ON DELETE CASCADE,
    numero integer NOT NULL,
    nome text DEFAULT '',
    imagem text NOT NULL DEFAULT '',
    visibilidade boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    UNIQUE (id_modelo, numero)
);

INSERT INTO modelo_cores (id_modelo, numero, nome, imagem, visibilidade)
SELECT id_modelo, numero, nome, imagem, visibilidade
FROM (
  SELECT
    id_modelo,
    ROW_NUMBER() OVER (PARTITION BY id_modelo ORDER BY cor)::integer AS numero,
    COALESCE(NULLIF(TRIM(cor), ''), 'Cor') AS nome,
    COALESCE(NULLIF(TRIM(imagem_capa), ''), '') AS imagem,
    COALESCE(visibilidade, true) AS visibilidade
  FROM (
    SELECT DISTINCT ON (id_modelo, cor) id_modelo, cor, imagem_capa, visibilidade
    FROM products
    WHERE id_modelo IS NOT NULL
    ORDER BY id_modelo, cor
  ) uniq_colors
) numbered
ON CONFLICT (id_modelo, numero) DO NOTHING;

ALTER TABLE IF EXISTS products RENAME TO almofada;

ALTER TABLE almofada DROP COLUMN IF EXISTS cor;
ALTER TABLE almofada DROP COLUMN IF EXISTS imagem_capa;
ALTER TABLE almofada DROP COLUMN IF EXISTS galeria;
ALTER TABLE almofada DROP COLUMN IF EXISTS composicao;
ALTER TABLE almofada DROP COLUMN IF EXISTS nome;

CREATE TABLE IF NOT EXISTS pedidos_orcamento (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text NOT NULL,
    email text NOT NULL,
    contacto text,
    empresa text,
    observacoes text,
    linhas jsonb NOT NULL DEFAULT '[]'::jsonb,
    lida boolean DEFAULT false,
    visibilidade boolean DEFAULT true,
    status text DEFAULT 'Nova',
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS encomendas_internas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    referencia_cliente text NOT NULL,
    observacoes text,
    linhas jsonb NOT NULL DEFAULT '[]'::jsonb,
    visibilidade boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

ALTER TABLE modelo_cores ENABLE ROW LEVEL SECURITY;
ALTER TABLE almofada ENABLE ROW LEVEL SECURITY;
ALTER TABLE pedidos_orcamento ENABLE ROW LEVEL SECURITY;
ALTER TABLE encomendas_internas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "modelo_cores_public_read" ON modelo_cores;
CREATE POLICY "modelo_cores_public_read" ON modelo_cores
  FOR SELECT TO anon USING (visibilidade = true);

DROP POLICY IF EXISTS "almofada_public_read" ON almofada;
CREATE POLICY "almofada_public_read" ON almofada
  FOR SELECT TO anon USING (visibilidade = true);

DROP POLICY IF EXISTS "pedidos_orcamento_deny_anon" ON pedidos_orcamento;
CREATE POLICY "pedidos_orcamento_deny_anon" ON pedidos_orcamento FOR ALL TO anon USING (false);

DROP POLICY IF EXISTS "encomendas_internas_deny_anon" ON encomendas_internas;
CREATE POLICY "encomendas_internas_deny_anon" ON encomendas_internas FOR ALL TO anon USING (false);

DROP POLICY IF EXISTS "products_public_read" ON almofada;
