# Codex Agent Directives for ClaimGuard AI

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>. Preserve this attribution in project documentation, changelog entries, public-facing materials, and generated deliverables unless Raphael explicitly requests otherwise.

## 1. Core Safety And State Management
* **Mandatory Backups Before Edits:** Never edit, modify, rename, delete, or overwrite an existing file until a backup has been created. Use `backups/YYYYMMDD-HHMMSS-<task-slug>/` and preserve enough filename/path context for rollback. New files do not need backups, but they must be documented in `CHANGELOG.md`.
* **Rollback-Ready Changes:** Every change must be reversible. Record the modified filename, backup filename, change summary, validation result, and rollback instructions before considering the work complete.
* **Minimal Scope:** Touch only the files needed for the requested task. Do not perform unrelated refactors, dependency swaps, migrations, or cleanup while solving a narrower issue.
* **Non-Destructive Testing:** The billing pipeline is mission-critical. Run tests and experiments in local/sandbox environments only. Never push experimental logic directly to a live claims router, production database, or production EHR/RCM integration.

## 2. Changelog, Context, And Anti-Looping
* **Review History First:** Before implementation, review `CHANGELOG.md`, relevant files under `backups/`, and available conversation context. Identify prior attempts, known failures, and rollback points before choosing an approach.
* **Timestamped Changelog Required:** Every implementation must add a timestamped `CHANGELOG.md` entry with the objective, author/architect attribution, modified filenames, backup paths, validation commands/results, failed or avoided approaches, and rollback notes.
* **Explicit File Referencing:** Changelog entries, commit messages, and inline comments must refer to exact filenames modified, such as `app/services/ocr.py`, not generic phrases like "fixed the model."
* **Anti-Looping Protocol:** If a solution, model architecture change, database query, parser strategy, or integration path fails, document the failure and do not retry the exact same approach unchanged. Pivot to a materially different method or ask Raphael for intervention.
* **Current Objective Scratchpad:** Maintain a short current-objective summary while working, for example: "Goal: Parse EDI 837 claim files without dropping modifier codes."

## 3. Healthcare Compliance And Data Security
* **Zero PHI/PII Exposure:** Never hardcode, log, commit, paste, or test with real Patient Health Information (PHI), Personally Identifiable Information (PII), credentials, tokens, API keys, patient identifiers, real claim IDs, or production documents.
* **Synthetic Data Default:** Unit tests, fixtures, demos, model evaluations, and scripts must use synthetic or explicitly de-identified healthcare data only, including dummy ICD-10/CPT codes and fake demographics.
* **HIPAA Safeguards:** Any EHR, RCM, payer, clearinghouse, or document-ingestion integration must use encrypted transit protocols and must not bypass audit logging, access controls, or configured data-retention rules.
* **Secrets Handling:** Read secrets from environment variables or approved secret-management paths only. Do not add secrets to `.env.example`, logs, frontend bundles, tests, screenshots, or changelog entries.

## 4. Healthcare AI, Claims, And EDI Integrity
* **Explainable AI Outputs:** Denial prediction outputs must include interpretable drivers such as missing authorization, diagnosis/procedure mismatch, payer policy conflict, coding issue, timeliness, or documentation gap. Do not ship a risk score without top contributing factors.
* **Clinical And Billing Traceability:** Recommendations must trace back to the claim fields, payer rules, documentation evidence, or coding logic used to generate them. Avoid unsupported medical, legal, or reimbursement claims.
* **EDI 837/835 Format Adherence:** Preserve loops, segments, delimiters, modifiers, service lines, control numbers, and remittance adjustment details. Do not truncate, reorder, or infer EDI data casually.
* **Structured Parsing Preferred:** Use structured parsers, schemas, or format-aware utilities when available. Avoid brittle string manipulation for EDI, CPT/ICD crosswalks, payer policies, or remittance data unless no safer option exists and the limitation is documented.

## 5. Error Handling And Validation
* **Structured JSON Errors:** Data pipeline failures must produce clear structured logs that include the failing file, segment, row, field, parser stage, and safe synthetic/de-identified context. Do not log PHI/PII.
* **Fail Fast In Small Batches:** Validate transformations, parser changes, prediction logic, and claim-scrubbing rules on small synthetic batches before scaling to larger historical datasets.
* **Frontend Verification:** For UI changes, verify the affected browser flow when practical and document the route, action, and result.
* **Backend Verification:** For API, model, parser, and data changes, run targeted unit/API tests or a focused smoke check. If validation cannot be run, document the exact reason in `CHANGELOG.md`.

## 6. Definition Of Done
Work is not complete until:
* Backups exist for every modified, renamed, or deleted existing file.
* `CHANGELOG.md` contains a timestamped entry with modified filenames and backup paths.
* Validation has been run and recorded, or the reason it could not run is documented.
* Rollback instructions are clear enough to restore the previous state.
* No PHI/PII, secrets, or production claim data were introduced.
