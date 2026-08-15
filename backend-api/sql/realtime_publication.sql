-- Publicar tabelas do catálogo no Realtime (postgres_changes)
-- Idempotente: só adiciona se a tabela existir e ainda não estiver na publication.

DO $$
DECLARE
  tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'categories',
    'modelos_almofadas',
    'almofada',
    'modelo_almofada_cores',
    'modelos_assentos',
    'assento',
    'modelo_assento_cores',
    'modelos_guarda_chuvas',
    'guarda_chuva',
    'modelo_guarda_chuva_cores',
    'modelos_oculos',
    'oculo',
    'modelo_oculo_cores',
    'modelos_toalhas_mesa',
    'toalha_mesa',
    'modelo_toalha_mesa_cores',
    'modelos_aventais',
    'avental',
    'modelo_avental_cores',
    'modelos_luvas',
    'luva',
    'modelo_luva_cores',
    'modelos_pegas',
    'pega',
    'modelo_pega_cores',
    'modelos_panos_cozinha',
    'pano_cozinha',
    'modelo_pano_cozinha_cores',
    'modelos_regionais',
    'regional',
    'modelo_regional_cores'
  ]
  LOOP
    IF to_regclass('public.' || tbl) IS NOT NULL AND NOT EXISTS (
      SELECT 1
      FROM pg_publication_tables
      WHERE pubname = 'supabase_realtime'
        AND schemaname = 'public'
        AND tablename = tbl
    ) THEN
      EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE public.%I', tbl);
    END IF;
  END LOOP;
END $$;
