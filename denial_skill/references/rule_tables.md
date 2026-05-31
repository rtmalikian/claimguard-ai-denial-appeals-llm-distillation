# ClaimGuard Source-Grounded Rule Tables

Last verified: 2026-05-29.

Use these tables as general source-grounded defaults. Do not treat them as a substitute for the denial letter, plan terms, provider contract, state insurance department rule, state Medicaid agency rule, or payer-specific instructions.

## Source Index

| source_id | source | use |
|---|---|---|
| SRC-HCG-INTERNAL | HealthCare.gov, Internal appeals, https://www.healthcare.gov/appeal-insurance-company-decision/internal-appeals/ | ACA/commercial internal appeal overview and common timing. |
| SRC-HCG-EXTERNAL | HealthCare.gov, External Review, https://www.healthcare.gov/appeal-insurance-company-decision/external-review/ | External review request and decision timing. |
| SRC-CCIIO-EXT | CMS/CCIIO external appeals information, https://www.cms.gov/cciio/programs-and-initiatives/consumer-support-and-information/csg-ext-appeals-facts | Federal external appeals background and state/federal process routing. |
| SRC-DOL-CLAIMS | DOL/EBSA Filing a Claim for Your Health Benefits, https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/resource-center/publications/filing-a-claim-for-your-health-benefits | ERISA participant-facing workflow, 180-day appeal baseline, and full-review practices. |
| SRC-ERISA-CFR | 29 CFR 2560.503-1, https://www.ecfr.gov/current/title-29/part-2560/section-2560.503-1 | ERISA/group-health claims procedure and timing rules. |
| SRC-ACA-CFR | 45 CFR 147.136, https://www.ecfr.gov/current/title-45/part-147/section-147.136 | ACA internal claims/appeals and external review requirements. |
| SRC-MEDICARE-FFS | CMS Original Medicare FFS appeals, https://www.cms.gov/medicare/appeals-grievances/fee-for-service | Medicare Part A/B appeal levels and appointment of representative. |
| SRC-MEDICARE-FFS-1 | CMS FFS redetermination, https://www.cms.gov/medicare/appeals-grievances/fee-for-service/first-level-appeal-redetermination-medicare-contractor | First-level FFS deadline and correction/reopening distinction. |
| SRC-MEDICARE-FFS-2 | CMS FFS reconsideration, https://www.cms.gov/medicare/appeals-grievances/fee-for-service/second-level-appeal | Second-level FFS deadline and evidence submission warning. |
| SRC-MEDICARE-FFS-3 | CMS FFS OMHA hearing, https://www.cms.gov/medicare/appeals-grievances/fee-for-service/third-level-appeal | OMHA filing deadline and amount-in-controversy warning. |
| SRC-MEDICARE-FFS-4 | CMS FFS Medicare Appeals Council, https://www.cms.gov/medicare/appeals-grievances/fee-for-service/fourth-level-appeal | Council filing and decision timing. |
| SRC-MEDICARE-MA | CMS Medicare Managed Care appeals and grievances, https://www.cms.gov/medicare/appeals-grievances/managed-care | Medicare Advantage appeal overview and current IRE routing. |
| SRC-MEDICARE-MA-RECON | CMS MA plan reconsideration, https://www.cms.gov/medicare/appeals-grievances/managed-care/reconsideration-advantage-health-plan-part-c | MA reconsideration filing and plan decision timing. |
| SRC-MEDICARE-MA-IRE | CMS Part C IRE reconsideration, https://www.cms.gov/medicare/appeals-grievances/managed-care/review-part-c-independent-entitiy | MA IRE decision timing. |
| SRC-MEDICARE-MA-ALJ | CMS MA ALJ hearing, https://www.cms.gov/medicare/appeals-grievances/managed-care/hearing-administration-law-judge | MA ALJ filing deadline and amount-in-controversy warning. |
| SRC-MEDICAID-CFR | 42 CFR Part 438 Subpart F, https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-C/part-438/subpart-F | Medicaid managed-care grievance, appeal, fair-hearing, continuation, and effectuation rules. |
| SRC-HIPAA-MIN | HHS HIPAA Minimum Necessary Requirement, https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/minimum-necessary-requirement/index.html | Minimum-necessary PHI handling. |
| SRC-AHIMA-DENIALS | AHIMA Journal, Claims Denials: A Step-by-Step Approach to Resolution, https://journal.ahima.org/page/top-ten-tips-for-denials-management-14 | Operational denial-management, root-cause, follow-up, and prevention practices. |

## Commercial, ACA, and ERISA Group-Health Timing

| context | general rule | operational task | citation |
|---|---|---|---|
| Initial prior-authorization/pre-service claim decision | Health plan denial notice timing is commonly 15 days for prior authorization or pre-service requests. ERISA group-health plans must decide pre-service claims within a reasonable period appropriate to medical circumstances, no later than 15 days, with one permitted extension up to 15 days when requirements are met. | Capture request received date, extension notice date, missing-information request, and source-stated due date. | SRC-HCG-INTERNAL; SRC-ERISA-CFR 29 CFR 2560.503-1(f)(2)(iii)(A). |
| Initial post-service claim decision | HealthCare.gov states 30 days for services already received. ERISA group-health plans must decide post-service claims no later than 30 days, with one permitted extension up to 15 days when requirements are met. | Verify payer counted from receipt of claim or clean claim; compare with provider contract and state prompt-pay rules separately. | SRC-HCG-INTERNAL; SRC-ERISA-CFR 29 CFR 2560.503-1(f)(2)(iii)(B). |
| Urgent-care initial claim | ERISA group-health plans must decide urgent-care claims as soon as possible but no later than 72 hours; if information is insufficient, the plan must request specific information within 24 hours and allow at least 48 hours to provide it. | Trigger expedited work queue and require clinician statement of urgency. | SRC-ERISA-CFR 29 CFR 2560.503-1(f)(2)(i). |
| Internal appeal filing | HealthCare.gov and DOL/EBSA state that internal appeals generally must be filed within 180 days after receiving notice of denial; plan terms may allow more time. | Treat denial-letter deadline as controlling; if missing, calculate conservative 180-day deadline and create verification task. | SRC-HCG-INTERNAL; SRC-DOL-CLAIMS; SRC-ACA-CFR 45 CFR 147.136(b). |
| Internal appeal decision - urgent | ERISA group-health plans must decide urgent-care appeals as soon as possible but no later than 72 hours after receipt of the appeal. HealthCare.gov also describes expedited internal/external handling when standard timing would seriously jeopardize life or ability to regain maximum function. | Track receipt timestamp, clinical urgency support, simultaneous external-review request when allowed. | SRC-ERISA-CFR 29 CFR 2560.503-1(i)(2)(i); SRC-HCG-INTERNAL. |
| Internal appeal decision - pre-service | ERISA group-health plans with one appeal level must decide within 30 days; if two mandatory appeal levels, each level is due within 15 days. HealthCare.gov states internal appeals for services not yet received must be completed within 30 days. | Determine whether the plan has one or two required levels; use the earliest plausible due date until verified. | SRC-ERISA-CFR 29 CFR 2560.503-1(i)(2)(ii); SRC-HCG-INTERNAL. |
| Internal appeal decision - post-service | ERISA group-health plans with one appeal level must decide within 60 days; if two mandatory appeal levels, each level is due within 30 days. HealthCare.gov states post-service internal appeals must be completed within 60 days. | Track filing date, complete packet date, tolling events, and response due date. | SRC-ERISA-CFR 29 CFR 2560.503-1(i)(2)(iii); SRC-HCG-INTERNAL. |
| External review request | HealthCare.gov states a written external review request must be filed within four months after receiving a notice or final determination from the insurer. | Verify state external review form, federal external review process, authorized representative form, and fee if any. | SRC-HCG-EXTERNAL; SRC-ACA-CFR 45 CFR 147.136(c)-(d). |
| External review decision - standard | Standard external reviews are decided as soon as possible and no later than 45 days after the request is received. | Track IRO assignment, completeness, evidence supplement deadline, and decision deadline. | SRC-HCG-EXTERNAL. |
| External review decision - expedited | Expedited external reviews are decided as soon as possible, no later than 72 hours or sooner based on medical urgency. | Trigger urgent work queue and require clinician-supported urgency statement. | SRC-HCG-EXTERNAL. |

## Medicare Fee-for-Service Timing

| level | filing or decision rule | operational task | citation |
|---|---|---|---|
| Level 1: MAC redetermination | Appellant has 120 days from receipt of the initial claim determination; receipt is presumed 5 calendar days after notice date unless evidence shows otherwise. MAC generally sends the redetermination decision within 60 days of receipt. | Use MSN/RA date, receipt evidence, MAC address/portal, and CMS-20027 or compliant written request. | SRC-MEDICARE-FFS-1. |
| Correction/reopening distinction | CMS states MACs do not process claim corrections involving minor errors and omissions through the appeals process. | If defect is clerical/minor omission, route to reopening/correction before formal appeal, while preserving appeal deadline. | SRC-MEDICARE-FFS-1. |
| Level 2: QIC reconsideration | Appellant has 180 days from receipt of redetermination decision; receipt is presumed 5 days after notice date unless contrary evidence exists. QIC generally sends decision within 60 days. Evidence not submitted at reconsideration may be excluded later unless good cause is shown. | Build complete evidence packet by QIC level; preserve proof of timely filing. | SRC-MEDICARE-FFS-2. |
| Level 3: OMHA ALJ hearing | Request must be filed within 60 days of receipt of the QIC reconsideration decision; receipt is presumed 5 days after notice date unless evidence shows otherwise. Amount in controversy changes annually and must be verified. For CY 2026, CMS lists $200. | Verify amount-in-controversy threshold at time of filing and send required notice to other parties. | SRC-MEDICARE-FFS-3. |
| Level 4: Medicare Appeals Council | Request must be filed within 60 days of receipt of OMHA decision/dismissal; receipt is presumed 5 days after notice date unless evidence shows otherwise. Council processing is generally 90 days from receipt for OMHA decisions and 180 days for escalations, subject to extensions. | Verify DAB filing method, parties copied, and decision due date. | SRC-MEDICARE-FFS-4. |
| Level 5: Federal district court | Available after Council stage when requirements are met, including amount-in-controversy and timing; legal counsel review required. | Do not provide legal advice; refer to counsel or compliance leadership. | SRC-MEDICARE-FFS. |

## Medicare Advantage Timing

| step | general rule | operational task | citation |
|---|---|---|---|
| MA adverse organization determination -> plan reconsideration | Reconsideration requests must be filed with the MA plan within 65 calendar days from the date of the organization determination notice. Standard requests are generally written unless plan accepts oral requests; expedited requests may be oral or written. | Verify Evidence of Coverage, denial notice, appointed representative, and physician support for expedited request. | SRC-MEDICARE-MA-RECON. |
| MA plan reconsideration decision | Plan decision and notice due as fast as health requires, but no later than 72 hours for expedited pre-service benefit or Part B drug requests, 30 calendar days for standard pre-service requests, 7 calendar days for standard Part B drug requests, and 60 calendar days for payment requests. | Track request type; if unfavorable in whole or part, ensure automatic IRE forwarding occurred. | SRC-MEDICARE-MA-RECON. |
| Part C IRE decision | IRE decides as fast as health requires, no later than 72 hours expedited, 30 calendar days standard pre-service, 7 calendar days standard Part B drug, or 60 calendar days payment. Up to 14 calendar day extension may be available except for Part B drug requests. | Track case transfer to IRE, current IRE contractor, and extension notices. | SRC-MEDICARE-MA; SRC-MEDICARE-MA-IRE. |
| MA ALJ hearing | Written request due within 60 calendar days from receipt of IRE reconsideration decision notice; amount-in-controversy threshold changes annually. CMS page listed CY 2026 threshold as $200. | Verify current amount-in-controversy and OMHA filing method. | SRC-MEDICARE-MA-ALJ. |
| MA Appeals Council | Request due within 60 calendar days after receipt of ALJ or attorney adjudicator decision. | Verify DAB-101 or written request requirements. | CMS MA Council page: https://www.cms.gov/medicare/appeals-grievances/managed-care/review-appeals-council |
| MA Federal District Court | Request due within 60 calendar days after receipt of Appeals Council decision; amount-in-controversy threshold changes annually. | Legal counsel review required. | CMS MA Federal District Court page: https://www.cms.gov/medicare/appeals-grievances/managed-care/federal-district-court-review |

## Medicaid Managed-Care Timing

| context | general rule | operational task | citation |
|---|---|---|---|
| Notice of adverse benefit determination | Denial of payment notice must occur at the time of any action affecting the claim. Service authorization notices and terminations/reductions follow 42 CFR 438.404 and linked Medicaid notice rules. | Capture notice sent date, action effective date, prior authorization period, and state-specific notice rules. | SRC-MEDICAID-CFR 42 CFR 438.404. |
| Standard appeal resolution | State must set a timeframe that may not exceed 30 calendar days from receipt of appeal. | Verify state/member-handbook deadline and track MCO receipt date. | SRC-MEDICAID-CFR 42 CFR 438.408(b). |
| Expedited appeal resolution | State must set a timeframe no longer than 72 hours after the plan receives the appeal. | Require urgency evidence and provider support. | SRC-MEDICAID-CFR 42 CFR 438.408(b)(3), 438.410. |
| Extension | MCO/PIHP/PAHP may extend appeal timeframes by up to 14 calendar days if the enrollee requests it or the plan shows need for additional information and the delay is in the enrollee's interest. If plan-initiated, written notice must be given within 2 calendar days. | Track extension reason, who requested it, written notice date, and new due date. | SRC-MEDICAID-CFR 42 CFR 438.408(c). |
| State fair hearing | Enrollee may request a State fair hearing after the managed-care appeal is upheld or deemed exhausted. State must allow no less than 90 and no more than 120 calendar days from the plan's notice of resolution. | Verify state hearing request window and whether appeal deemed exhausted by missed plan timing. | SRC-MEDICAID-CFR 42 CFR 438.408(f). |
| Continuation of benefits | For termination, suspension, or reduction of previously authorized services, continuation requires timely filing on or before the later of 10 calendar days after notice is sent or the intended effective date, plus other conditions in 42 CFR 438.420. | Flag immediately when services are being reduced or stopped; ask staff to verify whether continuation should be requested. | SRC-MEDICAID-CFR 42 CFR 438.420. |
| Effectuation after reversal | If denial/limit/delay of services is reversed and services were not furnished while pending, plan must authorize or provide promptly and no later than 72 hours after receiving notice reversing the determination. | Track reversal date and service authorization/payment execution. | SRC-MEDICAID-CFR 42 CFR 438.424. |

## Privacy and Authority Controls

| issue | rule | operational task | citation |
|---|---|---|---|
| Minimum necessary PHI | HIPAA generally requires covered entities to take reasonable steps to limit use, disclosure, and requests for PHI to the minimum necessary for the purpose, with specified exceptions including treatment, individual authorization, and disclosures required by law. | Limit packets and training data to appeal-relevant PHI; redact non-relevant identifiers and unrelated chart sections. | SRC-HIPAA-MIN. |
| Authorized representative | ERISA group-health claims procedures may not preclude an authorized representative, and urgent-care claims must permit a health care professional with knowledge of the claimant's condition to act as authorized representative. Medicare uses CMS-1696 or a written notice with required elements. | Validate AOB, authorized representative form, patient consent, provider appeal rights, and payer-specific requirements. | SRC-ERISA-CFR 29 CFR 2560.503-1(b)(4); SRC-MEDICARE-FFS. |
| Claim file and criteria request | ERISA denial notices must identify reasons, plan provisions, needed materials, appeal procedures, and, for group health plans, relied-upon internal rules or clinical judgment explanation or availability on request. | Request medical policy, clinical criteria, internal guideline/protocol, claim file, coding rationale, reviewer specialty, and all records reviewed. | SRC-ERISA-CFR 29 CFR 2560.503-1(g), (h), (j). |

## Verify-Locally Rules

Create a `verify_locally` task whenever:

- the denial letter contains a different deadline, address, portal, form, or representative requirement than a general source;
- state law, state Medicaid agency policy, workers' compensation rules, or a provider contract may control;
- a plan is self-funded ERISA, non-federal governmental, grandfathered, excepted benefit, FEHBP, TRICARE, VA, workers' compensation, or another non-standard plan type;
- external review eligibility turns on a state process, medical judgment, surprise-billing rule, grandfathered-plan exception, or specific plan participation;
- amount-in-controversy thresholds or appeal levels may have changed after the cited source date;
- the model only has an EOB/ERA and not the full adverse determination letter.

## Operational Denial-Management Practices

| practice | operational task | source |
|---|---|---|
| Correct and prevent | After resolving a denial, determine what actions are needed to prevent recurrence and assign responsibility with a payer-compliant deadline. | SRC-AHIMA-DENIALS. |
| Track denial categories and trends | Categorize denial reasons, track rates/dollars, analyze patterns, and feed findings into process improvements. | SRC-AHIMA-DENIALS. |
| Act quickly and follow up | Keep denied claims organized, work them promptly, and track every claim through correction, appeal, follow-up, and resolution. | SRC-AHIMA-DENIALS. |
| Use multidisciplinary expertise | Involve registration, case management, patient financial services, HIM/coding, IT, finance, compliance, nursing, and physicians when the denial category requires it. | SRC-AHIMA-DENIALS. |
