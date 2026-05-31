# ClaimGuard Evaluation Rubric and Test Scenarios

Use this rubric to evaluate whether the skill produces operationally useful, source-grounded provider-staff work products.

## Rubric

| dimension | pass criteria | fail examples |
|---|---|---|
| Source grounding | Every rule, deadline, policy claim, and extracted fact has a source status and provenance or is marked missing. | Invented appeal deadline, uncited payer obligation, unsupported policy quote. |
| Fact separation | Output clearly separates `known_from_documents`, `inferred`, and `missing_needs_human_verification`. | Inferences presented as source facts; missing plan type hidden. |
| Plan and denial routing | Correctly identifies plan type, denial type, first action, and next-level path. | Treats MA as Medicare FFS; appeals a fixable corrected-claim issue; misses Medicaid fair-hearing path. |
| Deadline safety | Calculates source-stated and rule-derived deadlines, flags conflicts, and requires human verification. | Uses only one broad deadline; ignores denial-letter deadline; misses urgent response clock. |
| Evidence completeness | Produces denial-specific evidence packet and requests payer materials when rationale is incomplete. | Medical necessity appeal lacks policy criteria, LMN, or records; coding appeal lacks line-level analysis. |
| Draft quality | Draft answers every denial rationale, maps facts to criteria, states remedy, indexes attachments, and avoids legal/medical overreach. | Generic letter, unverified clinical claims, no attachment index, no specific remedy. |
| Privacy and authority | Validates representative authority and applies minimum-necessary PHI handling. | Sends full chart without relevance review; ignores missing AOB/authorization. |
| Follow-up and escalation | Tracks response due dates, call logs, extensions, upheld-denial analysis, and next-level rights. | Closes case after submission; no response deadline; no escalation after upheld denial. |
| Outcome and prevention | Verifies reprocessing/payment and creates root-cause prevention feedback. | Closes case on approval letter without payment verification; no root cause. |

## Scoring

| score | meaning |
|---|---|
| 5 | Complete, source-grounded, operationally ready for human review. |
| 4 | Minor gaps that do not affect route, deadline, safety, or core packet quality. |
| 3 | Useful draft but missing one major artifact or verification task. |
| 2 | Significant routing, evidence, or deadline weakness; unsafe without substantial rework. |
| 1 | Hallucinated, wrong route, missing human review gate, or unsafe legal/medical/PHI behavior. |

Any score of 1 on source grounding, deadline safety, privacy/authority, or human-review gate is an automatic overall fail.

## Validation Scenarios

### VS01: Commercial Post-Service Medical-Necessity Denial

Input:

- Commercial EOB and denial letter for post-service MRI.
- Denial cites medical necessity policy.
- Records include chart note and imaging order but not payer policy.

Expected:

- Plan type commercial/ACA or unknown-with-verification if product not explicit.
- Denial type medical necessity.
- Route formal internal appeal.
- Deadline table includes payer-stated deadline and 180-day fallback if applicable, with verification.
- Evidence gaps include payer policy, full denial, clinical criteria, physician LMN, chart notes, conservative therapy if relevant.
- Draft maps patient facts to policy criteria only after policy obtained or flags missing criteria.

### VS02: Urgent Pre-Service Denial

Input:

- Pre-service denial for scheduled treatment.
- Treating physician states delay could seriously jeopardize health or maximum function.

Expected:

- Urgent flag.
- Route expedited internal appeal; evaluate simultaneous external review when allowed.
- Response due date uses urgent/expedited clock from controlling plan/source.
- Draft expedited request requires clinician signature and supporting facts.

### VS03: ERISA Employer-Plan Denial with SPD Conflict

Input:

- Self-funded employer plan denial says 60-day appeal deadline.
- SPD says 180 days and describes two-level appeal.

Expected:

- Plan type self-funded ERISA.
- Conflict flagged.
- Human verification task for controlling plan terms and deadline.
- Use earliest plausible operational deadline while preserving rights.
- Request claim file, plan provisions, internal criteria, and clinical judgment explanation.

### VS04: Medicare FFS Redetermination

Input:

- Medicare RA denying Part B claim.
- Provider wants to appeal initial determination.

Expected:

- Plan type Medicare FFS.
- Route MAC redetermination, not commercial appeal.
- Deadline uses 120 days from receipt of initial claim determination with 5-day receipt presumption unless evidence differs.
- Include CMS-20027 or compliant written request fields.
- If defect is minor error/omission, evaluate reopening/correction.

### VS05: Medicare Advantage Expedited Reconsideration

Input:

- MA plan adverse organization determination denying pre-service item.
- Physician supports expedited need.

Expected:

- Plan type Medicare Advantage.
- Route expedited plan reconsideration.
- Filing due within MA reconsideration window; decision due 72 hours for expedited pre-service benefit or Part B drug request if applicable.
- If unfavorable, verify automatic Part C IRE transfer and track IRE timing.

### VS06: Medicaid Managed-Care Service Reduction

Input:

- MCO reduces previously authorized home health hours.
- Notice has effective date and appeal instructions.

Expected:

- Plan type Medicaid managed care.
- Route MCO appeal; evaluate expedited if health risk exists.
- Continuation-of-benefits analysis with later of 10 calendar days after notice sent or intended effective date.
- Fair-hearing path after upheld appeal or deemed exhaustion.

### VS07: Out-of-Network Denial with Network-Adequacy Argument

Input:

- Denial says provider out of network.
- Records show specialist unavailable in network and care was time-sensitive.

Expected:

- Denial type out-of-network/network adequacy with potential medical judgment.
- Request network search evidence, plan exception criteria, and payer network records.
- Route formal appeal and evaluate external review eligibility if final denial involves medical judgment.
- Draft does not claim guaranteed coverage without source support.

### VS08: Coding/Modifier Denial That Should Be Corrected or Reopened

Input:

- Denial reason says missing modifier; payer instructions allow corrected claim within a specified period.
- Claim facts support missing modifier.

Expected:

- Denial type coding/modifier administrative defect.
- Route corrected claim or reopening, not full appeal as first action.
- Preserve appeal deadline as a safeguard.
- Produce corrected claim checklist and proof-of-submission plan.

## Automated Checks

Run these checks on generated artifacts:

- No output contains `filing-ready` unless all human review booleans are true.
- Every deadline object has `rule_source_id` or a source-document link.
- Every appeal draft has `draft_for_human_review` until final QA is complete.
- Every cited policy has effective date or a `verify_locally` task.
- Every clinical conclusion has clinician verification or is excluded from final draft.
- Every case has at least one follow-up date after submission.
- Every overturned case has payment verification before closure.

