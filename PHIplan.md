  # Combined Plan: Safe Corpus, De-Identification, Distillation Upgrade, and Student Cutover

  ## Summary

  - The prior work completed a narrow synthetic distillation MVP, not a production-grade training corpus.
  - Current evidence is limited to 10 synthetic scenarios, 10 reviewed synthetic SFT records, one sample denial TXT, one
    public model notice PDF, a source URL registry, and an appeal-letter template.

  - The largest missing item is a safe repository of denial-letter and appeal-letter examples, including paired denial/appeal
    examples.

  - Add a formal de-identification pipeline before any real-world denial or appeal document can enter the corpus.
  - Automation may produce candidate de-identified documents, but Raphael will manually review before training eligibility.
  - Current runtime remains NVIDIA by default: LLM_PROVIDER=nvidia_nim; the student is integrated/status-visible but
    CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false.

  ## Key Changes

  - Build a safe hybrid corpus:
      - Public/government model denial notices and appeal-process examples.
      - Synthetic denial/appeal pairs generated from denial_skill.
      - Formally de-identified real examples only when Raphael provides or approves them.
      - Paired denial-letter plus appeal-letter examples wherever possible.

  - Add document intake states:
      - raw_quarantined
      - machine_deidentified
      - qa_failed
      - human_review_required
      - privacy_review_passed
      - expert_determination_required
      - training_eligible

  - Add a versioned corpus manifest with:
      - source_id, document_id, pair_id, source_type, document_role, source_url_or_path, checksum, phi_status,
        deidentification_status, license_status, review_status, residual_risk_score, training_eligible, split, and
        micro_skill_ids.

  - Add automated de-identification:
      - Regex/rule checks for HIPAA Safe Harbor identifiers.
      - Healthcare-specific checks for claim IDs, authorization numbers, policy/member/subscriber IDs, payer portal metadata,
        fax headers, document footers, barcodes/QR text, and attachment filenames.

      - Local-only LLM/NER review for contextual identifiers and rare narrative facts; no external API unless explicitly
        approved.

  - Replace identifiers with stable placeholders:
      - [PATIENT_1], [MEMBER_ID_1], [CLAIM_ID_1], [AUTH_ID_1], [PROVIDER_1], [DATE_SERVICE_1].
      - Preserve workflow meaning while removing real identifiers.
      - Generalize dates, geography, ages, and rare facts according to the chosen de-identification method.

  - Add residual-risk scoring:
      - Detect rare diagnosis/procedure narratives, exact timeline uniqueness, small geography plus provider plus date
        combinations, unusual service/dollar combinations, and free-text facts that could re-identify a patient.

      - Block training eligibility when residual risk is above threshold.

  - Add manual review:
      - All real-world documents require Raphael/privacy review before training use.
      - High-risk documents require expert determination or remain retrieval-only/excluded.
      - Store reviewer ID, timestamp, method, findings, residual-risk score, and training decision.

  ## Platform And Distillation Integration

  - Corpus/API/backend:
      - Add corpus status/import/validate endpoints under /api/v1/denial-workflow/corpus.
      - Import approved de-identified documents into the encrypted retrieval/corpus store.
      - Extend retrieval metadata to distinguish rule sources, denial examples, appeal examples, templates, and paired denial/
        appeal examples.

      - Report counts by raw/de-identified/reviewed/training-eligible status.

  - Frontend:
      - Add an admin corpus readiness panel showing source counts, PHI/license/review gates, training-eligible counts,
        residual-risk status, and missing categories.

      - Add student-default readiness status with clear blockers before enabling default student use.
      - Prevent one-click training use for real documents unless all gates pass.

  - Distillation:
      - Only training_eligible=true records can be exported into SFT datasets.
      - Generate larger SFT records from approved corpus entries.
      - Preserve paired denial-letter plus appeal-letter relationships.
      - Preserve denial_skill MS01-MS12 coverage and add coverage by payer type, denial type, route, appeal level, outcome,
        source type, and document role.

      - Add appeal-letter quality rubrics, source-grounding checks, hallucination checks, deadline/citation checks, PHI-
        minimization checks, and route correctness checks.

      - Require human or compliant large-teacher review for corpus-derived labels.

  - Runtime:
      - Keep NVIDIA as default until gates pass.
      - After corpus validation and benchmark acceptance, enable supervised MLX auto-launch.
      - Then set the student as default for denial workflow and appeal generation only.
      - Keep NVIDIA OCR and broader document-analysis paths unless separately replaced.
      - Add a rollback flag that returns denial workflow to NVIDIA/deterministic fallback without code changes.

  ## Test And Acceptance Plan

  - Corpus/de-identification validation:
      - Manifest schema tests, checksum tests, PHI-scan tests, license gate tests, de-identification gate tests, and import
        failure tests.

      - Unit tests for each identifier class and placeholder replacement.
      - OCR/PDF tests for hidden text, headers, footers, scanned pages, metadata, barcodes/QR text, and attachment filenames.
      - Negative tests where raw names, DOBs, claim IDs, member IDs, phone numbers, emails, addresses, exact dates, and
        policy/member identifiers must be removed.

      - Residual-risk tests for rare condition narratives and unique fact combinations.
      - End-to-end test: raw denial plus appeal pair enters quarantine, is machine de-identified, fails or passes QA, and only
        passes into training export after manual review.
        outcomes.
        correctness, appeal-letter quality, and no-PHI checks.

      - Rollback flag restores NVIDIA/deterministic fallback without code changes.

  ## Assumptions

  - Use the safe hybrid corpus strategy.
  - Raphael will manually review de-identified real-world documents before training eligibility.
  - Use Safe Harbor-style automation as the baseline, with Expert Determination available for higher-utility datasets where
    preserving more detail is necessary.

  - Do not use external LLM APIs for de-identifying PHI unless Raphael explicitly approves a compliant vendor path.
  - Do not train on raw uploaded denial letters, claim files, or appeal packets.
# ClaimGuard AI PHI Safeguards Plan

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current Objective Scratchpad: Implement concrete PHI/PII safeguards for denial
workflow intake, source ingestion, exports, corpus distillation gates, tests,
retrieval-source governance, model-improvement compliance gates, and validation
while keeping matched values out of logs, upload/document-inspection output,
scanner output, changelog entries, and generated evidence. Continue production
hardening with local AI safety guardrails for prompt-injection text,
hallucination-risk language, and NVIDIA provider fallback without exposing raw
document text, prompts, model responses, credentials, PHI, or production
document content in logs or evidence. Keep admin PHIplan readiness visibility
sanitized to requirement IDs, counts, statuses, and safe blocker tokens.

## Implementation Tracking

The combined plan above is the active PHI/corpus/student-cutover scope. Earlier
in this run the file was observed as empty, then the broader plan content became
available. The controls below record implementation progress against the current
plan plus the active ClaimGuard `AGENTS.md`.

## Implemented Controls

- Treat denial workflow intake as `contains_phi` by default unless the caller
  explicitly declares `deidentified`, `no_phi`, or `unknown`.
- Run a metadata-only PHI/PII scan on denial workflow text and return only
  finding type, line, and column metadata. Matched values are never returned by
  the scanner.
- Add a compliance task and quality-check blocker when PHI/PII-like patterns
  are detected so exports and submissions remain blocked until minimum
  necessary PHI scope is reviewed.
- Include a PHI scan summary in Markdown/DOCX/PDF export content without
  including matched values.
- Reject retrieval-source ingestion when a source is declared `no_phi` but the
  scanner finds PHI/PII-like content.
- Require `privacy_review_completed=true` before ingesting a source declared
  `deidentified` when scanner findings exist.
- Prevent model-improvement opt-in unless source status is `no_phi` or
  `deidentified`, and require completed privacy review when findings exist.
- Add corpus manifest schemas with the required fields: `source_id`,
  `document_id`, `pair_id`, `source_type`, `document_role`,
  `source_url_or_path`, `checksum`, `phi_status`,
  `deidentification_status`, `license_status`, `review_status`,
  `residual_risk_score`, `training_eligible`, `split`, and
  `micro_skill_ids`.
- Add the required document intake states: `raw_quarantined`,
  `machine_deidentified`, `qa_failed`, `human_review_required`,
  `privacy_review_passed`, `expert_determination_required`, and
  `training_eligible`.
- Add rule-based de-identification for patient, member, claim, authorization,
  date, phone, email, SSN, and address patterns using stable placeholders such
  as `[PATIENT_1]`, `[MEMBER_ID_1]`, `[CLAIM_ID_1]`, `[AUTH_ID_1]`,
  and `[DATE_SERVICE_1]`.
- Add residual-risk scoring and training-export blockers for raw PHI,
  missing privacy review, unresolved license status, missing split,
  missing micro-skill coverage, and excessive residual risk.
- Add local-only contextual re-identification risk review for rare or unique
  narrative facts without external API calls. Corpus de-identification and
  document-surface inspection now return metadata-only contextual findings for
  age-over-89 cues, rare condition/device facts, small geography or unique
  provider cues, exact unlabeled timelines, unusual dollar amounts, and public
  uniqueness cues. These findings do not include matched values and force
  `expert_determination_required` plus human review before training
  eligibility.
- Add a structured manual corpus review-decision API at
  `/api/v1/denial-workflow/corpus/review-decision`. The request accepts only
  manifest/review metadata, not raw document text, and records reviewer ID,
  review method, generic findings, residual-risk score, review completion
  flags, expert-determination status, and training decision. The service
  blocks `approve_for_training` unless privacy review, license review,
  residual-risk review, allowed license status, safe PHI status, train/valid/test
  split, micro-skill coverage, reviewer note, and any required expert
  determination all pass, then reruns manifest validation before returning a
  training-eligible record.
- Add a metadata-only corpus review queue at
  `/api/v1/denial-workflow/corpus/review-queue`. The response summarizes
  manifest records by source type, document role, review state, PHI status,
  residual-risk score, paired-denial/appeal completeness, production-corpus
  candidacy, blocker codes, and next action while redacting document text,
  source paths, checksums, matched values, approval references, and secrets.
  The Denial Workflow admin UI displays this queue so corpus reviewers can see
  which manifest records need license review, expert determination, pairing,
  production source classification, or metadata-only review decisions before
  import/export.
- Wire the Denial Workflow admin corpus-import UI through the metadata-only
  review-decision API. The UI now builds a non-training-eligible candidate
  manifest record, sends privacy, license, residual-risk, split, micro-skill,
  and expert-determination attestations to the backend, displays backend
  blockers, and calls the approved-import endpoint only with the
  backend-returned training-approved record.
- Add a production semantic/vector-readiness gate for retrieval sources. The
  backend now reports embedding backend, embedding model, vector backend,
  hash-fallback status, active chunk counts, stored embedding-model counts, and
  reindex blockers without returning source text, vector values, credentials,
  or PHI. The default local hash embedding path remains safe for development
  but blocks PHIplan production readiness until a real semantic embedding
  backend/vector store is configured and stored chunks are reindexed.
- Add a retrieval embedding provider boundary so production semantic embedding
  adapters can be injected without hardcoding service URLs, credentials, raw
  source text, or vector values in source control. `app/services/retrieval.py`
  now defines metadata-bearing embedding results and a default
  `HashEmbeddingProvider`; `RetrievalStoreService` stores encrypted embedding
  metadata from the configured provider, and Denial Workflow retrieval uses the
  store provider for query embeddings when one is supplied. The checked-in
  provider remains the development hash fallback by default, so production
  retrieval remains blocked until a private approved semantic provider,
  production vector backend, reindex evidence, health check, and quality smoke
  evidence are configured outside source control.
- Add a metadata-only retrieval embedding reindex operation at
  `/api/v1/denial-workflow/sources/reindex-embeddings`. The operation is
  admin-only, defaults to dry-run mode, returns aggregate counts and safe
  provider labels only, refuses non-dry-run writes with the checked-in
  development hash provider, and keeps raw source text, vector values,
  provider endpoints, PHI, secrets, and production document content out of
  responses and audit details. Production write reindexing still requires a
  privately injected approved semantic provider and private vector backend
  evidence outside source control.
- Add a retrieval-vector startup configuration guard in
  `health-ai-medical-billing-medical-corporations-20260414_180528/app/utils/retrieval_vector_config.py`.
  Startup now validates that production environments are not using the
  development hash embedding backend, unapproved embedding models, local
  metadata vector storage, hash fallback, or backend settings that contain URLs
  or credentials. The guard logs and returns only safe booleans, blocker
  counts, and blocker codes; it does not emit source text, vector values,
  embedding service URLs, credentials, PHI, or production document content.
  `llm-distill/scripts/run_phi_plan_production_readiness_audit.py` now mirrors
  these startup blockers and redacts URL/credential-shaped vector backend
  settings in production-readiness evidence.
- Add a boolean-only retrieval vector backend evidence template at
  `llm-distill/data/retrieval_vector_backend/vector_backend_evidence.template.json`
  and a validator at
  `llm-distill/scripts/validate_retrieval_vector_backend.py`. The checked-in
  report at `llm-distill/evals/reports/retrieval_vector_backend_report.json`
  has `safe_to_review=true` and `vector_backend_ready=false`; it blocks until
  semantic embedding configuration, approved embedding model selection,
  production vector backend configuration, hash-fallback disablement for
  production, chunk reindexing, vector backend health, and quality smoke checks
  are complete. Local governance checks, backup/restore review, and
  rollback/disable-path review are now attested without storing source text,
  vector values, credentials, PHI, secrets, or production document content.
  The validator now also verifies the source-controlled private semantic
  provider loader at
  `health-ai-medical-billing-medical-corporations-20260414_180528/app/services/retrieval_semantic_provider.py`
  exists with provider factory, private endpoint/token redaction, HTTPS or
  loopback safety, dimension checks, and hash fallback markers without
  emitting loader text, endpoint values, tokens, source text, or vector values.
  The validator now also verifies the source-controlled operator runbook at
  `llm-distill/docs/retrieval-vector-backend-runbook.md` exists with required
  private-configuration, no-secret/no-PHI, reindex, rollback, and
  `vector_backend_ready=false` markers without emitting the runbook text.
  The validator now also verifies the source-controlled reindex checklist at
  `llm-distill/docs/retrieval-vector-reindex-checklist.md` exists with
  required approved-model, production-vector-backend, hash-fallback-disable,
  application-reindex-operation, active-chunk reindex, stored-hash absence,
  reindex job, reindex audit, health-check, quality-smoke, boolean-only,
  no-raw-source-text, and `vector_backend_ready=false` markers without
  emitting the checklist text.
  The validator now also verifies the source-controlled runtime smoke checklist
  at `llm-distill/docs/retrieval-vector-runtime-smoke-checklist.md` exists
  with required approved-model, production-vector-backend,
  hash-fallback-disable, active-chunk reindex, stored-hash absence,
  vector-health, retrieval-quality, backup-restore, rollback/disable,
  metadata-only audit, boolean-only, no-raw-source-text, no-raw-vector-value,
  no-service-URL, and `vector_backend_ready=false` markers without emitting the
  checklist text. Production vector backend readiness still blocks until
  private semantic backend configuration, production vector store configuration,
  reindex completion, vector health checks, and retrieval quality smoke checks
  are actually complete outside source control.
  The validator now also verifies
  `llm-distill/scripts/render_retrieval_vector_runtime_private_evidence.py`,
  a source-controlled private runtime evidence renderer that writes only to a
  private path, requires health, quality-smoke, reindex, backup, rollback, and
  no-raw-value attestations for approved mode, and reports redacted booleans
  without emitting private evidence references, source text, vector values,
  endpoint values, credentials, PHI, or production document content.
  The retrieval-vector path now also includes
  `llm-distill/scripts/render_retrieval_vector_private_env.py`, a renderer for
  the final private retrieval/vector runtime environment file. It refuses
  output inside source control, requires explicit semantic backend, embedding
  model approval, production vector backend, hash-fallback disablement,
  reindex completion, vector health, retrieval quality smoke, rollback, and
  no-raw-value attestations before approved mode, reads private backend/model/
  vector labels from environment variables, verifies the configured
  retrieval/vector backend evidence report is safe, ready, and unblocked before
  writing enabled settings, writes private output with `0600` permissions, and
  prints only redacted booleans/counts. This prepares the
  private semantic retrieval configuration handoff without storing provider
  labels, model names, vector-store labels, service URLs, credentials, source
  text, vector values, PHI, or production document content in source control.
- Add corpus endpoints under `/api/v1/denial-workflow/corpus` for status,
  manifest validation, machine de-identification, manual review decision, and
  import of approved de-identified documents into the encrypted retrieval store.
- Add a frontend corpus readiness panel showing manifest availability,
  training-eligible counts, blocked counts, missing categories, and export
  readiness.
- Add a starter versioned corpus manifest at
  `llm-distill/data/corpus/manifest.json`.
- Add a manifest-aware corpus SFT exporter at
  `llm-distill/scripts/export_corpus_sft_data.py` that exports only
  `training_eligible=true` de-identified/reviewed denial plus appeal pairs,
  verifies local checksums, requires zero PHI/PII scanner findings in source
  and generated rows, preserves `pair_id` relationships in row metadata,
  reports MS01-MS12 and payer/denial/route/appeal-level/outcome coverage, and
  writes `training_allowed=false` with blockers unless train/valid/test splits
  and required coverage gates pass.
- Extend the MLX fine-tune preflight so approved de-identified corpus SFT
  manifests can pass the data-tier/PHI-status gate without weakening the
  existing `training_allowed`, split-file, JSON-contract, draft-status, and
  PHI-scan checks.
- Extend the top-level distillation readiness audit so the current synthetic
  adapter evidence is no longer enough for production release/default
  readiness; the audit now blocks until the safe corpus manifest has at least
  three approved training-eligible denial/appeal pairs and a guarded corpus SFT
  export exists with complete splits and coverage.
- Add document-surface PHI/PII inspection for corpus candidates under
  `/api/v1/denial-workflow/corpus/inspect-document`, covering source filename,
  visible text, hidden PDF text, OCR text, scanned-page text, inferred or
  supplied header/footer text, metadata, barcode/QR text, and attachment
  filenames. The endpoint returns only metadata findings, surface names,
  counts, residual-risk status, and review blockers; matched values are not
  returned.
- Add three synthetic no-PHI denial/appeal corpus pairs under
  `llm-distill/data/corpus/synthetic_pairs/` and promote
  `llm-distill/data/corpus/manifest.json` to version `1.1` with six
  checksum-verified, training-eligible records across train/valid/test splits,
  complete MS01-MS12 coverage, payer/denial/route/outcome coverage, and
  `training_approved` synthetic fixture review metadata.
- Run the guarded corpus SFT export to
  `llm-distill/data/distillation/mlx_sft_corpus/`, producing train/valid/test
  chat JSONL splits plus a manifest with `training_allowed=true`,
  `pair_count=3`, zero PHI/PII scanner findings, preserved `pair_id`
  relationships, and complete micro-skill coverage.
- Regenerate the top-level distillation readiness audit so corpus manifest and
  corpus SFT export gates are now ready. The audit now reports
  `release_ready=true` for the current evidence while preserving next actions
  that keep `CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false` until Raphael approves
  production runtime/default cutover.
- Add Denial Workflow UI controls for encrypted retrieval-source creation,
  explicit privacy-review attestation, model-improvement opt-in gating through
  the existing backend validation, stored source visibility, document-surface
  inspection, machine de-identification, and approved de-identified corpus
  import. The import button stays disabled until surface inspection has no
  blocking findings, machine de-identification has zero scanner findings,
  residual risk is within threshold, required privacy/license/residual-risk and
  expert-determination attestations are checked, a train/valid/test split and
  micro-skill coverage are present, and the backend review-decision endpoint
  returns an approved training record.
- Add role-scoped governance for encrypted retrieval-source documents with
  `owner`, `billing_team`, and `admin_only` access scopes; list/search and
  denial workflow retrieval now filter persisted chunks by the current user
  role before source snippets can be returned.
- Add retrieval-source retention and soft-deletion workflow fields,
  `POST /api/v1/denial-workflow/sources/{source_id}/delete`, and a governance
  summary endpoint that reports active, expired-active, retired, and
  no-expiration counts without exposing source text or matched PHI/PII values.
- Add an admin-only retrieval-document audit dashboard endpoint plus Denial
  Workflow admin UI panels for access scope, retention date entry, soft-retire
  actions, governance counts, and safe per-document audit event metadata.
- Add disabled-by-default user-data model-improvement compliance gates requiring
  runtime legal approval, BAA confirmation, consent notice version, approval
  reference, and per-request legal/BAA/consent attestations before
  `user_data_opt_in_for_model_improvement` can be accepted. The Denial
  Workflow admin UI now displays readiness blockers, and approved corpus import
  no longer silently opts user data into model improvement. FastAPI startup now
  also runs a metadata-only production guard that fails fast if user-data model
  improvement is enabled before legal approval, BAA confirmation, consent
  notice configuration, approval reference configuration, and a ready safe
  evidence report are present.
- Connect document-surface inspection to the automated `/api/v1/claims/upload-document`
  file-ingestion workflow. Uploaded PDF/image/text documents now inspect source
  filename, MIME type, extracted visible or OCR text, and safe processing/OCR
  metadata, persist only redacted inspection summaries with the analyzed claim,
  include safe surface counts/status in audit details, and show a surface
  inspection panel in the Claims UI. The route now rejects unsupported, empty,
  and over-10 MB files with structured safe error details before file
  processing, PDF parsing, OCR, document analysis, denial workflow generation,
  database writes, or audit-log creation; upload reads are bounded to the
  configured size limit plus one byte and disguised inner extension chains such
  as script suffixes under a supported final suffix are rejected before any file
  bytes are read. Image uploads now apply an explicit Pillow pixel-count ceiling
  and treat decompression-bomb warnings as safe processing failures before
  resize/compression work proceeds.
- Add a guarded `/api/v1/claims/batch-upload` EDI 837 workflow that accepts
  only `.edi` or `.txt` files within the 10 MB limit, runs metadata-only
  document-surface inspection over the source filename, MIME type, EDI text, and
  parser metadata, returns structured per-claim parser results with validation
  issues, and logs only safe counters/booleans without raw segment payloads.
  The endpoint now also estimates aggregate segment and claim-loop counts
  before constructing full parser claim objects, rejecting excessive batches
  with metadata-only `pre_parse_batch_validation` errors so oversized uploads
  fail before full EDI parsing, document-surface inspection, database writes,
  or audit-log creation. EDI batch uploads now also use bounded reads and block
  disguised inner extension chains before reading uploaded bytes.
  EDI 837 parser errors and validation issues now carry safe structured
  `error_code`, `parser_stage`, `field`, `segment_index`, `segment_id`, and
  `safe_context` metadata so rejected batch uploads and parser warnings can be
  triaged without raw filenames, raw EDI text, raw segment payloads, PHI, or
  production claim content.
- Extend the same safe structured parser context to the EDI 835 remittance
  parser. `EDI835ParserError` and `EDI835ValidationIssue` now carry
  `error_code`, `parser_stage`, field, claim, segment ID/index, and
  `safe_context` metadata for CLP/CAS payment and adjustment parsing without
  logging raw remittance text, raw segment payloads, PHI, secrets, or
  production payment content.
- Add a guarded `/api/v1/claims/remittance-upload` EDI 835 workflow for
  billing-role users. The endpoint accepts only `.835`, `.edi`, or `.txt`
  files within the 10 MB limit, blocks disguised inner extension chains before
  reading uploaded bytes, parses CLP/CAS/LQ remittance content through the
  structured EDI 835 parser, runs metadata-only document-surface inspection,
  returns payment/adjustment/remark summaries with patient and payer control
  numbers represented only as presence booleans, and logs only safe aggregate
  counters without raw filenames, remittance text, segment payloads, patient
  identifiers, payer control numbers, PHI, secrets, or production payment
  content.
- Harden claim document-analysis JSON parsing and prediction circuit-breaker
  recovery. `app/api/v1/claims.py` now routes analysis JSON extraction through
  a shared helper with specific `json.JSONDecodeError` handling and
  metadata-only structured warning context instead of bare `except:` blocks,
  while `app/services/prediction.py` uses `total_seconds()` so an open circuit
  can recover after the configured timeout even when the outage crosses a day
  boundary.
- Add metadata-only prediction threshold, fairness, and explainability
  telemetry. Claim denial prediction now ties denial reasons to driver
  categories and source-field families rather than raw claim values, labels the
  high-risk threshold as a human-review routing threshold instead of an
  auto-denial rule, and provides a demographic-parity metric utility for
  approved batch evaluations that returns only group indexes, counts, rates,
  and disparity status without raw demographic values or claim content.
  Production threshold calibration and continuous fairness monitoring now have
  a separate boolean-only evidence template and validator at
  `llm-distill/data/prediction_fairness_evidence/fairness_monitoring_evidence.template.json`
  and `llm-distill/scripts/validate_prediction_fairness_evidence.py`; the
  evidence now references
  `llm-distill/docs/prediction-fairness-model-card.md` and
  `llm-distill/docs/prediction-fairness-monitoring-runbook.md`, and the
  validator verifies that the model card, source-controlled monitoring
  runbook, source-controlled calibration checklist at
  `llm-distill/docs/prediction-fairness-calibration-checklist.md`, and
  source-controlled monitoring validation checklist at
  `llm-distill/docs/prediction-fairness-monitoring-validation-checklist.md`
  plus source-controlled legal/privacy checklist at
  `llm-distill/docs/prediction-fairness-legal-privacy-checklist.md`
  exist with required safety markers for human-review-only threshold use, no
  auto-denial threshold, approved outcome data, sample size, calibration,
  continuous monitoring, demographic grouping review, alert ownership, latest
  run evidence, legal/privacy review, approval references outside source
  control, rollback, boolean-only evidence, no raw demographic/outcome values,
  no legal/BAA/consent document text, and
  `prediction_fairness_monitoring_ready=false`. The fairness evidence path
  now also includes
  `llm-distill/scripts/render_prediction_fairness_private_evidence.py`, a
  renderer for the final private boolean-only prediction-fairness evidence
  file. It refuses output inside source control, requires explicit
  outcome-data, sample-size, calibration, threshold-review, human-review,
  demographic-grouping, continuous-monitoring, disparity-threshold,
  alert-owner, latest-run, legal/privacy, rollback, metadata-only audit, and
  no-raw-value attestations before approved mode, reads private governance
  references from environment variables, writes private output with `0600`
  permissions, and prints only redacted booleans/counts. This prepares the
  private fairness-evidence handoff without storing references, raw
  demographic values, production outcome rows, claim content, legal records, or
  approval documents in source control. The PHIplan
  production-readiness audit blocks
  on that report until approved outcome data, monitoring ownership, latest run
  evidence, and legal/privacy governance are complete outside source control.
  FastAPI startup
  now also runs a metadata-only prediction fairness guard that fails fast in production while
  `PREDICTION_FAIRNESS_EVIDENCE_REPORT` is missing, unsafe, blocked, or not
  ready, without logging the report path, raw evidence, raw demographic values,
  production outcome rows, PHI, secrets, or approval-reference values.
  The manual production-gate packet now carries the local model-card sub-gate
  forward as boolean evidence: `model_card_updated=true` and
  `model_card_required_markers_verified=true`, while still blocking production
  fairness readiness on approved outcome data, sample size, calibration,
  monitoring, alerting, latest-run, and legal/privacy review attestations.
- Add bounded retry/backoff and slow-request observability to the NVIDIA NIM
  client used by document analysis, claim prediction, appeal generation, and
  OCR. `app/services/nvidia.py` retries connect/timeout failures and transient
  HTTP status codes with exponential backoff, logs retry/error/slow-request
  metadata with provider, endpoint, model, attempt counts, status or exception
  type, and safe no-raw-content flags, and avoids logging prompts, OCR bytes,
  raw responses, authorization headers, API keys, PHI, or production document
  content.
- Add metadata-only NVIDIA startup configuration validation for the current
  default runtime path. Startup now validates whether NVIDIA is required by the
  configured LLM/OCR providers, confirms the API key is present, checks HTTPS
  base URL shape, detects embedded URL credentials, confirms chat/OCR model
  names and positive timeout values, logs only safe booleans/counts/blocker
  codes, and fails fast only in production when blockers remain. The validator
  never logs API keys, authorization headers, prompts, OCR bytes, raw
  responses, PHI, or document content.
- Add production packaging scaffolding for the conservative NVIDIA-default
  deployment path. The backend image now uses a multi-stage Python build with a
  non-root runtime user and safe `/health` health check, the production
  frontend image builds static Vite assets and serves them through nginx with
  `/healthz`, the development compose frontend has a local health check, and
  `docker-compose.production.yml` requires production secrets and approval
  evidence through environment variables instead of storing values in source
  control. The production compose API environment now also forwards the exact
  startup-guard settings consumed by `app/core/config.py` for student default
  cutover, student runtime auto-launch, user-data model improvement,
  prediction fairness evidence, and retrieval vector backend readiness with
  conservative defaults, and removes
  the unconsumed `CLAIMGUARD_ALLOW_MODEL_IMPROVEMENT` alias. The PHIplan
  production-readiness audit now checks this production compose environment as
  a current-state gate and will block `safe_current_state` if required guard
  variables are missing, self-reference the wrong runtime setting, use
  non-conservative defaults, or reintroduce the unconsumed alias. FastAPI
  startup also treats `CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH=true` as a
  student-runtime request and fails fast in production unless release,
  Raphael-approval, approval-reference, supervised-runtime, runtime-health, and
  rollback gates are ready. This does not enable student-default cutover,
  student auto-launch, user-data model improvement, or production
  semantic/vector retrieval.
- Add an admin-only Prometheus metrics endpoint at
  `/api/v1/monitoring/metrics`. The endpoint emits aggregate counts and
  boolean runtime flags only, includes a no-PHI context metric, requires admin
  JWT authorization through the existing middleware/dependency stack, and does
  not expose patient identifiers, provider identifiers, claim IDs, filenames,
  payer names, prompts, raw document text, source text, vectors, credentials,
  or approval references. It now includes PHIplan production-gate gauges for
  student default/auto-launch/cutover approval state, non-secret approval
  reference presence, supervised runtime, rollback-to-NVIDIA, user-data model
  improvement legal/BAA/consent/reference state, prediction-fairness evidence
  report configuration, retrieval semantic/vector safety flags, hash-fallback
  state, and conservative runtime defaults; all gate values are emitted only as
  `0` or `1`. The PHIplan production-readiness audit now also verifies this
  monitoring surface as `monitoring_gate_metrics_ready` by checking required
  source metric names, runtime Prometheus output coverage, and sentinel
  approval/reference/report values are not emitted.
- Add an admin-only PHIplan readiness endpoint at
  `/api/v1/monitoring/phi-plan-readiness`. The endpoint reads the checked-in
  production-readiness report and returns sanitized readiness counts,
  requirement IDs, statuses, safe blocker/warning tokens, and no-PHI context
  flags only. It requires admin JWT authorization and omits raw report paths,
  raw evidence objects, next-action text, approval references, PHI, document
  text, source text, vectors, and secrets. The PHIplan production-readiness
  audit now verifies this monitoring surface as
  `monitoring_readiness_endpoint_ready` by checking endpoint source markers,
  runtime payload keys, safe-context flags, and sentinel raw-value
  non-emission.
- Add metadata-only denial prediction accuracy tracking at
  `/api/v1/analytics/prediction-accuracy`. The endpoint uses existing claim
  outcome status and denial-prediction score fields to produce aggregate
  time-bucketed confusion-matrix metrics, accuracy, precision, recall, false
  positive rate, actual denial rate, predicted denial rate, evaluated-claim
  counts, and excluded-claim counts. It only evaluates finalized outcome
  statuses, excludes pending/in-flight claims, logs safe counters only, and
  does not return claim IDs, patient/provider identifiers, filenames, payer
  names, denial text, document text, prompts, PHI, secrets, or production
  document content.
- Add Sprint 6.2 operational documentation under
  `health-ai-medical-billing-medical-corporations-20260414_180528/docs/`.
  `docs/api-authentication.md` documents bearer-token auth, public routes,
  roles, route-family authorization requirements, and safe token handling.
  `docs/edi-formats.md` documents current EDI 837 batch-upload constraints,
  EDI 835 parser utility behavior, parser-safe error context, and future EDI
  endpoint requirements. `docs/deployment-guide.md` documents local and
  production compose paths, required private environment categories, student
  default boundaries, validation commands, and rollback steps while keeping
  PHIplan production readiness blocked until external/manual gates clear.
  These docs add no secrets, real EDI files, PHI, raw production documents, or
  production-ready claims.
- Add frontend session-timeout enforcement for browser auth state. Login now
  stores the backend `expires_in` value as an absolute session expiry,
  records last-activity metadata in session storage, and enforces inactivity
  logout plus login redirect before attaching bearer tokens to new API
  requests. Activity updates never rewrite the absolute expiry, so the
  existing 30-minute JWT lifetime is not extended.
- Add operational backup and disaster recovery documentation at
  `health-ai-medical-billing-medical-corporations-20260414_180528/docs/backup-disaster-recovery.md`.
  The runbook documents automated PostgreSQL backup procedure, off-repository
  encrypted storage rules, metadata-only backup verification, isolated restore
  testing, disaster recovery sequence, recovery objectives, and pre-production
  evidence checks without adding backup artifacts, credentials, PHI, production
  EDI files, raw documents, or production data to the repository.
- Add public GitHub documentation drift validation with
  `llm-distill/scripts/validate_public_repo_docs.py`. The validator checks that
  `README.md` links to
  `docs/technical-llm-distillation-analysis.md`, that the technical breakdown
  includes aggregate LLM distillation statistics and tool references from
  checked-in evidence reports, that Raphael Malikian attribution remains
  present, and that public docs do not expose raw local paths, secret-shaped
  values, PHI-like identifiers, source text, prompts, approval references, or
  production document content.
- Add local AI safety guardrails at
  `health-ai-medical-billing-medical-corporations-20260414_180528/app/services/ai_safety.py`.
  Document analysis now treats denial-letter text as untrusted source evidence,
  detects prompt-injection-like instructions with metadata-only categories,
  returns explicit `human_review_required=true` and `filing_ready=false`
  guardrail metadata, replaces unsupported approval/payment/deadline/no-review
  certainty with human-review-required output, and uses deterministic extracted
  field fallback when NVIDIA analysis is unavailable or empty. Denial workflow
  analysis now adds prompt-injection blocker tasks, warnings, quality checks,
  and model metadata while keeping deterministic workflow controls authoritative
  when optional LLM review is unavailable or fails the hallucination guardrail.
  The guardrails do not log raw prompts, raw document text, raw model responses,
  exception messages, credentials, PHI, or production document content.
- Add claim state machine enforcement at
  `health-ai-medical-billing-medical-corporations-20260414_180528/app/services/claim_state.py`
  and `/api/v1/claims/{claim_id}/status`. New claim-document analysis records
  now use canonical `draft` status instead of the legacy `analyzed` status,
  status updates are limited to canonical states and allowed transitions, and
  invalid transitions return structured safe errors with allowed next statuses,
  blocker codes, and no raw claim data, raw document text, transition-note
  text, patient identifiers, or provider identifiers. Legacy reporting aliases
  remain readable for existing analytics/history filters, but are not accepted
  as write targets.
- Add database-backed claim status constraints in
  `health-ai-medical-billing-medical-corporations-20260414_180528/app/models/__init__.py`
  and
  `health-ai-medical-billing-medical-corporations-20260414_180528/alembic/versions/20260531_004528_add_claim_status_constraint.py`.
  The `claims.status` column is now non-null and constrained to canonical
  claim states, and the migration normalizes known legacy readable statuses
  before adding the check constraint. This prevents direct database writes from
  bypassing the application state-machine contract.
- Add record-level soft-delete support and query indexes in
  `health-ai-medical-billing-medical-corporations-20260414_180528/app/models/__init__.py`,
  `health-ai-medical-billing-medical-corporations-20260414_180528/app/api/v1/claims.py`,
  `health-ai-medical-billing-medical-corporations-20260414_180528/app/api/v1/patients.py`,
  and
  `health-ai-medical-billing-medical-corporations-20260414_180528/alembic/versions/20260531_033507_add_claim_patient_soft_delete_indexes.py`.
  Active claim and patient reads now filter `deleted_at IS NULL`, admin delete
  actions set metadata-only soft-delete fields instead of hard-deleting rows,
  admin restore endpoints clear those fields, and new indexes cover
  soft-delete lookups plus `claims.submission_date` and
  `claims.denial_prediction`. Audit details record only IDs, booleans, counts,
  status labels, and no raw patient or claim content.
- Add request ID tracking middleware across the FastAPI app. Incoming safe
  `X-Request-ID` values are preserved, unsafe or missing values are replaced
  with generated opaque IDs, the normalized value is attached to
  `request.state.request_id`, exposed through a context variable for structured
  logging, and returned on successful and authentication-failure responses
  without including PHI, credentials, raw documents, prompts, or user
  identifiers.
- Extend safe structured failure context to non-EDI claim-document pipelines.
  Claim document upload failures now return and log metadata-only details for
  file-processing failures, post-processing size rejection, PDF text extraction
  failures, and empty text extraction, including `error_code`,
  `processing_stage`, safe size/type metadata, and explicit no-raw-content
  flags without raw filenames, raw document text, raw file bytes, raw parser
  errors, or exception messages. Batch document analysis failures now log
  metadata-only per-document validation and processing failures with document
  index, text length, document type, exception type, and no raw document text,
  prompts, model responses, or exception messages.
- Add a shared structured API error-response layer. FastAPI HTTP errors,
  request-validation failures, rate-limit failures, unhandled exceptions, and
  auth-middleware rejections now emit `error_code`, `message`, `status_code`,
  `detail`, request ID, and safe no-raw-content flags. Validation responses
  strip raw request input, unhandled exception responses suppress raw exception
  text, and structured endpoint-level details are preserved for existing EDI
  and document-upload errors.
- Add legacy claim-document governance for stored `Claim.document_text`
  records: access scopes, retention timestamps, soft-retire metadata,
  metadata-only governance summary, admin audit dashboard responses with
  whitelisted details only, and Dashboard UI status for restricted, retired, or
  expired claim documents. Claim list/detail responses no longer return raw
  document text, upload surface IDs no longer derive from filenames, and new
  upload audit details avoid raw filenames.
- Add a supervised student-default cutover gate. `CLAIMGUARD_STUDENT_USE_BY_DEFAULT`
  is only effective when release evidence is ready, the MLX runtime is checked
  and online, `CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=true`,
  `CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE` is configured,
  `CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=true`, and
  `CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA=false`. The status API, health check,
  Denial Workflow UI, distillation readiness audit, and startup guard now
  surface these blockers; production startup fails fast if student default use
  is requested without those gates, and the rollback flag keeps
  deterministic/NVIDIA fallback authoritative without code changes.
- Add PHI-clean public/government corpus source notes under
  `llm-distill/data/corpus/public_sources/` and promote
  `llm-distill/data/corpus/manifest.json` to version `1.3` with seven
  non-training `public_government_source` `rule_source` records covering all
  seven entries in `llm-distill/data/source_registry.json`: HealthCare.gov
  internal appeals, HealthCare.gov external review, DOL EBSA health benefit
  claims/appeals, CMS Medicare fee-for-service redetermination, CMS Medicare
  Advantage reconsideration, 42 CFR Part 438 Subpart F, and HHS HIPAA minimum
  necessary guidance. These records expand source coverage for
  retrieval/governance context while remaining excluded from MLX SFT export
  because they are not paired denial/appeal training examples.
- Add `llm-distill/scripts/audit_public_source_notes.py` and checked-in
  evidence at
  `llm-distill/evals/reports/public_source_note_coverage_report.json` to prove
  every no-PHI public/government registry source has a local metadata-only
  source note, zero PHI/PII findings, checksum coverage, required safety/use
  markers, and `training_eligible=false`.
- Run the guarded MLX fine-tune preflight against
  `llm-distill/data/distillation/mlx_sft_corpus/manifest.json` and write
  `llm-distill/evals/reports/mlx_finetune_corpus_preflight_report.json` with
  `ready=true`, zero split-file PHI/PII findings, and no training attempted.
  The same MLX fine-tune runner now blocks `--run` for corpus-derived data
  tiers unless `llm-distill/evals/reports/production_corpus_evidence_report.json`
  is safe to review and `production_corpus_ready=true`, preventing adapter
  writes from synthetic-only or otherwise blocked production corpus evidence.
- Add an automated file-ingestion surface audit at
  `llm-distill/scripts/audit_file_ingestion_surfaces.py` with checked-in
  evidence at
  `llm-distill/evals/reports/file_ingestion_surface_audit_report.json`. The
  audit inventories FastAPI `UploadFile`/`File` endpoints and blocks release
  evidence unless each automated file-ingestion endpoint is registered with
  metadata-only document-surface inspection, access-governance, and safe audit
  markers. The top-level distillation readiness audit now includes this report
  as a safety requirement so future upload/document repositories cannot be
  silently added without extending coverage.
- Wire the file-ingestion surface audit into
  `llm-distill/scripts/run_phi_plan_production_readiness_audit.py` as a
  top-level PHIplan production-readiness gate. The refreshed PHIplan report now
  records `file_ingestion_surface_audit_ready` as ready with three discovered,
  three registered, and zero unregistered upload surfaces, and would block
  `safe_current_state` if an UploadFile/File endpoint is added without
  metadata-only PHI surface inspection, governance, and safe audit markers.
- Add PHI access-audit hardening for patient, claim, analytics, and appeal
  routes. `app/utils/audit.py` now sanitizes audit details at the logging
  boundary by redacting sensitive keys and PHI/PII-like values, while route
  audit events record metadata-only IDs, counts, flags, status values, and
  result sizes instead of raw MRNs, document text, filenames, appeal letters,
  prompts, or matched identifier values.
- Generate 900 synthetic denial/appeal training pairs under
  `llm-distill/data/corpus/generated_synthetic_pairs/` using deterministic
  no-PHI templates. The generator documents format family, layout profile,
  typography profile, and length profile per letter, keeps denial notices
  consistent with the existing synthetic corpus style, keeps appeal drafts
  marked `draft_for_human_review`, and produces
  `manifest_synthetic_900.json` plus `generation_report.json` with zero
  PHI/PII scan findings.
- Add rendered HTML companions for the same 900 synthetic denial/appeal pairs
  under `llm-distill/data/corpus/generated_synthetic_pairs/rendered_html/`.
  The renderer preserves the same no-PHI text while applying actual CSS font
  stacks and layout wrappers, and writes `visual_manifest_synthetic_900.json`
  plus `visual_render_report.json` with 1,800 rendered HTML files, eight font
  family variants, twelve layout variants, eight typography variants, and zero
  PHI/PII findings.
- Add a full generated-corpus format and variation audit at
  `llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py` with checked-in
  evidence at
  `llm-distill/evals/reports/synthetic_denial_appeal_corpus_format_audit_report.json`.
  The audit verifies every generated denial/appeal file has the required
  training/draft markers, manifest-matching format/layout/typography/length
  metadata, unique text content, complete pair links, documented length
  variation, README documentation, rendered HTML font/layout coverage,
  role-by-profile coverage for denial and appeal letters, split-by-profile
  coverage across train/valid/test, appeal-draft quality controls, and zero
  PHI/PII scan findings. The appeal contract requires draft/human-review/
  not-filing-ready markers, source-grounding language, deadline/citation
  verification language, minimum necessary PHI scope, route and appeal-level
  alignment, denial-type alignment, and zero unsupported legal, deadline, or
  approval-guarantee claims.
- Add a generated-denial document-analysis extraction audit at
  `llm-distill/scripts/audit_synthetic_document_analysis_extraction.py` with
  checked-in evidence at
  `llm-distill/evals/reports/synthetic_document_analysis_extraction_report.json`.
  The audit runs the local `DocumentAnalysisService` field extractor over all
  900 generated synthetic denial notices and requires zero missing payer names,
  denial rationales, billed amounts, procedure codes, PHI findings, unexpected
  patient-name extraction, or synthetic coverage-placeholder extraction before
  the corpus can be used as denial-document stress fixtures.
- Add authenticated API smoke coverage for the generated mock-denial corpus at
  `health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_mock_denial_letter_api_smoke.py`.
  The test verifies the checked-in visual manifest still documents 1,800
  rendered no-PHI files, including 900 denial notices and 900 appeal drafts
  across eight font stacks, twelve layout wrappers, eight typography profiles,
  train/valid/test splits, and varied document lengths. It then posts twelve
  representative rendered denial notices, one per layout profile, through the
  authenticated `/api/v1/claims/upload-document` route with a billing-role JWT,
  mocked local analyzer/workflow calls, metadata-only surface inspection, and
  persisted `billing_team` document access scope.
- Export the generated 900-pair corpus through the guarded MLX SFT pipeline to
  `llm-distill/data/distillation/mlx_sft_synthetic_900/`, producing 720 train,
  90 valid, and 90 test rows with `training_allowed=true`, no blockers, complete
  MS01-MS12 coverage, and preserved `pair_id` relationships.
- Harden the MLX fine-tune preflight so `mlx_lm.lora` must pass an import/help
  runtime check before training can run. Current synthetic-900 run evidence at
  `llm-distill/evals/reports/mlx_finetune_synthetic_900_run_report.json`
  shows the data is valid but training was not attempted because this session
  cannot access a Metal device; no synthetic-900 adapter files were written.
- Extend the top-level distillation readiness audit so the generated 900-pair
  stress corpus is enforced as current evidence. The audit now requires the
  synthetic corpus generation report, manifest, 1,800 letter files, file-level
  format/variation audit, format/layout/typography/length coverage, app
  document-analysis extraction coverage for generated denials, zero PHI findings
  across the letter tree, the 900-row SFT export, and the guarded synthetic-900
  MLX run report.
  The current audit remains unblocked while recording the synthetic-900 MLX
  no-Metal condition as a warning instead of training or writing placeholder
  adapter weights.
- Add a separate PHIplan production-readiness audit at
  `llm-distill/scripts/run_phi_plan_production_readiness_audit.py` with
  checked-in evidence at
  `llm-distill/evals/reports/phi_plan_production_readiness_report.json`. The
  report intentionally separates the conservative current state from production
  readiness: current evidence has `safe_current_state=true` because NVIDIA
  remains the default and user-data model improvement remains disabled, while
  `production_ready=false` until student-default cutover approval, legal/BAA/
  consent model-improvement approval, production semantic/vector retrieval
  backend configuration, non-synthetic approved denial/appeal training pairs,
  and production threshold/fairness monitoring evidence are complete. The
  manual packet requirement now carries only
  metadata-level `blocked_requirement_ids` so reviewers can see which manual
  gates remain open without reading approval values, PHI, secrets, source
  paths, vectors, or document content. Approval references are recorded only as
  configured/not-configured booleans.
  The top-level report also propagates only metadata-level dependent
  `blocked_requirement_ids` from the MLX runtime supervisor, model-improvement
  evidence, retrieval-vector backend evidence, production-corpus evidence, and
  prediction-fairness monitoring evidence reports so reviewers can identify
  exact remaining gates without exposing nested approval values, PHI, secrets,
  source paths, vectors, raw demographic values, outcome rows, or raw documents.
- Add a boolean-only manual production-gate packet template at
  `llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`
  and a validator at
  `llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`. The checked-in
  report at
  `llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json` has
  `safe_to_review=true` and `production_gate_ready=false`; it blocks until the
  packet attests student cutover approval/runtime ownership, user-data model
  improvement legal/BAA/consent readiness, dedicated model-improvement evidence
  report readiness, approved non-synthetic paired corpus evidence,
  dedicated production-corpus evidence report readiness, and
  source-controlled corpus review runbook documentation plus source-controlled
  collection/license checklist documentation and pair/source checklist
  documentation. The student cutover
  section now also requires source-controlled runtime owner handoff checklist
  documentation while keeping private runtime owner assignment and approval
  references outside source control. The validator now also
  verifies the source-controlled manual production-gate checklist at
  `llm-distill/docs/phi-plan-manual-production-gate-checklist.md` exists with
  required markers for student cutover approval, user-data model-improvement
  approval, non-synthetic denial/appeal pair evidence, semantic vector backend
  readiness, production fairness evidence, the manual gate private packet
  renderer, file-ingestion surface audit readiness, boolean-only evidence, no
  approval references in source control, no PHI or production document content,
  and `production_gate_ready=false` without emitting checklist text. The manual
  gate path now also includes
  `llm-distill/scripts/render_phi_plan_manual_gate_private_packet.py`, a
  renderer for the final private manual production-gate packet. It refuses
  output inside source control, requires explicit student cutover,
  student-runtime, model-improvement, production-corpus, retrieval-vector,
  prediction-fairness, file-ingestion, dependent-report-readiness, and
  no-raw-value attestations before approved mode, reads private manifest record
  ids and governance references from environment variables, verifies the
  configured supervisor, model-improvement, production-corpus,
  retrieval-vector, prediction-fairness, and file-ingestion surface reports are
  ready before writing a ready packet, writes private output with `0600`
  permissions, and prints only redacted booleans/counts. This
  prepares the final manual gate packet handoff without storing approval
  values, manifest record ids, PHI, source text, vectors, raw demographic
  values, production outcome rows, or production document content in source
  control. The packet also
  requires retrieval-vector backend readiness through
  `vector_backend_evidence_report_ready`, source-controlled runbook
  documentation, source-controlled reindex checklist documentation,
  source-controlled runtime smoke checklist documentation, semantic backend
  configuration, production vector backend configuration, chunk reindexing,
  governance review, and runtime validation review without storing approval
  reference values, PHI, secrets, source text, vector values, backend URLs, or
  production document content. The manual
  packet now also requires
  `prediction_fairness_evidence_report_ready`, approved outcome-data and
  sample-size attestations, threshold review, demographic grouping review,
  monitoring configuration, disparity thresholds, alerting ownership, latest
  monitoring-run evidence, legal/privacy review, source-controlled calibration
  checklist documentation, source-controlled monitoring runbook documentation,
  source-controlled monitoring validation checklist documentation,
  source-controlled legal/privacy checklist documentation, model-card update
  and required-marker verification evidence, rollback review, and
  metadata-only audit verification without
  storing raw demographic values, production outcome rows, PHI, secrets,
  approval references, or individual identifiers. The
  manual packet now also carries a ready
  `manual_file_ingestion_surface_evidence` requirement with three expected upload
  surfaces, three registered upload surfaces, zero unregistered upload surfaces,
  and boolean-only attestations for metadata-only surface inspection and safe
  audit marker coverage. The production-readiness audit now consumes this
  packet report as a
  required gate.
- Add a boolean-only user-data model-improvement evidence template at
  `llm-distill/data/model_improvement_evidence/model_improvement_evidence.template.json`
  and a validator at
  `llm-distill/scripts/validate_model_improvement_evidence.py`. The checked-in
  report at
  `llm-distill/evals/reports/model_improvement_evidence_report.json` has
  `safe_to_review=true` and `model_improvement_ready=false`; current checked-in
  runtime evidence is ready for disabled-by-default behavior, per-request
  attestations, approved-corpus import not auto-opting into model improvement,
  safe audit logging review, and frontend blocker visibility, but the report
  now has local governance evidence ready for source-controlled approval
  runbook documentation, data-use scope documentation, retention review, and
  revocation-path review, while still blocking until model-improvement request,
  legal approval, BAA confirmation, consent notice configuration, and approval
  reference configuration are attested. The
  report now also includes a ready `model_improvement_safety_boundaries`
  requirement that keeps external PHI de-identification disabled by default,
  raw PHI training disabled, production user data excluded until approval,
  training jobs dependent on a ready evidence packet, and revocation as a
  future-training blocker. The evidence does this without storing approval
  reference values, legal documents, consent documents, user data, PHI,
  secrets, or production document content. The production-readiness audit now
  consumes this report as a required user-data model-improvement gate. The
  validator now also verifies
  `llm-distill/docs/model-improvement-approval-runbook.md` exists with required
  disabled-default, private approval-reference, no external PHI
  de-identification, no raw PHI training, approved-corpus opt-in blocking, and
  `model_improvement_ready=false` markers without emitting the runbook text.
  The model-improvement evidence path now also includes
  `llm-distill/scripts/render_model_improvement_private_env.py`, a renderer for
  the final private model-improvement environment file. It refuses output
  inside source control, requires explicit legal/BAA/consent/request/
  retention/revocation/per-request/evidence-readiness attestations before
  approved mode, reads the approval reference and consent notice version from
  private environment variables, verifies the configured model-improvement
  evidence report is safe to review, ready, and unblocked before writing an
  enabled private env, writes private output with `0600` permissions, and
  prints only redacted booleans/counts. This prepares the private runtime
  configuration path without approving user-data use, enabling model
  improvement, storing approval or consent values, or weakening the current
  blocker.
  The
  application startup guard consumes the same checked-in report path through
  `USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT` only when user-data model
  improvement is enabled, and logs booleans plus blocker IDs without approval
  values, consent-version values, raw report evidence, PHI, secrets, or user
  data.
- Add a boolean-only production corpus evidence template at
  `llm-distill/data/production_corpus_evidence/corpus_evidence.template.json`
  and a validator at
  `llm-distill/scripts/validate_production_corpus_evidence.py`. The checked-in
  report at `llm-distill/evals/reports/production_corpus_evidence_report.json`
  has `safe_to_review=true` and `production_corpus_ready=false`; it reads only
  manifest metadata. Current checked-in manifest review evidence is ready for
  privacy review, license review, residual-risk review, training-scope review,
  no-PHI review, and source/license scope documentation, while production
  corpus readiness still blocks until outside-source-control pair/source review
  and at least one approved non-synthetic denial/appeal pair are complete. The
  report emits counts and blocker codes only, not source paths, checksums,
  approval references, PHI, secrets, raw denial letters, raw appeal letters, or
  production document content. The validator now also verifies the
  source-controlled corpus review runbook at
  `llm-distill/docs/production-corpus-review-runbook.md` exists with required
  quarantine, de-identification, Safe Harbor/Expert Determination, approved
  non-synthetic pair, outside-source-control review, and
  `production_corpus_ready=false` markers without emitting the runbook text.
  The validator now also verifies the source-controlled collection/license
  checklist at `llm-distill/docs/production-corpus-collection-license-checklist.md`
  exists with required source inventory, source category, license terms,
  terms-of-use, payer policy reuse restriction, public/real de-identified source
  scope, collection owner, privacy/license/residual-risk/training-scope/no-PHI,
  no raw documents, no source paths/URLs, no checksums, no approval reference
  values, no PHI, and `production_corpus_ready=false` markers without emitting
  the checklist text.
  The validator now also verifies the source-controlled pair/source checklist
  at `llm-distill/docs/production-corpus-pair-source-checklist.md` exists with
  required denial/appeal roles, shared pair id, outside-source-control pair and
  source review, privacy/license/residual-risk/training-scope/no-PHI review,
  no raw documents, no source paths/URLs, no checksums, no approval reference
  values, no PHI, and `production_corpus_ready=false` markers without emitting
  the checklist text.
  The production corpus evidence path now also includes
  `llm-distill/scripts/render_production_corpus_private_evidence.py`, a
  renderer for the final private boolean-only production corpus evidence file.
  It refuses output inside source control, requires explicit approved
  non-synthetic pair, privacy, license, residual-risk, training-scope, no-PHI,
  source/license, pair-id, source-document, metadata-only manifest,
  no-raw-document, and no-raw-value attestations before approved mode, reads
  private manifest and review references from environment variables, verifies
  the private manifest metadata contains at least one approved non-synthetic
  denial/appeal pair before writing ready private evidence, stores only the
  manifest-path environment variable name in private evidence, writes private
  output with `0600` permissions, and prints only redacted booleans/counts. The
  validator resolves the private manifest path from that environment variable
  at operator runtime without emitting the raw path in reports. This prepares
  the private production-corpus evidence handoff without
  storing raw denial letters, raw appeal letters, source paths, private
  manifest paths, checksums, approval references, credentials, PHI, secrets, or
  production document content in source control.
- Add a non-secret MLX student runtime supervisor evidence template at
  `llm-distill/data/runtime_supervision/` plus
  `llm-distill/scripts/validate_mlx_runtime_supervisor.py`. The checked-in
  report at `llm-distill/evals/reports/mlx_runtime_supervisor_report.json` has
  `safe_to_review=true` and `supervisor_ready=false`; it verifies the launchd
  template uses `mlx_lm.server`, loopback binding, adapter-path wiring,
  KeepAlive/log paths, no shell wrapper, and an allowlisted launchd environment
  surface. The validator now requires `CLAIMGUARD_RUNTIME_PROFILE` to remain
  `student_denial_workflow_local_only`, rejects unapproved or secret/proxy-
  shaped launchd environment-variable names, and omits raw environment values
  from reports. The runtime supervision path now includes
  `llm-distill/scripts/render_mlx_launchd_private_copy.py`, a non-installing
  renderer that writes a private launchd plist outside source control, refuses
  repository output paths, keeps the runtime profile allowlisted, and returns
  only redacted booleans/counts. The validator now also verifies this renderer
  exists with required no-source-control-output, loopback/runtime-profile, and
  redacted-summary markers. It now also verifies the source-controlled supervisor runbook
  at `llm-distill/docs/mlx-runtime-supervisor-runbook.md` exists with required
  local-only, private-copy, rollback, and no-raw-value markers, without
  emitting the runbook text. It now also verifies the source-controlled runtime
  validation checklist at
  `llm-distill/docs/mlx-runtime-validation-checklist.md` exists with required
  MLX preflight, student status endpoint, runtime health, launchd load, restart
  test, rollback, and boolean-only/no-raw-output markers, without emitting the
  checklist text. It now also verifies the source-controlled owner handoff
  checklist at `llm-distill/docs/mlx-runtime-owner-handoff-checklist.md`
  exists with required private runtime-owner assignment, Raphael approval,
  outside-source-control approval reference, private launchd copy, loopback,
  MLX preflight, status endpoint, runtime health, restart, rollback,
  conservative default flags, boolean-only/no-raw-output, and
  `supervisor_ready=false` markers, without emitting the checklist text. It
  also verifies no PHI/PII and no raw approval, secret, or production document
  values. Local operator-control evidence now attests restart-policy review,
  health-check review, manual-start command review, rollback-to-NVIDIA review,
  source-controlled runbook documentation, runtime validation checklist
  documentation, owner handoff checklist documentation, and environment-file
  exclusion from source control.
  The runtime supervision path now also includes
  `llm-distill/scripts/render_mlx_runtime_supervisor_private_evidence.py`, a
  renderer for the final private boolean-only supervisor evidence file. It
  refuses output inside source control, requires explicit runtime owner,
  private launchd copy, restart-policy, health-check, manual-start, rollback,
  environment-file exclusion, preflight, status endpoint, runtime health,
  launchd load, restart-test, and no-raw-value attestations before approved
  mode, reads private launchd plist and validation references from environment
  variables, writes private output with `0600` permissions, and prints only
  redacted booleans/counts. This prepares the private runtime-supervision
  evidence handoff without storing private plist paths, runtime owner values,
  approval references, logs, endpoint responses, model output, PHI, or secrets
  in source control.
  The production-readiness audit and manual gate packet still block
  default student cutover until private runtime owner assignment, manual
  runbook review,
  runtime preflight, student status/health checks, launchd load evidence, and
  supervisor restart testing are complete outside source control. The app
  startup path now also runs a metadata-only student-default startup guard so a
  production environment cannot quietly request student-default routing before
  release evidence, Raphael approval, non-secret approval-reference
  configuration, supervised runtime, runtime health, and rollback-off status
  are all true.
  The same startup guard now consumes `CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH`
  and rejects production auto-launch requests before release evidence, Raphael
  approval, approval-reference configuration, supervised runtime, runtime
  health, and rollback-off status are ready.
  The manual production-gate path now also includes
  `llm-distill/scripts/render_student_cutover_private_env.py`, a renderer for
  the final private student-cutover environment file. It refuses output inside
  source control, requires explicit Raphael approval/runtime/distillation/
  rollback attestations before approved-cutover mode, reads the approval
  reference from a private environment variable, verifies the configured MLX
  runtime supervisor evidence report is safe, ready, and unblocked before
  writing enabled settings, writes private output with `0600` permissions, and
  prints only redacted booleans/counts. This closes a
  source-controlled operator-preparation gap, but it does not provide the
  private approval reference, supervised runtime ownership, runtime health
  evidence, or PHIplan production readiness needed to enable default student
  routing.
- Add local healthcare code format validation utilities at
  `health-ai-medical-billing-medical-corporations-20260414_180528/app/utils/healthcare_codes.py`
  for NPI check-digit validation, ICD-10-CM, CPT/HCPCS, CARC group/reason, and
  RARC format checks. Claim prediction and claim submission now reject invalid
  diagnosis/procedure formats with safe structured 400 responses before
  prediction or persistence. EDI 837 validation now flags invalid diagnosis and
  service-line procedure code formats with metadata-only parser issues, and
  EDI 835 parsing now validates CARC group/reason and LQ remark codes without
  returning raw code values, segment payloads, claim text, patient identifiers,
  provider identifiers, PHI, or production document content.
- Add conservative diagnosis/procedure linkage metadata validation. Claim
  prediction and claim submission now require diagnosis-code support when
  procedure-code metadata is present, validate explicit diagnosis-pointer
  references when supplied, and reject invalid linkage metadata before
  prediction or persistence. EDI 837 parsing now flags missing professional
  SV1 diagnosis pointers and invalid/out-of-range service-line diagnosis
  pointers as metadata-only validation issues. These checks do not assert
  clinical medical necessity, payer-specific coverage, or a production
  diagnosis/CPT policy crosswalk, and they do not return raw code values, raw
  pointer values, raw claim payloads, segment payloads, PHI, secrets, or
  production claim content.
- Add a versioned local CARC/RARC lifecycle seed database at
  `health-ai-medical-billing-medical-corporations-20260414_180528/app/data/carc_rarc_codes.json`
  with a loader in `app/utils/carc_rarc_database.py`. EDI 835 CAS/LQ parsing
  now attaches metadata-only status, category, and code-list identifiers for
  known active or inactive seed codes, rejects known inactive seed codes, and
  treats format-valid unknown codes as `format_valid_unconfirmed` instead of
  falsely rejecting them from an incomplete local seed. The seed intentionally
  stores lifecycle metadata and internal categories only, not official
  long-form descriptions, and remains a local safeguard rather than a licensed
  production code-list update feed.
- Add local administrative billing code-set validation for EDI 837. The same
  utility now validates CMS place-of-service codes, claim-frequency codes, and
  revenue-code format with metadata-only issue details. `app/utils/edi_parser.py`
  parses CLM05 place-of-service/frequency metadata and SV2 revenue codes,
  returns safe validation issues for invalid values, and exposes those claim
  code fields in batch-upload responses without raw segment payloads, PHI,
  secrets, or production claim content. The local validators are not a
  substitute for payer policy, clearinghouse edits, or a production code-set
  update feed.
- Add metadata-only appeal deadline tracking for the standalone appeal
  generator. `app/services/appeal_deadlines.py` builds conservative deadline
  tracking rows from structured claim metadata or existing denial-workflow
  deadline tables, `app/api/v1/appeals.py` returns the tracking summary with
  every appeal draft and includes fallback-letter deadline-review language, and
  `app/schemas/analytics.py` exposes the response shape. The implementation
  calculates only from structured dates/windows already present on the claim,
  marks unverified or urgent/past-due items as human-review required, and does
  not infer payer-specific legal rules from free text or mark any appeal
  filing-ready.
- Add submit-time required claim field validation for payer, subscriber, and
  service-date metadata. `app/api/v1/claims.py` now rejects `/api/v1/claims/submit`
  requests that lack those fields, or have an invalid structured service date,
  before denial prediction or persistence. Rejections return safe structured
  metadata-only issue details with accepted field names, issue codes, counts,
  and PHI-safe context flags, and audit logs record only endpoint, issue
  counts, issue types, and claim-data key count without raw claim values,
  patient identifiers, provider identifiers, document text, PHI, or production
  claim content.
- Add local demographic and claim-value validation guards for future patient
  dates of birth and negative structured claim amounts. `app/api/v1/patients.py`
  now rejects create/update requests with future `date_of_birth` values before
  persistence, and `app/api/v1/claims.py` rejects negative top-level or
  service-line amount metadata before denial prediction or claim submission.
  Rejections return structured metadata-only field/error details and safe
  context flags without returning raw dates, raw amount values, patient
  identifiers, provider identifiers, full claim payloads, PHI, secrets, or
  production claim content.
- Add high-risk prediction human-review gating for claim prediction and
  submission. `app/api/v1/claims.py` now derives metadata-only review flags
  when denial risk exceeds the configured threshold, a denial reason is
  high-severity, or a recommendation is high-priority. `app/schemas/claim.py`
  returns `human_review_required`, `human_review_status`,
  `human_review_reasons`, `human_review_threshold`, and
  `human_review_next_action` on prediction, submit, and claim-list/detail
  responses. The Claims and Dashboard UI now show review-required indicators
  before the next payer action, and claim prediction/submission audit details
  record presence flags, counts, thresholds, and safe context instead of raw
  patient/provider identifiers or claim text.
- Add structured charge-master and contract-rate claim pricing checks for
  prediction. `app/services/contract_rates.py` evaluates only explicit
  structured claim metadata, procedure-code rate maps, and service-line rate
  fields; `app/services/prediction.py` converts findings into CO-45 or
  charge-master denial drivers and recommendations. Findings and prediction
  reasons include ratios, generic descriptions, and safe context booleans, but
  do not serialize raw dollar values, raw claim data, payer-specific contract
  values inferred from free text, PHI, secrets, or production claim content.
- Add frontend XSS hardening for model-generated and user-supplied review
  output. `frontend/src/utils/safeHtml.ts` escapes display text, normalizes line
  breaks, and sanitizes the result with DOMPurify while allowing only `<br>`
  tags and no attributes. `frontend/src/components/common/SafeHtml.tsx`
  isolates the only allowed `dangerouslySetInnerHTML` use, and Claims,
  Dashboard, Appeals, and Denial Workflow high-risk output surfaces render
  through that component instead of ad hoc HTML insertion.
- Keep all regression coverage synthetic; no real patient, claim, contact, or
  credential values were added.

## Remaining Production Work

- When a future automated file-ingestion document store is intentionally added,
  register it in `llm-distill/scripts/audit_file_ingestion_surfaces.py`, extend
  role-scoped retention/deletion and audit-dashboard coverage in code, and
  refresh `llm-distill/evals/reports/file_ingestion_surface_audit_report.json`
  before treating it as a production document repository.
- Obtain and configure real legal approval reference, BAA confirmation, and
  consent notice version, then rerun
  `llm-distill/scripts/validate_model_improvement_evidence.py`, before enabling
  user-data model improvement in any production environment. Follow
  `llm-distill/docs/model-improvement-approval-runbook.md` and render any
  final env file with
  `llm-distill/scripts/render_model_improvement_private_env.py` for private
  approval-reference and consent-version handling; approved renderer mode will
  also refuse to write if the configured model-improvement evidence report is
  missing, unsafe, blocked, or not ready. Keep the local governance and
  `model_improvement_safety_boundaries` evidence ready so data-use scope,
  retention, revocation, external PHI de-identification, raw PHI training,
  production user-data use, and training-job eligibility remain explicitly
  gated; the FastAPI startup guard will still reject production enablement
  while this evidence remains blocked.
- Expand the production training corpus beyond the synthetic 900-pair stress
  corpus with public/government denial/appeal example pairs when suitable
  no-PHI/licensed examples are available, and with Raphael-approved
  de-identified real examples. Keep the current manifest review attestations
  ready, add at least one approved non-synthetic paired denial/appeal source
  reviewed outside source control, render the final private corpus evidence
  file with `llm-distill/scripts/render_production_corpus_private_evidence.py`,
  confirm that only the private manifest-path environment variable name is
  serialized, then rerun
  `llm-distill/scripts/validate_production_corpus_evidence.py`.
- When adding future automated file-ingestion workflows beyond
  `/api/v1/claims/upload-document`, `/api/v1/claims/batch-upload`, and
  `/api/v1/claims/remittance-upload`, extend document-surface inspection and
  keep the file-ingestion surface audit ready before production use.
- If building a corpus-derived adapter, run the MLX fine-tune training path
  against the guarded corpus manifest from a local macOS session with Metal
  access only after `llm-distill/scripts/validate_production_corpus_evidence.py`
  produces a safe ready report, then repeat live benchmark plus acceptance gates
  before promotion.
- Obtain Raphael approval and configure the non-secret student cutover
  reference/runtime-supervision flags outside source control before making
  default student use or student runtime auto-launch effective in a production
  environment. The private student-cutover env renderer now refuses enabled
  output if the configured supervisor evidence report is missing, unsafe,
  blocked, or not ready.
- Install and validate the MLX runtime supervisor from a private operator copy
  of `llm-distill/data/runtime_supervision/claimguard.mlx-student.launchd.template.plist`,
  follow `llm-distill/docs/mlx-runtime-supervisor-runbook.md`, render the
  final private supervisor evidence file with
  `llm-distill/scripts/render_mlx_runtime_supervisor_private_evidence.py`,
  then rerun `llm-distill/scripts/validate_mlx_runtime_supervisor.py` before
  setting supervised runtime flags.
- Configure the production semantic embedding backend/vector store outside
  source control, render the private retrieval/vector environment file with
  `llm-distill/scripts/render_retrieval_vector_private_env.py`, run the admin
  reindex operation in dry-run mode, reindex retrieval/corpus chunks with the
  approved private provider, run health and retrieval quality smoke checks, and rerun
  `llm-distill/scripts/validate_retrieval_vector_backend.py` before treating
  retrieval as production semantic search. The private retrieval/vector env
  renderer now refuses enabled output if the configured evidence report is
  missing, unsafe, blocked, or not ready. Keep the local governance,
  source-controlled retrieval-vector runbook and reindex-checklist
  documentation, backup/restore, and rollback/disable-path review evidence
  ready.
- Clear the blockers in
  `llm-distill/evals/reports/phi_plan_production_readiness_report.json` before
  treating the PHIplan as production-ready: external student cutover approval,
  user-data model-improvement legal/BAA/consent approval, production semantic
  vector backend approval, at least one approved non-synthetic paired
  denial/appeal training source, and production prediction threshold/fairness
  monitoring evidence.
- Follow `llm-distill/docs/production-corpus-review-runbook.md` before marking
  non-synthetic denial/appeal pairs production training eligible; keep raw
  documents, source paths, checksums, approval references, PHI, and production
  document content outside source control, and keep
  `production_corpus_ready=false` until private pair/source review is complete.
- Complete
  `llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`
  with boolean-only evidence, including
  `model_improvement_evidence_report_ready` and
  `source_control_approval_runbook_documented`,
  `production_corpus_evidence_report_ready`,
  `source_control_review_runbook_documented`,
  `vector_backend_evidence_report_ready`,
  `source_control_runbook_documented`,
  `file_ingestion_surface_report_ready`, registered/upload surface counts,
  `source_control_calibration_checklist_documented`,
  semantic backend configuration, production vector backend configuration,
  chunk reindexing, governance review, and runtime validation review, and rerun
  `llm-distill/scripts/validate_phi_plan_manual_gate_packet.py` before any
  production default cutover, model-improvement enablement, non-synthetic
  corpus-derived training run, production semantic retrieval promotion, or
  production calibrated-threshold/fairness-monitoring promotion. The private
  manual gate renderer now refuses a ready packet if any configured dependent
  report is missing, unsafe, blocked, or not ready.

## Rollback

Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/retrieval.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/retrieval_store.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/denial_workflow.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_retrieval_store.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`, and
`llm-distill/docs/retrieval-vector-backend-runbook.md` from
`backups/20260531-110228-semantic-retrieval-provider-boundary/` if rolling back
the semantic retrieval provider boundary.

Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/api/v1/claims.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/schemas/claim.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/utils/edi_835_parser.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/docs/edi-formats.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_edi_835_parser.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_file_ingestion_surface_audit.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`llm-distill/scripts/audit_file_ingestion_surfaces.py`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/evals/reports/file_ingestion_surface_audit_report.json`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260531-104519-edi835-remittance-upload-surface/`; remove
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_claims_remittance_upload.py`
if rolling back the EDI 835 remittance upload surface.

Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/api/v1/claims.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_claims_endpoints.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_claims_coverage.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-011635-required-claim-fields/`; remove
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_required_claim_fields.py`
if rolling back the required claim fields slice.

Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/package.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/package-lock.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/src/pages/Claims.tsx`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/src/pages/Dashboard.tsx`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/src/pages/Appeals.tsx`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/src/pages/DenialWorkflow.tsx`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-012730-xss-dompurify/`; remove
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/src/utils/safeHtml.ts`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/src/components/common/SafeHtml.tsx`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_frontend_xss_dompurify.py`
if rolling back the DOMPurify frontend XSS hardening slice.

Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/api/v1/appeals.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/schemas/analytics.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-010754-appeal-deadline-tracking/`; remove
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/appeal_deadlines.py`
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_appeal_deadline_tracking.py`
if rolling back the appeal deadline tracking slice.

Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/api/v1/claims.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/utils/edi_parser.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/utils/edi_835_parser.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-005429-healthcare-code-validation/`; remove
`health-ai-medical-billing-medical-corporations-20260414_180528/app/utils/healthcare_codes.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_healthcare_code_validation.py`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_edi_healthcare_code_validation.py`
if rolling back the healthcare code validation slice. The late-current
`tests/unit/test_edi_parser.py.late-current` file in the backup directory is
remediation evidence from moving accidental exploratory coverage into the new
dedicated EDI healthcare-code test file; it is not a rollback target unless a
future inspection finds `tests/unit/test_edi_parser.py` changed.

Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/models/__init__.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-004528-claim-status-db-constraints/`; remove
`health-ai-medical-billing-medical-corporations-20260414_180528/alembic/versions/20260531_004528_add_claim_status_constraint.py`
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_claim_status_db_constraints.py`
if rolling back the claim status database-constraint slice.

Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/api/v1/claims.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/schemas/claim.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-003219-claim-state-machine/`; remove
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/claim_state.py`
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_claim_state_machine.py`
if rolling back the claim state machine slice.

Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/document_analysis.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/denial_workflow.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-002121-ai-safety-guardrails/`; remove
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/ai_safety.py`
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_ai_safety_guardrails.py`
if rolling back the AI safety guardrails slice.

Restore files from the relevant timestamped directory under `backups/`, starting
with `backups/20260530-162400-phi-access-audit/` for the latest PHI
access-audit and synthetic corpus slice. Remove the generated
`llm-distill/data/corpus/generated_synthetic_pairs/`,
`llm-distill/data/distillation/mlx_sft_synthetic_900/`, and
`llm-distill/evals/reports/mlx_finetune_synthetic_900_preflight_report.json`
artifacts if rolling back the corpus generation. Restore
`llm-distill/scripts/run_mlx_finetune.py` and
`llm-distill/evals/reports/mlx_finetune_synthetic_900_run_report.json` from
`backups/20260530-164204-mlx-runtime-gate/` if rolling back the runtime-gate
correction. Restore `llm-distill/scripts/run_distillation_readiness_audit.py`
and `llm-distill/evals/reports/distillation_readiness_audit_report.json` from
`backups/20260530-165152-synthetic900-readiness-audit/` if rolling back the
synthetic-900 readiness-audit coverage, then rerun the targeted validation
commands recorded in `CHANGELOG.md`. Restore `PHIplan.md`,
`CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/README.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-001247-backup-disaster-recovery-docs/`; remove
`health-ai-medical-billing-medical-corporations-20260414_180528/docs/backup-disaster-recovery.md`
if rolling back the backup/disaster recovery documentation slice.
Restore `PHIplan.md`,
`CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/README.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-000545-api-edi-deployment-docs/`; remove
`health-ai-medical-billing-medical-corporations-20260414_180528/docs/api-authentication.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/docs/edi-formats.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/docs/deployment-guide.md`
if rolling back the Sprint 6.2 API/EDI/deployment documentation slice.
Restore `PHIplan.md`,
`CHANGELOG.md`, `health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and `health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260530-165956-phi-production-readiness/` and remove
`llm-distill/scripts/run_phi_plan_production_readiness_audit.py`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`, and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_production_readiness_audit.py`
if rolling back the PHIplan production-readiness audit slice.
Restore `llm-distill/scripts/run_phi_plan_production_readiness_audit.py`,
`PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_production_readiness_audit.py`
from `backups/20260530-171548-phi-production-gate-packet/` and remove
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`, and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`
if rolling back the manual production-gate packet slice.
Restore `llm-distill/scripts/run_distillation_readiness_audit.py`,
`llm-distill/scripts/generate_synthetic_denial_appeal_corpus.py`,
`llm-distill/data/corpus/generated_synthetic_pairs/README.md`, `PHIplan.md`,
`CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_distillation_readiness_audit.py`,
`llm-distill/evals/reports/distillation_readiness_audit_report.json`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-173841-synthetic-format-audit/`; remove
`llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py`,
`llm-distill/evals/reports/synthetic_denial_appeal_corpus_format_audit_report.json`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_synthetic_corpus_format_audit.py`
if rolling back the generated synthetic corpus format-audit slice.
Restore `llm-distill/scripts/generate_synthetic_denial_appeal_corpus.py`,
`llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py`,
`llm-distill/data/corpus/generated_synthetic_pairs/README.md`,
`llm-distill/evals/reports/synthetic_denial_appeal_corpus_format_audit_report.json`,
`PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_synthetic_corpus_format_audit.py`
from `backups/20260530-194750-synthetic-visual-layouts/`; remove
`llm-distill/scripts/render_synthetic_corpus_visual_layouts.py`,
`llm-distill/data/corpus/generated_synthetic_pairs/rendered_html/`,
`llm-distill/data/corpus/generated_synthetic_pairs/visual_manifest_synthetic_900.json`,
`llm-distill/data/corpus/generated_synthetic_pairs/visual_render_report.json`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_synthetic_corpus_visual_layouts.py`
if rolling back the rendered visual-layout companions.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/schemas/corpus.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/corpus.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/api/v1/denial_workflow.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_corpus_safety.py`,
and `llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-175138-corpus-review-decision/` if rolling back the manual
corpus review-decision API slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/src/api/client.ts`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/src/pages/DenialWorkflow.tsx`,
and `llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-180129-corpus-review-ui-gate/` if rolling back the manual
corpus review-decision UI gate slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/core/config.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/schemas/denial_workflow.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/retrieval_store.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/api/v1/denial_workflow.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_retrieval_store.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_production_readiness_audit.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/src/api/client.ts`,
`health-ai-medical-billing-medical-corporations-20260414_180528/frontend/src/pages/DenialWorkflow.tsx`,
`llm-distill/scripts/run_phi_plan_production_readiness_audit.py`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-181204-vector-readiness-gate/` if rolling back the semantic
vector-readiness gate slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_production_readiness_audit.py`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/scripts/run_phi_plan_production_readiness_audit.py`,
`llm-distill/docs/mlx-setup.md`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-183910-mlx-runtime-supervisor/`; remove
`llm-distill/data/runtime_supervision/claimguard.mlx-student.launchd.template.plist`,
`llm-distill/data/runtime_supervision/supervisor_evidence.template.json`,
`llm-distill/scripts/validate_mlx_runtime_supervisor.py`,
`llm-distill/evals/reports/mlx_runtime_supervisor_report.json`, and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_mlx_runtime_supervisor.py`
if rolling back the MLX runtime supervisor evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`llm-distill/data/runtime_supervision/supervisor_evidence.template.json`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_mlx_runtime_supervisor.py`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/mlx_runtime_supervisor_report.json`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_mlx_runtime_supervisor.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-062207-supervisor-runbook-evidence/`; remove
`llm-distill/docs/mlx-runtime-supervisor-runbook.md` if rolling back the
source-controlled supervisor runbook evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`llm-distill/data/runtime_supervision/supervisor_evidence.template.json`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_mlx_runtime_supervisor.py`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/mlx_runtime_supervisor_report.json`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_mlx_runtime_supervisor.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-101512-mlx-runtime-owner-handoff-checklist/`; remove
`llm-distill/docs/mlx-runtime-owner-handoff-checklist.md` if rolling back the
source-controlled runtime owner handoff checklist evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_production_readiness_audit.py`,
`llm-distill/scripts/run_phi_plan_production_readiness_audit.py`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-185428-vector-backend-evidence/`; remove
`llm-distill/data/retrieval_vector_backend/vector_backend_evidence.template.json`,
`llm-distill/scripts/validate_retrieval_vector_backend.py`,
`llm-distill/evals/reports/retrieval_vector_backend_report.json`, and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_retrieval_vector_backend_evidence.py`
if rolling back the retrieval vector backend evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`llm-distill/data/retrieval_vector_backend/vector_backend_evidence.template.json`,
`llm-distill/scripts/validate_retrieval_vector_backend.py`,
`llm-distill/evals/reports/retrieval_vector_backend_report.json`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_retrieval_vector_backend_evidence.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-063456-retrieval-vector-runbook-evidence/`; remove
`llm-distill/docs/retrieval-vector-backend-runbook.md` if rolling back the
source-controlled retrieval vector backend runbook evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`llm-distill/scripts/validate_retrieval_vector_backend.py`,
`llm-distill/data/retrieval_vector_backend/vector_backend_evidence.template.json`,
`llm-distill/evals/reports/retrieval_vector_backend_report.json`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_retrieval_vector_backend_evidence.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-072616-retrieval-reindex-checklist/`; remove
`llm-distill/docs/retrieval-vector-reindex-checklist.md` if rolling back the
source-controlled retrieval vector reindex checklist evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_production_readiness_audit.py`,
`llm-distill/scripts/run_phi_plan_production_readiness_audit.py`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-190243-production-corpus-evidence/`; remove
`llm-distill/data/production_corpus_evidence/corpus_evidence.template.json`,
`llm-distill/scripts/validate_production_corpus_evidence.py`,
`llm-distill/evals/reports/production_corpus_evidence_report.json`, and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_production_corpus_evidence.py`
if rolling back the production corpus evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`llm-distill/data/production_corpus_evidence/corpus_evidence.template.json`,
`llm-distill/scripts/validate_production_corpus_evidence.py`,
`llm-distill/evals/reports/production_corpus_evidence_report.json`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_production_corpus_evidence.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-064317-production-corpus-review-runbook/`; remove
`llm-distill/docs/production-corpus-review-runbook.md` if rolling back the
source-controlled production corpus review runbook evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`llm-distill/scripts/validate_production_corpus_evidence.py`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/data/production_corpus_evidence/corpus_evidence.template.json`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/evals/reports/production_corpus_evidence_report.json`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_production_corpus_evidence.py`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`
from `backups/20260531-103843-production-corpus-pair-source-checklist/`;
remove `llm-distill/docs/production-corpus-pair-source-checklist.md` if
rolling back the source-controlled production corpus pair/source checklist
evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`llm-distill/scripts/validate_production_corpus_evidence.py`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/data/production_corpus_evidence/corpus_evidence.template.json`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/evals/reports/production_corpus_evidence_report.json`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_production_corpus_evidence.py`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`
from `backups/20260531-103408-production-corpus-collection-license-checklist/`;
remove `llm-distill/docs/production-corpus-collection-license-checklist.md` if
rolling back the source-controlled production corpus collection/license
checklist evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`llm-distill/data/model_improvement_evidence/model_improvement_evidence.template.json`,
`llm-distill/scripts/validate_model_improvement_evidence.py`,
`llm-distill/evals/reports/model_improvement_evidence_report.json`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_model_improvement_evidence.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-065141-model-improvement-approval-runbook/`; remove
`llm-distill/docs/model-improvement-approval-runbook.md` if rolling back the
source-controlled model-improvement approval runbook evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_production_readiness_audit.py`,
`llm-distill/scripts/run_phi_plan_production_readiness_audit.py`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-191205-model-improvement-evidence/`; remove
`llm-distill/data/model_improvement_evidence/model_improvement_evidence.template.json`,
`llm-distill/scripts/validate_model_improvement_evidence.py`,
`llm-distill/evals/reports/model_improvement_evidence_report.json`, and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_model_improvement_evidence.py`
if rolling back the model-improvement evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`llm-distill/scripts/validate_prediction_fairness_evidence.py`,
`llm-distill/data/prediction_fairness_evidence/fairness_monitoring_evidence.template.json`,
`llm-distill/evals/reports/prediction_fairness_evidence_report.json`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_prediction_fairness_evidence.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-073351-prediction-fairness-calibration-checklist/`;
remove `llm-distill/docs/prediction-fairness-calibration-checklist.md` if
rolling back the source-controlled prediction fairness calibration checklist
evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`llm-distill/scripts/validate_prediction_fairness_evidence.py`,
`llm-distill/data/prediction_fairness_evidence/fairness_monitoring_evidence.template.json`,
`llm-distill/evals/reports/prediction_fairness_evidence_report.json`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`,
`llm-distill/evals/reports/phi_plan_production_readiness_report.json`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_prediction_fairness_evidence.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`
from `backups/20260531-102420-prediction-fairness-legal-privacy-checklist/`;
remove `llm-distill/docs/prediction-fairness-legal-privacy-checklist.md` if
rolling back the source-controlled prediction fairness legal/privacy checklist
evidence slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-192235-manual-model-evidence-link/` if rolling back the
manual packet model-improvement evidence-link slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-192723-manual-corpus-evidence-link/` if rolling back the
manual packet production-corpus evidence-link slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_manual_gate_packet.py`,
`llm-distill/data/production_gate_evidence/manual_gate_packet.template.json`,
`llm-distill/scripts/validate_phi_plan_manual_gate_packet.py`,
`llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-193540-manual-vector-evidence-link/` if rolling back the
manual packet retrieval-vector evidence-link slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_production_readiness_audit.py`,
`llm-distill/scripts/run_phi_plan_production_readiness_audit.py`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-194203-manual-packet-blocker-visibility/` if rolling back
the production-readiness manual-packet blocker visibility slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_phi_plan_production_readiness_audit.py`,
`llm-distill/scripts/run_phi_plan_production_readiness_audit.py`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-200112-dependent-report-blocker-visibility/` if rolling
back the dependent-report blocker visibility slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_synthetic_corpus_format_audit.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_distillation_readiness_audit.py`,
`llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py`,
`llm-distill/scripts/run_distillation_readiness_audit.py`,
`llm-distill/evals/reports/synthetic_denial_appeal_corpus_format_audit_report.json`,
`llm-distill/evals/reports/distillation_readiness_audit_report.json`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-213535-synthetic-profile-matrix-audit/` if rolling back the
synthetic profile-matrix audit slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_synthetic_corpus_format_audit.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_distillation_readiness_audit.py`,
`llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py`,
`llm-distill/scripts/run_distillation_readiness_audit.py`,
`llm-distill/evals/reports/synthetic_denial_appeal_corpus_format_audit_report.json`,
`llm-distill/evals/reports/distillation_readiness_audit_report.json`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-214402-synthetic-appeal-quality-audit/` if rolling back the
synthetic appeal-quality audit slice.
Restore `PHIplan.md`, `CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/app/services/document_analysis.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/implementation.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/CHANGELOG.md`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_document_analysis.py`,
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_distillation_readiness_audit.py`,
`llm-distill/scripts/run_distillation_readiness_audit.py`,
`llm-distill/evals/reports/distillation_readiness_audit_report.json`, and
`llm-distill/evals/reports/phi_plan_production_readiness_report.json` from
`backups/20260530-215412-synthetic-document-extraction-audit/`; remove
`llm-distill/scripts/audit_synthetic_document_analysis_extraction.py`,
`llm-distill/evals/reports/synthetic_document_analysis_extraction_report.json`,
and
`health-ai-medical-billing-medical-corporations-20260414_180528/tests/unit/test_synthetic_document_analysis_extraction_audit.py`
if rolling back the synthetic document-analysis extraction audit slice.
