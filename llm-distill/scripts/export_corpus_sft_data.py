#!/usr/bin/env python3
"""Export approved de-identified corpus pairs into guarded MLX-LM SFT splits."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "health-ai-medical-billing-medical-corporations-20260414_180528"
DISTILL_DIR = REPO_ROOT / "llm-distill"
DEFAULT_MANIFEST = DISTILL_DIR / "data" / "corpus" / "manifest.json"
DEFAULT_OUTPUT_DIR = DISTILL_DIR / "data" / "distillation" / "mlx_sft_corpus"
DEFAULT_ADAPTER_PATH = (
    DISTILL_DIR / "models" / "adapters" / "claimguard-qwen3-4b-lora-corpus"
)
REQUIRED_SPLITS = ("train", "valid", "test")
REQUIRED_ROLES = ("denial_letter", "appeal_letter")
SYSTEM_PROMPT = (
    "You are a ClaimGuard denial workflow assistant. Return compact JSON only. "
    "Do not provide legal advice, medical advice, fabricated deadlines, "
    "fabricated citations, or filing-ready language. Mark all drafts as "
    "draft_for_human_review."
)

for import_path in (APP_ROOT, SCRIPT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app.schemas.corpus import CorpusManifestRecord  # noqa: E402
from app.services.corpus import CorpusSafetyService  # noqa: E402
from prepare_mlx_sft_data import (  # noqa: E402
    REQUIRED_MICRO_SKILLS,
    build_train_command,
    write_command_file,
)
from run_phi_scan import scan_text  # noqa: E402


def load_manifest_records(path: Path) -> tuple[list[CorpusManifestRecord], list[str]]:
    if not path.exists():
        return [], [f"manifest not found: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"manifest is not valid JSON: {exc}"]

    raw_records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(raw_records, list):
        return [], ["manifest JSON must be a list or an object with records"]

    records: list[CorpusManifestRecord] = []
    errors: list[str] = []
    for index, raw_record in enumerate(raw_records, start=1):
        try:
            records.append(CorpusManifestRecord.model_validate(raw_record))
        except Exception as exc:  # Pydantic versions expose different exception types.
            errors.append(f"records[{index}] is invalid: {exc}")
    return records, errors


def resolve_local_text_path(raw_path: str, document_root: Path | None = None) -> tuple[Path | None, str | None]:
    parsed = urlparse(raw_path)
    if parsed.scheme in {"http", "https", "s3", "gs", "synthetic"}:
        return None, f"document source must be a local de-identified text file, not {parsed.scheme}://"
    if parsed.scheme == "file":
        path = Path(parsed.path)
    else:
        path = Path(raw_path)
    if not path.is_absolute():
        base = document_root or REPO_ROOT
        path = (base / path).resolve()
    if not path.exists():
        return None, f"document source file not found: {path}"
    if not path.is_file():
        return None, f"document source is not a file: {path}"
    return path, None


def read_document_text(record: CorpusManifestRecord, document_root: Path | None) -> tuple[str | None, str | None]:
    path, error = resolve_local_text_path(record.source_url_or_path, document_root)
    if error or path is None:
        return None, error
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, f"document source is not UTF-8 text: {path}"
    except OSError as exc:
        return None, f"document source could not be read: {path}: {exc}"


def checksum_matches(text: str, declared_checksum: str) -> bool:
    actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
    normalized = declared_checksum.removeprefix("sha256:").lower()
    return normalized == actual


def record_blockers(
    record: CorpusManifestRecord,
    text: str,
    *,
    source_path: Path,
) -> list[str]:
    blockers: list[str] = []
    if not checksum_matches(text, record.checksum):
        blockers.append(f"{record.document_id}: checksum mismatch")
    findings = scan_text(source_path, text)
    if findings:
        finding_types = sorted({finding["finding_type"] for finding in findings})
        blockers.append(
            f"{record.document_id}: PHI/PII scan findings in de-identified source: {finding_types}"
        )
    return blockers


def split_for_pair(denial: CorpusManifestRecord, appeal: CorpusManifestRecord) -> tuple[str | None, str | None]:
    if denial.split != appeal.split:
        return None, f"pair {denial.pair_id}: denial and appeal records must share the same split"
    if denial.split not in REQUIRED_SPLITS:
        return None, f"pair {denial.pair_id}: split must be train, valid, or test for SFT export"
    return denial.split, None


def metadata_value(record: CorpusManifestRecord, key: str) -> str:
    value = getattr(record, key)
    return value if isinstance(value, str) and value.strip() else "unknown"


def assistant_payload(
    *,
    pair_id: str,
    denial: CorpusManifestRecord,
    appeal: CorpusManifestRecord,
    appeal_text: str,
) -> dict[str, Any]:
    plan_type = metadata_value(denial, "payer_type")
    denial_type = metadata_value(denial, "denial_type")
    route = metadata_value(denial, "appeal_route")
    return {
        "case_summary": (
            f"De-identified corpus pair {pair_id} links an approved denial example "
            "to a reviewed appeal-letter example."
        ),
        "known_from_documents": [
            {
                "field": "denial_letter_document_id",
                "value": denial.document_id,
                "source": denial.source_id,
            },
            {
                "field": "appeal_letter_document_id",
                "value": appeal.document_id,
                "source": appeal.source_id,
            },
        ],
        "inferred": [],
        "missing_needs_human_verification": [
            "Verify current payer rule, filing authority, deadline, attachments, and clinical facts before use."
        ],
        "cited_rules": [],
        "plan_type": plan_type,
        "denial_type": denial_type,
        "recommended_route": route,
        "deadline_table": [],
        "evidence_gaps": [
            "Corpus example does not replace current source validation or deadline verification."
        ],
        "draft_sections": [
            {
                "section_id": "appeal_letter",
                "draft_status": "draft_for_human_review",
                "body": appeal_text,
            }
        ],
        "follow_up_plan": [
            "Use only as supervised learning signal after the corpus manifest remains training eligible."
        ],
        "human_review_required": True,
        "warnings": [
            "De-identified training example; not legal, medical, or filing-ready advice."
        ],
    }


def user_prompt(
    *,
    pair_id: str,
    denial: CorpusManifestRecord,
    appeal: CorpusManifestRecord,
    denial_text: str,
) -> str:
    payload = {
        "task": "Produce ClaimGuard appeal-generation JSON from this approved de-identified corpus pair.",
        "rules": [
            "Use only the de-identified denial document and reviewed corpus metadata.",
            "Do not invent deadlines, citations, clinical facts, or filing authority.",
            "Every appeal draft must remain draft_for_human_review.",
            "Preserve minimum necessary detail and do not add patient identifiers.",
        ],
        "pair_id": pair_id,
        "denial_document": {
            "document_id": denial.document_id,
            "source_id": denial.source_id,
            "source_type": denial.source_type,
            "document_role": denial.document_role,
            "text": denial_text,
        },
        "target_appeal_document": {
            "document_id": appeal.document_id,
            "source_id": appeal.source_id,
            "document_role": appeal.document_role,
        },
        "coverage": {
            "micro_skill_ids": sorted(set(denial.micro_skill_ids + appeal.micro_skill_ids)),
            "payer_type": metadata_value(denial, "payer_type"),
            "denial_type": metadata_value(denial, "denial_type"),
            "appeal_route": metadata_value(denial, "appeal_route"),
            "appeal_level": metadata_value(denial, "appeal_level"),
            "outcome": metadata_value(appeal, "outcome"),
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def build_pair_row(
    *,
    pair_id: str,
    denial: CorpusManifestRecord,
    appeal: CorpusManifestRecord,
    denial_text: str,
    appeal_text: str,
) -> dict[str, Any]:
    micro_skill_ids = sorted(set(denial.micro_skill_ids + appeal.micro_skill_ids))
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": user_prompt(
                    pair_id=pair_id,
                    denial=denial,
                    appeal=appeal,
                    denial_text=denial_text,
                ),
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    assistant_payload(
                        pair_id=pair_id,
                        denial=denial,
                        appeal=appeal,
                        appeal_text=appeal_text,
                    ),
                    sort_keys=True,
                ),
            },
        ],
        "metadata": {
            "pair_id": pair_id,
            "document_ids": {
                "denial_letter": denial.document_id,
                "appeal_letter": appeal.document_id,
            },
            "source_ids": {
                "denial_letter": denial.source_id,
                "appeal_letter": appeal.source_id,
            },
            "micro_skill_ids": micro_skill_ids,
            "coverage": {
                "payer_type": metadata_value(denial, "payer_type"),
                "denial_type": metadata_value(denial, "denial_type"),
                "appeal_route": metadata_value(denial, "appeal_route"),
                "appeal_level": metadata_value(denial, "appeal_level"),
                "outcome": metadata_value(appeal, "outcome"),
                "source_type": denial.source_type,
                "document_roles": list(REQUIRED_ROLES),
            },
        },
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def coverage_counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                row["metadata"]["coverage"].get(field, "unknown")
                for row in rows
            ).items()
        )
    )


def micro_skill_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                skill_id
                for row in rows
                for skill_id in row["metadata"].get("micro_skill_ids", [])
            ).items()
        )
    )


def write_manifest(
    *,
    path: Path,
    manifest_path: Path,
    output_dir: Path,
    records: list[CorpusManifestRecord],
    rows_by_split: dict[str, list[dict[str, Any]]],
    blocked_reasons: list[str],
    ignored_records: dict[str, int],
    model: str,
    adapter_path: Path,
    train_command: list[str],
) -> dict[str, Any]:
    rows = [row for split in REQUIRED_SPLITS for row in rows_by_split.get(split, [])]
    skill_counts = micro_skill_counts(rows)
    missing_required_skills = sorted(REQUIRED_MICRO_SKILLS - set(skill_counts))
    split_counts = {split: len(rows_by_split.get(split, [])) for split in REQUIRED_SPLITS}
    for split, count in split_counts.items():
        if count <= 0:
            blocked_reasons.append(f"{split}.jsonl must contain at least one corpus pair")
    if missing_required_skills:
        blocked_reasons.append(
            "Missing required ClaimGuard micro-skill coverage: "
            + ", ".join(missing_required_skills)
        )

    unique_blockers = sorted(set(blocked_reasons))
    phi_statuses = {record.phi_status for record in records if record.training_eligible}
    data_phi_status = "deidentified" if "deidentified" in phi_statuses else "no_phi"
    payload = {
        "artifact": "claimguard_mlx_sft_corpus",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "adapter_path": str(adapter_path),
        "format": "mlx_lm_chat_jsonl",
        "training_allowed": not unique_blockers,
        "blocked_reasons": unique_blockers,
        "source_manifest": str(manifest_path),
        "record_count": len(rows),
        "pair_count": len(rows),
        "exported_document_count": len(rows) * 2,
        "eligible_manifest_record_count": sum(1 for record in records if record.training_eligible),
        "ignored_records": ignored_records,
        "split_counts": split_counts,
        "pair_ids": [row["metadata"]["pair_id"] for row in rows],
        "required_micro_skill_ids": sorted(REQUIRED_MICRO_SKILLS),
        "missing_required_micro_skill_ids": missing_required_skills,
        "micro_skill_coverage_complete": not missing_required_skills,
        "micro_skill_counts": skill_counts,
        "coverage_counts": {
            "payer_type": coverage_counts(rows, "payer_type"),
            "denial_type": coverage_counts(rows, "denial_type"),
            "appeal_route": coverage_counts(rows, "appeal_route"),
            "appeal_level": coverage_counts(rows, "appeal_level"),
            "outcome": coverage_counts(rows, "outcome"),
            "source_type": coverage_counts(rows, "source_type"),
            "document_role": dict.fromkeys(REQUIRED_ROLES, len(rows)),
        },
        "data_safety": {
            "data_tier": "approved_deidentified_corpus",
            "phi_status": data_phi_status,
            "user_phi_allowed": False,
            "requires_training_eligible_manifest_records": True,
            "requires_privacy_review": True,
            "requires_checksum_match": True,
            "requires_zero_phi_scan_findings": True,
            "external_model_calls_made": False,
            "local_model_weights_written": False,
        },
        "quality_gates": {
            "paired_denial_appeal_relationships_preserved": True,
            "draft_for_human_review_required": True,
            "source_grounding_required": True,
            "hallucinated_deadlines_and_citations_blocked_by_prompt": True,
            "route_and_authority_require_human_verification": True,
        },
        "train_command": train_command,
        "notes": [
            "Only manifest records with training_eligible=true are considered for export.",
            "Each exported row preserves its denial_letter plus appeal_letter pair_id in metadata.",
            "The assistant completion remains draft_for_human_review and is not filing-ready.",
            "Run run_mlx_finetune.py against this manifest before any LoRA command.",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_command_file(
        output_dir / "train_lora_command.txt",
        train_command,
        training_allowed=payload["training_allowed"],
    )
    return payload


def export_corpus_sft(
    *,
    manifest_path: Path,
    output_dir: Path,
    model: str,
    adapter_path: Path,
    document_root: Path | None = None,
    iters: int = 60,
    steps_per_report: int = 10,
    steps_per_eval: int = 30,
) -> dict[str, Any]:
    records, load_errors = load_manifest_records(manifest_path)
    blocked_reasons = list(load_errors)
    eligible_records = [record for record in records if record.training_eligible]
    ignored_records = {
        "not_training_eligible": len(records) - len(eligible_records),
        "non_pair_role": 0,
    }

    validation = CorpusSafetyService(manifest_path=manifest_path).validate_manifest(records)
    for issue in validation.issues:
        if issue.document_id in {record.document_id for record in eligible_records}:
            blocked_reasons.append(
                f"{issue.document_id}: {issue.field}: {issue.code}: {issue.message}"
            )
    if validation.missing_categories:
        blocked_reasons.append(
            "Corpus manifest is missing required training categories: "
            + ", ".join(validation.missing_categories)
        )

    records_by_id = {record.document_id: record for record in eligible_records}
    document_texts: dict[str, str] = {}
    for record in eligible_records:
        text, error = read_document_text(record, document_root)
        if error or text is None:
            blocked_reasons.append(f"{record.document_id}: {error}")
            continue
        source_path, _ = resolve_local_text_path(record.source_url_or_path, document_root)
        blocked_reasons.extend(
            record_blockers(record, text, source_path=source_path or Path(record.source_url_or_path))
        )
        document_texts[record.document_id] = text

    pairs: dict[str, dict[str, CorpusManifestRecord]] = defaultdict(dict)
    for record in eligible_records:
        if record.document_role not in REQUIRED_ROLES:
            ignored_records["non_pair_role"] += 1
            continue
        if not record.pair_id:
            blocked_reasons.append(f"{record.document_id}: training record requires pair_id")
            continue
        pair = pairs[record.pair_id]
        if record.document_role in pair:
            blocked_reasons.append(f"pair {record.pair_id}: duplicate {record.document_role} record")
        pair[record.document_role] = record

    rows_by_split: dict[str, list[dict[str, Any]]] = {split: [] for split in REQUIRED_SPLITS}
    for pair_id, pair_records in sorted(pairs.items()):
        missing_roles = [role for role in REQUIRED_ROLES if role not in pair_records]
        if missing_roles:
            blocked_reasons.append(f"pair {pair_id}: missing roles {missing_roles}")
            continue
        denial = pair_records["denial_letter"]
        appeal = pair_records["appeal_letter"]
        if denial.document_id not in records_by_id or appeal.document_id not in records_by_id:
            blocked_reasons.append(f"pair {pair_id}: all pair records must be training eligible")
            continue
        split, split_error = split_for_pair(denial, appeal)
        if split_error or split is None:
            blocked_reasons.append(split_error or f"pair {pair_id}: split unavailable")
            continue
        denial_text = document_texts.get(denial.document_id)
        appeal_text = document_texts.get(appeal.document_id)
        if denial_text is None or appeal_text is None:
            blocked_reasons.append(f"pair {pair_id}: source text unavailable")
            continue
        row = build_pair_row(
            pair_id=pair_id,
            denial=denial,
            appeal=appeal,
            denial_text=denial_text,
            appeal_text=appeal_text,
        )
        row_findings = scan_text(output_dir / f"{split}.jsonl", json.dumps(row, sort_keys=True))
        if row_findings:
            finding_types = sorted({finding["finding_type"] for finding in row_findings})
            blocked_reasons.append(f"pair {pair_id}: generated SFT row has PHI/PII findings: {finding_types}")
            continue
        rows_by_split[split].append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    for split in REQUIRED_SPLITS:
        write_jsonl(output_dir / f"{split}.jsonl", rows_by_split[split])

    train_command = build_train_command(
        model,
        output_dir,
        adapter_path,
        iters=iters,
        steps_per_report=steps_per_report,
        steps_per_eval=steps_per_eval,
    )
    return write_manifest(
        path=output_dir / "manifest.json",
        manifest_path=manifest_path,
        output_dir=output_dir,
        records=records,
        rows_by_split=rows_by_split,
        blocked_reasons=blocked_reasons,
        ignored_records=ignored_records,
        model=model,
        adapter_path=adapter_path,
        train_command=train_command,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--document-root", type=Path, default=None)
    parser.add_argument("--model", default="Qwen/Qwen3-4B-MLX-4bit")
    parser.add_argument("--adapter-path", type=Path, default=DEFAULT_ADAPTER_PATH)
    parser.add_argument("--iters", type=int, default=60)
    parser.add_argument("--steps-per-report", type=int, default=10)
    parser.add_argument("--steps-per-eval", type=int, default=30)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    manifest = export_corpus_sft(
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        document_root=args.document_root,
        model=args.model,
        adapter_path=args.adapter_path,
        iters=args.iters,
        steps_per_report=args.steps_per_report,
        steps_per_eval=args.steps_per_eval,
    )
    print(
        "wrote corpus MLX SFT export to "
        f"{args.output_dir} "
        f"(training_allowed={manifest['training_allowed']}, pairs={manifest['pair_count']})"
    )
    if args.fail_on_blocked and not manifest["training_allowed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
