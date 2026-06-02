# PHIplan Private Evidence Handoff

Architect: Raphael Malikian <rtmalikian@gmail.com>

Current status: source-control-ready but production-blocked.

This handoff maps the remaining PHIplan private or external blockers to the
source-controlled validators, private renderers, and public runbooks that
operators must use before production readiness can be claimed. It is an
operator checklist, not an approval record.

All final evidence must use boolean-only evidence and keep approval references
outside source control, private summary paths outside source control, raw
report paths outside source control, no PHI, no secrets, and no production
document content.

Audit markers: approval references outside source control; private summary
paths outside source control; raw report paths outside source control; no PHI;
no secrets; no production document content.

## Blocker Matrix

| Top-level blocker | Validator or report | Private renderer or handoff | Evidence boundary |
|---|---|---|---|
| `manual_production_gate_packet_evidence` | `llm-distill/scripts/validate_phi_plan_manual_gate_packet.py` | `llm-distill/scripts/render_phi_plan_manual_gate_private_packet.py` | Render the final manual packet only after every dependent report is safe, ready, and unblocked. |
| `student_default_cutover_external_approval` | `llm-distill/scripts/validate_mlx_runtime_supervisor.py` | `llm-distill/scripts/render_student_cutover_private_env.py`; `llm-distill/scripts/render_mlx_runtime_supervisor_private_evidence.py` | Keep student default disabled until Raphael approval, private owner assignment, supervised runtime, runtime health, launch evidence, and rollback controls are complete. |
| `user_data_model_improvement_external_approval` | `llm-distill/scripts/validate_model_improvement_evidence.py` | `llm-distill/scripts/render_model_improvement_private_env.py` | Keep user-data model improvement disabled until legal approval, BAA confirmation, consent notice configuration, approval reference configuration, per-request attestations, and revocation controls are complete. |
| `production_semantic_vector_backend` | `llm-distill/scripts/validate_retrieval_vector_backend.py` | `llm-distill/scripts/render_retrieval_vector_private_env.py`; `llm-distill/scripts/render_retrieval_vector_runtime_private_evidence.py` | Keep the hash fallback as development-only until semantic backend, approved embedding model, production vector backend, reindex, health, quality smoke, backup, and rollback evidence are complete. |
| `production_corpus_expansion_beyond_synthetic` | `llm-distill/scripts/validate_production_corpus_evidence.py` | `llm-distill/scripts/render_production_corpus_private_evidence.py` | Keep production corpus training blocked until approved non-synthetic denial/appeal pair evidence, privacy review, license review, residual-risk review, source/license review, and pair/source checks are complete. |
| `production_prediction_fairness_monitoring` | `llm-distill/scripts/validate_prediction_fairness_evidence.py` | `llm-distill/scripts/render_prediction_fairness_private_evidence.py` | Keep thresholds human-review-only until approved outcome data, sample size, calibration, demographic grouping review, continuous monitoring, latest-run evidence, alert ownership, legal/privacy review, and rollback evidence are complete. |
| `backup_disaster_recovery_evidence` | `llm-distill/scripts/validate_backup_disaster_recovery_evidence.py` | `llm-distill/scripts/render_backup_disaster_recovery_private_evidence.py` | Keep production readiness blocked until off-repository encrypted backup storage, restore validation, key recovery, retention approval, disaster-recovery smoke evidence, and governance review are complete. |
| `dependency_security_evidence` | `llm-distill/scripts/validate_dependency_security_evidence.py` | `llm-distill/scripts/render_dependency_security_private_evidence.py` | Keep production readiness blocked until Python, frontend, and container scans plus remediation or private approval, compensating controls, rebuild/retest evidence, upgrade planning, and governance review are complete. |
| `clearinghouse_submission_evidence` | `llm-distill/scripts/validate_clearinghouse_submission_evidence.py` | `llm-distill/scripts/render_clearinghouse_submission_private_evidence.py` | Keep submission disabled until clearinghouse or payer enrollment, private credentials, encrypted transit, EDI 837 contract tests, acknowledgement handling, retry/duplicate controls, rollback, metadata-only audit, access, retention, and governance evidence are complete. |

## Review Sequence

1. Complete each private evidence packet outside source control with only
   approved governance systems or approved private storage.
2. Run the matching validator for each private packet and confirm the checked
   report is safe to review, ready, unblocked, and metadata-only.
3. Render the final manual production-gate packet with
   `llm-distill/scripts/render_phi_plan_manual_gate_private_packet.py` only
   after all dependent reports pass.
4. Rerun `llm-distill/scripts/run_phi_plan_production_readiness_audit.py` and
   confirm `production_ready=true` only when every private or external blocker
   is cleared by valid private evidence.
5. Confirm source-controlled reports still exclude approval references, private
   summary paths, raw report paths, PHI, secrets, raw EDI payloads, endpoint
   values, vulnerability details, demographic values, outcome rows, source
   text, vectors, and production document content.

## Source-Control Boundary

This repository may contain templates, validators, redacted reports, and
reviewer runbooks. It must not contain private approval references, private
summary paths, raw scanner output, raw dependency findings, payer endpoint
values, clearinghouse credentials, production EDI payloads, production
denial/appeal documents, patient identifiers, raw demographic/outcome rows,
provider secrets, or production backup artifacts.
