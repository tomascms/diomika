-- LEGADO — não usar em deploys novos.
-- Substituído por: migration_drop_paletas.sql + schemas.py (cores só em id_modelo).
-- Mantido só como histórico da introdução de assentos.

-- Assentos + paletas reutilizáveis (Fantasia, etc.)
-- Cores: reutiliza modelo_cores (id_modelo ou id_paleta)  ← OBSOLETO

-- Categorias são criadas apenas no backoffice — sem INSERT automático.

-- Paletas partilhadas entre categorias

CREATE TABLE IF NOT EXISTS paletas_cores (

    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    nome text NOT NULL,

    slug text DEFAULT '',

    visibilidade boolean DEFAULT true,

    created_at timestamptz DEFAULT now()

);



-- Modelos de assento

CREATE TABLE IF NOT EXISTS modelos_assentos (

    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    id_categoria uuid NOT NULL REFERENCES categories(id),

    nome text NOT NULL,

    slug text DEFAULT '',

    descricao text DEFAULT '',

    material_forro text NOT NULL DEFAULT '',

    material_enchimento text NOT NULL DEFAULT '',

    alturas jsonb NOT NULL DEFAULT '[]'::jsonb,

    id_paleta uuid REFERENCES paletas_cores(id) ON DELETE SET NULL,

    visibilidade boolean DEFAULT true,

    created_at timestamptz DEFAULT now()

);



-- Produto: 1 EAN / código de barras por modelo

CREATE TABLE IF NOT EXISTS assento (

    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    id_categoria uuid NOT NULL REFERENCES categories(id),

    id_modelo uuid NOT NULL UNIQUE REFERENCES modelos_assentos(id) ON DELETE CASCADE,

    ean text NOT NULL UNIQUE,

    barcode_url text,

    visibilidade boolean DEFAULT true,

    created_at timestamptz DEFAULT now()

);



-- Unificar cores: modelo_cores serve modelos (almofada/assento) e paletas

ALTER TABLE modelo_cores DROP CONSTRAINT IF EXISTS modelo_cores_id_modelo_fkey;

ALTER TABLE modelo_cores ALTER COLUMN id_modelo DROP NOT NULL;

ALTER TABLE modelo_cores ADD COLUMN IF NOT EXISTS id_paleta uuid REFERENCES paletas_cores(id) ON DELETE CASCADE;



ALTER TABLE modelo_cores DROP CONSTRAINT IF EXISTS modelo_cores_id_modelo_numero_key;

DROP INDEX IF EXISTS modelo_cores_id_modelo_numero_key;

CREATE UNIQUE INDEX IF NOT EXISTS modelo_cores_model_numero_idx

    ON modelo_cores (id_modelo, numero) WHERE id_modelo IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS modelo_cores_paleta_numero_idx

    ON modelo_cores (id_paleta, numero) WHERE id_paleta IS NOT NULL;



ALTER TABLE modelo_cores DROP CONSTRAINT IF EXISTS modelo_cores_owner_check;

ALTER TABLE modelo_cores ADD CONSTRAINT modelo_cores_owner_check CHECK (

    (id_modelo IS NOT NULL AND id_paleta IS NULL) OR

    (id_modelo IS NULL AND id_paleta IS NOT NULL)

);



-- Migrar dados de tabelas antigas (se existirem)

DO $$

BEGIN

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'paleta_cores') THEN

        INSERT INTO modelo_cores (id_paleta, numero, nome, imagem, visibilidade, created_at)

        SELECT id_paleta, numero, nome, imagem, visibilidade, created_at

        FROM paleta_cores

        ON CONFLICT DO NOTHING;

    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'modelo_assento_cores') THEN

        INSERT INTO modelo_cores (id_modelo, numero, nome, imagem, visibilidade, created_at)

        SELECT id_modelo, numero, nome, imagem, visibilidade, created_at

        FROM modelo_assento_cores

        ON CONFLICT DO NOTHING;

    END IF;

END $$;



DROP TABLE IF EXISTS paleta_cores CASCADE;

DROP TABLE IF EXISTS modelo_assento_cores CASCADE;



-- Paleta Fantasia (reutilizável) — cores em modelo_cores (id_paleta)

INSERT INTO paletas_cores (nome, slug, visibilidade)

SELECT 'Fantasia', 'fantasia', true

WHERE NOT EXISTS (SELECT 1 FROM paletas_cores WHERE slug = 'fantasia');



-- RLS

ALTER TABLE paletas_cores ENABLE ROW LEVEL SECURITY;

ALTER TABLE modelos_assentos ENABLE ROW LEVEL SECURITY;

ALTER TABLE assento ENABLE ROW LEVEL SECURITY;



DROP POLICY IF EXISTS "paletas_public_read" ON paletas_cores;

CREATE POLICY "paletas_public_read" ON paletas_cores FOR SELECT TO anon USING (visibilidade = true);



DROP POLICY IF EXISTS "modelos_assentos_public_read" ON modelos_assentos;

CREATE POLICY "modelos_assentos_public_read" ON modelos_assentos FOR SELECT TO anon USING (visibilidade = true);



DROP POLICY IF EXISTS "assento_public_read" ON assento;

CREATE POLICY "assento_public_read" ON assento FOR SELECT TO anon USING (visibilidade = true);

