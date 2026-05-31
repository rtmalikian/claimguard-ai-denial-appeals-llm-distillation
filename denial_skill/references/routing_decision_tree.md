# ClaimGuard Routing Decision Tree

Use this before drafting. Preserve appeal rights while pursuing any informal, corrected, peer-to-peer, or reconsideration route.

## Required Routing Inputs

- Plan type: commercial fully insured, self-funded ERISA, Marketplace/ACA, Medicare FFS, Medicare Advantage, Medicaid managed care, other government, workers' compensation, or unknown.
- Denial type and all secondary rationales.
- Payer-stated route, form, channel, deadline, and next-level rights.
- Service posture: pre-service, concurrent, post-service, payment, termination/reduction, or urgent.
- Authority to act: provider appeal right, assignment of benefits, authorized representative form, patient consent, CMS appointment form, or state Medicaid representative requirement.
- Evidence posture: complete, incomplete but timely, or missing critical payer/clinical records.

## Decision Tree

1. Is the plan type unknown?

   Route to `verify_plan_type` first. In parallel, calculate the earliest plausible deadline from the denial letter and general sources, then protect that deadline.

2. Is there an imminent health-risk, pre-service, concurrent-care, or termination/reduction issue?

   If yes, evaluate expedited appeal. For Medicaid managed care, also evaluate continuation of benefits when a previously authorized service is terminated, suspended, or reduced. For ACA/commercial plans, evaluate simultaneous expedited internal appeal and external review when allowed by the controlling process. Require clinician/provider verification.

3. Does the denial turn on a fixable claim defect rather than a payer disagreement?

   Route to `corrected_claim` or `reopening` if the denial is caused by clerical error, wrong or missing modifier, coding typo, missing attachment that payer invites by correction, duplicate submission defect, wrong provider identifier, minor omission, or other non-merits processing issue. For Medicare FFS, CMS says minor errors and omissions are not processed through the appeals process, so evaluate reopening/correction while preserving the appeal deadline.

4. Did the payer request additional information without issuing a final denial?

   Route to `additional_information_response` if the claim is pended or denied for missing documentation and the payer process allows cure. Submit only relevant records, preserve proof, and track whether appeal deadline is tolled or not. If unclear, file protective appeal or obtain human decision.

5. Is a peer-to-peer available and useful?

   Route to `peer_to_peer` only if payer instructions allow it, it can occur before the deadline, and it does not waive formal appeal rights. Use for medical necessity, level of care, setting, or prior-authorization denials where clinician discussion may resolve or clarify criteria. If the peer-to-peer is denied, exhausted, or would miss a deadline, proceed to formal appeal.

6. Is the denial a coverage, medical judgment, authorization, coding-support, timeliness, eligibility/COB, network, benefit exclusion, or policy-criteria dispute?

   Route to `formal_internal_appeal` unless the controlling plan requires a named reconsideration process first. Draft with issue-by-issue rebuttal and evidence matrix.

7. Is this Medicare FFS?

   Route by level:

   - Initial determination -> MAC redetermination.
   - MAC redetermination upheld -> QIC reconsideration.
   - QIC upheld and amount-in-controversy met -> OMHA ALJ/attorney adjudicator.
   - OMHA unfavorable -> Medicare Appeals Council.
   - Council unfavorable and requirements met -> legal/counsel review for Federal district court.

8. Is this Medicare Advantage?

   Route by level:

   - Adverse organization determination -> MA plan reconsideration.
   - Unfavorable plan reconsideration -> automatic Part C IRE review should occur; verify transfer.
   - IRE unfavorable and amount-in-controversy met -> OMHA ALJ.
   - ALJ unfavorable -> Medicare Appeals Council.
   - Council unfavorable and requirements met -> legal/counsel review for Federal district court.

9. Is this Medicaid managed care?

   Route by posture:

   - MCO adverse benefit determination -> MCO appeal.
   - Expedited risk -> expedited MCO appeal.
   - Previously authorized services reduced, suspended, or terminated -> evaluate continuation of benefits immediately.
   - MCO appeal upheld or deemed exhausted -> state fair hearing.
   - Optional external medical review may be available only if state offers it and it does not delay or deter fair hearing rights.

10. Is this commercial/ACA or ERISA?

   Route by stage:

   - Initial adverse benefit determination -> internal appeal within plan process.
   - Urgent pre-service -> expedited internal appeal, and external review at the same time when permitted.
   - Final internal adverse determination involving medical judgment, experimental/investigational treatment, qualifying rescission, or qualifying external-review issue -> state or federal external review.
   - Final denied ERISA benefit claim with exhausted required appeals -> legal referral may be appropriate; do not provide legal advice.

11. Is this out-of-network/network adequacy?

   Determine whether the denial is pure plan exclusion, medical judgment about whether services can be provided in-network, surprise-billing protection, emergency-service issue, or network adequacy/access problem. Route to formal appeal and possible external review when medical judgment or qualifying federal/state external review criteria are met. Consider regulator complaint for network access only after verifying state and plan jurisdiction.

12. Is this eligibility or coordination of benefits?

   If facts show eligibility or COB record is wrong and payer allows update, route to eligibility/COB correction plus protective appeal. If payer denies coverage despite verified eligibility/COB evidence, route to formal appeal.

13. Is this timely filing?

   Route to corrected claim or reconsideration if payer instructions allow cure and proof exists. Route to formal appeal when arguing timely filing was met, payer/clearinghouse error occurred, eligibility delay prevented filing, a contract exception applies, or plan/payer instructions were defective.

14. Is this experimental/investigational?

   Route to formal appeal with FDA indication, policy criteria mapping, specialty guideline support, peer-reviewed literature, and clinician letter. If final internal denial is upheld, evaluate external review eligibility.

15. Is this legal escalation?

   Route to `legal_referral` only after internal/external administrative routes, plan type, deadline, amount-in-controversy, and authority are verified. The model may prepare a factual referral summary, not legal advice.

## Routing Output Format

Every routing result must include:

```json
{
  "recommended_route": "formal_internal_appeal",
  "route_confidence": "medium",
  "why": [
    {
      "fact": "Denial cites medical necessity and policy criteria.",
      "source_status": "known_from_documents",
      "source_ref": "denial_letter.pdf#page=2"
    }
  ],
  "routes_considered": [
    {
      "route": "corrected_claim",
      "decision": "not_selected",
      "reason": "No fixable claim defect identified."
    }
  ],
  "deadline_risk": "high",
  "human_verification_required": [
    "Verify plan type and payer appeal channel.",
    "Verify deadline before submission."
  ]
}
```

## Escalation Triggers

Escalate to a supervisor, compliance, or legal contact when:

- filing deadline is within 10 calendar days or uncertain;
- patient care is urgent or services are being reduced/terminated;
- plan type is self-funded ERISA, Medicaid, Medicare, workers' compensation, FEHBP, TRICARE, VA, or unknown;
- payer instructions conflict with plan/SPD/EOC or state/federal rule;
- high-dollar case exceeds client threshold;
- representative authority is disputed;
- payer misses required decision timeframe;
- legal rights, court filing, regulator complaint, or fair-hearing issue is involved.

