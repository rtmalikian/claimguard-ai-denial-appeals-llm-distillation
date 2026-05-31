# LLM Distillation Plan for Health Insurance Denial Appeals

Last updated: 2026-05-29

## 1. Executive Summary

This project is an independent AI platform for helping users navigate health
insurance denials and generate appeal-letter drafts. It should not fork, branch,
or structurally depend on the Fight Health Insurance repository.

The platform should use a small local student model, retrieval over trusted
documents, and strict structured outputs. The model should help with:

- Reviewing denial letters and EOBs.
- Explaining what the insurer denied and why.
- Identifying missing evidence, procedural errors, and next steps.
- Routing the user to the correct appeal path.
- Drafting a cited appeal letter and supporting-document checklist.

The primary hardware target is:

- 2021 M1 iMac
- Apple M1, 8 cores
- 16 GB unified memory
- macOS 26.5
- Apple Silicon optimized local inference via MLX/MLX-LM

Recommended first model:

- `Qwen/Qwen3-4B-MLX-4bit`
- Apache-2.0 license
- MLX-native 4-bit quantized format
- Small enough for the M1 iMac while still strong enough for appeal drafting
- Model card: https://huggingface.co/Qwen/Qwen3-4B-MLX-4bit

Recommended fallback model:

- `Qwen/Qwen3-1.7B`
- Use for routing, extraction, and very low-resource operation
- Model card: https://huggingface.co/Qwen/Qwen3-1.7B

Important principle: the model should not be trusted as a standalone insurance
expert. Retrieval, citations, templates, and explicit uncertainty handling should
carry the safety-critical parts of the product.

## 2. Product Goals

### 2.1 Core User Outcomes

The system should help a user answer:

- What was denied?
- Why was it denied?
- What kind of plan or payer path applies?
- What deadline or next step matters?
- What evidence is missing?
- What language should my appeal letter include?
- What documents should I attach?
- What public rules or similar cases support the appeal?

### 2.2 Core Product Capabilities

The MVP should support:

- Uploading a denial letter, EOB, plan document, medical policy, or supporting
  provider letter.
- OCR and text extraction from PDF/image inputs.
- Structured extraction of denial facts.
- Payer and appeal-path routing.
- Retrieval over plan language, agency rules, public hearing/adjudication
  records, and insurer policies.
- Cited checklist generation.
- Appeal-letter drafting.
- Export to Markdown, DOCX, and PDF.
- User review and edit before final output.

### 2.3 Non-Goals for V1

Do not attempt to solve all of these immediately:

- Fully automated legal advice.
- Fully automated medical necessity determination.
- Live insurer submission workflows.
- Real-time phone negotiation with insurers.
- Training on user PHI.
- Comprehensive state-by-state appeal expertise for every payer and benefit
  category.
- Direct weight pruning before quantized model benchmarks exist.

## 3. Safety and Compliance Posture

Treat every uploaded user document as PHI by default.

### 3.1 Required Controls

The production platform should include:

- Encryption at rest.
- Encryption in transit.
- Strong authentication.
- Role-based access controls.
- Per-document access audit logs.
- Configurable retention and deletion.
- No user-uploaded PHI in training by default.
- Explicit opt-in before using any user data for improvement.
- Automated de-identification plus human review before any real user document is
  allowed into a training dataset.
- BAA-backed vendors only if PHI is sent to external services.

### 3.2 Model Behavior Rules

The model must:

- Avoid claiming to provide legal advice.
- Avoid claiming to provide medical advice.
- Avoid fabricating deadlines.
- Avoid fabricating plan language.
- Avoid fabricating policy citations.
- Avoid making unsupported clinical claims.
- Ask for missing denial pages or plan documents when necessary.
- Clearly label uncertainty.
- Cite retrieved sources for procedural and policy recommendations.

### 3.3 Training Data Rule

Default training data posture:

- Public data.
- Synthetic data.
- Formally de-identified data.

Do not train on raw user uploads.

## 4. Recommended Model Strategy

### 4.1 Primary Student Model

Use `Qwen/Qwen3-4B-MLX-4bit` as the first local student model.

Reasons:

- 4B parameters is a practical quality/size tradeoff.
- The 4-bit MLX build is appropriate for 16 GB unified memory.
- The model is small enough for local experimentation on Apple Silicon.
- Qwen3 supports instruction following and structured generation well enough to
  evaluate for JSON extraction and appeal drafting.
- Apache-2.0 licensing is preferable for independent product development.

Source:

- https://huggingface.co/Qwen/Qwen3-4B-MLX-4bit

### 4.2 Fallback Model

Use `Qwen/Qwen3-1.7B` as the low-resource fallback.

Use cases:

- Denial classification.
- Payer routing.
- Deadline extraction.
- Missing-field detection.
- Checklist prefill.
- Triage when the 4B model is unavailable.

Source:

- https://huggingface.co/Qwen/Qwen3-1.7B

### 4.3 Benchmark Alternatives

Evaluate these before final production lock-in:

- `microsoft/Phi-4-mini-instruct`
  - Strong candidate for memory/compute constrained scenarios.
  - Source: https://huggingface.co/microsoft/Phi-4-mini-instruct

- Gemma 3 4B variants
  - Useful comparison for laptop/desktop deployment.
  - Source: https://huggingface.co/google/gemma-3-4b-pt

### 4.4 Teacher Model

Use a larger teacher model only for dataset creation and evaluation, not as the
required user runtime.

Teacher tasks:

- Convert public decisions and hearing records into structured examples.
- Generate synthetic denial letters from templates and case summaries.
- Draft appeal letters from source-grounded records.
- Label missing evidence and appeal paths.
- Produce grading rubrics for student outputs.

The teacher model should not receive PHI unless it is operated under a compliant
environment with the correct contractual controls.

## 5. Apple Silicon and MLX Plan

### 5.1 Runtime Choice

Use MLX-LM as the default local inference runtime on the M1 iMac.

Sources:

- MLX: https://github.com/ml-explore/mlx
- MLX-LM: https://github.com/ml-explore/mlx-lm

MLX is appropriate because it is designed for Apple Silicon and uses the unified
memory model. MLX-LM supports generation, local serving, prompt caching,
quantization, and fine-tuning workflows.

### 5.2 Local Inference Command

Install MLX-LM:

```bash
python3 -m pip install --upgrade mlx-lm
```

Start a local OpenAI-compatible endpoint:

```bash
mlx_lm.server --model "Qwen/Qwen3-4B-MLX-4bit"
```

The application should call the local server through the OpenAI-compatible API:

```text
POST http://localhost:8080/v1/chat/completions
```

The exact port should be confirmed from the `mlx_lm.server --help` output in the
implementation environment.

### 5.3 MLX Optimization Defaults

Use these defaults for the M1 iMac path:

- Prefer MLX-format models over GGUF/Ollama for the primary runtime.
- Use streaming generation for responsive UI.
- Use prompt caching for repeated static material.
- Use retrieval/chunking instead of feeding entire documents into context.
- Keep maximum context bounded per workflow.
- Keep JSON extraction prompts short and deterministic.
- Use `enable_thinking=False` for extraction, classification, and schema output.
- Enable reasoning only for complex appeal strategy review.
- Do not store internal chain-of-thought in logs, history, or outputs.

### 5.4 Long Document Handling

Do not put full plan PDFs or long public decisions directly into the prompt.

Use:

- OCR/text extraction.
- Section-aware chunking.
- Embeddings.
- RAG retrieval.
- Page/section citations.
- Prompt caching for repeated fixed context.
- Smaller focused prompts for extraction and drafting.

### 5.5 Portability Runtime

Keep GGUF/llama.cpp or Ollama as fallback options for non-Apple systems, but the
optimized first path should be MLX.

## 6. Product Architecture

### 6.1 High-Level Components

The product should have these components:

- Web or desktop UI.
- Document ingestion service.
- OCR/text extraction pipeline.
- PHI-safe document store.
- Local model service through MLX-LM.
- Retrieval/indexing service.
- Denial analyzer.
- Payer router.
- Appeal strategy generator.
- Appeal-letter generator.
- Export service.
- Evaluation harness.

### 6.2 Document Ingestion

Input types:

- PDF denial letters.
- Image denial letters.
- EOBs.
- Plan documents.
- Summary Plan Descriptions.
- Medical policies.
- Provider letters.
- Medical records selected by the user.

Processing steps:

- Upload.
- Virus/type validation.
- OCR if needed.
- Text extraction.
- Page-level segmentation.
- PHI tagging.
- Metadata extraction.
- Storage with encryption.
- Indexing for retrieval.

### 6.3 Retrieval Layer

Indexes should cover:

- User denial letter and EOB.
- User plan document or SPD.
- Insurer medical policy.
- CMS rules and notices.
- DOL/ERISA appeal rules.
- State external review rules.
- Public IRO decisions.
- Public fair hearing decisions.
- Public Medicare appeal decisions.
- Appeal templates.

Each chunk should store:

- Source URL or local document ID.
- Title.
- Source type.
- Jurisdiction.
- Payer type.
- Date.
- Page number or section.
- Extracted text.
- PHI status.
- License/reuse status.

### 6.4 Model Task Split

Use small, structured tasks rather than one large free-form prompt.

Task 1: Document classification

- Is this a denial letter, EOB, policy, plan document, medical record, or appeal
  response?

Task 2: Denial fact extraction

- Extract dates, claim/service details, reason, payer, plan type, and cited
  policy language.

Task 3: Payer routing

- Classify as commercial, ERISA, Medicare, Medicare Advantage, Part D, Medicaid,
  Medicaid managed care, marketplace, state-regulated, or unknown.

Task 4: Missing evidence analysis

- Identify missing records, provider letters, clinical criteria, coding details,
  prior authorization records, and plan provisions.

Task 5: Retrieval query generation

- Generate search queries against local indexes.

Task 6: Appeal strategy

- Create a source-grounded strategy and checklist.

Task 7: Appeal letter drafting

- Draft a letter with citations and user-editable placeholders.

Task 8: Quality check

- Check for unsupported claims, missing citations, missing deadlines, and unsafe
  advice.

## 7. Core Output Schema

The denial analyzer should produce structured JSON similar to:

```json
{
  "document_type": "denial_letter",
  "payer_name": null,
  "payer_type": "unknown",
  "plan_type": "unknown",
  "service_or_item": null,
  "provider": null,
  "date_of_service": null,
  "denial_date": null,
  "claim_number": null,
  "denial_reason": null,
  "denial_category": "unknown",
  "appeal_deadline": null,
  "appeal_level": "unknown",
  "required_documents": [],
  "missing_evidence": [],
  "policy_citations": [],
  "public_rule_citations": [],
  "similar_public_cases": [],
  "recommended_fix": [],
  "appeal_letter_draft": null,
  "confidence": 0.0,
  "needs_human_review": true,
  "warnings": []
}
```

Important behavior:

- Use `null` or `unknown` when facts are missing.
- Do not infer deadlines without source support.
- Do not create citations unless the retrieval layer supplied them.
- Flag ambiguous payer type for human review.

## 8. Distillation and Fine-Tuning Strategy

### 8.1 Sequence

Do not start with direct weight pruning.

Recommended sequence:

1. Collect public/source-grounded data.
2. Normalize documents into source chunks.
3. Use a teacher model to create structured examples.
4. Build a gold evaluation set manually.
5. Establish baseline performance with `Qwen/Qwen3-4B-MLX-4bit`.
6. Fine-tune with LoRA/QLoRA where useful.
7. Convert/finalize for MLX.
8. Quantize and benchmark.
9. Compare against fallback models.
10. Only then consider pruning or model architecture changes.

### 8.2 Training Examples

Each training example should include:

- Input document excerpt.
- Source metadata.
- Expected JSON extraction.
- Retrieved supporting source snippets.
- Expected checklist.
- Expected appeal-letter draft.
- Refusal/uncertainty behavior when needed.

Example categories:

- Medical necessity denial.
- Experimental/investigational denial.
- Prior authorization denial.
- Out-of-network denial.
- Coding/billing denial.
- Missing documentation denial.
- Eligibility/coverage denial.
- ERISA appeal denial.
- Medicare Advantage denial.
- Medicare Part D denial.
- Medicaid managed-care denial.

### 8.3 Distillation Objective

The student should learn:

- The output format.
- The routing logic.
- The language style.
- The uncertainty policy.
- How to turn retrieved facts into an appeal letter.

The student should not be expected to memorize all policy rules.

### 8.4 Evaluation Before Fine-Tuning

Before fine-tuning, measure:

- Base model extraction quality.
- Base model JSON validity.
- Citation discipline.
- Latency.
- Memory pressure.
- Draft usefulness.

Fine-tune only if the evaluation shows consistent gaps that prompting and
retrieval do not solve.

## 9. Public Data Sources

### 9.1 Government Notice and Rule Sources

CMS Medicare Advantage denial notices:

- https://www.cms.gov/Medicare/Medicare-General-Information/BNI/MADenialNotices.html

CMS Medicare Summary Notice:

- https://www.cms.gov/medicare/coverage/summary-notice

CMS Part C/D Appeals Decision Search:

- https://www.cms.gov/medicare/appeals-grievances/appeals-decision-search-part-c-d

DOL/EBSA internal claims and external review:

- https://www.dol.gov/node/63657

HealthCare.gov internal appeals:

- https://www.healthcare.gov/appeal-insurance-company-decision/internal-appeals/

HealthCare.gov external review:

- https://www.healthcare.gov/appeal-insurance-company-decision/external-review/

Federal external review/adverse benefit determination rule reference:

- https://www.law.cornell.edu/cfr/text/29/2590.715-2719

### 9.2 Hearing and Adjudication Sources

Congressional/GovInfo hearing records:

- Useful for real-world denial, rescission, appeal, and insurer behavior fact
  patterns.
- Some records may include redacted exhibits or insurer communications.
- Example: https://www.govinfo.gov/app/details/CHRG-111hhrg73743/CHRG-111hhrg73743

HHS Departmental Appeals Board:

- Medicare and HHS program adjudication decisions.
- https://www.hhs.gov/about/agencies/dab/decisions/index.html

Medicare Appeals Council selected decisions:

- https://www.hhs.gov/about/agencies/dab/decisions/council-decisions/index.html

NY OTDA Fair Hearing Decision Archive:

- Publishes fair hearing decisions edited to remove identifying information.
- Useful for Medicaid and managed-care dispute patterns.
- https://otda.ny.gov/hearings/search/

NY DFS External Appeal Search:

- Public external appeal case summaries and outcomes.
- https://www.dfs.ny.gov/public-appeal/search

Washington IRO decisions:

- https://fortress.wa.gov/oic/consumertoolkit/search.aspx?searchtype=indrev

Oregon IRO Case Detail Report:

- https://dfr.oregon.gov/insure/health/understand/coverage/Pages/iro-decision-report.aspx

Texas IRO archive:

- https://www.tdi.texas.gov/hmo/mcqa/iro_decisions.html

California DMHC IMR determinations:

- Use for external medical review trends and examples.
- https://test.lab.data.ca.gov/dataset?name=independent-medical-review-imr-determinations-trend

CourtListener RECAP:

- Useful for ERISA and insurer-litigation exhibits.
- Treat as research-only until PHI, copyright, and terms review are complete.
- https://www.courtlistener.com/recap/

### 9.3 Insurer Policy Sources

Public insurer medical policies can support retrieval and appeal drafting.

Examples:

- Aetna Clinical Policy Bulletins:
  https://www.aetna.com/health-care-professionals/clinical-policy-bulletins.html

- Cigna coverage policies:
  https://www.cigna.com/health-care-providers/coverage-and-claims/policies/medical-necessity-definitions

Other insurers to evaluate:

- UnitedHealthcare medical policies.
- Blue Cross Blue Shield medical policies.
- Anthem/Elevance policies.
- Humana medical coverage policies.
- Kaiser coverage policies where public.

Policies should be stored with source date, URL, jurisdiction if applicable, and
retrieval metadata.

## 10. Data Safety Tiers

### 10.1 Tier 1: Training-Safe Candidates

These are the safest sources to use first:

- Government-authored model notices.
- Agency-authored decisions.
- Public decision summaries with identifying information removed.
- Synthetic denial and appeal examples generated from public rules/templates.
- Public policy snippets where licensing allows internal training use.

### 10.2 Tier 2: Use After Review

These may be useful but need extra review:

- Legislative hearing exhibits.
- Public comments containing appeal-process examples.
- IRO summaries with partial facts.
- State hearing decisions requiring additional PHI screening.
- Public insurer policies with terms-of-use constraints.

### 10.3 Tier 3: Research-Only Until Cleared

Do not train on these until legal, PHI, and copyright review is complete:

- Court exhibits.
- Actual insurer denial letters from litigation.
- Claim files.
- Patient-submitted public posts.
- Reddit/forum posts.
- Documents containing names, member IDs, claim numbers, addresses, dates of
  birth, provider names tied to rare conditions, or rare-condition narratives.

## 11. MVP Workflow

### 11.1 User Flow

1. User uploads a denial letter.
2. User optionally uploads EOB, plan document, SPD, policy, or provider letter.
3. System extracts text and page references.
4. System identifies document type.
5. Model extracts structured denial facts.
6. Payer router determines likely appeal path.
7. Retrieval layer finds relevant plan, policy, rule, and public-case snippets.
8. Model generates a denial explanation.
9. Model generates "what to fix" checklist.
10. Model drafts appeal letter.
11. Quality checker flags unsupported claims or missing citations.
12. User edits final output.
13. System exports letter and attachment checklist.

### 11.2 Generated User Outputs

The system should produce:

- Denial summary.
- Appeal deadline warning.
- Appeal route.
- Missing evidence checklist.
- Provider-letter request checklist.
- Cited appeal strategy.
- Appeal-letter draft.
- Attachment list.
- Uncertainty and human-review warnings.

## 12. Evaluation Plan

### 12.1 Gold Test Set

Create a gold test set across:

- Commercial medical necessity denials.
- Prior authorization denials.
- Post-service claim denials.
- Experimental/investigational denials.
- Coding/billing denials.
- Network/coverage denials.
- ERISA plan denials.
- Medicare Advantage denials.
- Medicare Part D denials.
- Medicaid managed-care denials.
- State external review cases.

### 12.2 Metrics

Score separately:

- Extraction accuracy.
- JSON validity.
- Payer routing accuracy.
- Deadline accuracy.
- Missing evidence detection.
- Citation correctness.
- Appeal draft usefulness.
- Unsupported claim rate.
- Hallucination rate.
- PHI leakage risk.
- Latency.
- Time to first token.
- Tokens per second.
- Peak memory pressure.

### 12.3 Acceptance Criteria

The MVP should meet these criteria before broad use:

- No fabricated citations in evaluated examples.
- No unsupported appeal deadlines in evaluated examples.
- No confident answer when payer regime is ambiguous.
- Every procedural recommendation cites a retrieved source or explicitly states
  that the source is missing.
- Local Qwen3-4B MLX 4-bit produces usable drafts on the M1 iMac.
- Outputs are editable and reviewable by the user.

## 13. Benchmark Matrix

Benchmark models:

- `Qwen/Qwen3-4B-MLX-4bit`
- `Qwen/Qwen3-1.7B`
- `microsoft/Phi-4-mini-instruct`
- Gemma 3 4B variants
- Larger teacher model for labeling only

Benchmark tasks:

- Denial fact extraction.
- Payer routing.
- Missing evidence detection.
- Appeal deadline detection.
- Checklist generation.
- Appeal-letter drafting.
- Citation discipline.

Benchmark hardware:

- Primary: M1 iMac, 16 GB unified memory.
- Optional: lower-RAM Apple Silicon machine.
- Optional: modest CPU-only machine.
- Optional: low-cost cloud GPU.

## 14. Recommended Implementation Phases

### Phase 1: Research and Corpus Builder

Deliverables:

- Source registry.
- Data license/status notes.
- Download/scrape scripts where permitted.
- Normalized document schema.
- PHI scanner.
- Initial corpus of public templates, rules, IRO cases, and hearing decisions.

### Phase 2: Local MLX Inference Harness

Deliverables:

- `mlx_lm.server` wrapper.
- Local prompt runner.
- Structured JSON extraction prompts.
- Baseline latency and quality benchmarks on the M1 iMac.

### Phase 3: Retrieval Prototype

Deliverables:

- Document chunker.
- Embedding/indexing pipeline.
- Source metadata.
- Retrieval API.
- Citation formatting.

### Phase 4: Denial Analyzer MVP

Deliverables:

- Upload and OCR path.
- Denial fact extraction.
- Payer routing.
- Missing evidence checklist.
- Appeal path summary.

### Phase 5: Appeal Drafting MVP

Deliverables:

- Appeal-letter generator.
- Attachment checklist.
- Citation validator.
- Export to Markdown/DOCX/PDF.

### Phase 6: Distillation Dataset

Deliverables:

- Teacher-labeled examples.
- Synthetic denial letters.
- Synthetic appeal drafts.
- Gold evaluation set.
- Fine-tuning dataset cards.

### Phase 7: Fine-Tune and Quantize

Deliverables:

- LoRA/QLoRA experiments.
- MLX-compatible converted model.
- 4-bit quantized model.
- Before/after evaluation.
- Regression suite.

### Phase 8: Compliance Hardening

Deliverables:

- PHI retention controls.
- Audit logs.
- Access controls.
- De-identification review flow.
- Vendor/BAA review if external services are used.

## 15. File and Repo Structure Recommendation

Suggested future structure:

```text
llm-distill/
  README.md
  llm-distill-plan.md
  docs/
    data-sources.md
    safety-and-hipaa.md
    eval-rubric.md
    mlx-setup.md
  data/
    raw/
    processed/
    eval/
  scripts/
    collect_sources.py
    normalize_documents.py
    run_phi_scan.py
    build_eval_set.py
  app/
    backend/
    frontend/
  models/
    prompts/
    adapters/
  evals/
    cases/
    reports/
```

Do not store PHI in git.

Add `.gitignore` rules before any data work:

```gitignore
data/raw/
data/processed/
data/eval/private/
models/local/
*.sqlite
*.db
*.parquet
*.safetensors
*.gguf
.env
```

## 16. Initial Commands for Local MLX Validation

These commands are for the implementation phase once dependencies are allowed.

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --upgrade mlx-lm
```

Run a quick generation test:

```bash
mlx_lm.generate \
  --model "Qwen/Qwen3-4B-MLX-4bit" \
  --prompt "Extract the denial reason from this sentence: Coverage was denied because the service was not medically necessary."
```

Start the local model server:

```bash
mlx_lm.server --model "Qwen/Qwen3-4B-MLX-4bit"
```

Test chat completion:

```bash
curl -sS http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-4B-MLX-4bit",
    "messages": [
      {
        "role": "user",
        "content": "Return JSON with denial_category for: The requested MRI is denied as not medically necessary."
      }
    ]
  }'
```

Confirm the actual port and server options with:

```bash
mlx_lm.server --help
```

## 17. Open Questions

These should be resolved before implementation beyond the planning document:

- Is the first user persona consumer, provider office, patient advocate, or
  attorney/benefits consultant?
- Should the first MVP prioritize commercial/ERISA, Medicare, Medicaid, or
  all-payer routing with shallow guidance?
- Should training happen locally on the M1 iMac or on a temporary larger cloud
  GPU?
- Which export formats are required first: DOCX, PDF, Markdown, or all three?
- Will user accounts and document storage be local-first, cloud-hosted, or hybrid?
- Will the product include provider-letter request templates?

## 18. Default Decisions

Unless changed later, use these defaults:

- Runtime: MLX-LM.
- Primary local model: `Qwen/Qwen3-4B-MLX-4bit`.
- Fallback model: `Qwen/Qwen3-1.7B`.
- Data posture: no user PHI in training.
- Training data: public, synthetic, and formally de-identified only.
- First correctness layer: retrieval and citations.
- First workflow: denial review, fix checklist, and appeal-letter draft.
- First hardware optimization target: M1 iMac with 16 GB unified memory.
- Court filings and real denial letters from public litigation: research-only
  until reviewed.

## 19. Key Risks

### 19.1 Hallucinated Rules or Deadlines

Mitigation:

- Require retrieval citations.
- Use null/unknown for missing facts.
- Use a quality-check pass.
- Add payer-specific deadline tests.

### 19.2 PHI Leakage

Mitigation:

- No PHI in git.
- No PHI in prompts sent to non-compliant external APIs.
- Redaction and review before training.
- Audit logs and retention controls.

### 19.3 Bad Appeal Advice

Mitigation:

- Avoid legal/medical advice claims.
- Cite sources.
- Flag uncertainty.
- Provide editable drafts.
- Encourage professional review for high-stakes cases.

### 19.4 Model Too Weak

Mitigation:

- Use RAG and templates.
- Keep the model task narrow.
- Compare Qwen3-4B against Phi-4-mini and Gemma 3 4B.
- Use a larger teacher for data generation.

### 19.5 Public Data Reuse Problems

Mitigation:

- Track source, license, and PHI status.
- Separate research-only documents from training-safe documents.
- Do not assume public court access equals training permission.

## 20. Final Recommendation

Start with a local MLX MVP on the M1 iMac:

1. Build the source registry and evaluation set.
2. Run `Qwen/Qwen3-4B-MLX-4bit` locally with MLX-LM.
3. Create structured prompts for extraction, routing, and checklist generation.
4. Add retrieval before fine-tuning.
5. Benchmark base performance.
6. Generate teacher-labeled public/synthetic training examples.
7. Fine-tune only after baseline failures are clearly measured.
8. Quantize and validate the student model on the M1 iMac.

This approach keeps the project lightweight, independent, Apple Silicon
optimized, and grounded in public sources rather than unsupported model memory.
