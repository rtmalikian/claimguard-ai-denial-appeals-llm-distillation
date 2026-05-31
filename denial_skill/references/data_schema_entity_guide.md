# ClaimGuard Data Schema Entity Guide

The machine-readable schema is `schemas/denial_appeal_schema.json`. This guide maps the required entities to minimum fields, provenance, confidence, and human verification controls.

| entity | minimum fields | provenance/source links | confidence fields | human verification flags |
|---|---|---|---|---|
| patient | `patient_id`, `full_name`, `member_id`, optional DOB/subscriber/group | `fact_string.provenance` or `fact_date.provenance` on each field | `provenance.confidence` | `provenance.human_verified`; `minimum_necessary_note` |
| provider | `provider_id`, `name`, NPI/TIN when needed | Field-level provenance on provider facts | `provenance.confidence` | `provenance.human_verified` |
| payer | `payer_id`, `name`, appeal contact/channel facts | Field-level provenance on payer and channel facts | `provenance.confidence` | `provenance.human_verified` |
| plan | `plan_id`, `plan_name`, `plan_type` | `plan_type.provenance`, SPD/EOC document ID, state jurisdiction source | `plan_type.provenance.confidence` | `plan_type.provenance.human_verified`, `verify_locally_required` |
| denial letter | `document_id`, `notice_date`, `received_date`, document type | Source document ID and page references in field provenance | Field-level confidence | `document_integrity_status`, field verification flags |
| claim | `claim_id`, `claim_number`, `dates_of_service` | Claim/EOB/ERA/RA provenance for claim facts | Field-level confidence | Field verification flags |
| denied service line | `service_line_id`, `service_date`, `procedure_code` | Service-line source references | Field-level confidence | Field verification flags |
| denial reason | `denial_reason_id`, `denial_type`, `payer_text` | Payer text, CARC/RARC, policy citation provenance | `model_classification_confidence` plus field confidence | `human_verified` |
| deadline | `deadline_id`, `deadline_type`, `calculated_deadline`, `verification_status` | Source-stated deadline provenance and `rule_source_id` | `deadline_confidence` | `verification_status` |
| appeal level | `appeal_level_id`, `route`, status | Strategy memo and route evidence in rationale | Route confidence should be recorded in rationale or linked decision artifact | `human_verified` |
| evidence item | `evidence_item_id`, `evidence_type`, `description`, `provenance` | Required `provenance` object; linked denial/service-line IDs | `provenance.confidence` | `clinician_verified`, `phi_minimum_necessary_checked` |
| appeal draft | `appeal_draft_id`, `draft_status`, `body` | Fact trace and citation trace references | Trace completeness fields; source facts retain confidence in linked evidence | `draft_status`, reviewer notes |
| submission record | `submission_id`, `channel`, `submitted_at` | Proof document ID and submitted package version | N/A; proof document carries provenance | `human_verified` |
| follow-up activity | `activity_id`, `activity_type`, `activity_at` | Reference number, agent, channel, and summary | N/A unless imported from OCR/API; use linked source when available | `human_verified` |
| payer response | `payer_response_id`, `response_type`, `received_at` | Response document ID and rationale provenance | Field-level confidence | `human_verified` |
| outcome | `outcome_status`, amount/payment fields when applicable | Payment/remittance/posting source should be linked through evidence or response IDs | Amount confidence should be inherited from source facts | Payment and patient-balance verification through status fields |
| prevention insight | `insight_id`, `root_cause_category`, `recommended_action` | Linked case outcome, denial reason, and evidence artifacts | Analyst confidence can be stored in note or extension field | Team approval/implementation timestamp |

## Fact Status Requirements

All material fields must be one of:

- `known_from_documents`: directly present in a source document or system record.
- `inferred`: derived by the model or analyst, with rationale and confidence.
- `missing_needs_human_verification`: absent, conflicting, illegible, stale, or otherwise unverified.
- `cited_rule`: rule or deadline from a cited source such as `references/rule_tables.md`.

## Implementation Notes

- Store model outputs as drafts until required `human_review` booleans are true.
- Preserve immutable originals and exact submitted package versions.
- Keep source-document IDs stable so fact traces do not break after OCR refresh.
- Do not put PHI into distillation examples unless data is synthetic, de-identified, or approved under the organization's privacy process.

