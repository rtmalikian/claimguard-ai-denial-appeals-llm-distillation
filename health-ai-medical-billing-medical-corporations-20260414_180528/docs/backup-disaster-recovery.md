# ClaimGuard Backup And Disaster Recovery Runbook

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current Objective Scratchpad: Document backup automation, recovery, and
verification controls without storing backup files, database dumps, secrets,
PHI, production EDI, or production claim content in the repository.

## Scope

This runbook covers the PostgreSQL database used by the current Docker Compose
deployment paths and the encrypted application records stored in that database.
It does not approve production use by itself. PHIplan production readiness still
depends on the manual production-gate packet, legal/BAA/consent evidence,
student runtime cutover approval, production vector backend evidence, and
approved non-synthetic corpus evidence.

Current evidence status: `backup_disaster_recovery_ready=false` until
off-repository encrypted backup storage, metadata-only restore verification,
encryption-key recovery, retention approval, disaster-recovery smoke evidence,
and private boolean-only backup/DR summary counts are validated outside source
control.

## Storage Rules

- Store backup output outside this repository, outside `backups/`, and outside
  frontend or API static paths.
- Encrypt backup artifacts at rest using an approved storage control or an
  operator-managed encryption process.
- Restrict backup access to authorized operators only.
- Do not paste backup paths containing sensitive host details into changelogs.
- Do not include database credentials, bearer tokens, API keys, production EDI
  files, raw uploaded documents, or approval references in backup filenames,
  logs, or tickets.
- Keep restore-test databases isolated from production services.

## Required Environment

Set these values in a private shell or private environment file, not in source
control:

| Variable | Purpose |
|---|---|
| `CLAIMGUARD_BACKUP_DIR` | Directory outside the repository where encrypted or soon-to-be-encrypted dumps are written |
| `POSTGRES_USER` | Database user used by the running Compose stack |
| `POSTGRES_DB` | Database name used by the running Compose stack |
| `COMPOSE_FILE` | Optional Compose file path, such as `docker-compose.production.yml` |

The production compose path already requires the database password through a
private runtime environment. Do not echo that value in shell history or logs.

## Automated Backup Procedure

Run backups from the application directory in an approved host context:

```bash
set -euo pipefail
test -n "${CLAIMGUARD_BACKUP_DIR:?set backup directory outside the repository}"
mkdir -p "${CLAIMGUARD_BACKUP_DIR}"
chmod 700 "${CLAIMGUARD_BACKUP_DIR}"

backup_name="claimguard-db-$(date -u +%Y%m%dT%H%M%SZ).dump"
compose_file="${COMPOSE_FILE:-docker-compose.production.yml}"

docker compose -f "${compose_file}" exec -T db \
  pg_dump \
  --username "${POSTGRES_USER:-claimguard}" \
  --dbname "${POSTGRES_DB:-claimguard}" \
  --format custom \
  --no-owner \
  --no-acl \
  > "${CLAIMGUARD_BACKUP_DIR}/${backup_name}"
```

If the deployment uses the development Compose path, set
`COMPOSE_FILE=docker-compose.yml` explicitly before running the command. For
production, schedule the command with an operator-owned scheduler such as cron,
launchd, or a managed backup service. The scheduler must keep logs metadata-only
and store artifacts outside source control.

Minimum schedule for production candidates:

| Backup type | Frequency | Retention target |
|---|---|---|
| Daily database dump | Every 24 hours | 7 daily restore points |
| Weekly database dump | Weekly | 4 weekly restore points |
| Monthly database dump | Monthly | 12 monthly restore points |

Adjust retention for contractual, legal, payer, and healthcare policy
requirements before production use.

## Backup Verification

Every scheduled backup cycle must verify that the backup file can be read and
restored into an isolated database. Verification must not print row-level data.
Restore verification must not print table rows.

Safe verification commands:

```bash
set -euo pipefail
test -n "${CLAIMGUARD_BACKUP_FILE:?set backup file path outside the repository}"

pg_restore --list "${CLAIMGUARD_BACKUP_FILE}" >/dev/null

createdb claimguard_restore_check
pg_restore \
  --dbname claimguard_restore_check \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  "${CLAIMGUARD_BACKUP_FILE}"

psql \
  --dbname claimguard_restore_check \
  --tuples-only \
  --no-align \
  --command "select to_regclass('public.claims') is not null;"

dropdb claimguard_restore_check
```

The verification log should record only:

- Backup timestamp.
- Backup file size.
- Checksum algorithm and checksum value.
- Restore-test pass/fail status.
- Schema-presence check pass/fail status.
- Operator or automation identity.

Do not log restored table rows, document text, claim payloads, source text,
tokens, credentials, or production file names.

## Disaster Recovery Plan

Use this sequence for a database-loss event:

1. Stop write traffic to the affected environment.
2. Preserve logs and current volume metadata for incident review without
   copying raw database content into source control.
3. Identify the latest verified backup that matches the recovery objective.
4. Provision a clean PostgreSQL database in the approved recovery environment.
5. Restore with `pg_restore --clean --if-exists --no-owner --no-acl`.
6. Start the API against the restored database using private runtime
   environment values.
7. Run `/health` and focused smoke checks for authentication, claims listing,
   denial workflow status, analytics summary, and upload-surface audit.
8. Verify encryption keys can decrypt existing encrypted records. If key
   rotation is needed, follow the encryption-key rotation procedure in
   `README.md`.
9. Keep user-data model improvement disabled and student default cutover
   disabled unless their production evidence packets are still valid after the
   restore.
10. Record recovery timing, backup identifier, verification results, and
    follow-up actions in an incident record that excludes PHI, secrets, raw
    documents, approval references, and production EDI content.

## Recovery Objectives

Set final recovery objectives during production approval. Recommended starting
targets for a production candidate:

| Objective | Starting target |
|---|---|
| Recovery point objective | Less than 24 hours of database changes |
| Recovery time objective | Restore service within 4 hours after backup selection |
| Verification frequency | At least one restore verification per backup cycle |
| Key availability | Encryption key recovery tested before production approval |

## Pre-Production Evidence Checklist

- [ ] Backup directory is outside the repository.
- [ ] Backup artifacts are encrypted at rest.
- [ ] Scheduler runs with least-privilege operator access.
- [ ] Restore verification runs without row-level output.
- [ ] Verification logs contain only metadata.
- [ ] Encryption-key recovery is tested.
- [ ] Disaster recovery smoke checks are documented.
- [ ] Retention period has legal and operational approval.
- [ ] PHIplan production-readiness audit is rerun after backup evidence is
  approved.
