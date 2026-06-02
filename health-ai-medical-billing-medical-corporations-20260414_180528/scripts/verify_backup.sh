#!/usr/bin/env bash
set -euo pipefail

# ClaimGuard AI backup verification script.
# Follows health-ai-medical-billing-medical-corporations-20260414_180528/docs/backup-disaster-recovery.md
# Verification must not print table rows. Logs contain only metadata.
# Do not log credentials, PHI, raw documents, or production claim content.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

required_vars=(CLAIMGUARD_BACKUP_FILE)
for var in "${required_vars[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: ${var} is not set. Point it to a backup file outside the repository." >&2
    exit 1
  fi
done

if [[ ! -f "${CLAIMGUARD_BACKUP_FILE}" ]]; then
  echo "ERROR: Backup file not found: ${CLAIMGUARD_BACKUP_FILE}" >&2
  exit 1
fi

restore_db="claimguard_restore_check_$(date +%s)"
pg_user="${POSTGRES_USER:-claimguard}"

backup_size=$(stat -f%z "${CLAIMGUARD_BACKUP_FILE}" 2>/dev/null || stat --printf="%s" "${CLAIMGUARD_BACKUP_FILE}" 2>/dev/null || echo "unknown")
checksum=$(shasum -a 256 "${CLAIMGUARD_BACKUP_FILE}" | awk '{print $1}')
timestamp=$(date -u +%Y%m%dT%H%M%SZ)

echo "Backup verification started"
echo "File: $(basename "${CLAIMGUARD_BACKUP_FILE}")"
echo "Size: ${backup_size} bytes"
echo "SHA-256: ${checksum}"
echo ""

echo "Step 1: Listing backup contents (metadata only)..."
if pg_restore --list "${CLAIMGUARD_BACKUP_FILE}" >/dev/null 2>&1; then
  list_status="PASS"
  echo "  pg_restore --list: PASS"
else
  list_status="FAIL"
  echo "  pg_restore --list: FAIL"
fi

echo ""
echo "Step 2: Restoring to isolated database..."
createdb "${restore_db}" 2>/dev/null || {
  echo "ERROR: Could not create restore-check database." >&2
  exit 1
}

restore_status="FAIL"
schema_status="FAIL"

if pg_restore \
  --dbname "${restore_db}" \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  "${CLAIMGUARD_BACKUP_FILE}" 2>/dev/null; then
  restore_status="PASS"
  echo "  pg_restore: PASS"

  echo ""
  echo "Step 3: Verifying schema presence..."
  claims_exists=$(psql \
    --dbname "${restore_db}" \
    --tuples-only \
    --no-align \
    --command "select to_regclass('public.claims') is not null;" 2>/dev/null || echo "f")

  if [[ "${claims_exists}" == "t" ]]; then
    schema_status="PASS"
    echo "  Schema check: PASS (claims table exists)"
  else
    schema_status="FAIL"
    echo "  Schema check: FAIL (claims table not found)"
  fi
else
  echo "  pg_restore: FAIL"
fi

echo ""
echo "Step 4: Cleaning up restore-check database..."
dropdb "${restore_db}" 2>/dev/null || echo "  Warning: Could not drop ${restore_db}" >&2

echo ""
echo "========================================"
echo "Backup Verification Report"
echo "========================================"
echo "Timestamp: ${timestamp}"
echo "Backup file: $(basename "${CLAIMGUARD_BACKUP_FILE}")"
echo "Backup size: ${backup_size} bytes"
echo "SHA-256: ${checksum}"
echo "pg_restore --list: ${list_status}"
echo "Restore test: ${restore_status}"
echo "Schema check: ${schema_status}"
echo "Operator: $(whoami)"
echo "========================================"

if [[ "${list_status}" == "PASS" && "${restore_status}" == "PASS" && "${schema_status}" == "PASS" ]]; then
  echo "Overall: VERIFIED"
  exit 0
else
  echo "Overall: FAILED"
  exit 1
fi
