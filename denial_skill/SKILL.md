# ClaimGuard Denial Appeal Skill

Use this skill when reviewing a U.S. medical insurance denial letter, EOB, ERA, remittance advice, payer portal notice, or adverse benefit determination for a healthcare provider or provider staff member. The skill helps staff create a case checklist, route the matter, assemble evidence, draft an appeal packet, submit through the required channel, follow up, escalate when needed, post outcomes, and feed prevention learnings back to billing, coding, authorization, and clinical operations.

## Operating Boundary

This is workflow guidance, not legal advice, medical advice, or independent clinical judgment. Do not tell staff that an appeal is ready to file until a human reviewer verifies all deadlines, plan/payer instructions, source facts, citations, medical necessity statements, PHI handling, and clinician/provider sign-off.

When plan terms, payer instructions, provider contract terms, state law, Medicaid agency rules, or denial-letter instructions conflict with a general rule in this skill, treat the local controlling source as controlling and create a `verify_locally` task.

## Required Input Handling

For every extracted or generated fact, label it as one of:

- `known_from_documents`: directly present in a supplied denial letter, EOB, ERA, remittance, plan document, policy, medical record, claim screen, authorization record, or staff note.
- `inferred`: reasoned from known facts; include the inference path and confidence.
- `missing_needs_human_verification`: required to proceed but absent, conflicting, illegible, stale, or outside the model's authority.
- `cited_rule`: a rule, deadline, or payer obligation grounded in a cited current source.

If the model cannot cite a rule or deadline, it must not present it as a rule. It must instead produce a missing-information task.

## Core Outputs

For each denial case, produce these artifacts:

1. Provider-staff checklist with owner, due date, source, and verification status.
2. Appeal packet outline or alternative first-action packet.
3. Draft appeal letter clearly marked `draft_for_human_review`.
4. Evidence packet checklist and attachment index.
5. Submission plan with required payer channel and proof-of-submission capture.
6. Follow-up plan with payer response deadlines, call script fields, and escalation triggers.
7. Outcome posting and prevention feedback summary.

## Workflow

Run the phases in order unless an urgent-care, continuation-of-benefits, or imminent-deadline trigger requires parallel work.

1. Intake and case creation.
2. Document extraction and source tagging.
3. Denial classification.
4. Payer, plan, authority, and privacy validation.
5. Deadline calculation and due-date controls.
6. Records, policy, and claim-file gathering.
7. Evidence packet construction.
8. Appeal strategy and first-action routing.
9. Appeal or correction drafting.
10. Quality control.
11. Submission and proof preservation.
12. Follow-up and payer-response tracking.
13. Escalation and next-level review.
14. Outcome posting.
15. Prevention feedback.

The atomic decomposition for these phases is in `references/workflow_decomposition.md`.

## Routing Rules

Always route the case before drafting:

- Use corrected claim or reopening when the denial turns on a fixable claim defect, minor error, missing modifier, typo, duplicate, clerical issue, or Medicare minor-error reopening path rather than a disagreement with coverage or medical judgment.
- Use peer-to-peer or reconsideration only when the payer permits or requires it and the deadline does not impair formal appeal rights.
- Use expedited appeal when the standard timeline could seriously jeopardize life, health, ability to regain maximum function, or avoidance of severe pain, or when a treating clinician supports urgent handling.
- Use formal internal appeal when coverage, medical necessity, experimental/investigational status, authorization, level of care, setting, network adequacy, eligibility, COB, benefit exclusion, timeliness, or payer rationale must be challenged.
- Use external review/IRO when an eligible final internal adverse determination involves medical judgment, experimental/investigational treatment, rescission, qualifying surprise-billing/network issue, or another eligible adverse determination under controlling rules.
- Use Medicare FFS, Medicare Advantage, Medicaid managed-care, ERISA, state fair hearing, regulator complaint, or legal referral paths only after plan type is verified.

Detailed decision logic is in `references/routing_decision_tree.md`.

## Drafting Rules

Every appeal draft must:

- Identify patient/member, payer, plan, provider, claim, service dates, service lines, CPT/HCPCS, ICD-10, revenue codes, authorization numbers, denial date, and appeal level when known.
- State the requested action and remedy.
- Summarize the denial without overstating payer rationale.
- Map patient facts to each plan, medical policy, LCD/NCD, clinical guideline, or coding rule criterion.
- Rebut every denial reason separately.
- Cite and attach only verified plan/payer policies, medical records, authorization proofs, coding references, and literature.
- Flag every unsupported medical claim as needing clinician verification.
- Include an attachment index.
- Include explicit human review and deadline verification requirements.

The reusable letter template and evidence checklist are in `templates/appeal_letter_template.md`.

## Timing and Source Control

Use `references/rule_tables.md` for cited general timing rules. The model must still verify the exact deadline from:

- denial letter or EOB/ERA;
- plan document, SPD, EOC, member handbook, or provider contract;
- payer portal instructions;
- applicable state insurance department or Medicaid agency rule;
- Medicare/CMS or eCFR rule when applicable.

Record both `calculated_deadline` and `source_stated_deadline`. If they conflict, use the earliest plausible deadline for operational tracking and assign a human verification task.

## Quality Gates

Before submission, require a human reviewer to confirm:

- All dates, member identifiers, claim numbers, codes, service lines, provider identifiers, and amounts match source documents.
- Payer address, fax, portal, form, appeal level, authorized representative requirements, and signature requirements match the controlling source.
- Every cited policy is current, attached, quoted or summarized accurately, and linked to provenance.
- Every denial rationale is answered.
- Deadlines and response due dates are independently verified.
- PHI is minimum necessary for the appeal purpose.
- Clinician or provider sign-off is complete for medical necessity, clinical facts, and urgency statements.

## Disallowed Behavior

Do not:

- fabricate statutes, deadlines, medical policies, plan terms, addresses, fax numbers, citations, literature, or clinical facts;
- give legal advice or decide whether to sue;
- make independent medical necessity determinations without clinician review;
- claim a payer must cover a service unless the controlling source supports that statement;
- omit appeal rights because a corrected claim, peer-to-peer, or reconsideration appears available;
- ignore urgent-care or Medicaid continuation-of-benefits triggers;
- include unnecessary PHI in drafts, packets, logs, or training examples.

## Supporting Artifacts

- Rule tables: `references/rule_tables.md`
- Workflow decomposition: `references/workflow_decomposition.md`
- Routing decision tree: `references/routing_decision_tree.md`
- Appeal template: `templates/appeal_letter_template.md`
- Platform schema: `schemas/denial_appeal_schema.json`
- Entity guide: `references/data_schema_entity_guide.md`
- Distillation design: `eval/distillation_dataset_design.md`
- Evaluation rubric: `eval/evaluation_rubric.md`
