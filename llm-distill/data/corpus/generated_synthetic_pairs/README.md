# Generated Synthetic Denial/Appeal Corpus

ClaimGuard AI is architected by Raphael Malikian.

This directory contains 900 synthetic denial/appeal pairs, or 1800
plain-text letters, generated for local ClaimGuard model-training experiments.

Safety and format rules:

- Every document is fictitious and generated locally from deterministic templates.
- No real patients, claim IDs, member IDs, contact details, credentials, payer records,
  user-uploaded files, or production documents were used.
- Denial letters follow the existing corpus style: each begins as a training
  synthetic corpus pair, describes a payer denial scenario, avoids direct
  identifiers, and names the reviewer action.
- Appeal letters follow the existing corpus style: each is marked
  `draft_for_human_review`, stays conditional, and requires source, deadline,
  authority, clinical, coding, and PHI-scope verification.
- Each file includes a Synthetic formatting profile with layout, typography,
  format-family, and length-profile metadata.
- The `rendered_html/` companions apply actual CSS font stacks and layout
  wrappers for the same no-PHI letter text, so visual/OCR-style stress tests
  can exercise different document fonts and page layouts without changing the
  plain UTF-8 training source.
- Use `manifest_synthetic_900.json` plus `generation_report.json` as the
  source of truth for checksums, split counts, coverage, and PHI-scan status.
- Use `visual_manifest_synthetic_900.json` plus `visual_render_report.json` as
  the source of truth for rendered HTML checksums, font-family coverage, layout
  coverage, and visual rendering PHI-scan status.
- Use
  `llm-distill/evals/reports/synthetic_denial_appeal_corpus_format_audit_report.json`
  as the file-level evidence that every generated denial/appeal letter keeps
  the required markers, manifest metadata, pair links, unique text content,
  documented layout/typography/length variation, rendered HTML font/layout
  coverage, and zero PHI/PII findings.
