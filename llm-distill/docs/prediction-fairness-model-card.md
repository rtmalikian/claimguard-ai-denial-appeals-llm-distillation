# ClaimGuard Prediction Fairness Model Card

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: not production-ready.

This document describes the current metadata-only prediction fairness and
threshold state for ClaimGuard denial-risk outputs. It is a local governance
artifact, not production calibration evidence.

## Intended Use

- Denial-risk output is used for human-review routing only.
- Human-review routing threshold only.
- No auto-denial threshold.
- High-risk flags must not be used as a final denial, payment, coverage, or
  medical-necessity decision.
- Appeal and denial recommendations remain draft-for-human-review material.

## Current Evidence Boundary

- The current checked-in evidence confirms no raw demographic values or
  production outcome rows are included.
- The current checked-in evidence does not include patient identifiers, claim
  identifiers, document text, payer correspondence, source records, PHI, or
  secrets.
- Synthetic fairness utilities can exercise code paths, but they are not
  evidence of production threshold calibration or continuous fairness
  monitoring.

## Required Before Production Fairness Readiness

- Approved real-world outcome data required.
- Minimum sample size must be verified on approved outcome data.
- Calibration required before production threshold changes.
- Threshold review must be completed by the accountable reviewer before
  production use.
- Demographic grouping must be reviewed through the approved privacy/legal
  process before any monitoring run is treated as production evidence.
- Continuous fairness monitoring required before production use.
- Disparity thresholds, alert ownership, latest monitoring-run evidence, and
  rollback or threshold-reversion procedures must be reviewed before readiness
  can be claimed.
- Legal/privacy review remains required before production fairness monitoring
  can be marked ready.

## Safe Reporting Rules

- Reports may include boolean readiness flags, blocker IDs, aggregate counts,
  and status tokens only.
- Reports must not include raw demographic values, production outcome rows,
  individual identifiers, source documents, appeal or denial letter text,
  approval references, PHI, secrets, credentials, or raw claim data.
- Any production fairness review material that contains sensitive values must
  stay outside source control and be represented here only by boolean
  attestations after approval.
