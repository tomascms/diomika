-- Separa modelo_cores em tabelas por família de catálogo.

CREATE TABLE IF NOT EXISTS modelo_almofada_cores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    id_modelo uuid NOT NULL REFERENCES modelos_almofadas(id) ON DELETE CASCADE,
    numero int NOT NULL,
    nome text DEFAULT '',
    imagem text NOT NULL,
    visibilidade boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE (id_modelo, numero)
);

CREATE TABLE IF NOT EXISTS modelo_assento_cores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    id_modelo uuid NOT NULL REFERENCES modelos_assentos(id) ON DELETE CASCADE,
    numero int NOT NULL,
    nome text DEFAULT '',
    imagem text NOT NULL,
    visibilidade boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE (id_modelo, numero)
);

INSERT INTO modelo_almofada_cores (id, id_modelo, numero, nome, imagem, visibilidade, created_at, updated_at)
SELECT mc.id, mc.id_modelo, mc.numero, COALESCE(mc.nome, ''), mc.imagem,
       COALESCE(NULLIF(mc.visibilidade, false), m.visibilidade, true),
       COALESCE(mc.created_at, now()), COALESCE(mc.updated_at, now())
FROM modelo_cores mc
JOIN modelos_almofadas m ON m.id = mc.id_modelo
ON CONFLICT (id_modelo, numero) DO UPDATE SET
    nome = EXCLUDED.nome,
    imagem = EXCLUDED.imagem,
    visibilidade = EXCLUDED.visibilidade,
    updated_at = now();

INSERT INTO modelo_assento_cores (id, id_modelo, numero, nome, imagem, visibilidade, created_at, updated_at)
SELECT mc.id, mc.id_modelo, mc.numero, COALESCE(mc.nome, ''), mc.imagem,
       COALESCE(NULLIF(mc.visibilidade, false), m.visibilidade, true),
       COALESCE(mc.created_at, now()), COALESCE(mc.updated_at, now())
FROM modelo_cores mc
JOIN modelos_assentos m ON m.id = mc.id_modelo
ON CONFLICT (id_modelo, numero) DO UPDATE SET
    nome = EXCLUDED.nome,
    imagem = EXCLUDED.imagem,
    visibilidade = EXCLUDED.visibilidade,
    updated_at = now();

ALTER TABLE modelo_almofada_cores ENABLE ROW LEVEL SECURITY;
ALTER TABLE modelo_assento_cores ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "modelo_almofada_cores_public_read" ON modelo_almofada_cores;
CREATE POLICY "modelo_almofada_cores_public_read" ON modelo_almofada_cores
  FOR SELECT TO anon USING (visibilidade = true);

DROP POLICY IF EXISTS "modelo_assento_cores_public_read" ON modelo_assento_cores;
CREATE POLICY "modelo_assento_cores_public_read" ON modelo_assento_cores
  FOR SELECT TO anon USING (visibilidade = true);

CREATE INDEX IF NOT EXISTS idx_modelo_almofada_cores_modelo ON modelo_almofada_cores (id_modelo);
CREATE INDEX IF NOT EXISTS idx_modelo_assento_cores_modelo ON modelo_assento_cores (id_modelo);

DO $$
DECLARE tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['modelo_almofada_cores', 'modelo_assento_cores']
  LOOP
    IF to_regclass('public.' || tbl) IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM pg_publication_tables
      WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = tbl
    ) THEN
      EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE public.%I', tbl);
    END IF;
  END LOOP;
END $$;
