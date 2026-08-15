-- Permite vários produtos assento por modelo (um EAN por altura).
-- Remove UNIQUE legado em id_modelo; mantém UNIQUE (id_modelo, altura).

ALTER TABLE assento DROP CONSTRAINT IF EXISTS assento_id_modelo_key;

CREATE UNIQUE INDEX IF NOT EXISTS assento_modelo_altura_idx
  ON assento (id_modelo, altura)
  WHERE altura IS NOT NULL AND trim(altura) <> '';
