# ClaimGuard Acceptance Audit

Last audited: 2026-05-29.

| requirement | evidence |
|---|---|
| Executive summary of workflow | `references/workflow_decomposition.md` Executive Summary. |
| Hierarchical skill map with phases and atomic steps | `references/workflow_decomposition.md` Phase Map and Atomic Steps. |
| Every atomic step has step ID, name, owner, trigger, inputs, action, criteria, artifact, timing, failures, LLM opportunity, and human verification | `references/workflow_decomposition.md` Atomic Steps table contains 43 rows with all required columns. |
| Routing decision tree covers corrected claim, reopening, reconsideration, peer-to-peer, internal appeal, expedited appeal, external review, grievance/complaint, state fair hearing, and legal escalation | `references/routing_decision_tree.md`. |
| Appeal-letter drafting template and evidence packet checklist | `templates/appeal_letter_template.md`. |
| Follow-up and tracking workflow | `references/workflow_decomposition.md` P12 steps and `references/routing_decision_tree.md` escalation triggers. |
| Data schema for denial appeal platform | `schemas/denial_appeal_schema.json` and `references/data_schema_entity_guide.md`. |
| Distillation dataset design | `eval/distillation_dataset_design.md`. |
| Evaluation rubric and validation scenarios | `eval/evaluation_rubric.md`. |
| Includes commercial/ACA, ERISA, Medicare FFS, Medicare Advantage, Medicaid managed care, external review, and state fair hearing paths | `references/rule_tables.md`, `references/routing_decision_tree.md`, and `eval/evaluation_rubric.md`. |
| Treats local plan, payer, state, contract, and denial-letter instructions as controlling | `SKILL.md` Operating Boundary and `references/rule_tables.md` Verify-Locally Rules. |
| Requires human review before submission | `SKILL.md` Quality Gates and Disallowed Behavior; `templates/appeal_letter_template.md` front matter; schema `human_review`. |
| Distinguishes known, inferred, missing, and cited-rule facts | `SKILL.md` Required Input Handling and schema `source_status`. |
| Provides cited rules and deadlines | `references/rule_tables.md` source-indexed timing tables. |
| Avoids legal advice, independent medical judgment, fabricated citations, fabricated policy terms, and unsupported payer obligations | `SKILL.md` Operating Boundary and Disallowed Behavior; `eval/evaluation_rubric.md` automatic fail rules. |

## Validation Performed

- `python3 -m json.tool schemas/denial_appeal_schema.json >/dev/null` passed.
- `rg -c "^\\| P[0-9][0-9]-S[0-9][0-9]" references/workflow_decomposition.md` returned 43 atomic steps.
- Required terms checked with `rg`: `known_from_documents`, `missing_needs_human_verification`, `draft_for_human_review`, `external review`, `state fair hearing`, `corrected claim`, `peer-to-peer`, `Medicare Advantage`, `Medicaid managed`, and `human review`.

