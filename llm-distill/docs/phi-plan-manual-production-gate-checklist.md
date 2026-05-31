# PHIplan Manual Production Gate Checklist

Architect: Raphael Malikian <rtmalikian@gmail.com>

Current status: manual production gate not ready.

This checklist is the source-controlled reviewer checklist for ClaimGuard AI
PHIplan production readiness. It documents what must be proven before the
manual production gate packet can be treated as complete. It must not contain
approval-reference values, PHI, secrets, production document content, source
document text, vector values, raw demographic values, outcome rows, patient
identifiers, or credentials.

## Required Gate Evidence

- student default cutover approval required
- student cutover private environment renderer required
- user-data model improvement legal/BAA/consent approval required
- model-improvement private environment renderer required
- approved non-synthetic denial/appeal pair required
- production semantic vector backend required
- retrieval vector private environment renderer required
- production threshold/fairness monitoring evidence required
- prediction-fairness private evidence renderer required
- file-ingestion surface audit must stay ready
- boolean-only evidence
- approval references must stay outside source control
- no PHI or production document content
- production_gate_ready=false

## Reviewer Instructions

1. Confirm the manual packet records only booleans, counts, safe paths, and
   metadata-level blocked requirement identifiers.
2. Confirm external approval references, consent notice values, BAA evidence,
   legal records, source documents, and production corpus records stay in
   approved runtime or governance systems outside source control.
3. For student default cutover, render any final environment file with
   `llm-distill/scripts/render_student_cutover_private_env.py` only to a
   private path outside source control, and confirm its command output includes
   redacted booleans/counts only.
4. For user-data model improvement, render any final environment file with
   `llm-distill/scripts/render_model_improvement_private_env.py` only to a
   private path outside source control after legal, BAA, consent, request, and
   approval evidence are complete; confirm command output includes redacted
   booleans/counts only.
5. For retrieval vector backend promotion, render any final environment file
   with `llm-distill/scripts/render_retrieval_vector_private_env.py` only to a
   private path outside source control after semantic backend, embedding model,
   production vector backend, reindex, health, quality smoke, and rollback
   evidence are complete; confirm command output includes redacted
   booleans/counts only.
6. For prediction fairness monitoring, render any final evidence file with
   `llm-distill/scripts/render_prediction_fairness_private_evidence.py` only
   to a private path outside source control after outcome-data, sample-size,
   threshold-review, monitoring, latest-run, and legal/privacy evidence are
   complete; confirm command output includes redacted booleans/counts only.
7. Confirm production readiness remains blocked until every required gate is
   ready in `llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`
   and `llm-distill/evals/reports/phi_plan_production_readiness_report.json`.
8. Confirm any future document-ingestion surface is registered in the
   file-ingestion surface audit before it handles production material.
