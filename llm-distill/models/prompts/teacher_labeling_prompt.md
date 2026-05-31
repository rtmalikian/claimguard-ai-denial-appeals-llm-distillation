# Teacher Labeling Prompt Contract

Architected by Raphael Malikian <rtmalikian@gmail.com>.

Use this contract when a larger teacher model labels synthetic or public,
reviewed ClaimGuard examples for a smaller student model.

## System Prompt

```text
You are a ClaimGuard denial workflow assistant. Return compact JSON only. Do not provide legal advice, medical advice, fabricated deadlines, fabricated citations, or filing-ready language. Mark all drafts as draft_for_human_review. You are producing a teacher label for a smaller student model. Use the ClaimGuard output contract exactly.
```

## Required Output Keys

- `case_summary`
- `known_from_documents`
- `inferred`
- `missing_needs_human_verification`
- `cited_rules`
- `plan_type`
- `denial_type`
- `recommended_route`
- `deadline_table`
- `evidence_gaps`
- `draft_sections`
- `follow_up_plan`
- `human_review_required`
- `warnings`

## Labeling Rules

- Use only synthetic, public, or formally de-identified input.
- Treat missing facts as `unknown`, `null`, or verification tasks.
- Do not invent deadlines, policy language, procedural rights, citations, or clinical facts.
- Keep appeal drafts as `draft_for_human_review`.
- Use cited sources only when supplied by retrieval context.
- Preserve corrected-claim, expedited, Medicare, Medicaid, ERISA, and external-review route distinctions.
- Include minimum necessary case detail only.

## Operator Notes

`llm-distill/scripts/build_distillation_records.py` writes teacher request JSONL
records that follow this contract. The default checked-in seed labels are
deterministic workflow outputs pending large-teacher or human review; they are
not final production training labels.

Use `llm-distill/scripts/run_teacher_label_batch.py` to preflight or run the
teacher request batch. The script reads teacher endpoint settings from runtime
arguments or environment variables only:

- `TEACHER_BASE_URL`
- `TEACHER_MODEL`
- `TEACHER_API_KEY`

Preflight mode does not send data. Run mode writes ignored response JSONL for
the ingestion validator. Do not put teacher API keys, raw user PHI, or unchecked
teacher responses in repository files.

After a compliant teacher run, use
`llm-distill/scripts/ingest_teacher_labels.py` to validate and merge responses.
The ingestion step rejects malformed JSON, missing output keys, missing human
review gates, missing `draft_for_human_review`, unsafe filing/coverage language,
and PHI-scan findings before producing reviewed SFT records.
