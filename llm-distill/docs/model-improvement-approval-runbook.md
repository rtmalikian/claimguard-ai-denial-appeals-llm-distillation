# Model Improvement Approval Runbook

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: not production-ready.

This runbook documents the source-controlled operator procedure for approving
user-data model improvement. It is not evidence that model improvement has been
requested, legally approved, covered by a BAA, covered by an approved consent
notice version, or configured with an approval reference.

## Safety Boundaries

- Keep `USER_DATA_MODEL_IMPROVEMENT_ENABLED` disabled until all legal, BAA,
  consent notice version, approval reference, and ready evidence gates pass.
- Store approval references only in approved private runtime configuration.
- Do not store approval reference values, legal documents, BAA documents,
  consent notice text, user data, raw documents, credentials, tokens, PHI,
  production claim content, or production document content in source control.
- Do not use external PHI de-identification services unless Raphael explicitly
  approves a compliant vendor path.
- Do not train on raw PHI or raw uploaded denial letters, claim files, appeal
  packets, source documents, or user data.
- Approved corpus import must not automatically opt any source into user-data
  model improvement.

## Private Operator Steps

1. Record the explicit model-improvement request outside source control.
2. Confirm legal approval outside source control.
3. Confirm BAA coverage outside source control.
4. Confirm the approved consent notice version outside source control.
5. Configure the approval reference outside source control.
6. Verify per-request attestations are enforced before any use of user data.
7. Verify retention and revocation behavior before enabling any production
   model-improvement path.
8. Update
   `llm-distill/data/model_improvement_evidence/model_improvement_evidence.template.json`
   only with booleans, status tokens, safe blocker identifiers, and the
   source-controlled runbook path.
9. Rerun `llm-distill/scripts/validate_model_improvement_evidence.py`.

## Required Before Model Improvement Readiness

- Model improvement requested.
- Legal approval attested.
- BAA confirmed.
- Consent notice version configured.
- Approval reference configured.
- Data-use scope documented.
- Retention policy reviewed.
- Revocation path reviewed.
- Evidence packet ready before training jobs can use any eligible user data.

## Evidence Rules

- Checked-in evidence may include booleans, aggregate counts, status tokens,
  blocker IDs, runbook path, and marker counts only.
- Checked-in evidence must not include approval reference values, legal
  documents, BAA documents, consent notice text, user data, raw documents, PHI,
  secrets, credentials, tokens, claim identifiers, production claim content, or
  production document content.
- The report may stay `safe_to_review=true` while
  `model_improvement_ready=false` until external legal, BAA, consent notice,
  approval reference, and explicit request gates are complete.
