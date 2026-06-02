#!/usr/bin/env bash
set -euo pipefail

# ClaimGuard AI database backup script.
# Follows health-ai-medical-billing-medical-corporations-20260414_180528/docs/backup-disaster-recovery.md
# Store backup output outside this repository. Encrypt artifacts at rest.
# Do not log credentials, PHI, raw documents, or production claim content.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

required_vars=(CLAIMGUARD_BACKUP_DIR)
for var in "${required_vars[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: ${var} is not set. Set it to a directory outside the repository." >&2
    exit 1
  fi
done

if [[ "${CLAIMGUARD_BACKUP_DIR}" == "${APP_ROOT}"* ]]; then
  echo "ERROR: CLAIMGUARD_BACKUP_DIR must be outside the repository." >&2
  exit 1
fi

mkdir -p "${CLAIMGUARD_BACKUP_DIR}"
chmod 700 "${CLAIMGUARD_BACKUP_DIR}"

backup_name="claimguard-db-$(date -u +%Y%m%dT%H%M%SZ).dump"
backup_path="${CLAIMGUARD_BACKUP_DIR}/${backup_name}"
compose_file="${COMPOSE_FILE:-docker-compose.production.yml}"
pg_user="${POSTGRES_USER:-claimguard}"
pg_db="${POSTGRES_DB:-claimguard}"

echo "Starting backup: ${backup_name}"
echo "Compose file: ${compose_file}"
echo "Database: ${pg_db}"

docker compose -f "${compose_file}" exec -T db \
  pg_dump \
  --username "${pg_user}" \
  --dbname "${pg_db}" \
  --format custom \
  --no-owner \
  --no-acl \
  > "${backup_path}"

chmod 600 "${backup_path}"

backup_size=$(stat -f%z "${backup_path}" 2>/dev/null || stat --printf="%s" "${backup_path}" 2>/dev/null || echo "unknown")
checksum=$(shasum -a 256 "${backup_path}" | awk '{print $1}')

echo "Backup complete: ${backup_name}"
echo "Size: ${backup_size} bytes"
echo "SHA-256: ${checksum}"
echo "Stored at: ${CLAIMGUARD_BACKUP_DIR}/"
echo ""
echo "Next steps:"
echo "  1. Verify backup with: scripts/verify_backup.sh"
echo "  2. Ensure backup is encrypted at rest"
echo "  3. Record metadata in backup log (no credentials or PHI)"
