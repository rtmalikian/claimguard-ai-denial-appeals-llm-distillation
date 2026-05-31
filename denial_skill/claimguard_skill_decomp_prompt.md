# ClaimGuard Skill Decomposition Prompt

Use this prompt to generate a source-grounded, provider-side workflow skill for reviewing medical insurance denial letters and producing appeal packets. The intended output should support both project design and LLM distillation for a smaller student model used inside a denial-management platform.

## Prompt

```text
You are a senior U.S. healthcare revenue-cycle, medical-necessity appeal, and payer-policy workflow analyst. Generate a comprehensive, source-grounded skill decomposition for an AI system that reviews medical insurance denial letters and helps provider staff draft, submit, and follow up on appeal letters.

Scope:
- U.S. medical insurance denials for healthcare providers and staff.
- Include commercial/ACA plans, employer/ERISA plans, Medicare Fee-for-Service, Medicare Advantage, Medicaid managed care, and external review paths.
- Treat payer-specific plan terms, state rules, contracts, and denial-letter instructions as controlling when they conflict with general workflow.
- This is workflow guidance, not legal or medical advice. Require human review before submission.

Recommended structure:
- Use a hierarchical skill, not one flat atomic list.
- Break the workflow into phases, then atomic steps inside each phase.
- Recommended phases: intake, classification, authority/privacy validation, deadline calculation, records and evidence gathering, appeal strategy, appeal drafting, quality control, submission, follow-up, escalation, outcome posting, and prevention feedback.

Output format:
1. Executive summary of the workflow.
2. Hierarchical skill map with phases and atomic steps.
3. For every atomic step, include:
   - step_id
   - step_name
   - owner role
   - trigger
   - required inputs
   - exact action
   - decision criteria
   - output artifact
   - deadline/timing field
   - common failure modes
   - LLM assistance opportunity
   - human verification requirement
4. Decision tree for routing a denial into corrected claim, reopening, reconsideration, peer-to-peer, internal appeal, expedited appeal, external review, grievance/complaint, state fair hearing, or legal escalation.
5. Appeal-letter drafting template and evidence packet checklist.
6. Follow-up and tracking workflow.
7. Data schema for an insurance-denial appeal platform.
8. Distillation dataset design for training a student LLM.
9. Evaluation rubric and test scenarios.

Required workflow phases and content:
- Receive denial/EOB/ERA/remittance advice and create case.
- Extract patient, payer, plan, claim, authorization, dates of service, provider, CPT/HCPCS, ICD-10, revenue codes, claim number, denial date, appeal deadline, denial codes, denial reason, policy cited, appeal address/fax/portal, and representative/authorization requirements.
- Determine payer and plan type: commercial fully insured, self-funded ERISA, Marketplace/ACA, Medicare Fee-for-Service, Medicare Advantage, Medicaid managed care, other government plan, workers' compensation, or unknown.
- Determine denial type: medical necessity, experimental/investigational, prior authorization, level of care, setting, out-of-network/network adequacy, coding/bundling/modifier, missing documentation, timely filing, eligibility/coordination of benefits, benefit exclusion, duplicate, contractual adjustment, patient responsibility, or administrative defect.
- Decide whether the correct first action is a corrected claim/reopening, payer reconsideration, peer-to-peer, formal appeal, expedited appeal, or external review.
- Validate authority to act: provider appeal rights, assignment of benefits, authorized representative form, patient consent where required, and HIPAA minimum-necessary handling.
- Calculate all deadlines and decision due dates. Include urgent, pre-service, post-service, Medicare, Medicare Advantage, Medicaid, ERISA, and external review timing as separate rule tables with citations and "verify payer/state-specific rule" warnings.
- Request missing records and payer materials: EOB/denial letter, plan document/SPD, medical policy, claim file, clinical criteria, internal guideline/protocol, coding rationale, prior authorization records, call logs, and all records reviewed by payer.
- Build clinical and administrative evidence packet: physician letter of medical necessity, chart notes, orders, test results, imaging/labs, operative/procedure notes, conservative therapy history, FDA indication, specialty guidelines, peer-reviewed literature, prior authorization proof, eligibility verification, network search evidence, coding support, and corrected claim data if applicable.
- Draft appeal: identify claim, state appeal request, summarize denial, state requested remedy, cite plan/policy criteria, map patient facts to each criterion, rebut denial rationale, explain medical necessity, address coding/authorization/timeliness issues, index attachments, request specialty-matched reviewer or peer-to-peer where appropriate, request expedited handling when criteria are met, and preserve external review rights.
- Quality-control appeal package: no hallucinated facts, all dates/codes match source documents, all cited policies are attached or quoted accurately, every denial reason is answered, deadlines verified, PHI minimized, clinician sign-off obtained.
- Submit via payer-required channel; preserve proof of submission, confirmation number, fax receipt, portal screenshot, certified mail receipt, and exact package version.
- Track payer response deadlines and follow up before/after due date; document calls with date, time, agent, reference number, and next action.
- If upheld, analyze final adverse determination, request missing rationale/claim file if needed, determine next level: second internal appeal, external review/IRO, Medicare QIC/OMHA/Council/Federal District Court, Medicare Advantage IRE/ALJ/Council/Federal District Court, Medicaid state fair hearing, complaint to regulator, or legal referral.
- If overturned, verify reprocessing/payment, patient balance correction, remittance posting, and denial root-cause feedback to billing/coding/prior-authorization teams.
- Feed learnings into prevention rules, payer-policy library, templates, and analytics.

Source requirements:
- Use current official sources wherever possible: CMS, HealthCare.gov, HHS, DOL/EBSA, eCFR/CFR, state insurance departments, state Medicaid agencies, and payer policy documents.
- Prioritize these source categories:
  - ACA/commercial internal appeals and external review rules from HealthCare.gov and CMS/CCIIO.
  - ERISA claim and appeal timing and "full and fair review" requirements from DOL/EBSA and 29 CFR 2560.503-1.
  - Denial and adverse benefit determination notice requirements from 45 CFR 147.136 and related federal rules.
  - Medicare Fee-for-Service appeal levels and forms from CMS.
  - Medicare Advantage organization determination, reconsideration, IRE, ALJ, Medicare Appeals Council, and judicial review guidance from CMS.
  - Medicaid managed-care adverse benefit determination, appeal, continuation of benefits, and state fair hearing rules from 42 CFR Part 438 and state Medicaid agencies.
  - HIPAA Privacy Rule minimum-necessary guidance from HHS.
  - Provider operational denial-management practices from reputable healthcare administration sources such as AHIMA or HFMA.
- Cite every legal/timing claim.
- If a deadline varies by state, payer, contract, or plan type, say so and create a "verify locally" task instead of guessing.
- Do not invent statutes, policy names, medical guidelines, or appeal deadlines.

Distillation requirements:
- Convert the workflow into teachable micro-skills:
  - document extraction
  - denial classification
  - payer/plan routing
  - authority and authorization validation
  - deadline calculation
  - evidence gap detection
  - medical-policy matching
  - appeal argument generation
  - citation grounding
  - submission checklist generation
  - follow-up planning
  - outcome analysis
- Propose supervised examples, preference pairs, rejection examples, and evaluation cases.
- Include red-team tests for hallucinated deadlines, wrong payer path, missing authorization, unsupported medical claims, stale policy citations, PHI over-disclosure, failure to distinguish corrected-claim issues from appeal issues, and failure to route urgent cases correctly.

Data schema requirements:
- Define entities for patient, provider, payer, plan, denial letter, claim, denied service line, denial reason, deadline, appeal level, evidence item, appeal draft, submission record, follow-up activity, payer response, outcome, and prevention insight.
- For each entity, identify minimum fields, provenance/source-document links, confidence fields, and human-verification flags.
- Clearly distinguish facts extracted from documents, facts inferred by the model, and missing facts that require staff action.

Appeal letter requirements:
- Produce a reusable appeal-letter template with sections for:
  - recipient and submission channel
  - patient/member and claim identifiers
  - service/procedure identifiers
  - appeal level and requested action
  - short denial summary
  - concise clinical facts
  - policy/plan criteria mapping
  - rebuttal to each denial rationale
  - medical necessity argument
  - administrative/coding/authorization argument if applicable
  - requested remedy
  - attachment index
  - contact and signature block
- Include instructions for adapting the template to medical-necessity, coding, authorization, timely filing, experimental/investigational, out-of-network, and eligibility/COB denials.

Acceptance criteria:
- The final skill should let an LLM produce a provider-staff checklist, an appeal packet outline, a draft appeal letter, and a follow-up plan from a denial letter plus available records.
- The LLM must clearly distinguish "known from documents," "inferred," and "missing/needs human verification."
- The LLM must provide cited sources for rules and deadlines.
- The LLM must never present a filing-ready appeal without clinician/provider review and deadline verification.
- The LLM must avoid legal advice, independent medical judgment, fabricated citations, fabricated policy terms, and unsupported statements about payer obligations.
```

## Validation Scenarios

Use these scenarios to test whether the generated skill is complete and operationally useful:

- Commercial post-service medical-necessity denial.
- Urgent pre-service denial where delay could seriously jeopardize patient health.
- ERISA employer-plan denial where the denial letter conflicts with the SPD.
- Medicare Fee-for-Service redetermination.
- Medicare Advantage expedited reconsideration.
- Medicaid managed-care service reduction requiring continuation-of-benefits analysis.
- Out-of-network denial with possible network-adequacy argument.
- Coding/modifier denial that should be corrected or reopened rather than appealed.

## Reference Sources To Prioritize

- HealthCare.gov internal appeals: https://www.healthcare.gov/appeal-insurance-company-decision/internal-appeals/
- HealthCare.gov external review: https://www.healthcare.gov/appeal-insurance-company-decision/external-review/
- CMS/HHS external appeals information: https://www.cms.gov/cciio/programs-and-initiatives/consumer-support-and-information/csg-ext-appeals-facts
- DOL denied health benefit claims guidance: https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/resource-center/faqs/denied-health-benefit-claims
- 45 CFR 147.136: https://www.law.cornell.edu/cfr/text/45/147.136
- 29 CFR 2560.503-1: https://www.law.cornell.edu/cfr/text/29/2560.503-1
- CMS Medicare Fee-for-Service appeals: https://www.cms.gov/medicare/appeals-grievances/fee-for-service
- CMS Medicare Advantage appeals and grievances: https://www.cms.gov/medicare/appeals-grievances/managed-care
- 42 CFR Part 438 Medicaid managed care appeals: https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-C/part-438/subpart-F
- HHS HIPAA minimum necessary guidance: https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/minimum-necessary-requirement/index.html
- AHIMA denials management guidance: https://journal.ahima.org/page/top-ten-tips-for-denials-management-14
