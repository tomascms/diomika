-- Assento: EAN/barcode por altura; modelo_cores: separar por tipo de catálogo

ALTER TABLE assento ADD COLUMN IF NOT EXISTS altura text;
ALTER TABLE modelo_cores ADD COLUMN IF NOT EXISTS tipo_catalogo text;

UPDATE modelo_cores mc
SET tipo_catalogo = 'almofada'
FROM modelos_almofadas m
WHERE mc.id_modelo = m.id
  AND (mc.tipo_catalogo IS NULL OR mc.tipo_catalogo = '');

UPDATE modelo_cores mc
SET tipo_catalogo = 'assento'
FROM modelos_assentos m
WHERE mc.id_modelo = m.id
  AND (mc.tipo_catalogo IS NULL OR mc.tipo_catalogo = '');

DO $$
DECLARE
  r record;
  first_alt text;
BEGIN
  FOR r IN
    SELECT a.id, m.alturas
    FROM assento a
    JOIN modelos_assentos m ON m.id = a.id_modelo
    WHERE a.altura IS NULL OR trim(a.altura) = ''
  LOOP
    first_alt := NULL;
    IF jsonb_typeof(r.alturas) = 'array' AND jsonb_array_length(r.alturas) > 0 THEN
      first_alt := trim(both '"' from (r.alturas->>0));
    END IF;
    IF first_alt IS NOT NULL AND first_alt <> '' THEN
      UPDATE assento SET altura = first_alt WHERE id = r.id;
    END IF;
  END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS assento_modelo_altura_idx
  ON assento (id_modelo, altura)
  WHERE altura IS NOT NULL AND altura <> '';

ALTER TABLE assento DROP CONSTRAINT IF EXISTS assento_id_modelo_key;

CREATE INDEX IF NOT EXISTS idx_modelo_cores_tipo_modelo
  ON modelo_cores (tipo_catalogo, id_modelo);
