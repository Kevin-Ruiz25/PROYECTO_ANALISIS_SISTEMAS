#!/usr/bin/env bash
# Copia de seguridad de la base de datos. Uso (desde la carpeta del proyecto):  ./deploy/backup.sh
# Guarda backups/sccvi-AAAA-MM-DD_HHMM.sql.gz y conserva los últimos 14.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
file="backups/sccvi-$(date +%F_%H%M).sql.gz"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$file"
echo "Copia creada: $file ($(du -h "$file" | cut -f1))"
ls -1t backups/sccvi-*.sql.gz | tail -n +15 | xargs -r rm --
