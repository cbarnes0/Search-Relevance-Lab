#!/usr/bin/env bash
# Dump the production Postgres database to a timestamped, gzipped file and prune
# old backups. Designed to run on the VM from cron. Idempotent and safe to re-run.
#
#   ./scripts/backup-postgres.sh
#
# Env overrides (all optional):
#   BACKUP_DIR        where dumps are written      (default: ./backups)
#   RETENTION_DAYS    delete dumps older than this (default: 14)

set -euo pipefail

# Resolve the repo root from this script's location, so cron can call it with an
# absolute path and the compose file / .env still resolve correctly.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

# POSTGRES_USER / POSTGRES_DB come from the same .env the stack uses.
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
fi
: "${POSTGRES_USER:?POSTGRES_USER not set (check .env)}"
: "${POSTGRES_DB:?POSTGRES_DB not set (check .env)}"

mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y%m%d-%H%M%S)"
outfile="$BACKUP_DIR/${POSTGRES_DB}-${timestamp}.sql.gz"

echo "Backing up '$POSTGRES_DB' -> $outfile"

# -T: no TTY (required under cron). pg_dump streams to stdout, gzip on the host.
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  | gzip > "$outfile"

# Fail loudly if the dump came out empty (e.g. container was down).
if [[ ! -s "$outfile" ]]; then
  echo "ERROR: backup file is empty, removing it" >&2
  rm -f "$outfile"
  exit 1
fi

echo "Pruning backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -name "${POSTGRES_DB}-*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "Done. Current backups:"
ls -lh "$BACKUP_DIR"
