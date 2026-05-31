# Prediction Fairness Monitoring Runbook

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: not production-ready.

This runbook documents the source-controlled operator procedure for production
prediction-threshold calibration and continuous fairness monitoring. It is not
evidence that approved outcome data, calibration, monitoring, alert ownership,
latest monitoring results, or legal/privacy review have been completed.

## Safety Boundaries

- Keep denial-risk thresholds limited to human-review routing until every
  production fairness evidence gate is complete.
- Do not use a high-risk score as an auto-denial, coverage, payment, or
  medical-necessity decision.
- Do not store raw demographic values, production outcome rows, individual
  identifiers, source documents, appeal or denial text, approval references,
  credentials, tokens, PHI, production claim content, or production document
  content in source control.
- Production outcome rows must stay outside source control and may be
  represented here only through boolean-only evidence after approval.
- Fairness monitoring evidence must use status tokens, blocker identifiers,
  aggregate counts, marker counts, boolean-only evidence, and no raw demographic values.

## Private Operator Steps

1. Confirm the approved outcome dataset required for calibration outside source
   control.
2. Confirm the minimum sample size required for threshold review outside source
   control.
3. Run the calibration run required before threshold changes without writing
   row-level outcomes or demographic values to source control.
4. Review the human-review routing threshold and document only boolean status
   in checked-in evidence.
5. Review demographic grouping through the approved privacy/legal process
   before any production monitoring run is treated as evidence.
6. Configure the continuous monitoring configuration required for production
   outside source control.
7. Confirm disparity thresholds and alert owner required for production
   monitoring outside source control.
8. Confirm the latest monitoring run required for readiness outside source
   control.
9. Complete the legal/privacy review required before production fairness
   monitoring readiness.
10. Review the rollback or threshold reversion required before any production
    promotion.
11. Update
    `llm-distill/data/prediction_fairness_evidence/fairness_monitoring_evidence.template.json`
    only with booleans, status tokens, safe blocker identifiers, and the
    source-controlled runbook path.
12. Rerun `llm-distill/scripts/validate_prediction_fairness_evidence.py`.

## Required Before Production Fairness Readiness

- Approved outcome dataset required.
- Minimum sample size required.
- Calibration run required before threshold changes.
- Threshold review required for human-review routing.
- Approved demographic grouping review required.
- Continuous monitoring configuration required.
- Disparity thresholds and alert owner required.
- Latest monitoring run required.
- Legal/privacy review required.
- Rollback or threshold reversion required.

## Evidence Rules

- Checked-in evidence may include booleans, aggregate counts, status tokens,
  blocker IDs, runbook path, and marker counts only.
- Checked-in evidence must not include raw demographic values, production
  outcome rows, individual identifiers, source documents, approval references,
  credentials, tokens, PHI, secrets, claim identifiers, production claim
  content, or production document content.
- The report may stay `safe_to_review=true` while
  `prediction_fairness_monitoring_ready=false` until approved outcome data,
  calibration, continuous monitoring, latest monitoring run evidence,
  alerting ownership, and legal/privacy governance are complete.
