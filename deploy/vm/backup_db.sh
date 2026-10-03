#!/usr/bin/env bash
# Backup diário da base de dados (Supabase) para o disco da VM.
#
# - pg_dump num contentor postgres:17 descartável (mesma versão do servidor);
# - credenciais tiradas da própria config da API (nada novo guardado);
# - pooler IPv4 da Supabase em modo sessão (o host directo é só IPv6 e a VM
#   não tem IPv6);
# - formato custom (-Fc), verificado com pg_restore --list;
# - guarda 14 dias em ~/backups/db (só o utilizador lê: umask 077).
#
# Instalado em cron por deploy/install_db_backups.py. Restaurar:
#   docker run --rm -i -e PGPASSWORD=... postgres:17-alpine \
#     pg_restore --clean --if-exists -h <host> -U <user> -d postgres < ficheiro.dump
set -euo pipefail
umask 077

POOLER_HOST="${POOLER_HOST:-aws-0-eu-west-1.pooler.supabase.com}"
KEEP_DAYS="${KEEP_DAYS:-14}"
DEST="${HOME}/backups/db"
LOG="${DEST}/backup.log"
mkdir -p "$DEST"

log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }

read -r REF PASS < <(sudo docker exec -w /app/backend-api deploy-api-1 python -c "
import os
from urllib.parse import urlparse
from core.database_url import get_database_url
ref = urlparse(os.environ['SUPABASE_URL']).hostname.split('.')[0]
print(ref, urlparse(get_database_url()).password)
")

STAMP="$(date -u +%Y-%m-%d)"
OUT="${DEST}/diomika-${STAMP}.dump"
TMP="${OUT}.partial"

log "início backup -> ${OUT}"
sudo docker run --rm -e PGPASSWORD="$PASS" postgres:17-alpine \
  pg_dump -h "$POOLER_HOST" -p 5432 -U "postgres.${REF}" -d postgres \
  -Fc --no-owner --no-privileges --schema=public > "$TMP"

# Valida que o ficheiro é um dump legível antes de o aceitar.
TABLES=$(sudo docker run --rm -i postgres:17-alpine pg_restore --list < "$TMP" | grep -c " TABLE DATA " || true)
if [ "${TABLES:-0}" -lt 5 ]; then
  log "ERRO: dump inválido (${TABLES} tabelas) — mantido como ${TMP}"
  exit 1
fi
mv -f "$TMP" "$OUT"
log "ok: $(du -h "$OUT" | cut -f1), ${TABLES} tabelas com dados"

find "$DEST" -name 'diomika-*.dump' -mtime +"$KEEP_DAYS" -print -delete | sed 's/^/removido /' >> "$LOG" || true
