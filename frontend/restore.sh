#!/usr/bin/env sh
set -eu
if [ "${1:-}" = "" ] || [ ! -f "$1" ]; then
  echo "Usage: ./scripts/restore.sh backups/aib-YYYYMMDDTHHMMSSZ.sql.gz" >&2
  exit 2
fi
echo "WARNING: this replaces the current AIB database contents."
[ "${CONFIRM_RESTORE:-}" = "YES" ] || { echo "Set CONFIRM_RESTORE=YES to continue." >&2; exit 2; }
gunzip -c "$1" | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
echo "Restore completed."
