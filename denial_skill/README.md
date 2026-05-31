# ClaimGuard Denial Appeal Skill

This directory implements `claimguard_skill_decomp_prompt.md` as a source-grounded workflow skill for provider-side medical insurance denial review, appeal-packet drafting, submission tracking, escalation, and distillation data design.

Primary files:

- `SKILL.md`: operational instructions for an LLM or workflow agent.
- `references/workflow_decomposition.md`: hierarchical phase and atomic-step map with required fields for every step.
- `references/rule_tables.md`: cited timing, routing, privacy, and source-control rules.
- `references/routing_decision_tree.md`: first-action and escalation routing logic.
- `templates/appeal_letter_template.md`: reusable appeal letter and evidence packet checklist.
- `schemas/denial_appeal_schema.json`: platform data schema with provenance, confidence, and verification flags.
- `references/data_schema_entity_guide.md`: entity-by-entity schema guide.
- `eval/distillation_dataset_design.md`: micro-skill distillation dataset plan.
- `eval/evaluation_rubric.md`: rubric and validation scenarios.
- `references/acceptance_audit.md`: implementation coverage audit.

Safety boundary:

- This is workflow support for provider staff. It is not legal advice, medical advice, or independent clinical judgment.
- Never produce a filing-ready appeal without clinician/provider review, deadline verification, payer-channel verification, and source-document reconciliation.
- Treat payer-specific plan terms, state rules, contracts, and denial-letter instructions as controlling when they conflict with generic workflow guidance.
