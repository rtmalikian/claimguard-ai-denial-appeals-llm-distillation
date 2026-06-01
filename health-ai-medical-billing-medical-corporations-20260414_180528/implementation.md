# ClaimGuard AI - Implementation Todo List

> **Last Updated:** April 15, 2026  
> **Project Status:** MVP Complete, Production Hardening Required  
> **Test Coverage:** 80% (299 tests)

Current Objective Scratchpad: Continue the ClaimGuard distillation plan by
distilling a larger teacher LLM into a lightweight student model focused only on
denial-claim processing and appeal-letter generation. The accepted reviewed
LoRA adapter is now exposed through application status, workflow metadata,
`denial_skill` phase controls, live MLX runtime health evidence, and a
copyable launch command while production auto-launch/supervision remains open.
The PHI safeguard slice now adds metadata-only PHI/PII scanning, denial workflow
privacy review blockers, source-ingestion declaration gates, export summaries,
corpus manifest validation, machine de-identification, approved-import gates,
frontend corpus readiness visibility, manifest-gated corpus SFT export for
approved de-identified denial/appeal pairs, top-level readiness-audit corpus
blocking before student default acceptance, document-surface PHI inspection for
PDF/OCR/metadata/barcode/filename surfaces, a starter synthetic no-PHI
denial/appeal corpus with guarded SFT export evidence, and synthetic regression
coverage. The admin UI now includes retrieval-source creation, privacy-review
attestation, document-surface inspection, machine de-identification, approved
corpus import, stored-source visibility, role-scoped retrieval-source access,
retention/soft-delete controls, governance counts, and an admin retrieval audit
feed backed by the existing API gates. User-data model-improvement opt-in is
now disabled by default unless runtime legal approval, BAA confirmation,
consent notice, approval reference, and per-request attestations are present;
approved corpus import no longer auto-opts sources into user-data model
improvement, and FastAPI startup now fails fast in production if that disabled
default is changed before legal/BAA/consent/reference flags and a safe ready
evidence report are present. Automated claim-document upload now runs the same
metadata-only document-surface inspection over filename, MIME type, extracted visible/OCR
text, and safe processing metadata, stores only redacted inspection summaries,
audits surface counts/status, and displays the result in the Claims UI. Legacy
claim-document storage now has access scopes, retention/soft-retire metadata,
safe governance/audit endpoints, redacted list/detail responses, and Dashboard
status for restricted, retired, or expired documents. Default student use is
now gated by explicit Raphael cutover approval, a non-secret approval
reference, supervised MLX runtime configuration, runtime health, release
evidence, and a rollback-to-NVIDIA flag that keeps deterministic fallback
authoritative without code changes. Retrieval source ingestion now has an
injectable embedding provider boundary: the default provider remains the
development hash fallback, but private production semantic embedding adapters
can be wired into `RetrievalStoreService` without storing provider URLs,
credentials, raw source text, or vector values in source control. Denial
Workflow retrieval reuses that store provider for query embeddings when
supplied, while production retrieval readiness remains blocked until a real
approved semantic provider, vector backend, reindex evidence, health check,
and quality smoke test are configured outside source control. The safe corpus
manifest now also includes
PHI-clean public/government appeal-process and privacy source notes for all
seven no-PHI source-registry entries, with a coverage audit proving checksum
coverage, required safety/use markers, zero PHI findings, and training
exclusion. These notes remain retrieval/governance context while keeping MLX
SFT export limited to approved paired denial/appeal examples, and the corpus
SFT manifest has a guarded MLX fine-tune preflight report with no training
attempted. Future automated
file-ingestion routes are now covered by an AST-based audit that inventories
`UploadFile`/`File` endpoints and blocks readiness unless each endpoint has
registered metadata-only surface inspection, governance, pre-processing size
validation, and safe audit markers; claim-document upload now rejects
unsupported, empty, and over-10 MB files before processing/OCR/analysis, and
the new EDI 837 batch upload endpoint is registered there and returns
structured per-claim parser results without raw segment payloads. EDI 837
batch upload now estimates aggregate segment and CLM claim-loop counts before
full parsing and rejects excessive batches with metadata-only
`pre_parse_batch_validation` errors before constructing claim objects,
document-surface inspection, database writes, or audit-log creation. EDI 837
parser failures and validation issues now carry safe `error_code`,
`parser_stage`, `field`, `segment_index`, `segment_id`, and `safe_context`
metadata for rejected uploads and structured parser warnings without raw
filenames, EDI text, segment payloads, PHI, or production claim content. The PHIplan
production-readiness audit now also consumes the file-ingestion surface audit as
a top-level current-state gate, so an unregistered UploadFile/File endpoint can
block both production readiness and `safe_current_state`. The EDI 835
remittance parser now has matching safe structured parser errors and validation
issues for CLP/CAS/LQ payment, adjustment, and remark-code parsing, and the
authenticated EDI 835 remittance upload surface is now registered in the
file-ingestion audit with bounded reads, safe structured upload errors,
metadata-only document-surface inspection, and payment summaries that do not
return raw patient or payer control numbers. Healthcare code validation
now rejects invalid claim ICD-10-CM and CPT/HCPCS formats before prediction or
persistence, validates NPI check digits through a local utility for provider
intake paths, and flags invalid EDI 837 diagnosis/procedure plus EDI 835
CARC/RARC formats through metadata-only parser issues without returning raw
code values or segment payloads. Claim-document upload and EDI 837 batch
upload now reject disguised inner extension chains before reading uploaded
bytes and read at most the configured limit plus one byte before size
validation. Image upload processing now enforces an explicit Pillow pixel-count
ceiling and converts decompression-bomb warnings into safe processing failures
before resize/compression work proceeds. Diagnosis/procedure linkage validation now
requires diagnosis-code support when procedure-code metadata is present,
validates explicit diagnosis pointers when supplied, and flags missing or
out-of-range professional EDI 837 service-line diagnosis pointers without
claiming clinical medical necessity or payer-policy correctness. EDI 835 CARC/RARC validation now also uses a
versioned local lifecycle seed database that attaches metadata-only code-list
status/category fields, rejects known inactive seed codes, and leaves
format-valid unknown codes as `format_valid_unconfirmed` so incomplete local
data does not overrule the official code lists. Administrative billing code
validation now adds local CMS place-of-service, claim-frequency, and
revenue-code format checks to EDI 837 claim parsing and batch-upload responses
while keeping parser issues metadata-only and avoiding payer-policy assertions. Appeal deadline
tracking now surfaces
metadata-only deadline rows and summaries on `/api/v1/appeals/generate` using
structured claim metadata or existing denial-workflow deadline tables, while
keeping unverified, urgent, and past-due items human-review-gated and not
filing-ready. Claim submission now validates required payer, subscriber, and
service-date metadata before prediction or persistence, returning safe
structured field-level errors and logging only issue counts/types and
claim-data key counts. Patient create/update now reject future date-of-birth
metadata before persistence, and claim prediction/submission now reject
negative structured top-level or service-line amount metadata before prediction
or persistence while returning/logging metadata-only validation details. High-risk claim prediction and submission now return
explicit human-review metadata, route high-risk dashboard rows to billing
review before the next payer action, and keep audit details metadata-only by
recording presence flags and review reason counts instead of patient/provider
identifiers. Production prediction threshold and fairness monitoring evidence
now has a FastAPI startup guard that fails fast in production while the
boolean-only evidence report is missing, unsafe, blocked, or not ready, and
logs only booleans plus blocker IDs without raw demographic values, outcome
rows, claim values, PHI, secrets, report paths, or approval-reference values.
Structured charge-master and contract-rate checks now evaluate
only explicit claim metadata, procedure-code rate maps, and service-line rate
fields, add CO-45 or charge-master denial drivers without serializing raw
dollar values, and avoid inferring payer-specific rates from free text.
Frontend model-generated and user-supplied review
outputs now render through a DOMPurify-backed SafeHtml component that escapes
text, permits only line-break tags, and isolates the only direct HTML insertion
path. Frontend auth session storage now records absolute token expiry,
last-activity timestamps, and an idle-timeout ceiling so inactivity clears
local auth state and redirects to login without extending the backend JWT
expiry. PHI access audit
logging now redacts sensitive audit detail keys and PHI/PII-like values at the
utility boundary while adding metadata-only access events for patient, claim,
analytics, and appeal flows. The safe training corpus
now also includes a generated 900-pair synthetic denial/appeal stress corpus
with documented format families, layout profiles, typography profiles, length
profiles, file-level format/variation audit evidence, train/valid/test SFT
export, rendered HTML companions with actual CSS font stacks and layout
wrappers, visual-layout audit evidence, role/split profile-matrix coverage,
appeal-quality contract checks, app document-analysis extraction coverage for
generated denial notices, and zero PHI findings. The MLX fine-tune wrapper now
verifies `mlx_lm.lora --help` before training so a headless session without
Metal access is blocked before adapter writes; the current synthetic-900 run
report records that no adapter was written because Metal is unavailable in this
session. The MLX fine-tune runner now also blocks corpus-derived `--run`
training unless the production corpus evidence report is safe and ready, so the
current synthetic-only production corpus cannot write corpus-derived adapter
weights. The top-level distillation readiness audit now also enforces the
generated synthetic-900 corpus, its 1,800 letter files, file-level
format/variation audit, documented format/layout/typography/length coverage,
appeal-quality contract evidence, app document-analysis extraction evidence,
SFT export, and guarded MLX run evidence so these stress-test artifacts cannot
silently go stale. A separate
PHIplan production-readiness audit now records
`safe_current_state=true` for the conservative current defaults while keeping
`production_ready=false` until external student cutover approval, legal/BAA/
consent model-improvement approval, and approved non-synthetic paired
denial/appeal training sources are complete. Manual production-gate evidence
now has a boolean-only packet template and validator; the current packet report
is safe to review but not production-ready, and the production-readiness audit
now blocks on that packet report as well as the underlying runtime, legal, and
corpus gates. MLX student runtime supervision now has a non-secret launchd
template, boolean-only evidence template, validator, and checked-in report; the
template is safe to review but not production-ready. Local operator-control
evidence now attests restart-policy review, health-check review, manual-start
command review, rollback-to-NVIDIA review, and environment-file exclusion from
source control. The supervisor validator now also verifies the launchd
environment surface is allowlisted, requires
`CLAIMGUARD_RUNTIME_PROFILE=student_denial_workflow_local_only`, rejects
unapproved or secret/proxy-shaped environment-variable names, and never emits
raw environment values in reports. The supervisor evidence now also verifies
the non-installing private launchd renderer at
`llm-distill/scripts/render_mlx_launchd_private_copy.py`; the renderer refuses
source-control output paths, writes only a private plist copy, keeps the
runtime profile allowlisted, and emits a redacted summary without local paths
or environment values. The private supervisor evidence renderer now parses the
private launchd plist in approved mode and rejects non-loopback hosts, missing
MLX server/adapter/port arguments, unsafe runtime profiles, missing launchd
operational settings, and unapproved or secret-like environment keys before
writing ready private evidence. The supervisor evidence now also verifies
the source-controlled runbook at
`llm-distill/docs/mlx-runtime-supervisor-runbook.md` has required private-copy,
local-only runtime, rollback, and no-raw-value markers without emitting the
runbook text. The supervisor evidence now also verifies the source-controlled
runtime validation checklist at
`llm-distill/docs/mlx-runtime-validation-checklist.md` has required MLX
preflight, student status endpoint, runtime health, launchd load, restart
test, rollback, boolean-only, and no-raw-output markers without emitting the
checklist text. The supervisor evidence now also verifies the
source-controlled owner handoff checklist at
`llm-distill/docs/mlx-runtime-owner-handoff-checklist.md` has required private
runtime-owner assignment, Raphael approval, outside-source-control approval
reference, private launchd copy, loopback, MLX preflight, student
status/health, restart, rollback, conservative default flags, boolean-only, and
no-raw-output markers without emitting the checklist text. Production
auto-launch and default student
cutover remain blocked until private runtime owner assignment, manual runbook
review, runtime
preflight, student status/health checks, launchd load evidence, and supervisor
restart testing are complete. The application startup path now also validates
student-default routing with metadata-only booleans and fails fast in
production if `CLAIMGUARD_STUDENT_USE_BY_DEFAULT=true` before release evidence,
Raphael approval, approval-reference configuration, supervised runtime, runtime
health, rollback-off status, and effective cutover readiness are all true.
The same startup path now consumes `CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH` and
fails fast in production if runtime auto-launch is requested before release
evidence, Raphael approval, approval-reference configuration, supervised
runtime, runtime health, and rollback-off status are ready.
Corpus de-identification and document-surface inspection now add local-only
contextual re-identification risk review for rare facts, age-over-89 cues,
small geography/provider uniqueness, exact timeline cues, unusual dollar
amounts, and public uniqueness references; findings remain metadata-only and
force expert determination before training eligibility. Corpus review now also
has a metadata-only review-decision API that records reviewer method, generic
findings, residual-risk score, review completion flags, expert determination,
and training decision while blocking training approval until every review,
license, residual-risk, split, micro-skill, and expert-determination gate
passes. The Denial Workflow admin corpus-import UI now routes approved corpus
import through that backend review-decision gate before calling the approved
import endpoint. Corpus review workflow now also includes a metadata-only
manifest review queue endpoint and admin UI panel that summarize review
blockers, pair completeness, production-corpus candidacy, and next actions
without returning document text, source paths, checksums, matched values, or
approval references. Retrieval governance now also includes a metadata-only
semantic/vector-readiness gate that blocks production readiness while the app is
still using the local hash embedding fallback or stored chunks need reindexing.
Retrieval vector backend production evidence now also has a boolean-only
template, validator, and checked-in report; the report is safe to review but
not production-ready, and the PHIplan audit blocks until semantic backend
configuration, production vector backend configuration, chunk reindexing,
runtime health, and quality smoke checks are complete outside source control.
Retrieval reindexing now also has an admin-only, metadata-only API/service
operation that defaults to dry-run mode, refuses non-dry-run writes with the
development hash provider, and reports only aggregate counts, provider labels,
warnings, and safe-context flags. Private production deployments must inject an
approved semantic provider before using the write path.
Retrieval vector backend evidence now also verifies
`llm-distill/scripts/render_retrieval_vector_private_env.py` as a
source-controlled private env renderer that refuses source-control output,
requires semantic backend, approved embedding model, production vector backend,
hash-fallback disablement, reindex completion, vector health, retrieval quality
smoke, rollback, and no-raw-value attestations before approved mode, reads
private backend/model/vector labels from environment variables only, verifies
the configured retrieval/vector backend evidence report is safe, ready, and
unblocked before writing enabled settings, writes `0600` private output, and
reports redacted booleans/counts without storing provider labels, model names,
vector-store labels, service URLs, credentials, source text, vector values,
PHI, or production document content.
Retrieval vector runtime private evidence now validates a private aggregate
runtime summary before ready evidence can be written; approved mode requires
semantic/reindex/health/quality/backup/rollback readiness booleans, positive
aggregate counts, and explicit no-raw-source/vector/endpoint/credential flags
without storing private summary paths, references, source text, vector values,
endpoints, credentials, PHI, or production document content.
Local governance checks, source-controlled retrieval-vector runbook
documentation, source-controlled retrieval reindex-checklist documentation,
backup/restore review, and rollback/disable-path review are now attested
without storing backend URLs, source text, vector values, credentials, PHI,
secrets, or production document content.
Production corpus evidence now has a boolean-only template, validator, and
checked-in report; the report is safe to review but not production-ready, and
the PHIplan audit blocks until approved non-synthetic paired denial/appeal
manifest evidence is complete. Current checked-in manifest review attestations
are ready for source-controlled review runbook documentation,
source-controlled collection/license checklist documentation,
source-controlled pair/source checklist documentation, privacy, license,
residual-risk, training-scope, no-PHI, and source/license scope without
storing raw documents, source paths, checksums, approval references, PHI, or
secrets; the remaining corpus gate is an approved non-synthetic paired
denial/appeal source with outside-source-control pair/source review.
User-data model-improvement evidence now also has a boolean-only template,
validator, and checked-in report; the report is safe to review but not
production-ready, and the PHIplan audit blocks until legal approval, BAA
confirmation, consent notice configuration, approval reference configuration,
and model-improvement request are complete. Its local governance evidence is
now ready for source-controlled approval runbook documentation, data-use scope
documentation, retention review, and revocation-path review, and its local
runtime evidence is ready for disabled-by-default behavior, per-request
attestations, approved-corpus import not auto-opting into model improvement,
safe audit logging review, and frontend blocker visibility. The report now also
carries ready `model_improvement_safety_boundaries` evidence for disabled
external PHI de-identification by default, disabled raw PHI training,
production user-data exclusion until approval, ready evidence-packet
enforcement for training jobs, and revocation blocking future training use
without storing approval values, legal documents, consent documents, user data,
PHI, secrets, or production document content. The PHIplan production-readiness
audit now carries only
metadata-level dependent blocker IDs from the MLX runtime supervisor,
model-improvement evidence, retrieval vector backend evidence, and production
corpus evidence reports so reviewers can identify exact remaining gates
without exposing approval values, PHI, secrets, source paths, vectors, or raw
documents.
Production prediction-threshold calibration and continuous fairness monitoring
now also have a boolean-only evidence template, validator, and checked-in
report; the report is safe to review but not production-ready, and the PHIplan
audit blocks until approved outcome data, sample-size evidence, calibration
review, monitoring ownership, latest run evidence, and legal/privacy
governance are complete outside source control. The current evidence now
marks model-card update ready only after verifying
`llm-distill/docs/prediction-fairness-model-card.md` exists with required
safety markers for human-review-only threshold use, no auto-denial threshold,
approved outcome data, calibration, continuous monitoring, and no raw
demographic/outcome values. The current evidence also verifies
`llm-distill/docs/prediction-fairness-monitoring-runbook.md` as a
source-controlled monitoring runbook with required markers for approved outcome
data, sample size, calibration, continuous monitoring, disparity thresholds,
alert ownership, latest monitoring run, legal/privacy review, rollback, and
metadata-only/no-raw-value evidence rules. The current evidence now also
verifies `llm-distill/docs/prediction-fairness-calibration-checklist.md` as a
source-controlled calibration checklist with required markers for approved
outcome data, minimum sample size, calibration run, threshold review,
human-review-only routing, no auto-denial threshold, demographic grouping,
legal/privacy review, rollback, boolean-only evidence, no raw demographic
values, and `prediction_fairness_monitoring_ready=false`. The current
evidence now also verifies
`llm-distill/docs/prediction-fairness-monitoring-validation-checklist.md` as a
source-controlled monitoring validation checklist with required markers for
approved demographic grouping, continuous monitoring configuration, disparity
threshold documentation, alert/review ownership, latest monitoring run,
legal/privacy review, rollback, boolean-only evidence, no raw demographic
values, and `prediction_fairness_monitoring_ready=false`.
The current evidence now also verifies
`llm-distill/docs/prediction-fairness-legal-privacy-checklist.md` as a
source-controlled legal/privacy checklist with required markers for approved
outcome data, demographic grouping, minimum sample size, human-review-only
routing, no auto-denial threshold, approval references outside source control,
rollback, boolean-only evidence, no raw demographic values, no production
outcome rows, and no legal/BAA/consent document text while keeping
`legal_privacy_review_completed=false`.
The current evidence now also verifies
`llm-distill/scripts/render_prediction_fairness_private_evidence.py` as a
source-controlled private evidence renderer that refuses source-control output,
requires approved outcome, sample-size, calibration, threshold-review,
monitoring, latest-run, legal/privacy, rollback, metadata-only audit, and
no-raw-value attestations before approved mode, reads private references and a
private aggregate monitoring-summary path only from environment variables,
validates required readiness booleans, positive aggregate counts, and explicit
no-raw-value flags, rejects unsupported fields or raw-value inclusion flags,
writes `0600` private output, and reports redacted booleans/counts without
storing private references, private summary paths, raw demographic values, or
production outcome rows.
The manual production-gate packet now also carries
`manual_prediction_fairness_monitoring_evidence`, including the dedicated
prediction-fairness evidence-report readiness flag plus boolean-only outcome
data, sample-size, threshold-review, demographic-grouping, monitoring,
alerting, latest-run, legal/privacy, source-controlled monitoring runbook,
source-controlled calibration checklist, source-controlled monitoring
validation checklist, source-controlled legal/privacy checklist, model-card
update, model-card-required-marker
verification, rollback, and metadata-only audit attestations. The checked-in
template now records the local model-card, runbook, calibration-checklist, and
monitoring-validation-checklist, and legal/privacy-checklist sub-gates as
ready while preserving all external production fairness blockers.
The manual production-gate packet validator now also verifies
`llm-distill/docs/phi-plan-manual-production-gate-checklist.md` as a
source-controlled manual gate checklist with required markers for student
cutover approval, user-data model-improvement approval, approved
non-synthetic denial/appeal pair evidence, semantic vector backend readiness,
production fairness evidence, manual gate private packet rendering,
file-ingestion surface audit readiness, boolean-only evidence, approval
references outside source control, no PHI or production document content, and
`production_gate_ready=false` without emitting checklist text. The manual gate
path now also includes
`llm-distill/scripts/render_phi_plan_manual_gate_private_packet.py`, a
source-controlled private packet renderer that refuses repository output,
requires explicit student cutover, student runtime, model-improvement,
production-corpus, retrieval-vector, prediction-fairness, file-ingestion,
dependent-report-readiness, and no-raw-value attestations before approved
mode, reads private manifest record ids and governance references from
environment variables only, verifies the configured supervisor,
model-improvement, production-corpus, retrieval-vector, prediction-fairness,
and file-ingestion surface reports are ready before writing a ready packet,
writes `0600` private output, and reports redacted booleans/counts while
preserving all external manual-gate blockers.
The manual production-gate packet now also carries the boolean
`model_improvement_evidence_report_ready` flag so the packet cannot pass
user-data model-improvement approval unless the dedicated evidence report has
already passed outside-source-control approval checks.
The manual production-gate packet also carries
`production_corpus_evidence_report_ready`, so its corpus section cannot pass
unless the dedicated production-corpus evidence report is ready.
The manual production-gate packet now also carries retrieval-vector backend
readiness booleans, including `vector_backend_evidence_report_ready`, so the
packet cannot pass production retrieval readiness unless the dedicated vector
backend evidence report, semantic backend configuration, production vector
backend configuration, chunk reindexing, governance review, and runtime
validation review are all attested; it also requires source-controlled reindex
checklist and private env renderer documentation without storing URLs, source
text, vector values, secrets, PHI, or production document content.
The manual production-gate packet now also carries
`manual_file_ingestion_surface_evidence`, including
`file_ingestion_surface_report_ready`, expected/registered/unregistered upload
surface counts, metadata-only surface inspection attestation, and safe audit
marker coverage attestation, so the manual packet reflects the currently ready
UploadFile/File audit without storing raw filenames or uploaded document
content.
The PHIplan production-readiness audit now also surfaces the manual packet's
metadata-only `blocked_requirement_ids`, allowing reviewers to see open manual
student cutover, model-improvement, production-corpus, retrieval-vector, and
prediction-fairness gates from the top-level readiness report without exposing
approval values, source paths, checksums, vectors, raw demographic values,
outcome rows, PHI, secrets, or production document content.
Production packaging now includes a multi-stage backend Dockerfile with a
non-root runtime user, a production frontend Dockerfile that builds Vite assets
and serves them through nginx, frontend health checks for development and
production compose paths, and a production compose file that requires secrets
and deployment approval evidence through environment variables instead of
checking values into source control. The production compose API environment now
forwards the exact startup-guard settings consumed by `app/core/config.py` for
student default cutover, student runtime auto-launch, user-data model
improvement, prediction fairness evidence, and retrieval vector backend
readiness with conservative defaults, and no longer uses the unconsumed
`CLAIMGUARD_ALLOW_MODEL_IMPROVEMENT` alias.
The PHIplan production-readiness audit now treats this production compose
environment as a current-state gate and will block `safe_current_state` if
guard variables are missing, mapped to the wrong env var, defaulted
non-conservatively, or if an unconsumed guard alias returns.
Monitoring now includes an admin-only Prometheus metrics endpoint that emits
aggregate counts and boolean PHIplan production-gate flags for student
default/auto-launch/cutover, user-data model improvement, prediction-fairness
evidence configuration, retrieval semantic/vector readiness, hash fallback, and
conservative runtime defaults without patient identifiers, provider identifiers,
claim IDs, filenames, payer names, source text, prompts, vectors, credentials,
approval references, report paths, PHI, or raw document content.
The PHIplan production-readiness audit now also verifies this metrics surface
as a current-state gate by checking required metric names, runtime Prometheus
output coverage, and absence of sentinel approval/reference/report values.
Monitoring also exposes an admin-only PHIplan readiness JSON endpoint at
`/api/v1/monitoring/phi-plan-readiness` that returns sanitized readiness counts,
requirement IDs, statuses, safe blocker/warning tokens, and no-PHI context flags
without raw report paths, evidence objects, next-action text, approval
references, PHI, document text, source text, vectors, or secrets. The PHIplan
production-readiness audit now verifies this endpoint as
`monitoring_readiness_endpoint_ready` and blocks `safe_current_state` if source
markers, runtime payload keys, safe-context flags, or raw-value protections
drift.
Analytics now includes metadata-only denial prediction accuracy tracking over
time through `/api/v1/analytics/prediction-accuracy`, returning aggregate
confusion-matrix, accuracy, precision, recall, false-positive-rate, actual
denial-rate, predicted-denial-rate, evaluated-count, and excluded-count
metrics for finalized outcomes without exposing claim IDs, patient/provider
identifiers, filenames, payer names, denial text, document text, prompts, PHI,
secrets, or production document content.
Sprint 6.2 documentation now links API authentication/RBAC requirements, EDI
837/835 format behavior and safe parser boundaries, and deployment runbook
gates under `docs/` without adding secrets, PHI, raw EDI files, or production
document content.
Operational security documentation now includes a backup and disaster recovery
runbook covering automated PostgreSQL dump procedure, off-repository encrypted
storage rules, restore verification, recovery sequence, recovery objectives,
and pre-production evidence without storing backup artifacts, credentials, PHI,
or production document content in the repository.
The public GitHub-facing README now links to a technical LLM distillation
breakdown with analysis statistics and tools used, and the repository includes
a public-doc validator that checks the link, section headings, report links,
aggregate statistics, tool references, attribution, and absence of raw local
paths, secret-shaped values, PHI-like identifiers, approval references, source
text, prompts, and production document content in those public docs.
AI safety hardening now adds local metadata-only prompt-injection detection,
untrusted-document prompt boundaries, hallucination-risk checks for unsupported
approval/payment/deadline/no-review certainty, deterministic document-analysis
fallback when NVIDIA is unavailable or empty, denial-workflow blocker
tasks/warnings/quality checks, and optional-student fallback metadata while
keeping human review and deterministic workflow controls authoritative.
Prediction fairness metadata now ties denial reasons to driver categories and
source-field families, labels the high-risk score threshold as human-review
routing rather than an auto-denial rule, and provides a demographic-parity
batch metric that reports group indexes, rates, counts, and disparity status
without raw demographic values or claim content.
Claim status handling now has a formal API/service state machine with
canonical statuses, allowed transitions, safe structured invalid-transition
errors, metadata-only audit logs, legacy read/filter compatibility for
historical analytics aliases, and canonical `draft` status for new
document-analysis-created claims instead of the legacy `analyzed` state.

---

## Executive Summary

This document tracks the implementation of ClaimGuard AI, a medical billing denial prediction and prevention system. The core MVP now uses NVIDIA NIM for document analysis, claim prediction, appeal generation, and OCR. Significant work remains for HIPAA compliance, security hardening, and production readiness.

### Vulnerability Audit Summary

| Severity | Count | Examples |
|----------|-------|----------|
| 🔴 CRITICAL | 12 | SQL injection, PHI encryption, CORS, path traversal |
| 🟠 HIGH | 27 | XSS, NPI validation, status transitions, rate limits |
| 🟡 MEDIUM | 25 | Form validation, session timeout, AI bias |
| 🟢 LOW | 5 | Accessibility, loading states |

### Priority Matrix

| Priority | Category | Items | Timeline |
|----------|----------|-------|----------|
| P0 | Security | Fix SQL injection, CORS, PHI encryption | 24 hours |
| P1 | Security | Audit logs, NPI validation, state machine | 1 week |
| P2 | Features | EDI parsers, charge master, appeal deadlines | 2 weeks |
| P3 | Production | Docker hardening, monitoring, clearinghouse | 3-4 weeks |

---

## Current Implementation Status

### ✅ Completed Features
- NVIDIA NIM document analysis with Llama Nemotron
- File upload (PDF, TXT, JPG, PNG, GIF, WebP, BMP)
- Patient CRUD with 3-identifier search safety
- Claim submission and prediction
- Appeal letter generation
- Analytics dashboard
- 299 unit tests (80% coverage)
- Source-grounded denial workflow analysis API with `known_from_documents`,
  `inferred`, `missing_needs_human_verification`, cited-rule deadlines, routing,
  evidence gaps, draft packet generation, follow-up planning, quality gates, and
  Markdown/DOCX/PDF export
- Protected denial workflow UI with de-identified text intake, source registry
  display, route/fact/deadline/evidence review, editable `draft_for_human_review`
  appeal text, and Markdown/DOCX/PDF export controls
- Persistent encrypted retrieval source store for trusted source chunks, with
  encrypted title, URL, text, section label, metadata, audited list/search
  endpoints, and denial workflow retrieval integration
- Dependency-free encrypted hybrid retrieval index with keyword ranking,
  deterministic hashed retrieval vectors, and `hybrid`/`keyword`/`embedding`
  search modes for persisted source chunks
- Offline synthetic workflow evaluation harness for baseline route, denial-type,
  human-review, required-behavior, forbidden-phrase, draft-label, and quality
  check scoring before fine-tuning
- Synthetic distillation data preparation harness that writes supervised seed
  records, teacher-label request batches, and a dataset card for later
  large-teacher review
- Guarded teacher-label batch runner that validates teacher request JSONL,
  reads teacher endpoint settings from runtime-only env/arguments, and keeps raw
  teacher response JSONL ignored until ingestion validation passes
- MLX-LM SFT seed export that writes chat-format train/valid/test JSONL, a
  LoRA command manifest, and adapter-output guardrails while labels remain
  pending review
- Local MLX-LM benchmark harness for synthetic prompt scoring, JSON/output
  contract checks, latency/throughput capture, and endpoint availability
  reports
- Teacher-label ingestion gate that validates completed large-teacher or
  human-reviewed JSONL before replacing deterministic seed labels
- Guarded MLX-LM LoRA fine-tune preflight/run harness that validates reviewed
  training permission, split-file shape, PHI scan results, and local
  `mlx_lm.lora` availability before any adapter training can run
- Student-model acceptance gate that refuses adapter promotion unless
  deterministic workflow regression, successful LoRA run evidence, full live
  base/student benchmarks, score comparison, and PHI scan checks all pass
- Reviewed-label distillation pipeline runner that orchestrates teacher
  response validation, reviewed-label ingestion, reviewed MLX SFT export,
  guarded LoRA fine-tuning, and student acceptance reporting
- Full synthetic seed coverage for ClaimGuard micro-skills MS01-MS12, including
  provider authority validation and unfavorable response / next-level outcome
  analysis, with MLX SFT manifest coverage gates
- Distillation readiness audit that prevents the larger-teacher to lightweight
  ClaimGuard student-model goal from being marked complete until reviewed
  labels, reviewed SFT export, local LoRA training, live benchmarks, student
  acceptance, quantization readiness, and PHI-safety evidence are all present
- Offline teacher/human review packet generator for the 10-record synthetic
  seed set, with pending-label preservation, required safety attestations,
  PHI-scan reporting, and blocked response export until labels are approved
- Synthetic large-teacher review helper for the 10-record synthetic/no-PHI
  packet, with schema, source-status, citation, human-review gate, and PHI
  checks before labels can be approved for local SFT experiments
- Reviewed-label MLX-LM LoRA run for `Qwen/Qwen3-4B-MLX-4bit` that produced
  `adapters.safetensors` under the ignored reviewed adapter path
- Strict ClaimGuard benchmark/runtime prompt contract
  `strict_claim_guard_json_v1`, covering required JSON keys, array-typed
  source-status groups, object-based `draft_sections`, human-review draft
  markers, and the reviewed-label denial-type taxonomy
- Passing live base and reviewed student-adapter MLX benchmarks over all 10
  synthetic scenarios, each scoring 58/60 with no JSON, required-key,
  human-review, or draft-marker gate failures
- Passing student-model acceptance report and top-level distillation readiness
  audit for the reviewed `Qwen/Qwen3-4B-MLX-4bit` LoRA adapter path
- API/backend integration for accepted distilled student status, strict schema
  contract metadata, and `denial_skill` P01-P15 phase checklist in every denial
  workflow response
- Frontend visibility for accepted student status, benchmark score, strict
  schema contract, and phase-by-phase workflow status before export
- Full-set base MLX benchmark evidence over the 10-record synthetic scenario
  set; current report correctly shows the local endpoint is unavailable and not
  a passing model-quality result
- MLX runtime preflight report that checks Apple Silicon host shape, `mlx-lm`
  package presence, `mlx_lm.server`/`mlx_lm.lora`/`mlx_lm.generate` CLI
  availability, and local `/v1/models` server reachability before benchmarks or
  LoRA training
- Project-local MLX-LM bootstrap that installs `mlx-lm` into `.venv-mlx`,
  refreshes runtime/fine-tune/readiness evidence, and keeps model download,
  server startup, LoRA training, benchmarks, quantization, PHI/PII, and secrets
  outside the bootstrap path
- Live base-model MLX benchmark over the full 10-record synthetic ClaimGuard
  scenario set for `Qwen/Qwen3-4B-MLX-4bit`, with endpoint availability,
  latency, throughput, and output-contract scoring captured before any student
  adapter promotion
- Optional MLX-LM OpenAI-compatible local model configuration targeting
  `Qwen/Qwen3-4B-MLX-4bit` with `Qwen/Qwen3-1.7B` fallback metadata
- Live runtime status and launch-command metadata for the accepted reviewed
  LoRA adapter, surfaced through the student-status API, app health check,
  backend workflow metadata, and denial workflow UI without making MLX a hard
  dependency unless explicitly configured as the default
- Metadata-only PHI/PII scan controls for denial workflow intake and export
  packets, including no-value scanner findings, minimum-necessary privacy
  review blockers, and retrieval-source gates for `no_phi`/`deidentified`
  declarations
- Safe corpus/de-identification backend slice with manifest schemas, intake
  states, stable placeholder replacement, residual-risk scoring, training
  eligibility blockers, status/validate/deidentify/import endpoints, and a
  starter corpus manifest
- Frontend corpus readiness panel showing manifest availability,
  training-eligible counts, blocked counts, missing categories, and export
  readiness
- Manifest-gated corpus SFT exporter that reads the safe corpus manifest,
  exports only `training_eligible=true` de-identified/reviewed denial plus
  appeal pairs, verifies checksums and zero PHI/PII scan findings, preserves
  `pair_id` metadata, and reports MS01-MS12 plus payer/denial/route/outcome
  coverage before allowing training
- Top-level distillation readiness audit now blocks production release/default
  student readiness until the safe corpus manifest and guarded corpus SFT export
  pass; the existing synthetic reviewed adapter remains visible but is not
  enough for `accepted_for_denial_workflow=true`
- Document-surface corpus inspection API that checks source filename, visible
  text, hidden text, OCR/scanned-page text, headers/footers, metadata,
  barcode/QR text, and attachment filenames without returning matched values
- Synthetic no-PHI corpus starter with three denial/appeal pairs across
  train/valid/test, checksum-verified manifest records, complete MS01-MS12
  coverage, guarded corpus SFT export evidence, and a top-level readiness audit
  that now passes while keeping default student use disabled until Raphael
  approves production cutover
- Denial Workflow admin controls for encrypted retrieval-source creation,
  privacy-review and model-improvement attestations, stored-source visibility,
  document-surface inspection, machine de-identification, and approved
  de-identified corpus import with backend review-decision gating before the
  import endpoint is invoked
- Metadata-only retrieval vector-readiness status for admins, including
  embedding backend/model, vector backend, hash-fallback status, active chunk
  count, reindex blockers, UI visibility, and PHIplan production-readiness audit
  blocking until a real semantic/vector backend is configured
- Role-scoped encrypted retrieval-source governance with `owner`,
  `billing_team`, and `admin_only` access scopes, active-source filtering for
  list/search/workflow retrieval, soft-retire metadata, retention-expiration
  reporting, an admin retrieval audit feed, and Denial Workflow UI controls for
  access scope, retention dates, governance counts, and source retirement
- Disabled-by-default user-data model-improvement compliance gate with runtime
  legal/BAA/consent readiness settings, request-level attestations, a status
  endpoint, Denial Workflow UI readiness display, and corpus import that no
  longer silently sets `user_data_opt_in_for_model_improvement`
- Production startup guard for user-data model improvement that checks the
  configured evidence report only when the feature is enabled, fails fast in
  production on missing legal/BAA/consent/reference/evidence readiness, and logs
  booleans plus blocker IDs without raw approval references, consent versions,
  evidence content, PHI, secrets, or user data
- Automated claim-document upload surface inspection that reuses the corpus
  inspection service for source filename, MIME type, extracted visible/OCR
  text, and safe processing metadata, then returns a redacted inspection summary
  and displays surface status in the Claims UI
- Legacy claim-document governance for stored `Claim.document_text` records,
  including access scopes, retention timestamps, soft-retire metadata, a
  governance summary, an admin audit dashboard with whitelisted safe details,
  filename-safe upload audit metadata, redacted claim list/detail responses,
  and Dashboard document-status visibility
- Supervised student-default cutover gate with explicit Raphael approval
  attestation, approval-reference configuration, supervised MLX runtime
  configuration, runtime-health gating, effective/default distinction,
  rollback-to-NVIDIA override, Denial Workflow UI blocker visibility, and
  refreshed distillation readiness-audit next actions
- Production prediction fairness startup guard that checks
  `PREDICTION_FAIRNESS_EVIDENCE_REPORT`, fails fast in production while
  threshold calibration/fairness evidence is blocked, and logs booleans plus
  blocker IDs without report paths, raw demographic values, production outcome
  rows, PHI, secrets, or claim values

### LLM Distillation Follow-Up Items
- [x] Backend source-grounded denial workflow API and export scaffolding
- [x] Frontend provider-staff review, edit, and export workflow
- [x] Persistent encrypted retrieval source/chunk store
- [x] Local encrypted hybrid retrieval index with stored hashed vectors
- [x] Offline synthetic workflow baseline evaluation harness
- [x] Synthetic supervised seed and teacher-label request generation
- [x] Guarded teacher-label batch runner for large-teacher review
- [x] MLX-LM SFT train/valid/test seed export with pending-label training block
- [x] Local MLX-LM benchmark harness with synthetic prompt scoring and
  availability reports
- [x] Teacher-label ingestion and validation gate
- [x] Guarded MLX-LM LoRA fine-tune preflight/run harness
- [x] Student-model acceptance gate for promotion/quantization readiness
- [x] Reviewed-label distillation pipeline orchestration runner
- [x] Synthetic seed coverage for required `denial_skill` MS01-MS12 micro-skills
- [x] Full distillation readiness audit with explicit blocked evidence
- [x] Offline teacher/human review packet for pending synthetic labels
- [x] Synthetic large-teacher review and reviewed-label export for the
  10-record synthetic/no-PHI packet
- [x] Reviewed MLX SFT export with `training_allowed=true`
- [x] Successful guarded reviewed-label LoRA run producing a local adapter
- [x] Live student-adapter MLX benchmark over all 10 synthetic scenarios
- [x] Full-set base MLX benchmark attempt over all 10 synthetic scenarios
- [x] MLX runtime/server preflight report
- [x] Project-local MLX-LM package and CLI bootstrap for `.venv-mlx`
- [x] Successful live base MLX benchmark results on the target M1 iMac
- [x] Strict benchmark/runtime schema contract for ClaimGuard student outputs
- [x] Passing student acceptance report and quantization/promotion readiness
  gate for the reviewed LoRA adapter
- [x] API endpoint exposing accepted distilled student readiness and contract
  evidence for ClaimGuard denial workflow use
- [x] Backend denial workflow response includes `denial_skill` P01-P15 phase
  checklist and accepted student contract metadata
- [x] Frontend denial workflow page displays accepted student status and
  phase-by-phase provider-staff workflow controls
- [x] Runtime status and launch-command metadata for the accepted reviewed LoRA
  adapter
- [x] Metadata-only PHI/PII scanner and source-ingestion declaration gates for
  denial workflow safety
- [x] Corpus manifest, machine de-identification, approved-import gates, and
  corpus readiness status for safe training-data expansion
- [x] Local-only contextual re-identification risk review for rare facts,
  age/geography/timeline/public-uniqueness cues, and unusual dollar amounts
  in corpus de-identification and document-surface inspection
- [x] Manifest-gated approved corpus SFT export for de-identified denial/appeal
  pairs with coverage and PHI/checksum blockers
- [x] Corpus manifest and corpus SFT export requirements wired into the
  top-level distillation readiness audit
- [x] Document-surface PHI/PII inspection for PDF/OCR/metadata/barcode/footer
  and attachment-filename surfaces
- [x] Starter synthetic no-PHI denial/appeal corpus records and guarded
  `mlx_sft_corpus` export evidence
- [x] Admin UI controls for retrieval-source creation, privacy-review
  attestation, document-surface inspection, and approved de-identified corpus
  import
- [x] Role-scoped retrieval-source access, retention/soft-deletion workflow,
  governance summary, and admin retrieval audit dashboard for encrypted stored
  source documents
- [x] User-data model-improvement legal/BAA/consent gate with disabled default,
  request attestations, readiness status, and no automatic corpus opt-in
- [x] Document-surface PHI/PII inspection wired into `/api/v1/claims/upload-document`
  file ingestion with redacted response/audit metadata and Claims UI visibility
- [x] Legacy claim-document retention, soft deletion, access scoping, and
  metadata-only audit/governance coverage for stored `Claim.document_text`
  records
- [x] Student default cutover approval, runtime-supervision, runtime-health, and
  rollback gates before `CLAIMGUARD_STUDENT_USE_BY_DEFAULT` can become
  effective
- [x] Public/government no-PHI corpus source notes in the versioned manifest,
  excluded from MLX SFT export unless they become approved paired
  denial/appeal training examples
- [x] Public source note coverage audit for all seven no-PHI source-registry
  entries with checksum coverage, required safety/use markers, zero PHI
  findings, and `training_eligible=false`
- [x] Guarded corpus SFT MLX fine-tune preflight report with no training run
  or adapter weights written
- [x] MLX fine-tune run gate blocks corpus-derived adapter training unless the
  production corpus evidence report is safe and ready
- [x] Automated file-ingestion surface audit wired into readiness evidence for
  future `UploadFile` endpoint coverage
- [x] EDI 837 batch upload endpoint registered in the file-ingestion audit with
  `.edi`/`.txt` validation, 10 MB limit, pre-parse claim-count and
  segment-count guards, metadata-only document-surface inspection, safe audit
  counters, and structured per-claim parser results without raw segment
  payloads
- [x] EDI 835 remittance upload endpoint registered in the file-ingestion audit
  with `.835`/`.edi`/`.txt` validation, 10 MB limit, metadata-only
  document-surface inspection, safe audit counters, and parsed
  payment/adjustment/remark summaries without raw patient or payer control
  numbers
- [x] Metadata-only PHI access audit hardening for patient, claim, analytics,
  and appeal routes, with audit utility redaction for sensitive keys and
  PHI/PII-like values
- [x] Generated 900 varied synthetic denial/appeal pairs with documented
  format/layout/typography/length profiles, rendered HTML font/layout
  companions, file-level format/variation audit evidence, guarded SFT export,
  and MLX fine-tune preflight evidence
- [x] MLX fine-tune runtime gate blocks synthetic-900 adapter training before
  writes when the current session cannot access a Metal device
- [x] Top-level readiness audit covers the synthetic-900 corpus, letter tree,
  file-level format/variation audit, SFT export, and no-Metal guarded run
  evidence
- [x] Synthetic-900 visual-layout evidence covers 1,800 rendered HTML
  companions, eight actual CSS font-family stacks, twelve layout wrappers, and
  zero PHI findings for visual/OCR-style stress tests
- [x] Synthetic-900 format audit enforces role-by-profile and split-by-profile
  coverage so denial letters, appeal letters, train, valid, and test all
  exercise layout, typography, and length variants
- [x] Synthetic-900 appeal-quality audit enforces draft, human-review,
  not-filing-ready, source-grounding, deadline/citation-safety,
  PHI-minimization, route-correctness, appeal-level, and denial-type alignment
  controls across all 900 generated appeal drafts
- [x] Synthetic-900 document-analysis extraction audit verifies all 900
  generated denial notices parse through the application extractor for payer,
  denial rationale, billed amount, and procedure code without extracting
  synthetic placeholders as patient or policy identifiers
- [x] Synthetic mock-denial upload API smoke verifies the checked-in
  900-denial/900-appeal visual manifest and feeds twelve representative
  rendered denial notices, one per layout profile, through the authenticated
  `/api/v1/claims/upload-document` route with metadata-only surface inspection
  and `billing_team` document access scope
- [x] Separate PHIplan production-readiness audit report distinguishing safe
  current defaults from blocked production gates
- [x] Boolean-only manual production-gate packet template, validator, and report
  wired into the PHIplan production-readiness audit
- [x] Source-controlled manual production-gate checklist validation with
  required student cutover, model-improvement, production corpus,
  retrieval-vector, prediction-fairness, file-ingestion surface, boolean-only,
  no-approval-reference, no-PHI, and `production_gate_ready=false` markers
  before marking the checklist sub-gate ready
- [x] Manual production-gate packet now has a source-controlled private packet
  renderer that refuses repository output, requires explicit manual gate and
  dependent-report attestations for approved mode, reads private manifest record
  ids and governance references from environment variables only, writes `0600`
  private output, and reports redacted booleans/counts while preserving external
  manual-gate blockers
- [x] Manual production-gate private packet renderer approved mode now refuses
  a ready packet unless the configured supervisor, model-improvement,
  production-corpus, retrieval-vector, prediction-fairness, and file-ingestion
  surface reports are safe or otherwise metadata-ready, ready, and unblocked
- [x] Boolean-only MLX runtime supervisor template, validator, and report wired
  into manual gate and PHIplan production-readiness blockers
- [x] MLX runtime supervisor operator-control evidence attests restart-policy
  review, health-check review, manual-start command review, rollback review,
  source-controlled runbook documentation, and environment-file exclusion while
  leaving runtime owner and live runtime validation blocked
- [x] Non-installing MLX private launchd renderer that refuses source-control
  output paths and emits only redacted booleans/counts for private operator use
- [x] MLX runtime supervisor now has a source-controlled private evidence
  renderer that refuses repository output, requires runtime owner, private
  launchd copy, restart-policy, health-check, manual-start, rollback,
  environment-file exclusion, preflight, status endpoint, runtime health,
  launchd load, restart-test, and no-raw-value attestations for approved mode,
  reads private plist/review references from environment variables only, writes
  `0600` output, and reports redacted booleans/counts while preserving live
  runtime owner and validation blockers
- [x] MLX runtime supervisor evidence validates a source-controlled runtime
  validation checklist with required MLX preflight, student status endpoint,
  runtime health, launchd load, restart-test, rollback, boolean-only, and
  no-raw-output markers before marking the checklist sub-gate ready
- [x] Manual production-gate packet propagates the student runtime validation
  checklist documentation as boolean-only ready evidence while leaving
  production student cutover and live runtime validation blocked
- [x] Student-default startup guard fails fast in production if default student
  routing is requested before release, approval, runtime supervision, runtime
  health, and rollback-off gates are ready
- [x] Metadata-only corpus review-decision API that blocks training approval
  until privacy/license/residual-risk/expert-determination review gates pass
- [x] Denial Workflow UI review-decision gate that sends metadata-only review
  attestations before invoking approved corpus import
- [x] Metadata-only corpus manifest review queue endpoint and admin UI panel
  showing review blockers, pair completeness, production-corpus candidacy, and
  next actions without source text, source paths, checksums, or matched values
- [x] Metadata-only production semantic/vector-readiness gate that keeps the
  local hash embedding fallback from being mistaken for production semantic
  retrieval
- [x] Boolean-only retrieval vector backend evidence template, validator, and
  report wired into PHIplan production-readiness blockers
- [x] Retrieval vector backend evidence validates source-controlled operator
  runbook, reindex checklist, and runtime smoke checklist procedures without
  storing source text, vector values, service URLs, credentials, PHI, or
  production document content
- [x] Retrieval vector backend evidence now has a source-controlled private env
  renderer that refuses repository output, requires semantic backend, approved
  embedding model, production vector backend, hash-fallback disablement,
  reindex, vector health, retrieval quality smoke, rollback, and no-raw-value
  attestations for approved mode, reads private backend/model/vector labels
  from environment variables only, writes `0600` output, and reports redacted
  booleans/counts while preserving external vector readiness blockers
- [x] Retrieval vector startup and default service construction now use a
  source-controlled private semantic provider loader that keeps the hash
  fallback as the default, requires approved private semantic runtime settings
  for non-hash providers, allows only HTTPS or loopback endpoints, and reports
  redacted booleans/blocker codes without storing endpoint values, tokens,
  source text, vector values, PHI, secrets, or production document content
- [x] Retrieval vector backend evidence now has a source-controlled private
  runtime evidence renderer that refuses repository output, requires semantic
  backend, approved embedding model, production vector backend, hash-fallback
  disablement, reindex, vector health, retrieval quality smoke, backup,
  rollback, and no-raw-value attestations for approved mode, writes `0600`
  private JSON, and reports redacted booleans/counts while preserving external
  vector readiness blockers
- [x] Retrieval vector runtime private evidence renderer approved mode validates
  a private aggregate runtime summary for required readiness booleans, positive
  counts, no-raw-source/vector/endpoint/credential flags, and unsupported-field
  rejection before writing ready private evidence
- [x] Metadata-only retrieval embedding reindex operation for approved private
  semantic providers, with dry-run default, aggregate-only response, safe audit
  details, and non-dry-run hash-provider refusal
- [x] Boolean-only production corpus evidence template, validator, and report
  wired into PHIplan production-readiness blockers
- [x] Production corpus evidence now has a source-controlled private evidence
  renderer that refuses repository output, requires approved non-synthetic
  pair, privacy, license, residual-risk, training-scope, no-PHI,
  source/license, pair-id, source-document, metadata-only manifest,
  no-raw-document, and no-raw-value attestations for approved mode, reads
  private manifest/review references from environment variables only, serializes
  only the private manifest-path env var name, writes `0600` output, and reports
  redacted booleans/counts while preserving external non-synthetic-pair
  blockers
- [x] Boolean-only user-data model-improvement evidence template, validator,
  and report wired into PHIplan production-readiness blockers
- [x] Boolean-only prediction fairness monitoring evidence template, validator,
  and report wired into PHIplan production-readiness blockers
- [x] Prediction fairness evidence validates a source-controlled model card
  with required human-review-only threshold, no-auto-denial, approved outcome
  data, calibration, continuous monitoring, and no-raw-value safety markers
  before marking the model-card governance sub-gate ready
- [x] Prediction fairness evidence validates a source-controlled monitoring
  runbook with required approved outcome data, sample size, calibration,
  continuous monitoring, latest-run, legal/privacy, rollback, and
  metadata-only evidence markers before marking the runbook sub-gate ready
- [x] Prediction fairness evidence validates a source-controlled calibration
  checklist with required approved outcome data, minimum sample size,
  calibration run, threshold review, human-review-only routing, no-auto-denial,
  demographic grouping, legal/privacy, rollback, boolean-only, and no-raw-value
  markers before marking the checklist sub-gate ready
- [x] Prediction fairness evidence validates a source-controlled legal/privacy
  checklist with required outside-source-control approvals, approved outcome
  data, demographic grouping, human-review-only routing, no-auto-denial,
  rollback, boolean-only, and no-raw-value markers before marking that
  documentation sub-gate ready
- [x] Prediction fairness evidence now has a source-controlled private
  evidence renderer that refuses repository output, requires approved outcome,
  sample-size, calibration, threshold-review, monitoring, latest-run,
  legal/privacy, rollback, metadata-only audit, and no-raw-value attestations
  for approved mode, reads private references from environment variables only,
  writes `0600` output, and reports redacted booleans/counts while preserving
  external fairness blockers
- [x] Manual production-gate packet propagates the prediction-fairness
  model-card update, monitoring-runbook documentation, calibration-checklist
  documentation, monitoring-validation documentation, legal/privacy-checklist
  documentation, private-evidence-renderer documentation, and required-marker
  verification as boolean-only ready evidence while leaving production fairness
  monitoring blocked
- [x] User-data model-improvement evidence marks local runtime controls ready
  for per-request attestations, approved-corpus import opt-in blocking, safe
  audit logging review, and frontend blocker visibility while leaving legal
  approvals blocked
- [x] Model-improvement private env renderer approved mode now refuses to write
  an enabled private env unless the configured model-improvement evidence
  report is safe to review, ready, and unblocked, preserving startup guard
  parity while keeping legal approvals blocked
- [x] User-data model-improvement evidence marks local governance controls
  ready for source-controlled approval runbook documentation, data-use scope
  documentation, retention review, and revocation-path review while keeping
  request, legal approval, BAA, consent notice, and approval reference gates
  blocked
- [x] User-data model-improvement now has a source-controlled private env
  renderer that refuses repository output, requires legal/BAA/consent/request/
  retention/revocation/per-request/evidence-readiness attestations for approved
  mode, reads approval and consent values from private environment only, writes
  `0600` output, and reports redacted booleans/counts while preserving external
  approval blockers
- [x] User-data model-improvement evidence requires explicit safety-boundary
  attestations for disabled external PHI de-identification, disabled raw PHI
  training, production user-data exclusion until approval, ready evidence
  packets for training jobs, and revocation blocking future training use
- [x] User-data model-improvement production startup guard with metadata-only
  logging and fail-fast behavior when production enablement is requested before
  legal, BAA, consent, approval-reference, and evidence gates are ready
- [x] Manual production-gate packet requires
  `model_improvement_evidence_report_ready` before user-data model-improvement
  evidence can pass
- [x] Manual production-gate packet requires
  `production_corpus_evidence_report_ready` before production corpus evidence
  can pass
- [x] Manual production-gate packet requires
  `vector_backend_evidence_report_ready` and retrieval-vector readiness
  attestations before production semantic retrieval evidence can pass
- [x] Manual production-gate packet requires
  `prediction_fairness_evidence_report_ready` and production threshold/fairness
  monitoring attestations before fairness monitoring evidence can pass
- [x] Prediction fairness private evidence renderer approved mode validates a
  private aggregate monitoring summary for required readiness booleans,
  positive counts, no-raw-value flags, and unsupported-field rejection before
  writing ready private evidence
- [x] Production prediction fairness startup guard with metadata-only logging
  and fail-fast behavior when production starts before threshold calibration,
  continuous monitoring, and governance evidence are safe and ready
- [x] Retrieval vector backend evidence marks local governance controls,
  source-controlled runbook documentation, private-env-renderer documentation,
  backup/restore review, and rollback/disable-path review ready while keeping
  semantic backend, production vector store, reindexing, health, and quality
  smoke checks blocked
- [x] Retrieval vector private env renderer approved mode now refuses enabled
  production vector settings unless the configured retrieval/vector backend
  evidence report is safe, ready, and unblocked
- [x] Production corpus evidence marks current checked-in manifest review
  attestations and source-controlled review runbook documentation ready while
  keeping approved non-synthetic paired denial/appeal source and
  outside-source-control review gates blocked
- [x] Production corpus evidence validates source-controlled
  collection/license checklist documentation with required source inventory,
  source category, license terms, terms-of-use, payer policy reuse
  restrictions, public/real de-identified source scope, collection owner,
  privacy, license, residual-risk, training-scope, no-PHI, boolean-only, and
  no-raw-value markers while keeping actual corpus collection approval blocked
- [x] Production corpus evidence validates source-controlled pair/source
  checklist documentation with required denial/appeal roles, shared pair id,
  outside-source-control pair/source review, privacy, license, residual-risk,
  training-scope, no-PHI, source license scope, boolean-only, and no-raw-value
  markers while keeping approved non-synthetic paired denial/appeal source
  gates blocked
- [x] Production corpus private evidence renderer approved mode now validates
  private manifest metadata for at least one approved non-synthetic
  denial/appeal pair before writing ready evidence, while keeping the private
  manifest path and review references out of checked-in evidence and command
  summaries
- [x] Manual production-gate packet carries ready file-ingestion surface audit
  evidence with three registered upload surfaces, zero unregistered surfaces,
  and metadata-only PHI surface/safe-audit-marker attestations
- [x] PHIplan production-readiness report includes manual packet
  `blocked_requirement_ids` without exposing raw values
- [x] PHIplan production-readiness report includes dependent report
  `blocked_requirement_ids` for runtime supervisor, model-improvement,
  retrieval-vector backend, production-corpus, and prediction-fairness gates
  without exposing raw values
- [x] PHIplan production-readiness report includes the file-ingestion surface
  audit as a top-level current-state gate with three registered upload surfaces
  and zero unregistered surfaces
- [x] Production Docker/nginx packaging scaffolding with frontend health checks
  and production compose startup-guard environment parity for student default,
  student auto-launch, model-improvement, prediction-fairness, and retrieval-vector gates
  and required runtime environment variables
- [x] PHIplan production-readiness audit covers production compose startup-guard
  env parity and blocks `safe_current_state` on missing guard variables,
  non-conservative defaults, wrong env references, or unconsumed aliases
- [x] Student runtime auto-launch flag is consumed by app settings and startup
  guard logic, with production fail-fast behavior until supervised runtime
  evidence is ready
- [x] MLX runtime supervisor validator requires an allowlisted launchd
  environment surface, `CLAIMGUARD_RUNTIME_PROFILE` set to the local-only
  student-denial workflow profile, no secret/proxy-shaped environment names,
  and no raw environment values in reports
- [x] MLX runtime supervisor validator requires the source-controlled operator
  runbook to exist with local-only runtime, private-copy, rollback, and
  no-raw-value markers before that local documentation sub-gate is ready
- [x] MLX runtime supervisor validator requires the source-controlled runtime
  validation checklist to exist with preflight, status, health, launchd load,
  restart, rollback, boolean-only, and no-raw-output markers before that local
  documentation sub-gate is ready
- [x] MLX runtime supervisor validator requires the source-controlled owner
  handoff checklist to exist before any private runtime owner assignment can
  clear the student cutover documentation sub-gate
- [x] MLX runtime supervisor validator requires the source-controlled private
  evidence renderer before private runtime owner and validation evidence can
  clear the supervisor-ready gate
- [x] MLX runtime supervisor private evidence renderer approved mode now parses
  the private launchd plist and rejects non-loopback hosts, missing
  MLX server/adapter/port arguments, unsafe runtime profiles, missing launchd
  operational settings, and unapproved or secret-like environment keys before
  writing ready private evidence
- [x] Student default cutover now has a source-controlled private env renderer
  that refuses repository output, requires approval/runtime/distillation/
  rollback attestations for approved-cutover mode, reads the approval reference
  from private environment only, writes `0600` output, and reports redacted
  booleans/counts while preserving private approval/runtime blockers
- [x] Student default cutover private env renderer approved mode now refuses
  enabled student-default or auto-launch settings unless the configured MLX
  runtime supervisor evidence report is safe, ready, and unblocked
- [x] Retrieval source ingestion has an injectable semantic embedding provider
  boundary while keeping the default hash fallback and production vector
  blockers in place until private backend/reindex evidence is ready
- [x] Admin-only Prometheus metrics endpoint with aggregate counts, PHIplan
  production-gate safety flags, and no raw PHI/document labels or approval
  reference values
- [x] PHIplan production-readiness audit covers required Prometheus PHIplan
  gate metrics and blocks `safe_current_state` if the metrics surface drifts or
  emits raw approval/reference/report values
- [x] Admin-only PHIplan readiness JSON endpoint with sanitized requirement
  IDs, counts, statuses, safe blocker tokens, no raw evidence/report paths, and
  PHIplan production-readiness audit coverage
- [x] Metadata-only denial prediction accuracy tracking endpoint with
  aggregate time buckets, confusion-matrix metrics, finalized-outcome
  filtering, safe audit counters, and no claim IDs, patient/provider
  identifiers, filenames, payer names, denial text, document text, prompts,
  PHI, secrets, or production document content
- [x] Sprint 6.2 API authentication/RBAC, EDI 837/835 format, and deployment
  guide documentation under `docs/`, linked from `README.md`, with production
  readiness still blocked by the PHIplan manual gates
- [x] Backup and disaster recovery runbook with off-repository encrypted
  backup storage rules, automated dump procedure, restore verification, and
  metadata-only evidence guidance
- [x] Public GitHub README link to a technical LLM distillation breakdown with
  analysis statistics and tools used, plus validator coverage for link
  presence, report links, aggregate stats, tool markers, attribution, and
  redacted public documentation posture
- [x] AI safety guardrails for prompt-injection-like document instructions,
  hallucination-risk certainty language, and metadata-only NVIDIA unavailable
  fallback in document analysis and denial workflow
- [x] Claim state machine service and `/api/v1/claims/{claim_id}/status`
  transition endpoint with canonical write statuses, safe structured transition
  errors, metadata-only audit logging, and legacy read/filter compatibility
- [x] Database-backed claim status constraints with non-null canonical
  `claims.status`, legacy-status migration normalization, and a named Alembic
  check constraint that keeps direct database writes aligned with the
  application state-machine contract
- [x] Healthcare code validation for claim ICD-10-CM and CPT/HCPCS formats,
  local NPI check-digit utility coverage, EDI 837 diagnosis/procedure code
  warnings, and EDI 835 CARC/RARC validation with metadata-only errors
- [x] Diagnosis/procedure linkage metadata validation for direct claim
  prediction/submission and EDI 837 professional service-line diagnosis
  pointers, without asserting clinical medical necessity or payer-specific
  policy correctness
- [x] Versioned local CARC/RARC lifecycle seed database for EDI 835 CAS/LQ
  parsing, with metadata-only active/inactive/unconfirmed status, safe
  category enrichment, and known-inactive seed-code rejection without storing
  official long-form descriptions or claiming a comprehensive licensed feed
- [x] Administrative healthcare code-set validation for EDI 837
  place-of-service, claim-frequency, and service-line revenue-code fields, with
  parser-safe issue metadata and batch-upload response fields
- [x] Appeal deadline tracking metadata on appeal generation, including
  structured claim/deadline-table date handling, urgent/past-due summaries,
  safe audit counters, fallback-letter deadline-review language, and
  human-review-required defaults
- [x] Required claim submission fields for payer, subscriber, and service date,
  enforced before prediction/persistence with metadata-only 400 errors and
  safe validation audit counters
- [x] Future patient date-of-birth and negative structured claim amount
  validation, enforced before patient persistence, denial prediction, or claim
  submission with metadata-only field errors and safe audit context
- [x] Frontend XSS hardening with DOMPurify-backed safe rendering for
  model-generated and user-supplied review output in Claims, Appeals, and
  Denial Workflow surfaces, with direct HTML insertion isolated to
  `frontend/src/components/common/SafeHtml.tsx`
- [x] Human-in-the-loop gate for high-risk claim predictions and submissions,
  including API response metadata, metadata-only audit flags, dashboard/claim
  review indicators, and synthetic regression coverage
- [x] Structured charge-master and contract-rate claim pricing checks, using
  explicit structured claim metadata and procedure-code maps only, with CO-45
  and charge-master denial drivers that exclude raw dollar values from
  serialized findings and prediction reasons
- [ ] Production semantic embeddings/vector backend, corpus ingestion, and review workflow
- [ ] Production packaging/default-model switch for a promoted local student
  adapter, if Raphael wants the app to load it by default
- [ ] Production process supervisor/auto-launch for `mlx_lm.server` with the
  reviewed LoRA adapter outside interactive validation sessions
- [ ] When introducing any future automated file-ingestion document repository,
  register it in the file-ingestion surface audit, implement retention/deletion
  and audit controls in code, and reconcile user-data opt-in with legal, BAA,
  and consent requirements before production use
- [ ] Configure real production legal approval reference, BAA confirmation, and
  consent notice version, then rerun
  `llm-distill/scripts/validate_model_improvement_evidence.py`, before any
  production user-data model-improvement use; then render the private
  model-improvement env file outside source control. The startup guard now
  rejects production enablement while the evidence report remains blocked
- [ ] Configure Raphael-approved production student cutover reference and
  supervised runtime ownership outside source control, verify the configured
  MLX runtime supervisor evidence report is safe, ready, and unblocked, then
  render the private student-cutover env file outside source control before
  enabling effective default student use
- [ ] Keep document-surface inspection and the file-ingestion surface audit
  ready for any additional future automated file-ingestion workflow beyond
  claim-document upload, EDI 837 batch upload, and EDI 835 remittance upload
- [ ] Clear `llm-distill/evals/reports/phi_plan_production_readiness_report.json`
  blockers before treating PHIplan production readiness as complete
- [ ] Complete and validate the manual production-gate packet with no raw
  approval references, PHI, secrets, or production document content, including
  the source-controlled manual gate checklist, the private manual-packet
  renderer, and the dedicated model-improvement, production-corpus,
  retrieval-vector, and prediction-fairness evidence-report readiness flags.
  Local progress: the private manual-packet renderer now also verifies
  configured dependent evidence reports before writing a ready packet.

### ❌ Not Implemented (Required for Production)
- JWT Authentication & RBAC
- EDI 837 clearinghouse claim submission
- EDI 835 remittance parser
- PHI encryption at rest
- Comprehensive audit logging
- Production charge master feed integration

---

## Priority 1: NVIDIA NIM Document Analysis (Critical) ✅ COMPLETED

### Solution Implemented
- **Current**: NVIDIA NIM API with `nvidia/llama-3.3-nemotron-super-49b-v1.5`
- OCR uses `nvidia/nemotron-parse`
- Document analysis saves to database with original text
- View original document feature in dashboard

## Priority 2: File Processing (NEW) ✅ COMPLETED

### Features Implemented
- **Image support**: JPG, PNG, GIF, WebP, BMP, TIFF
- **Auto-resize**: Images larger than 4096px are resized
- **Compression**: JPEG quality optimization (85%), PNG compression
- **Format conversion**: Images converted to JPEG for consistency
- **PDF compression**: Large PDFs compressed automatically
- **OCR support**: Images and scanned PDFs processed with NVIDIA Nemotron Parse

### Supported File Types
| Type | Extension | Processing |
|------|-----------|------------|
| PDF | .pdf | Text extraction, compression |
| Text | .txt, .text, .denial | Direct text |
| Image | .jpg, .jpeg, .png, .gif, .webp, .bmp, .tif, .tiff | NVIDIA Nemotron Parse extraction |

## Priority 3: Patient Search (NEW) ✅ COMPLETED

### Features Implemented
- **Search by first name**: Case-insensitive partial match
- **Search by last name**: Case-insensitive partial match
- **Search by DOB**: Exact date match
- **Combined filters**: All filters can be used together
- **Patient management**: CRUD operations for patients
- **Medical safety**: Minimum 3 identifiers required for patient searches

### Patient Safety Validation ⚠️ NEW
Medical claims require minimum 3 identifiers to prevent patient misidentification:
- Valid combinations: MRN + DOB + Last Name, or MRN + First Name + Last Name, etc.
- Patient ID + First Name + Last Name is also valid
- Searching with fewer than 3 identifiers returns 400 Bad Request with error message
- This prevents selecting the wrong patient, which could lead to medical errors

Example error response:
```json
{
  "detail": "Safe patient search requires at least 3 identifiers. Provided 1. Please include: MRN, Date of Birth, and/or Last Name. Missing: mrn, first_name, last_name, date_of_birth"
}
```

### Patient Model
```python
class Patient(Base):
    mrn: str (unique, required)
    first_name: Optional[str]
    last_name: Optional[str]
    date_of_birth: Optional[date]
    demographics_encrypted: Optional[text]
```

## Priority 4: Testing & Quality ✅ COMPLETED

- [x] Add integration tests for document analysis ✓
- [x] Add unit tests for field extraction regexes ✓
- [x] Test with real denial letter PDFs ✓
- [x] Verify PDF text extraction works ✓
- [x] Test coverage: **80%** (299 tests) ✓

## Priority 5: CI/CD & Pre-Production ✅ COMPLETED

- [x] Unit tests ✓ (299 tests covering services, schemas, models, utilities)
- [x] GitHub Actions workflow ✓
- [x] Health check endpoint ✓ (checks database & NVIDIA NIM)
- [x] API rate limiting ✓ (5 requests/minute for document analysis)
- [x] Edge case handling ✓ (empty text, short text, file size limits)
- [x] Audit logging for HIPAA compliance ✓

## Priority 6: Features ✅ COMPLETED

- [x] Claim prediction from ICD/CPT codes (use existing prediction service) ✓
- [x] Appeal letter generation (with fallback template) ✓
- [x] Batch document analysis ✓
- [x] Audit logging for HIPAA compliance ✓
- [x] API rate limiting ✓

## API Endpoints

### Claims
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/claims/analyze-document | Analyze document (rate limited: 5/min) |
| POST | /api/v1/claims/upload-document | Upload PDF/image file (supports JPG/PNG) |
| POST | /api/v1/claims/analyze-documents-batch | Batch analyze (max 20 docs) |
| GET | /api/v1/claims/{id}/document | View original document |
| GET | /api/v1/claims/ | List all claims (with patient filters) |
| POST | /api/v1/denial-workflow/analyze | Produce denial appeal workflow artifacts with source status and human-review gates |
| POST | /api/v1/denial-workflow/export | Export a workflow packet to Markdown, DOCX, or PDF |
| GET | /api/v1/denial-workflow/source-registry | List built-in public rule source metadata |

### Patients
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/patients/ | Create patient |
| GET | /api/v1/patients/ | List patients |
| GET | /api/v1/patients/{id} | Get patient by ID |
| GET | /api/v1/patients/mrn/{mrn} | Get patient by MRN |
| PUT | /api/v1/patients/{id} | Update patient |
| DELETE | /api/v1/patients/{id} | Delete patient |

### Analytics & Appeals
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/appeals/generate | Generate appeal letter |
| GET | /api/v1/analytics/summary | Analytics summary |
| GET | /api/v1/analytics/denial-trends | Denial trends over time |
| GET | /health | Health check |

### Claim Search Parameters
```
GET /api/v1/claims/?patient_first_name=John&patient_last_name=Doe&patient_dob=1990-01-15&status_filter=pending
```

## Test Coverage

```
TOTAL                                 1048    209    80%
```

### Coverage by Module
| Module | Coverage |
|--------|----------|
| app/__init__.py | 100% |
| app/api/__init__.py | 100% |
| app/api/v1/__init__.py | 100% |
| app/api/v1/analytics.py | 83% |
| app/api/v1/appeals.py | 95% |
| app/api/v1/claims.py | 69% |
| app/api/v1/patients.py | **100%** |
| app/core/__init__.py | 100% |
| app/core/config.py | 100% |
| app/core/limiter.py | 100% |
| app/core/security.py | 97% |
| app/db/__init__.py | 100% |
| app/db/database.py | 100% |
| app/models/__init__.py | 100% |
| app/schemas/__init__.py | 100% |
| app/schemas/analytics.py | 100% |
| app/schemas/claim.py | 100% |
| app/services/__init__.py | 100% |
| app/services/document_analysis.py | 84% |
| app/services/prediction.py | 79% |
| app/utils/audit.py | 100% |
| app/utils/file_processing.py | 32% |
| app/utils/format.py | 94% |
| app/utils/patient_search_validator.py | **100%** |

### New Test Files
- `tests/unit/test_file_processing.py` - File processing utilities
- `tests/unit/test_patient_search.py` - Patient search and schemas
- `tests/unit/test_patient_search_validator.py` - 3-identifier validation tests (15 tests)
- `tests/unit/test_patients.py` - Patient CRUD endpoint tests (19 tests)

## Dependencies Added
```
pillow==10.2.0          # Image processing
python-magic==0.4.27     # File type detection
pypdf==4.0.1           # PDF processing (updated)
```

## Quick Test Commands

```bash
# Run all tests with coverage
python3 -m pytest tests/unit/ --cov=app --cov-report=term-missing

# Test document analysis
curl -X POST http://localhost:8000/api/v1/claims/analyze-document \
  -H "Content-Type: application/json" \
  -d '{"document_text": "Denial from Aetna. Denial Code: CO29. Amount: $500."}'

# Test PDF upload
curl -X POST http://localhost:8000/api/v1/claims/upload-document \
  -F "file=@sample_denial_letter_cms.pdf"

# Test image upload (NEW)
curl -X POST http://localhost:8000/api/v1/claims/upload-document \
  -F "file=@denial_letter_scan.jpg"

# Search claims by patient name (requires 3 identifiers minimum)
curl "http://localhost:8000/api/v1/claims/?patient_first_name=John&patient_last_name=Doe&patient_dob=1990-01-15"

# Search claims by DOB (requires 3 identifiers minimum)
curl "http://localhost:8000/api/v1/claims/?patient_dob=1990-01-15&patient_last_name=Smith&patient_mrn=MRN-001"

# Create patient
curl -X POST http://localhost:8000/api/v1/patients/ \
  -H "Content-Type: application/json" \
  -d '{"mrn": "MRN-001", "first_name": "John", "last_name": "Doe", "date_of_birth": "1990-01-15"}'

# Health check
curl http://localhost:8000/health
```

## File Processing Notes

1. **Images are automatically converted to JPEG** for consistency
2. **Large images are resized** to max 4096px dimension
3. **JPEG quality is optimized** at 85%
4. **OCR requires `NVIDIA_API_KEY`** and uses `nvidia/nemotron-parse`.
5. `app/services/ocr.py` routes images and scanned PDFs to NVIDIA Nemotron Parse; `app/api/v1/claims.py`
   keeps direct `pypdf` extraction for text PDFs.

## Remaining Coverage Opportunities

The remaining 25% uncovered lines are primarily in:
- File processing utilities (requires actual Pillow/NVIDIA OCR integration)
- Patient endpoint CRUD operations
- Error handling paths in async httpx calls
- Rate limiting middleware paths

These require integration tests with real database connections or more complex mocking setups.

---

# Sprint Planning - Tomorrow's Work

## Project Status Summary

| Category | Status |
|----------|--------|
| Backend API Endpoints | 15 implemented |
| Frontend Pages | 5 (Dashboard, Claims, Patients, Appeals, Analytics) |
| Test Coverage | 80% (299 tests) |
| Authentication | JWT + RBAC enforced for API routes |
| EDI 837/835 Parsing | PARSERS IMPLEMENTED; clearinghouse submission/autoposting not implemented |
| Alembic Migrations | NOT IMPLEMENTED |
| Patients UI | IMPLEMENTED |
| Appeals UI | IMPLEMENTED |

---

## Sprint 1: Security Hardening 🔴 CRITICAL

### 1.1 Authentication & Authorization
- [x] Implement JWT authentication middleware
- [x] Add role-based access control (RBAC): admin, billing_staff, viewer
- [x] Protect all API endpoints with authentication
- [x] Add login/logout endpoints

### 1.2 CORS & Security Headers
- [x] Fix CORS: replace `allow_origins=["*"]` with specific domains
- [x] Add security headers middleware (X-Frame-Options, CSP, etc.)
- [x] Validate CORS origins from environment variable

### 1.3 Encryption & Keys
- [x] Generate proper Fernet encryption keys (not placeholder strings)
- [x] Add key rotation support
- [x] Document key management in .env.example

---

## Sprint 2: Frontend Completeness 🟡 HIGH

### 2.1 Patients Management Page
- [x] Create `frontend/src/pages/Patients.tsx`
- [x] Add patient CRUD UI (create, list, edit, delete)
- [x] Add patient search with 3-identifier validation UI
- [x] Add API client methods in `client.ts`

### 2.2 Appeals Generation UI
- [x] Create `frontend/src/pages/Appeals.tsx`
- [x] Add form to select claim and generate appeal letter
- [x] Add preview and download functionality
- [x] Connect to `POST /appeals/generate` endpoint

### 2.3 API Client Completeness
- [x] Add patient CRUD methods to `client.ts`
- [x] Add batch document analysis method
- [x] Add appeals generation method

---

## Sprint 3: Data Pipeline 🟡 HIGH

### 3.1 EDI 837 Claim Parser
- [x] Create `app/utils/edi_parser.py`
- [x] Implement claim loop (2300, 2400) parsing
- [x] Extract diagnosis codes (HI segments)
- [x] Extract procedure codes (SV1, SV2 segments)
- [x] Extract payer information (NM1 segments)
- [x] Add validation and error logging per EDI rules

### 3.2 EDI 835 Remittance Parser
- [x] Create `app/utils/edi_835_parser.py`
- [x] Parse payment information (CLP segments)
- [x] Extract adjustments (CAS segments)
- [x] Track paid claims against submitted
- [x] Add safe structured parser errors and validation issues with error code,
  parser stage, field, claim, and segment ID/index context without raw
  remittance text or segment payloads
- [x] Add guarded `POST /api/v1/claims/remittance-upload` endpoint for EDI 835
  `.835`, `.edi`, and `.txt` uploads with billing-role authorization,
  metadata-only surface inspection, and safe parsed payment summaries

### 3.3 Batch Claims Upload
- [x] Add `POST /api/v1/claims/batch-upload` endpoint
- [x] Accept EDI 837 files (.edi, .txt)
- [x] Process multiple claims from single file
- [x] Return detailed results per claim

### 3.4 mock data
- [x] Create multiple realistic anonymized mock claims denial letters using
  the checked-in CMS-style denial sample/template conventions and feed them
  into the API to test the system. Evidence: the generated synthetic corpus
  contains 900 denial notices and 900 appeal drafts with documented
  format/layout/typography/length variation; `tests/unit/test_mock_denial_letter_api_smoke.py`
  verifies that manifest and posts twelve representative rendered denial
  notices through `/api/v1/claims/upload-document`.
---

## Sprint 4: Database & Migrations 🟢 MEDIUM

### 4.1 Alembic Setup
- [x] Initialize Alembic with `alembic init`
- [x] Configure alembic.ini for PostgreSQL
- [x] Maintain additive migrations from the existing SQLAlchemy model baseline
- [x] Document migration workflow in `docs/database-migrations.md`

### 4.2 Database Indexes
- [x] Add indexes on frequently queried columns:
  - `claims.patient_id`
  - `claims.status`
  - `claims.submission_date`
  - `claims.denial_prediction`
  - `patients.mrn`

### 4.3 Soft Delete Support
- [x] Add `deleted_at` column to Claim, Patient models
- [x] Update queries to filter soft-deleted records
- [x] Add restore functionality

Notes: `app/models/__init__.py` now defines record-level soft-delete metadata
for `Claim` and `Patient`, `app/api/v1/claims.py` and
`app/api/v1/patients.py` filter active records by default, and
`alembic/versions/20260531_033507_add_claim_patient_soft_delete_indexes.py`
adds the additive PostgreSQL migration for soft-delete columns plus the new
query indexes.

---

## Sprint 5: Technical Debt 🟢 MEDIUM

### 5.1 Bug Fixes
- [x] Fix circuit breaker in `prediction.py:24` - `.seconds` → `.total_seconds()`
- [x] Replace bare `except:` clauses with specific exceptions in `claims.py`

### 5.2 Error Handling
- [x] Add claim-document upload size validation before file processing, PDF
  parsing, OCR, document analysis, denial workflow generation, database writes,
  or audit logging
- [x] Add comprehensive error responses with error codes
- [x] Add retry logic with exponential backoff for NVIDIA NIM calls

### 5.3 Logging Improvements
- [x] Add structured JSON logging for EDI 837 batch-upload parser failures
  with safe error codes, parser stage, field, segment context, and no raw
  filename/text/segment values
- [x] Log safe EDI 837 segment ID/index context for validation and parser
  failures when a segment is available
- [x] Add structured safe logging for claim document-analysis JSON parse
  failures with parser stage, error code, type/length metadata, and no raw
  analysis or document text
- [x] Add safe structured NVIDIA NIM retry/error/slow-request logging without
  raw prompts, OCR bytes, raw responses, authorization headers, API keys, PHI,
  or production document content
- [x] Extend the same structured JSON logging pattern to remaining non-EDI data
  pipeline failures
- [x] Add request ID tracking for debugging

---

## Sprint 6: Production Readiness 🟢 MEDIUM

### 6.1 Docker & Deployment
- [x] Create production Dockerfile (multi-stage build)
- [x] Add health check for frontend service
- [x] Validate NVIDIA API configuration on startup
- [x] Add nginx for production serving

## LLM Distillation MVP Implementation - 2026-05-29

### Completed
- [x] Added local MLX-LM provider configuration for OpenAI-compatible
  `mlx_lm.server` runtime.
- [x] Added deterministic denial workflow analyzer aligned to `denial_skill`
  fact-source statuses, routing logic, deadline safety, evidence gaps,
  human-review gate, and draft-for-review behavior.
- [x] Added lightweight retrieval/indexing scaffold with built-in public rule
  source chunks and citation metadata.
- [x] Added Markdown, DOCX, and PDF export service for workflow packets without
  adding dependencies.
- [x] Integrated workflow output into existing document analysis and upload
  claim data.
- [x] Hardened appeal fallback prompts/templates to require human review and
  avoid unsupported clinical/legal/citation claims.
- [x] Added persistent encrypted retrieval source/chunk storage and wired
  persisted chunks into denial workflow retrieval.
- [x] Added local encrypted hybrid retrieval indexing with deterministic hashed
  vectors and keyword/embedding/hybrid search modes.
- [x] Added offline synthetic workflow baseline scoring harness for held-out
  scenario families.
- [x] Incorporated the accepted distilled ClaimGuard student into backend/API
  metadata and status checks without making the local server a hard dependency.
- [x] Added `denial_skill` P01-P15 phase checklist to API responses, exports,
  and frontend review controls.
- [x] Added live student runtime health status, default-use gating metadata, and
  copyable `mlx_lm.server` launch command for the reviewed LoRA adapter.

### Still Open
- [ ] Build production semantic embedding provider/vector backend,
  source-corpus ingestion, and review workflow on top of the encrypted source
  store. Local progress: production startup now fails fast if the retrieval
  vector configuration still uses hash embeddings, unapproved embedding models,
  local metadata storage, hash fallback, or backend settings that contain URLs
  or credentials; the readiness API and PHIplan production-readiness audit
  expose the same metadata-only blockers without emitting URL or credential
  values. Retrieval-vector backend evidence now also requires the checked-in
  operator runbook at `llm-distill/docs/retrieval-vector-backend-runbook.md`,
  reindex checklist at
  `llm-distill/docs/retrieval-vector-reindex-checklist.md`, and runtime smoke
  checklist at
  `llm-distill/docs/retrieval-vector-runtime-smoke-checklist.md` while keeping
  the injectable semantic embedding provider boundary and metadata-only reindex
  operation ready in code. The private env renderer now also verifies the
  configured evidence report is safe, ready, and unblocked before writing
  enabled production vector settings, and the private runtime evidence renderer
  now validates a private aggregate runtime summary before writing ready
  evidence, while private semantic backend configuration, chunk reindexing,
  health, and quality checks remain blocked until real production evidence
  exists.
- [ ] Approve at least one non-synthetic denial/appeal training pair through
  the production corpus review workflow. Local progress: production corpus
  evidence now requires the checked-in operator runbook at
  `llm-distill/docs/production-corpus-review-runbook.md`, the checked-in
  collection/license checklist at
  `llm-distill/docs/production-corpus-collection-license-checklist.md`, and
  the checked-in pair/source checklist at
  `llm-distill/docs/production-corpus-pair-source-checklist.md`; it keeps
  `production_corpus_ready=false` until private pair/source review is complete.
  The source-controlled private renderer at
  `llm-distill/scripts/render_production_corpus_private_evidence.py` can render
  the final private evidence file only after external pair/source and review
  attestations exist and private manifest metadata contains at least one
  approved non-synthetic denial/appeal pair, while keeping raw private manifest
  paths out of evidence and validator reports.
- [ ] Configure real legal approval reference, BAA confirmation, and consent
  notice version before enabling user-data model improvement. Local progress:
  model-improvement evidence now requires the checked-in operator runbook at
  `llm-distill/docs/model-improvement-approval-runbook.md` and keeps
  `model_improvement_ready=false` until private approval, consent, BAA, and
  explicit request gates are complete. The private env renderer now also
  verifies the configured evidence report is safe, ready, and unblocked before
  writing enabled user-data model-improvement settings.
- [ ] Add full corpus collection and licensing review before any training data
  build. Local progress: source-controlled collection/license checklist
  documentation is now required and validated, but real collection inventory,
  license terms, source terms, and approval records must remain outside source
  control until reviewed.
- [x] Run live MLX-LM latency, tokens/sec, and memory benchmarks on the M1 iMac.
- [x] Add synthetic supervised seed records and teacher-label request batches.
- [x] Export synthetic seed records to MLX-LM chat-format SFT splits with
  training blocked until label review.
- [x] Add local MLX-LM benchmark harness and report shape.
- [x] Add reviewed teacher-label ingestion and validation gate.
- [x] Replace seed labels with reviewed large-teacher labels and fine-tune only
  after baseline failures are measured.
- [x] Add frontend workflow screens for editing and exporting the new packet.
- [x] Add production fail-fast startup guard for unsafe student-default routing
  requests while leaving default student use disabled.
- [ ] Add a production process supervisor/auto-launch path for the accepted
  reviewed LoRA adapter if ClaimGuard should load the local student by default.
  Local progress: supervisor evidence now requires the checked-in owner
  handoff checklist at
  `llm-distill/docs/mlx-runtime-owner-handoff-checklist.md` while keeping
  `supervisor_ready=false`; a private launchd plist renderer is now available
  for non-installing operator preparation, and the private supervisor evidence
  renderer now validates the private plist structure before ready evidence can
  be written. Private owner assignment, runtime preflight, health/status
  checks, launchd load evidence, and restart testing remain required.

### 6.2 Documentation
- [x] Create API documentation with authentication requirements
- [x] Document EDI format specifications
- [x] Add deployment guide

### 6.3 Monitoring
- [x] Add Prometheus metrics endpoint
- [x] Log slow NVIDIA NIM requests
- [x] Track denial prediction accuracy over time

---

## Dependencies to Add

```bash
# Authentication
python-jose[cryptography]  # JWT handling
passlib[bcrypt]           # Password hashing

# EDI Parsing
regex  # Better regex for EDI patterns

# Monitoring
prometheus-client  # Metrics
```

---

## Recommended Tomorrow Sequence

1. **Morning**: Critical bug fixes complete for circuit breaker timeout
   recovery and `claims.py` bare `except:` removal; next focus is
   authentication middleware.
2. **Mid-Morning**: Implement authentication middleware
3. **Midday**: Create Patients page in frontend
4. **Afternoon**: Create Appeals page in frontend
5. **End of Day**: Run full test suite, update docs

---

## Files to Create/Modify

### New Files
- `app/api/v1/auth.py` - Authentication endpoints
- `app/middleware/auth.py` - JWT validation middleware
- `app/utils/edi_parser.py` - EDI 837 parser
- `app/utils/edi_835_parser.py` - EDI 835 parser
- `frontend/src/pages/Patients.tsx` - Patient management UI
- `frontend/src/pages/Appeals.tsx` - Appeal letter UI
- `alembic/` - Database migrations

### Critical Modifications
- `app/main.py` - Add auth middleware, fix CORS
- `frontend/src/api/client.ts` - Add missing API methods
- `app/api/v1/claims.py` - Bare `except:` JSON parsing fixed; EDI endpoint added
- `app/services/prediction.py` - Circuit breaker timeout bug fixed

---

# Comprehensive Security & Compliance Audit

## Vulnerability Summary

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Input Validation | 4 | 5 | 3 | 2 | 14 |
| HIPAA Safeguards | 6 | 5 | 2 | 0 | 13 |
| Data Validation | 0 | 5 | 5 | 0 | 10 |
| Edge Cases | 0 | 4 | 4 | 0 | 8 |
| AI/ML Concerns | 0 | 4 | 4 | 0 | 8 |
| Operational | 2 | 2 | 3 | 0 | 7 |
| Frontend | 0 | 2 | 4 | 3 | 9 |
| **TOTAL** | **12** | **27** | **25** | **5** | **69** |

---

## CRITICAL Security Issues (Fix Immediately)

### 1.1 SQL Injection Vectors 🔴
| Location | Issue |
|----------|-------|
| `claims.py:118,121` | ILIKE query without sanitization on `patient_first_name`, `patient_last_name` |
| `patients.py:53,56` | LIKE query vulnerable to SQL injection |

**Fix:** Sanitize input with regex before query:
```python
import re
if not re.match(r'^[\w\s]*$', patient_first_name):
    raise HTTPException(status_code=400, detail="Invalid characters in name")
```

### 1.2 PHI Encryption at Rest 🔴
| Location | Issue |
|----------|-------|
| `models/__init__.py:16` | `demographics_encrypted` column exists but NEVER USED |
| `models/__init__.py:51` | `document_text` stores PHI unencrypted |
| `claims.py:221,399` | Document text saved without encryption |

**Fix:** Encrypt before storing:
```python
from app.core.security import encryption_service
claim.document_text = encryption_service.encrypt(doc_request.document_text)
```

### 1.3 CORS Wildcard with Credentials 🔴
| Location | Issue |
|----------|-------|
| `main.py:24` | `allow_origins=["*"]` with `allow_credentials=True` |

**Fix:** Restrict to specific frontend domain from environment variable.

### 1.4 Path Traversal in File Uploads 🔴
| Location | Issue |
|----------|-------|
| `file_processing.py:61` | Filename not sanitized for `../../etc/passwd` |

**Fix:** Sanitize filename:
```python
def sanitize_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    return filename[:255]
```

### 1.5 XSS in Frontend Display ✅
| Location | Status |
|----------|--------|
| `frontend/src/pages/Claims.tsx` | Fixed: high-risk analysis, recommendation, denial reason, code, and appeal strategy output renders through `SafeHtml`. |
| `frontend/src/pages/Dashboard.tsx` | Fixed: saved AI analysis, appeal strategy, denial reason, recommendation, filename, and document preview output renders through `SafeHtml`. |
| `frontend/src/pages/Appeals.tsx` | Fixed: generated appeal preview, supporting evidence, top denial reason, and user-facing notices render through `SafeHtml`. |
| `frontend/src/pages/DenialWorkflow.tsx` | Fixed: review summaries, strategy, facts, tasks, evidence, de-identified text, corpus notices, and audit details render through `SafeHtml`. |

`frontend/src/utils/safeHtml.ts` escapes display text, converts line breaks to
`<br>`, and sanitizes with DOMPurify while allowing only `<br>` tags and no
attributes. `frontend/src/components/common/SafeHtml.tsx` isolates the only
direct `dangerouslySetInnerHTML` use in the frontend.

### 1.6 Audit Log Missing User Context 🔴
| Location | Issue |
|----------|-------|
| `audit.py:16` | `user_id` parameter never populated |
| `audit.py:36` | `ip_address` parameter never passed |
| All endpoints | No PHI access logging for claim retrieval |

**Fix:** Pass user context from request:
```python
user_id = request.state.user_id if hasattr(request.state, 'user_id') else None
ip_address = request.client.host if request.client else None
```

---

## HIGH Priority Issues

### 2.1 Missing Claim State Machine
- [x] Formal API/service state transitions added in
  `app/services/claim_state.py` and `/api/v1/claims/{claim_id}/status`; direct
  `pending` to `paid` transition is blocked with a safe structured 409 error
- [x] Canonical write states `draft`, `pending`, `submitted`, `denied`,
  `appealed`, `paid`, `partially_paid`, and `write_off` are enforced for
  status updates, with legacy read/filter aliases retained for historical
  analytics compatibility
- [x] Invalid or non-canonical status changes return structured safe errors
  with allowed statuses, allowed next statuses, blocker codes, and no raw claim
  data, document text, transition-note text, patient identifiers, or provider
  identifiers
- [x] `claims.status` is non-null and protected by the
  `ck_claims_status_canonical` database check constraint, with Alembic
  migration `20260531_004528_add_claim_status_constraint.py` normalizing known
  legacy readable statuses before enforcement

**Required States:**
```python
VALID_STATES = ["draft", "pending", "submitted", "denied", "appealed", "paid", "partially_paid", "write_off"]
STATE_TRANSITIONS = {
    "draft": ["pending", "submitted", "write_off"],
    "pending": ["submitted", "write_off"],
    "submitted": ["denied", "paid", "partially_paid", "write_off"],
    "denied": ["appealed", "write_off"],
    "appealed": ["denied", "paid", "partially_paid", "write_off"],
    "partially_paid": ["appealed", "paid", "write_off"],
    "paid": [],  # Terminal
    "write_off": [],  # Terminal
}
```

### 2.2 Missing Required Claim Fields
| Field | Status |
|-------|--------|
| Payer ID / Insurance | Missing - CRITICAL |
| Subscriber ID | Missing - CRITICAL |
| Group Number | Missing |
| Service Date | Missing - CRITICAL |
| Place of Service Code | Missing - CRITICAL |
| Authorization Number | Missing |
| NDC Codes (drugs) | Missing |
| Referring Provider NPI | Missing |

### 2.3 No NPI Validation
| Location | Issue |
|----------|-------|
| `models/__init__.py:27` | NPI stored without 10-digit checksum validation |

**Fix (Luhn algorithm):**
```python
def validate_npi(npi: str) -> bool:
    if not npi.isdigit() or len(npi) != 10:
        return False
    digits = [int(d) for d in npi]
    check = sum(digits[-2::-2]) + sum(sum(divmod(2*d, 10)) for d in digits[-1::-2])
    return check % 10 == 0
```

### 2.4 No ICD-10/CPT Validation
- [x] Diagnosis-code format validation before prediction, submission, and EDI
  837 review
- [x] Procedure-code format validation before prediction, submission, and EDI
  837 review
- [x] Diagnosis/procedure linkage metadata guard for procedure-code claims and
  EDI 837 diagnosis pointers; production clinical/payer crosswalk remains a
  future licensed policy-data integration

### 2.5 Race Conditions
| Location | Issue |
|----------|-------|
| `patients.py:90-93` | TOCTOU race on MRN uniqueness check |
| `claims.py:59` | Duplicate claim submission possible |

### 2.6 Human-in-the-Loop Missing
| Location | Issue |
|----------|-------|
| `claims.py:62-76` | High-risk claims auto-submitted without review |
| `claims.py:189-223` | Document analysis creates claims without human review |

---

## MEDIUM Priority Issues

### 3.1 Code Validation Gaps
- [x] Future dates rejected for patient `date_of_birth` on create/update
- [x] Negative structured claim amounts rejected before prediction/submission
- [x] EDI 837 batch upload now applies pre-parse segment-count and claim-count
  guards before constructing parsed claim objects

### 3.2 Session Timeout
- [x] Frontend auth state now enforces automatic logout after inactivity.
- [x] `ACCESS_TOKEN_EXPIRE_MINUTES: int = 30` remains unchanged; frontend
  session activity updates only last-activity metadata and does not extend the
  absolute JWT expiry.

### 3.3 AI/ML Concerns
- [x] Metadata-only demographic parity metric available for approved batch
  prediction evaluations without exposing raw demographic values.
- [x] High-risk threshold (`> 0.5`) is now documented in prediction metadata as
  a human-review routing threshold, not an auto-denial rule.
- [x] Denial reasons now carry driver categories and source-field families.
- [x] Prediction responses and audit details now include metadata-only fairness,
  threshold, and explainability telemetry.
- [ ] Production calibrated threshold and continuous fairness monitoring over
  approved real-world outcome data remain blocked by production corpus and
  manual governance gates; boolean-only evidence validation is now wired into
  the PHIplan production-readiness audit and startup guard, the local
  source-controlled monitoring runbook, calibration checklist, monitoring
  validation checklist, legal/privacy checklist, and private evidence renderer
  sub-gates are ready; the private renderer now validates a private aggregate
  monitoring summary before ready evidence can be written, and the current
  evidence remains blocked until approved outcome data and governance review
  exist.
- [ ] Corpus-derived MLX fine-tuning remains blocked in `--run` mode until
  `llm-distill/scripts/validate_production_corpus_evidence.py` produces a safe
  ready report with approved non-synthetic paired denial/appeal examples.

### 3.4 File Upload Issues
- [x] `app/api/v1/claims.py` rejects disguised inner extension chains such as
  `.php.txt` and `.php.edi` before reading uploaded bytes.
- [x] `app/api/v1/claims.py` reads claim-document and EDI batch uploads with a
  bounded `max_bytes + 1` read before size validation instead of unbounded
  `file.read()`.
- [x] `app/utils/file_processing.py` rejects excessive image pixel counts and
  treats Pillow decompression-bomb warnings as processing failures before
  resize/compression work proceeds.

### 3.5 Missing Healthcare Standards
| Standard | Status |
|----------|--------|
| CMS-1500 fields | Incomplete |
| UB-04 fields | Not implemented |
| CARC/RARC codes | Only 5 hardcoded |
| NDC codes | Not supported |
| Revenue codes | Not supported |

---

## Claim Lifecycle & Workflow Gaps

### Missing Claim States
```python
VALID_CLAIM_STATES = [
    "draft",           # Created but not ready
    "pending",         # Awaiting submission
    "scrubbing",      # Being validated
    "submitted",      # Sent to payer
    "accepted",       # Received by payer
    "in_review",      # Payer reviewing
    "denied",         # Rejected by payer
    "appealed",       # Appeal in progress
    "appeal_approved",# Appeal successful
    "appeal_denied",  # Appeal rejected
    "paid",           # Fully paid
    "partially_paid", # Partial payment
    "write_off",      # Balance written off
    "timely_filing",  # Past deadline
]
```

### Missing Appeal Deadline Tracking
```python
# Required fields:
class Claim(Base):
    denial_date: Optional[datetime] = None
    appeal_deadline: Optional[date] = None  # Calculated from denial_date + payer_timeline
    appeal_level: int = 0  # 1 = first, 2 = second, 3 = external
    appeal_status: Optional[str] = None
```

### Missing Reporting Requirements
| Report | Priority |
|--------|----------|
| Clean Claim Rate | P0 |
| Denial Rate by Payer | P0 |
| Appeal Success Rate | P0 |
| Timely Filing Compliance | P0 |
| Aging Report (A/R) 30/60/90+ | P1 |
| Average Days to Payment | P1 |
| Provider Productivity | P2 |

### Missing Financial Controls
| Control | Priority |
|---------|----------|
| Charge Master Integration | P0 |
| Contracted Rate Verification | P0 |
| Patient Responsibility Calculator | P1 |
| Coordination of Benefits (COB) | P1 |

---

## Missing Healthcare Standards

### EDI Integration Status
| Standard | Status | Priority |
|----------|--------|----------|
| EDI 837 Claim Intake/Parser | IMPLEMENTED; clearinghouse claim submission not implemented | P0 |
| EDI 835 Remittance Parser | IMPLEMENTED; ERA/EFT autoposting not implemented | P0 |
| Eligibility (270/271) | NOT IMPLEMENTED | P0 |
| ERA/EFT (835 auto-posting) | NOT IMPLEMENTED | P1 |
| Claim Status (276/277) | NOT IMPLEMENTED | P1 |
| Clearinghouse Integration | NOT IMPLEMENTED | P0 |

### Place of Service Codes
Required 2-digit codes (21 available):
```python
VALID_POS_CODES = {
    "01": "Pharmacy", "02": "Telehealth", "11": "Office",
    "12": "Home", "20": "Urgent Care", "21": "Inpatient Hospital",
    "22": "Outpatient Hospital", "23": "Emergency Room",
    "24": "Ambulatory Surgical Center", # ... etc
}
```

### Revenue Codes (UB-04)
Required for institutional claims:
```python
VALID_REVENUE_CODES = {
    "0110": "Room & Board - Private", "0250": "Pharmacy",
    "0300": "Lab", "0320": "Radiology", "0610": "MRI",
    "0700": "OR Services", # ... 100+ codes
}
```

### CARC/RARC Codes
A local versioned seed database now lives at `app/data/carc_rarc_codes.json`
with lifecycle lookup code in `app/utils/carc_rarc_database.py`. The EDI 835
parser uses it to distinguish active seed codes, known inactive/deactivated
seed codes, and format-valid unconfirmed codes without returning raw segment
payloads or copying official long-form code descriptions. Production still
needs a licensed code-list update feed and governance review before the local
seed can be treated as comprehensive.

---

## Operational Security Concerns

### 1.1 Database Backup
- [x] Automated database backup procedure documented in `docs/backup-disaster-recovery.md`
- [x] Disaster recovery plan documented in `docs/backup-disaster-recovery.md`
- [x] Backup verification documented in `docs/backup-disaster-recovery.md`

### 1.2 Dependency Vulnerabilities
| Package | Issue |
|---------|-------|
| `pydantic` v1.x | CVE series - upgrade to v2.x |
| `python-jose` | CVE-2024-2023-1095 |
| `pillow` | Periodic CVEs - ensure latest |

### 1.3 NVIDIA NIM Security
- [x] Prompt-injection-like document instructions detected as metadata-only
  categories, untrusted document prompt boundaries added, and denial workflow
  blocker tasks/warnings/quality checks produced without returning matched
  values
- [x] Hallucination-risk handling for unsupported approval/payment/deadline/
  no-review certainty keeps outputs `human_review_required=true`,
  `filing_ready=false`, and deterministic workflow controls authoritative
- [x] Metadata-only deterministic fallback when NVIDIA NIM document analysis is
  unavailable or empty, with safe logging that excludes raw prompts, raw
  document text, raw model responses, exception messages, credentials, PHI, and
  production document content

---

## Immediate Action Items (24 Hours)

1. **Fix SQL injection** - Sanitize all LIKE/ILIKE inputs
2. **Restrict CORS** - Replace `*` with specific origin
3. **Encrypt PHI** - Use encryption service for document_text
4. **Pass user context** - Add user_id and ip_address to audit logs
5. **Sanitize filenames** - Prevent path traversal

## Week 1 Actions

1. [x] Add human-in-the-loop for high-risk predictions

## Week 2 Actions

1. [x] Implement EDI 837 parser
2. [x] Add charge master and contract rates
3. [x] Add missing healthcare code sets
4. [x] Implement CARC/RARC code database

## Week 3-4 Actions

1. EDI 835 remittance parser
2. Eligibility verification
3. Clearinghouse integration
4. Comprehensive reporting suite
5. Production hardening

---

## Files to CREATE for Compliance

```
app/models/
  claim_state.py          # State machine definitions
  charge_master.py        # Charge master and rates
  payer.py                # Payer information
  insurance.py            # Insurance coverage
  appeal.py               # Appeal tracking

app/services/
  claim_state_machine.py  # State transitions
  charge_master_service.py # Rate lookups
  patient_responsibility.py # Responsibility calc
  eligibility.py          # 270/271 handling

app/data/
  carc_codes.py           # CARC/RARC codes (100+)
  pos_codes.py            # Place of service codes
  revenue_codes.py        # Revenue codes for UB-04

app/validators/
  npi_validator.py        # NPI checksum validation
  icd10_validator.py      # ICD-10 format validation
  cpt_validator.py        # CPT code validation
```

---

## Quick Reference Card

### Critical Security Fixes (Before Deploy)

| File | Line | Fix Required |
|------|------|--------------|
| `app/api/v1/claims.py` | 118, 121 | Sanitize `patient_first_name`, `patient_last_name` with regex |
| `app/api/v1/patients.py` | 53, 56 | Sanitize `first_name`, `last_name` with regex |
| `app/main.py` | 24 | Replace `allow_origins=["*"]` with specific domain |
| `app/models/__init__.py` | 51 | Encrypt `document_text` before saving |
| `app/utils/file_processing.py` | 61 | Sanitize filename with `os.path.basename()` |
| `frontend/src/pages/Claims.tsx` | 162 | Fixed: DOMPurify-backed `SafeHtml` rendering |
| `frontend/src/pages/Dashboard.tsx` | 212, 359 | Fixed: DOMPurify-backed `SafeHtml` rendering |
| `app/utils/audit.py` | - | Pass `user_id` and `ip_address` from request |
| `app/services/prediction.py` | 24 | Fixed: changed `.seconds` to `.total_seconds()` |

### One-Line Security Fixes

```python
# SQL Injection Fix (claims.py, patients.py)
import re
if not re.match(r'^[\w\s]*$', patient_name):
    raise HTTPException(400, "Invalid characters")

# CORS Fix (main.py)
allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")]

# PHI Encryption Fix (claims.py)
from app.core.security import encryption_service
claim.document_text = encryption_service.encrypt(text)

# Filename Sanitization (file_processing.py)
filename = os.path.basename(filename.replace("\\", "/"))
```

### Environment Variables Required

```bash
# .env.example additions
FRONTEND_URL=http://localhost:5173
SECRET_KEY=<generate-32-byte-key>
# Generate with: python3 scripts/generate_fernet_key.py
ENCRYPTION_KEYS=
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

### Healthcare Code Validation Patterns

```python
# ICD-10: A00-Z99 with optional decimals
ICD10_PATTERN = r'^[A-Z][0-9]{2}(\.[0-9A-Z]{1,4})?$'

# CPT: 5 digits with optional modifier
CPT_PATTERN = r'^[0-9]{5}(-[A-Z0-9]{2,4})?$'

# NPI: 10 digits with Luhn checksum
NPI_PATTERN = r'^[0-9]{10}$'

# CARC: 3-letter code with optional reason
CARC_PATTERN = r'^(CO|COA|PI|PR|CR|AJ|OC)[0-9]{1,2}$'
```

---

*Document maintained by: Development Team*  
*Next Review: After security fixes completion*
