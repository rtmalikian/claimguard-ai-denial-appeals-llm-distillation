# Prediction Fairness Calibration Checklist

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: not calibrated for production.

This checklist documents the source-controlled review steps required before a
ClaimGuard denial-risk threshold can be treated as production-calibrated. It is
not evidence that approved outcome data, sample-size review, calibration,
threshold approval, demographic grouping, monitoring, or legal/privacy review
has been completed.

## Required Preconditions

- approved outcome dataset required before calibration evidence can pass.
- minimum sample size required before threshold review.
- calibration run required before threshold changes.
- threshold review required for human-review routing.
- human-review routing only.
- no auto-denial threshold.
- approved demographic grouping review required before monitoring.
- legal/privacy review required before production fairness readiness.
- rollback or threshold reversion required before promotion.

## Evidence Rules

- boolean-only evidence must be used in checked-in templates and reports.
- production outcome rows must stay outside source control.
- no raw demographic values may be written to source control.
- no PHI, secrets, approval references, individual identifiers, source
  documents, appeal or denial text, production claim content, or production
  document content may be checked in.
- `prediction_fairness_monitoring_ready=false` remains the expected checked-in
  state until all private outcome-data, calibration, monitoring, and governance
  evidence passes.

## Operator Checklist

1. Confirm approved outcome-data scope outside source control.
2. Confirm minimum sample size on the approved outcome dataset.
3. Run calibration analysis without writing row-level outcomes or raw
   demographic values to source control.
4. Complete accountable threshold review for human-review routing only.
5. Confirm that the threshold will not be used for auto-denial, coverage,
   payment, or medical-necessity decisions.
6. Confirm approved demographic grouping through privacy/legal review.
7. Configure continuous monitoring outside source control.
8. Confirm disparity thresholds, alert ownership, and latest monitoring-run
   evidence outside source control.
9. Confirm rollback or threshold reversion procedures.
10. Update checked-in evidence only with booleans, counts, marker counts,
    status tokens, and blocker identifiers.
