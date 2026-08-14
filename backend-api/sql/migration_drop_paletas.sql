-- Formaliza: cores só no modelo; sem paletas; categoria só no modelo.
-- Idempotente.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'modelo_cores' AND column_name = 'id_paleta'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'modelos_assentos' AND column_name = 'id_paleta'
  ) THEN
    INSERT INTO modelo_cores (id, id_modelo, numero, nome, imagem, visibilidade, created_at)
    SELECT gen_random_uuid(), ma.id, mc.numero, mc.nome, mc.imagem, mc.visibilidade, now()
    FROM modelos_assentos ma
    JOIN modelo_cores mc ON mc.id_paleta = ma.id_paleta
    WHERE ma.id_paleta IS NOT NULL
      AND mc.id_paleta IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM modelo_cores x
        WHERE x.id_modelo = ma.id AND x.numero = mc.numero
      );

    DELETE FROM modelo_cores WHERE id_paleta IS NOT NULL;
  END IF;
END $$;

ALTER TABLE modelo_cores DROP CONSTRAINT IF EXISTS modelo_cores_owner_check;
DROP INDEX IF EXISTS modelo_cores_paleta_numero_idx;
DROP INDEX IF EXISTS idx_modelo_cores_paleta;
ALTER TABLE modelo_cores DROP COLUMN IF EXISTS template_modelo;
ALTER TABLE modelo_cores DROP COLUMN IF EXISTS id_paleta;

DELETE FROM modelo_cores WHERE id_modelo IS NULL;
ALTER TABLE modelo_cores ALTER COLUMN id_modelo SET NOT NULL;

DROP INDEX IF EXISTS modelo_cores_model_numero_idx;
DROP INDEX IF EXISTS modelo_cores_id_modelo_numero_key;
ALTER TABLE modelo_cores DROP CONSTRAINT IF EXISTS modelo_cores_id_modelo_numero_key;
CREATE UNIQUE INDEX IF NOT EXISTS modelo_cores_model_numero_idx
    ON modelo_cores (id_modelo, numero);
CREATE INDEX IF NOT EXISTS idx_modelo_cores_modelo ON modelo_cores (id_modelo);

ALTER TABLE modelo_cores DROP CONSTRAINT IF EXISTS modelo_cores_id_modelo_fkey;

ALTER TABLE modelos_assentos DROP COLUMN IF EXISTS id_paleta;

DROP INDEX IF EXISTS idx_almofada_categoria;
DROP INDEX IF EXISTS idx_assento_categoria;
ALTER TABLE almofada DROP COLUMN IF EXISTS id_categoria;
ALTER TABLE assento DROP COLUMN IF EXISTS id_categoria;

DROP POLICY IF EXISTS "paletas_public_read" ON paletas_cores;
DROP TABLE IF EXISTS paletas_cores CASCADE;
