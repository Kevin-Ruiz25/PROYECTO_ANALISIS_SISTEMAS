#!/usr/bin/env bash
# Restaura una copia. Uso:  ./deploy/restore.sh backups/sccvi-2026-11-15_0300.sql.gz
# ATENCIÓN: reemplaza todos los datos actuales.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f "${1:-}" ] || { echo "Indica el archivo de la copia."; exit 1; }
read -r -p "Esto BORRA los datos actuales y los reemplaza por $1. ¿Continuar? (escribe SI) " ok
[ "$ok" = "SI" ] || { echo "Cancelado."; exit 1; }
docker compose stop backend
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\"" -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\""'
gunzip -c "$1" | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > /dev/null
docker compose start backend
echo "Restauración terminada."
