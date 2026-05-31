# Clinician Guide: How ClaimGuard AI Was Created

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

This guide explains the project in plain language for clinicians, billers,
operators, and healthcare leaders who want to understand what was built and why.

## 1. Start With The Healthcare Problem

Claim denials interrupt care, delay payment, and create avoidable work for
clinical and billing teams. Many denials are related to missing documentation,
authorization gaps, coding issues, eligibility problems, or timing rules. The
project starts from that operational pain point: help staff identify denial
risk earlier and prepare better human-reviewed appeal work when a denial has
already happened.

## 2. Break The Denial Workflow Into Human Steps

Before training or using a model, the workflow was decomposed into concrete
steps:

- Receive the denial or claim document.
- Identify the payer, plan type, service, denial reason, and appeal route.
- Separate known facts from model inferences.
- Identify missing documents or verification tasks.
- Decide whether the issue is an appeal, corrected claim, coding review, or
  documentation gap.
- Draft appeal language only for human review.
- Keep deadline, legal, payer-policy, and clinical statements gated for
  verification.

That decomposition matters because the model should support a staff workflow,
not invent payer rules or file appeals by itself.

## 3. Add PHI And Privacy Controls First

Healthcare AI work cannot safely start with raw patient information. ClaimGuard
therefore adds metadata-only PHI/PII scanning, document-surface inspection,
de-identification states, residual-risk checks, and manual review gates.

The system is designed so reports can show what is blocked without printing
names, claim identifiers, member IDs, raw documents, prompts, API keys, or
approval references.

## 4. Create Safe Synthetic Denial And Appeal Examples

The project includes a generated synthetic denial/appeal stress corpus. These
documents are fictitious, paired, varied by format and layout, and designed for
testing. They are not real patient or payer documents.

The synthetic corpus helps stress-test:

- denial-letter formats,
- appeal-letter draft formats,
- document length variation,
- layout variation,
- typography and rendered HTML variation,
- train/validation/test data splits,
- PHI scanning,
- appeal quality rules.

## 5. Build A Source-Grounded App

The application combines:

- a FastAPI backend,
- a React frontend,
- claim prediction endpoints,
- denial workflow analysis,
- appeal draft support,
- analytics,
- EDI parser controls,
- PHI-safe logging and error responses,
- encrypted retrieval-source storage,
- admin readiness and monitoring endpoints.

The app is not just a model demo. It includes operational controls for how
documents are uploaded, inspected, reviewed, stored, retired, and audited.

## 6. Use A Teacher Model To Produce Better Training Labels

LLM distillation means using a larger model or human-reviewed process to
produce high-quality examples, then training a smaller model to follow that
behavior.

In simple terms:

1. Create safe examples.
2. Ask a larger teacher or human reviewer to produce high-quality structured
   outputs.
3. Validate that those outputs follow the schema and safety rules.
4. Export the approved examples into a training format.
5. Fine-tune a smaller student model.
6. Benchmark the student model against the same workflow requirements.

ClaimGuard keeps this process guarded. Synthetic examples can be used for local
experiments, but production corpus training requires approved non-synthetic
denial/appeal pairs and privacy/legal review.

## 7. Train A Smaller Student Model For A Narrow Job

The student model is intended for a narrow ClaimGuard task: denial workflow and
appeal draft support. It is not a general medical model and it is not allowed
to make final medical, legal, coverage, or payment decisions.

The project includes MLX-LM tooling for Apple Silicon experiments, guarded
LoRA fine-tuning scripts, benchmark harnesses, acceptance gates, and runtime
supervision evidence.

## 8. Keep Human Review In The Loop

Appeal drafts stay labeled as drafts for human review. Deadline claims,
clinical assertions, coding recommendations, and payer-policy statements must
be verified against the source record, plan language, current rules, and
professional judgment.

This is especially important because an AI system may summarize or structure a
case well while still missing plan-specific or patient-specific details.

## 9. Separate Local Progress From Production Readiness

ClaimGuard has many local controls already implemented, but production
readiness requires evidence that cannot be safely stored in a public source
repository:

- real legal and BAA approval,
- consent notice configuration,
- non-secret approval references,
- approved non-synthetic denial/appeal training sources,
- production semantic vector backend configuration,
- runtime owner assignment,
- latest monitoring run evidence,
- production fairness and threshold calibration review.

That is why the current readiness reports can say the local state is safe while
also saying production is not ready.

## 10. How Clinicians Can Evaluate This Project

Clinicians and healthcare operators should look for these properties:

- Does the tool explain why a denial risk exists?
- Does it separate known facts from inferred facts?
- Does it preserve human review before submission?
- Does it keep PHI out of logs and evidence files?
- Does it avoid claiming legal, payer-policy, or medical certainty?
- Does it document what is still blocked before production use?

ClaimGuard is designed around those questions.

## Collaboration

If you are dealing with claim denials, appeal volume, documentation gaps, EDI
workflows, reimbursement analytics, or healthcare AI safety problems, Raphael
Malikian is available to collaborate.

Email: <rtmalikian@gmail.com>
