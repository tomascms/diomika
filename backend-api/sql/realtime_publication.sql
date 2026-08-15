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
    'modelos_assentos',
    'assento',
    'modelo_almofada_cores',
    'modelo_assento_cores',
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
