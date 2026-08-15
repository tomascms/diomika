-- Migra material (text) → composicao (jsonb %) nos modelos de cozinha/regional.
-- Idempotente — aplicar após sync do schema Pydantic.

ALTER TABLE modelos_aventais ADD COLUMN IF NOT EXISTS composicao jsonb;
ALTER TABLE modelos_luvas ADD COLUMN IF NOT EXISTS composicao jsonb;
ALTER TABLE modelos_pegas ADD COLUMN IF NOT EXISTS composicao jsonb;
ALTER TABLE modelos_panos_cozinha ADD COLUMN IF NOT EXISTS composicao jsonb;
ALTER TABLE modelos_regionais ADD COLUMN IF NOT EXISTS composicao jsonb;

UPDATE modelos_aventais
SET composicao = jsonb_build_object(material, 100)
WHERE material IS NOT NULL AND trim(material) <> ''
  AND (composicao IS NULL OR composicao = '{}'::jsonb);

UPDATE modelos_luvas
SET composicao = jsonb_build_object(material, 100)
WHERE material IS NOT NULL AND trim(material) <> ''
  AND (composicao IS NULL OR composicao = '{}'::jsonb);

UPDATE modelos_pegas
SET composicao = jsonb_build_object(material, 100)
WHERE material IS NOT NULL AND trim(material) <> ''
  AND (composicao IS NULL OR composicao = '{}'::jsonb);

UPDATE modelos_panos_cozinha
SET composicao = jsonb_build_object(material, 100)
WHERE material IS NOT NULL AND trim(material) <> ''
  AND (composicao IS NULL OR composicao = '{}'::jsonb);

UPDATE modelos_regionais
SET composicao = jsonb_build_object(material, 100)
WHERE material IS NOT NULL AND trim(material) <> ''
  AND (composicao IS NULL OR composicao = '{}'::jsonb);
