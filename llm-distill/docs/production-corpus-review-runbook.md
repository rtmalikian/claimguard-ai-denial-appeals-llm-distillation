# Production Corpus Review Runbook

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: not production-ready.

This runbook documents the source-controlled operator procedure for reviewing
production denial/appeal corpus candidates before any non-synthetic record can
be treated as training eligible. It is not evidence that a real-world,
de-identified, approved denial/appeal pair has been reviewed or approved.

## Safety Boundaries

- Keep raw denial letters and raw appeal letters quarantined and encrypted.
- Do not store raw documents, source paths, checksums, approval references,
  credentials, tokens, PHI, production claim content, or production document
  content in source control.
- Machine de-identification is a draft safety step only; Raphael or an
  approved reviewer must complete human/privacy review before training
  eligibility.
- Use Safe Harbor-style automation as the baseline and require Expert
  Determination when rare narrative facts, unusually specific timelines,
  geography, device, condition, amount, or public uniqueness cues increase
  residual re-identification risk.
- Do not train on raw uploaded denial letters, claim files, appeal packets, or
  documents that have not passed the approved review gates.

## Private Operator Steps

1. Ingest candidate denial and appeal documents only through the quarantined
   intake path.
2. Run machine de-identification and document-surface PHI/PII inspection.
3. Review privacy status, license status, residual-risk score, source/license
   scope, training scope, and required micro-skill metadata.
4. Confirm each approved training candidate has both `denial_letter` and
   `appeal_letter` roles linked by a pair identifier.
5. Confirm pair identifiers and source documents are reviewed outside source
   control.
6. Record only boolean readiness evidence, aggregate counts, source-type
   categories, and blocker identifiers in checked-in evidence.
7. Render any final private evidence file with
   `llm-distill/scripts/render_production_corpus_private_evidence.py` only to a
   private path outside source control after privacy, license, residual-risk,
   training-scope, no-PHI, source/license, pair-id, source-document, and
   metadata-only manifest attestations are complete. Confirm command output
   includes redacted booleans/counts only.
8. Rerun `llm-distill/scripts/validate_production_corpus_evidence.py`.

## Required Before Production Corpus Readiness

- Approved non-synthetic denial/appeal pair required.
- Pair ids reviewed outside source control required.
- Source documents reviewed outside source control required.
- Privacy review, license review, residual-risk review, training-scope review,
  no-PHI review, and source/license scope documentation must all be attested.
- Any Expert Determination requirement must be completed before training
  eligibility.

## Evidence Rules

- Checked-in evidence may include booleans, aggregate counts, source-type
  categories, status tokens, blocker IDs, runbook path, and marker counts only.
- Private rendered evidence files must stay outside source control and may not
  be copied into changelog entries, reports, screenshots, tests, or checked-in
  documentation.
- Checked-in evidence must not include raw denial letters, raw appeal letters,
  source paths, checksums, approval references, credentials, tokens, matched
  PHI/PII values, claim identifiers, patient identifiers, production claim
  content, or production document content.
- The report may stay `safe_to_review=true` while
  `production_corpus_ready=false` until at least one approved non-synthetic
  denial/appeal pair and outside-source-control pair/source review are
  complete.
