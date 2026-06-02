# Clearinghouse Submission Evidence Runbook

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current source-controlled status: `clearinghouse_submission_ready=false`.

This runbook documents the evidence required before ClaimGuard can send EDI
837 claims to a clearinghouse, payer gateway, EHR, RCM integration, or other
production submission workflow. The checked-in application can parse and
validate synthetic EDI 837/835 files, but production claim submission remains
blocked until private operating evidence is complete outside source control.

## Required Private Evidence

The private evidence packet must confirm all of the following without storing
raw values in this repository:

- Payer or clearinghouse enrollment has been confirmed for the intended
  production submission path.
- Test-mode credentials are configured privately and are not committed to
  source control.
- Encrypted transit has been validated for the private endpoint.
- The production endpoint is configured privately; endpoint values and portal
  URLs are not stored in source control.
- Source-controlled files contain no clearinghouse credentials, payer portal
  credentials, registry tokens, test account values, production endpoint
  values, or approval reference values.
- EDI 837 submission contract behavior has been validated with synthetic or
  de-identified test transactions.
- Control-number management has been reviewed so interchange, group, and
  transaction identifiers are not casually truncated, reused, or inferred.
- 999 and 277CA acknowledgement handling has been validated before production
  submission is enabled.
- Rejection handling, retry limits, duplicate-submission controls, and rollback
  to non-submission mode have been reviewed.
- Metadata-only audit logging is reviewed for submission, acknowledgement,
  rejection, retry, and rollback events.
- Access controls and retention policy are reviewed for submission metadata.
- Raw EDI payloads, PHI, payer portal credentials, production claim content,
  approval reference values, and private summary paths are not stored in
  checked-in evidence, changelog entries, screenshots, tests, reports, or logs.

## Required Command Flow

1. Keep production submission disabled while the source-controlled report says
   `clearinghouse_submission_ready=false`.
2. Run private clearinghouse and payer enrollment checks outside source
   control.
3. Run synthetic or explicitly de-identified test transactions only.
4. Record private references and aggregate counts in a private summary file
   outside this repository.
5. Render boolean-only private evidence with
   `llm-distill/scripts/render_clearinghouse_submission_private_evidence.py`.
6. Validate the rendered evidence with
   `llm-distill/scripts/validate_clearinghouse_submission_evidence.py`.
7. Rerun `llm-distill/scripts/run_phi_plan_production_readiness_audit.py`.
8. Keep PHIplan production-readiness blocked until the clearinghouse
   submission evidence report is safe, ready, and unblocked.

## Source-Control Rules

Do not store raw EDI payloads, claim batches, patient identifiers, subscriber
identifiers, payer control numbers, claim control numbers, payer portal
credentials, clearinghouse credentials, endpoint URLs, private approval
references, production response files, PHI, secrets, or production document
content in this repository.

Only boolean flags, aggregate counts, environment-variable names, and safe
blocker IDs belong in source-controlled evidence.
