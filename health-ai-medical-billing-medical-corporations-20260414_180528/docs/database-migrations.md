# ClaimGuard AI Database Migrations

Architected by Raphael Malikian <rtmalikian@gmail.com>.

## Scope

ClaimGuard uses Alembic for PostgreSQL schema changes that need to be
repeatable across local, staging, and production-like environments. Migration
files must not contain PHI, PII, secrets, production claim values, real patient
identifiers, or raw denial documents.

## Local Workflow

1. Review `app/models/__init__.py` and the latest file in `alembic/versions/`.
2. Create a timestamped backup before modifying any existing model, schema,
   endpoint, or migration documentation file.
3. Add or revise the SQLAlchemy model fields.
4. Create an Alembic revision under `alembic/versions/` with a clear
   `revision`, `down_revision`, `upgrade()`, and `downgrade()`.
5. Run syntax checks on the touched migration and model files.
6. Run focused unit/API tests using synthetic data only.
7. Run the PHI scanner on touched code/docs before promoting the change.
8. Record validation results and rollback instructions in `CHANGELOG.md`.

## Commands

Run these from `health-ai-medical-billing-medical-corporations-20260414_180528/`:

```bash
alembic history
alembic current
alembic upgrade head
alembic downgrade -1
```

`alembic/env.py` reads `settings.DATABASE_URL`, so runtime configuration should
come from approved environment variables or secret-management paths. Do not put
real database credentials in migration files, `.env.example`, tests, docs, or
logs.

## Current Baseline

The Alembic chain is initialized in `alembic/` and currently applies additive
migrations on top of the project schema. The existing SQLAlchemy models already
define indexes for `claims.patient_id`, `claims.status`, and `patients.mrn`.
The `20260531_033507_add_claim_patient_soft_delete_indexes.py` revision adds
record-level soft-delete fields for `claims` and `patients`, plus indexes for
soft-delete lookups, `claims.submission_date`, and `claims.denial_prediction`.

## Rollback

Use `alembic downgrade -1` only in a sandbox or approved maintenance window
after confirming that no active workflow depends on the newer schema. For code
rollback, restore the matching backup folder recorded in `CHANGELOG.md`, then
rerun focused tests and PHI scans.
