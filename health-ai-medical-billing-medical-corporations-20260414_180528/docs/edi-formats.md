# ClaimGuard EDI Format Notes

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current Objective Scratchpad: Document current EDI 837/835 parser behavior and
safe error boundaries without introducing real EDI files, PHI, payer data,
credentials, or production clearinghouse content.

## Scope

This document describes the current EDI handling in:

- `app/api/v1/claims.py`
- `app/utils/edi_parser.py`
- `app/utils/edi_835_parser.py`
- `tests/unit/test_claims_batch_upload.py`
- `tests/unit/test_edi_835_parser.py`

It is not a full X12 implementation guide and does not approve production
clearinghouse connectivity.

## EDI 837 Batch Upload

Current API route:

| Method | Route | Required roles |
|---|---|---|
| `POST` | `/api/v1/claims/batch-upload` | `admin`, `billing_staff` |

The route accepts UTF-8 text uploads with `.edi` or `.txt` extensions and a
maximum size of 10 MB. It rejects unsupported extensions, empty files,
oversized uploads, and non-UTF-8 payloads before parsing.

The parser detects separators from the ISA envelope when present. It otherwise
uses the default `*` element separator, `:` component separator, and `~`
segment terminator, with newline-separated fallback for simple local fixtures.

### Parsed 837 Elements

| Area | Current extraction |
|---|---|
| Envelope | ISA13, GS06, ST02 control values |
| Payer context | `NM1*PR` name and identifier |
| Claim loop | `CLM` loop reference and total charge amount |
| Diagnoses | `HI` composites with supported diagnosis qualifiers |
| Professional service lines | `SV1` procedure code, modifiers, charge amount, unit count, qualifier, diagnosis pointers |
| Institutional service lines | `SV2` revenue code, procedure code, modifiers, charge amount, unit count, qualifier |

Validation issues are attached to the relevant claim or service-line context
when required fields are missing. Current validation checks include missing
claim loop, missing diagnosis codes, missing service lines, missing payer
context, missing claim reference, and missing service-line procedure codes.

### 837 Response Boundaries

The batch upload response returns structured parse summaries:

- Accepted flag.
- Source file extension and MIME type.
- Segment, claim, valid-claim, invalid-claim, and validation-issue counts.
- Envelope control values.
- Metadata-only document-surface inspection summary.
- Per-claim extracted billing fields and validation issues.

The response and audit events must not include raw EDI text, raw segment
payloads, raw filenames, PHI, credentials, or production document content.
Parser errors and warnings expose only safe context:

| Field | Meaning |
|---|---|
| `error_code` | Stable machine-readable error identifier |
| `parser_stage` | Parser stage such as `file_validation`, `segment_split`, `claim_validation`, or `service_line_parse` |
| `field` | Safe field category |
| `claim_index` | Ordinal claim position when applicable |
| `segment_index` | Ordinal segment position when applicable |
| `segment_id` | Segment identifier such as `CLM`, `HI`, `SV1`, or `SV2` |
| `segment_count` | Safe aggregate segment count when available |
| `safe_context` | Flags proving raw EDI text and raw segment payloads were not included |

## EDI 835 Parser Utility

Current parser utility:

| Utility | Current exposure |
|---|---|
| `app/utils/edi_835_parser.py` | Internal parser and unit-tested utility; no public upload endpoint is currently registered. |

The 835 parser extracts safe claim-payment and adjustment summaries from CLP
and CAS segments. It detects envelope delimiters the same way as the 837 parser.

### Parsed 835 Elements

| Area | Current extraction |
|---|---|
| Envelope | ISA13, GS06, ST02 control values |
| Claim payment | `CLP` control reference, status code, total charge amount, paid amount, responsibility amount, payer reference |
| Payment status | Derived as `paid`, `partially_paid`, `denied`, or `unknown` |
| Adjustments | `CAS` group code, reason code, amount, and optional quantity |

Current validation checks include missing CLP segments, CAS before CLP, missing
CAS group code, incomplete CAS adjustment triplets, missing reason codes,
invalid adjustment amounts, and missing/invalid CLP amount fields.

## Future EDI Endpoint Requirements

Any future EDI 835 upload route or expanded clearinghouse integration must:

- Require bearer authentication and role-scoped authorization.
- Register the route in `llm-distill/scripts/audit_file_ingestion_surfaces.py`.
- Run metadata-only document-surface inspection before storage or downstream
  processing.
- Enforce file size, extension, MIME, and text-decoding validation before parse.
- Preserve loops, service lines, delimiters, modifiers, control values,
  adjustment details, and remittance summaries without truncating or reordering
  parsed structures casually.
- Return structured parser errors without raw EDI text or raw segment payloads.
- Log safe aggregate metadata only.
- Keep real clearinghouse credentials and production EDI files outside source
  control.

