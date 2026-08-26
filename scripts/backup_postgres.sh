#!/usr/bin/env sh
set -eu

backup_dir="${BACKUP_DIR:-./backups}"
mkdir -p "$backup_dir"
timestamp="$(date +%Y%m%d-%H%M%S)"
output="$backup_dir/business-dashboard-$timestamp.sql.gz"
docker-compose exec -T db pg_dump -U "${POSTGRES_USER:-business_app}" "${POSTGRES_DB:-business_dashboard}" | gzip > "$output"
printf 'Backup written to %s\n' "$output"
