#!/usr/bin/env python3
"""Audit end-to-end readiness for ClaimGuard student-model distillation."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_phi_scan import scan_text


REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
DATA_DIR = DISTILL_DIR / "data" / "distillation"
REPORT_DIR = DISTILL_DIR / "evals" / "reports"

DEFAULT_REPORT = REPORT_DIR / "distillation_readiness_audit_report.json"
DEFAULT_SOURCE_REGISTRY = DISTILL_DIR / "data" / "source_registry.json"
DEFAULT_CORPUS_MANIFEST = DISTILL_DIR / "data" / "corpus" / "manifest.json"
DEFAULT_SYNTHETIC_900_DIR = DISTILL_DIR / "data" / "corpus" / "generated_synthetic_pairs"
DEFAULT_SYNTHETIC_900_GENERATION_REPORT = DEFAULT_SYNTHETIC_900_DIR / "generation_report.json"
DEFAULT_SYNTHETIC_900_MANIFEST = DEFAULT_SYNTHETIC_900_DIR / "manifest_synthetic_900.json"
DEFAULT_SYNTHETIC_900_FORMAT_AUDIT_REPORT = REPORT_DIR / (
    "synthetic_denial_appeal_corpus_format_audit_report.json"
)
DEFAULT_SYNTHETIC_DOCUMENT_ANALYSIS_EXTRACTION_REPORT = REPORT_DIR / (
    "synthetic_document_analysis_extraction_report.json"
)
DEFAULT_SEED_RECORDS = DATA_DIR / "seed_synthetic_supervised.jsonl"
DEFAULT_TEACHER_REQUESTS = DATA_DIR / "teacher_label_requests.jsonl"
DEFAULT_SEED_SFT_MANIFEST = DATA_DIR / "mlx_sft_seed" / "manifest.json"
DEFAULT_REVIEWED_SFT_MANIFEST = DATA_DIR / "mlx_sft_reviewed" / "manifest.json"
DEFAULT_CORPUS_SFT_MANIFEST = DATA_DIR / "mlx_sft_corpus" / "manifest.json"
DEFAULT_SYNTHETIC_900_SFT_MANIFEST = DATA_DIR / "mlx_sft_synthetic_900" / "manifest.json"
DEFAULT_WORKFLOW_REPORT = REPORT_DIR / "workflow_baseline_report.json"
DEFAULT_TEACHER_BATCH_REPORT = REPORT_DIR / "teacher_label_batch_preflight_report.json"
DEFAULT_TEACHER_REVIEW_PACKET = DATA_DIR / "teacher_review_packet.jsonl"
DEFAULT_TEACHER_REVIEW_PACKET_REPORT = REPORT_DIR / "teacher_review_packet_report.json"
DEFAULT_FILE_INGESTION_SURFACE_REPORT = REPORT_DIR / "file_ingestion_surface_audit_report.json"
DEFAULT_MLX_RUNTIME_REPORT = REPORT_DIR / "mlx_runtime_preflight_report.json"
DEFAULT_FINE_TUNE_REPORT = REPORT_DIR / "mlx_finetune_preflight_report.json"
DEFAULT_SYNTHETIC_900_FINE_TUNE_REPORT = REPORT_DIR / "mlx_finetune_synthetic_900_run_report.json"
DEFAULT_BASE_BENCHMARK = REPORT_DIR / "local_mlx_benchmark_report.json"
DEFAULT_STUDENT_BENCHMARK = REPORT_DIR / "student_mlx_benchmark_report.json"
DEFAULT_ACCEPTANCE_REPORT = REPORT_DIR / "student_acceptance_report.json"
DEFAULT_PIPELINE_REPORT = REPORT_DIR / "reviewed_distillation_pipeline_report.json"
EXTERNAL_PATH_REDACTION = "external_path_redacted"
LOCAL_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])/(?:Users|private|tmp|var|Volumes)/[^\s\"']+"
)
REQUIRED_MICRO_SKILLS = [f"MS{index:02d}" for index in range(1, 13)]
REVIEWED_STATUS_KEYS = {"large_teacher_reviewed", "human_reviewed"}
TRAINING_ALLOWED_PHI_STATUSES = {"no_phi", "deidentified"}
TRAINING_ALLOWED_REVIEW_STATUSES = {"privacy_review_passed", "training_approved"}
TRAINING_BLOCKED_LICENSE_STATUSES = {"review_required", "unknown", "prohibited"}
CORPUS_SFT_DATA_TIERS = {"approved_deidentified_corpus", "safe_hybrid_corpus"}
REQUIRED_CORPUS_ROLES = {"denial_letter", "appeal_letter"}
REQUIRED_CORPUS_COVERAGE = [
    "payer_type",
    "denial_type",
    "appeal_route",
    "appeal_level",
    "outcome",
    "source_type",
    "document_role",
]
REQUIRED_SPLITS = ["train", "valid", "test"]
MAX_TRAINING_RESIDUAL_RISK = 0.2
NEXT_ACTION_BY_REQUIREMENT = {
    "phase1_source_registry": "Refresh the public source registry until it has trusted, no-PHI source evidence.",
    "phase6_corpus_manifest_training_gates": "Build a safe hybrid corpus with approved no-PHI or de-identified denial/appeal pairs, privacy review, residual-risk review, and training_eligible=true manifest records.",
    "phase6_corpus_sft_export": "Run llm-distill/scripts/export_corpus_sft_data.py after the corpus manifest has approved train/valid/test denial/appeal pairs and MS01-MS12 coverage.",
    "phase6_synthetic_900_stress_corpus": "Regenerate the deterministic synthetic 900-pair denial/appeal corpus and keep zero PHI findings before using it for stress testing.",
    "phase6_synthetic_900_format_contract_audit": "Run llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py so every generated synthetic letter has the required formatting, metadata, pairing, uniqueness, and PHI-clean evidence.",
    "phase6_synthetic_document_analysis_extraction": "Run llm-distill/scripts/audit_synthetic_document_analysis_extraction.py so generated denial notices prove application document-analysis extraction coverage before stress testing.",
    "phase6_synthetic_900_sft_export": "Export the deterministic synthetic 900-pair corpus through llm-distill/scripts/export_corpus_sft_data.py before any synthetic-900 fine-tune attempt.",
    "phase7_synthetic_900_mlx_runtime_gate": "Rerun the synthetic-900 guarded LoRA command from a local macOS session where MLX can access Metal before promoting a synthetic-900 adapter.",
    "phase6_teacher_request_preflight": "Configure a compliant large-teacher endpoint or complete offline review packet approvals before using teacher labels.",
    "phase6_reviewed_teacher_labels": "Ingest reviewed labels only after human or compliant large-teacher approval.",
    "phase6_reviewed_sft_export": "Export reviewed MLX SFT data with training_allowed=true.",
    "safety_file_ingestion_surface_audit": "Run llm-distill/scripts/audit_file_ingestion_surfaces.py and register any new UploadFile endpoint with PHI surface inspection, governance, and safe audit markers.",
    "phase5_7_mlx_runtime_preflight": "Install MLX-LM training/runtime tools on the target Apple Silicon environment.",
    "phase7_student_fine_tune_run": "Complete a guarded LoRA run and keep adapter output in ignored model paths.",
    "phase7_base_live_benchmark": "Run a live base-model MLX benchmark over the full synthetic ClaimGuard scenario set.",
    "phase7_student_live_benchmark": "Run a live student-adapter MLX benchmark over the full synthetic ClaimGuard scenario set.",
    "phase7_student_acceptance": "Pass student acceptance before treating the adapter as release-ready.",
    "phase8_quantization_promotion": "Perform quantization or promotion only after acceptance and fine-tune evidence remain release-ready.",
}


def build_next_required_actions(blocked_items: list[dict[str, Any]], release_ready: bool) -> list[str]:
    if blocked_items:
        actions = []
        for item in blocked_items:
            requirement_id = item.get("requirement_id")
            action = NEXT_ACTION_BY_REQUIREMENT.get(requirement_id)
            if action and action not in actions:
                actions.append(action)
        if actions:
            return actions
        return ["Resolve blocked readiness requirements before any student promotion or default-model change."]
    if release_ready:
        return [
            "Keep CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false until Raphael approves production runtime/default cutover, CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=true, CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE is configured, CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=true, and CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA=false.",
            "Complete remaining PHIplan production controls before using real-world corpus examples: admin review/import UI, role-scoped document access, retention/deletion workflows, audit dashboards, and legal/BAA/consent review.",
            "If building a corpus-derived adapter, run run_mlx_finetune.py against llm-distill/data/distillation/mlx_sft_corpus/manifest.json and repeat live benchmark plus acceptance gates before promotion.",
        ]
    return ["Resolve readiness warnings and acceptance evidence before any student promotion or default-model change."]


def default_sft_manifest() -> Path:
    if DEFAULT_REVIEWED_SFT_MANIFEST.exists():
        return DEFAULT_REVIEWED_SFT_MANIFEST
    return DEFAULT_SEED_SFT_MANIFEST


def sanitize_report_string(value: str) -> str:
    repo_root = str(REPO_ROOT.resolve())
    sanitized = value.replace(repo_root + "/", "")
    if sanitized == repo_root:
        return "."
    return LOCAL_ABSOLUTE_PATH_RE.sub(EXTERNAL_PATH_REDACTION, sanitized)


def sanitize_report_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_report_string(value)
    if isinstance(value, list):
        return [sanitize_report_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: sanitize_report_value(item)
            for key, item in value.items()
        }
    return value


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing file: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {path}: {exc}"]


def count_jsonl(path: Path) -> tuple[int | None, list[str]]:
    if not path.exists():
        return None, [f"missing file: {path}"]
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    if count <= 0:
        return count, [f"no JSONL records: {path}"]
    return count, []


def phi_scan_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "finding_count": None, "findings": []}
    findings = scan_text(path, path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "exists": True,
        "finding_count": len(findings),
        "findings": findings,
    }


def phi_scan_tree(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "file_count": 0,
            "finding_count": None,
            "findings": [],
            "read_errors": [f"missing path: {path}"],
        }
    if not path.is_dir():
        scan = phi_scan_file(path)
        scan["file_count"] = 1 if scan["exists"] else 0
        scan["read_errors"] = []
        return scan

    findings: list[dict[str, Any]] = []
    read_errors: list[str] = []
    file_count = 0
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        file_count += 1
        try:
            text = item.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            read_errors.append(f"non-UTF-8 file cannot be PHI-scanned: {item}")
            continue
        findings.extend(scan_text(item, text))
    return {
        "path": str(path),
        "exists": True,
        "file_count": file_count,
        "finding_count": len(findings),
        "findings": findings,
        "read_errors": read_errors,
    }


def status_from_blockers(blockers: list[str], warnings: list[str] | None = None) -> str:
    if blockers:
        return "blocked"
    if warnings:
        return "warning"
    return "ready"


def requirement(
    *,
    requirement_id: str,
    phase: str,
    name: str,
    status: str,
    evidence: dict[str, Any],
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "phase": phase,
        "name": name,
        "status": status,
        "blockers": blockers or [],
        "warnings": warnings or [],
        "evidence": evidence,
    }


def source_registry_requirement(path: Path, min_sources: int) -> dict[str, Any]:
    payload, errors = load_json(path)
    scan = phi_scan_file(path)
    blockers = list(errors)
    source_count = len(payload) if isinstance(payload, list) else None
    tier1_count = 0
    no_phi_count = 0
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("tier") == 1:
                tier1_count += 1
            if isinstance(item, dict) and item.get("phi_status") == "no_phi":
                no_phi_count += 1
        if source_count < min_sources:
            blockers.append(f"source registry must contain at least {min_sources} public/trusted sources")
        if no_phi_count != source_count:
            blockers.append("all checked-in source registry entries must be marked no_phi")
    else:
        blockers.append("source registry must be a JSON list")
    if scan["finding_count"]:
        blockers.append("source registry PHI/PII scan must have zero findings")
    return requirement(
        requirement_id="phase1_source_registry",
        phase="source_corpus",
        name="Public source registry is present, trusted, and PHI-clean",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={
            "path": str(path),
            "source_count": source_count,
            "tier1_count": tier1_count,
            "no_phi_count": no_phi_count,
            "phi_scan": scan,
        },
    )


def compliance_docs_requirement() -> dict[str, Any]:
    required_files = [
        DISTILL_DIR / "docs" / "safety-and-hipaa.md",
        DISTILL_DIR / "docs" / "data-sources.md",
        DISTILL_DIR / "docs" / "eval-rubric.md",
        DISTILL_DIR / "docs" / "mlx-setup.md",
        DISTILL_DIR / "models" / "prompts" / "teacher_labeling_prompt.md",
        DISTILL_DIR / "models" / "prompts" / "denial_workflow_prompts.md",
        REPO_ROOT / "denial_skill" / "SKILL.md",
        REPO_ROOT / "denial_skill" / "eval" / "distillation_dataset_design.md",
    ]
    blockers = [f"missing required documentation: {path}" for path in required_files if not path.exists()]
    return requirement(
        requirement_id="safety_compliance_docs",
        phase="safety_and_specification",
        name="Safety, prompt, and denial-skill specifications exist",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={"required_files": [str(path) for path in required_files]},
    )


def load_manifest_records(path: Path) -> tuple[list[dict[str, Any]], list[str], Any | None]:
    payload, errors = load_json(path)
    if errors:
        return [], errors, payload
    raw_records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(raw_records, list):
        return [], ["corpus manifest must be a JSON list or an object with records"], payload
    records = [record for record in raw_records if isinstance(record, dict)]
    if len(records) != len(raw_records):
        return records, ["corpus manifest records must all be JSON objects"], payload
    return records, [], payload


def corpus_manifest_requirement(path: Path, min_pairs: int) -> dict[str, Any]:
    records, errors, payload = load_manifest_records(path)
    scan = phi_scan_file(path)
    blockers = list(errors)
    warnings: list[str] = []
    training_records = [record for record in records if record.get("training_eligible") is True]
    role_counts: dict[str, int] = {}
    source_type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    phi_counts: dict[str, int] = {}
    pair_roles: dict[str, set[str]] = {}
    training_pair_ids: set[str] = set()
    complete_training_pair_ids: set[str] = set()

    for record in records:
        role = str(record.get("document_role", "unknown"))
        source_type = str(record.get("source_type", "unknown"))
        status = str(record.get("deidentification_status", "unknown"))
        phi_status = str(record.get("phi_status", "unknown"))
        role_counts[role] = role_counts.get(role, 0) + 1
        source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        phi_counts[phi_status] = phi_counts.get(phi_status, 0) + 1
        pair_id = record.get("pair_id")
        if isinstance(pair_id, str) and pair_id:
            pair_roles.setdefault(pair_id, set()).add(role)

    for record in training_records:
        document_id = record.get("document_id", "unknown_document")
        pair_id = record.get("pair_id")
        if isinstance(pair_id, str) and pair_id:
            training_pair_ids.add(pair_id)
        else:
            blockers.append(f"{document_id}: training-eligible corpus record requires pair_id")
        if record.get("phi_status") not in TRAINING_ALLOWED_PHI_STATUSES:
            blockers.append(f"{document_id}: training phi_status must be no_phi or deidentified")
        if record.get("deidentification_status") != "training_eligible":
            blockers.append(f"{document_id}: deidentification_status must be training_eligible")
        if record.get("review_status") not in TRAINING_ALLOWED_REVIEW_STATUSES:
            blockers.append(f"{document_id}: review_status must show privacy/training approval")
        if record.get("license_status") in TRAINING_BLOCKED_LICENSE_STATUSES:
            blockers.append(f"{document_id}: license_status is not approved for training")
        if record.get("split") not in REQUIRED_SPLITS:
            blockers.append(f"{document_id}: split must be train, valid, or test")
        if not isinstance(record.get("micro_skill_ids"), list) or not record.get("micro_skill_ids"):
            blockers.append(f"{document_id}: micro_skill_ids are required")
        residual_risk = record.get("residual_risk_score")
        if not isinstance(residual_risk, (int, float)) or residual_risk > MAX_TRAINING_RESIDUAL_RISK:
            blockers.append(f"{document_id}: residual_risk_score is too high for training")

    for pair_id in training_pair_ids:
        roles = pair_roles.get(pair_id, set())
        if REQUIRED_CORPUS_ROLES.issubset(roles):
            complete_training_pair_ids.add(pair_id)
        else:
            blockers.append(f"{pair_id}: training corpus pair must include denial_letter and appeal_letter")

    if len(complete_training_pair_ids) < min_pairs:
        blockers.append(
            f"corpus manifest must include at least {min_pairs} complete training-eligible denial/appeal pairs"
        )
    if not records:
        blockers.append("corpus manifest has no records")
    if scan["finding_count"]:
        blockers.append("corpus manifest PHI/PII scan must have zero findings")
    if isinstance(payload, dict) and not payload.get("version"):
        warnings.append("corpus manifest should include a version")

    return requirement(
        requirement_id="phase6_corpus_manifest_training_gates",
        phase="safe_corpus",
        name="Safe corpus manifest has reviewed de-identified training-eligible denial/appeal pairs",
        status=status_from_blockers(blockers, warnings),
        blockers=blockers,
        warnings=warnings,
        evidence={
            "path": str(path),
            "record_count": len(records),
            "training_eligible_count": len(training_records),
            "complete_training_pair_count": len(complete_training_pair_ids),
            "complete_training_pair_ids": sorted(complete_training_pair_ids),
            "counts_by_document_role": dict(sorted(role_counts.items())),
            "counts_by_source_type": dict(sorted(source_type_counts.items())),
            "public_government_source_count": source_type_counts.get(
                "public_government_source",
                0,
            ),
            "counts_by_deidentification_status": dict(sorted(status_counts.items())),
            "counts_by_phi_status": dict(sorted(phi_counts.items())),
            "phi_scan": scan,
        },
    )


def count_split_jsonl(path: Path) -> tuple[int | None, list[str]]:
    if not path.exists():
        return None, [f"missing split file: {path}"]
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                return count, [f"{path}:{line_number}: invalid JSONL row: {exc}"]
            count += 1
    return count, []


def corpus_sft_export_requirement(manifest_path: Path, corpus_manifest_path: Path, min_pairs: int) -> dict[str, Any]:
    manifest, errors = load_json(manifest_path)
    blockers = list(errors)
    warnings: list[str] = []
    evidence: dict[str, Any] = {"path": str(manifest_path)}
    if isinstance(manifest, dict):
        split_counts = manifest.get("split_counts", {})
        coverage_counts = manifest.get("coverage_counts", {})
        data_safety = manifest.get("data_safety", {})
        missing_skill_ids = manifest.get("missing_required_micro_skill_ids")
        output_dir = manifest_path.parent
        split_file_counts: dict[str, int | None] = {}
        split_phi_scans: dict[str, dict[str, Any]] = {}
        split_errors: list[str] = []
        for split in REQUIRED_SPLITS:
            split_path = output_dir / f"{split}.jsonl"
            split_count, count_errors = count_split_jsonl(split_path)
            split_file_counts[split] = split_count
            split_errors.extend(count_errors)
            split_phi_scans[split] = phi_scan_file(split_path)
            if split_phi_scans[split]["finding_count"]:
                blockers.append(f"corpus SFT {split}.jsonl PHI/PII scan must have zero findings")
            if isinstance(split_counts, dict) and split_count != split_counts.get(split):
                blockers.append(f"corpus SFT {split}.jsonl count must match manifest split_counts")
        blockers.extend(split_errors)
        evidence.update(
            {
                "artifact": manifest.get("artifact"),
                "training_allowed": manifest.get("training_allowed"),
                "blocked_reasons": manifest.get("blocked_reasons"),
                "source_manifest": manifest.get("source_manifest"),
                "pair_count": manifest.get("pair_count"),
                "record_count": manifest.get("record_count"),
                "split_counts": split_counts,
                "split_file_counts": split_file_counts,
                "split_phi_scans": split_phi_scans,
                "micro_skill_counts": manifest.get("micro_skill_counts"),
                "micro_skill_coverage_complete": manifest.get("micro_skill_coverage_complete"),
                "missing_required_micro_skill_ids": missing_skill_ids,
                "coverage_counts": coverage_counts,
                "data_safety": data_safety,
            }
        )
        if manifest.get("artifact") != "claimguard_mlx_sft_corpus":
            blockers.append("corpus SFT manifest artifact must be claimguard_mlx_sft_corpus")
        if manifest.get("training_allowed") is not True:
            blockers.append("corpus SFT manifest must show training_allowed=true")
            for reason in manifest.get("blocked_reasons", []):
                if isinstance(reason, str):
                    blockers.append(reason)
        if not isinstance(manifest.get("pair_count"), int) or manifest["pair_count"] < min_pairs:
            blockers.append(f"corpus SFT manifest must export at least {min_pairs} denial/appeal pairs")
        if not isinstance(split_counts, dict):
            blockers.append("corpus SFT manifest split_counts must be an object")
        else:
            for split in REQUIRED_SPLITS:
                if not isinstance(split_counts.get(split), int) or split_counts[split] <= 0:
                    blockers.append(f"corpus SFT manifest split_counts.{split} must be positive")
        if manifest.get("micro_skill_coverage_complete") is not True:
            blockers.append("corpus SFT manifest must show complete required micro-skill coverage")
        if missing_skill_ids:
            blockers.append(f"corpus SFT manifest is missing micro-skills: {missing_skill_ids}")
        if not isinstance(data_safety, dict):
            blockers.append("corpus SFT manifest data_safety must be an object")
        else:
            if data_safety.get("data_tier") not in CORPUS_SFT_DATA_TIERS:
                blockers.append("corpus SFT data_safety.data_tier must be an approved corpus tier")
            if data_safety.get("phi_status") not in TRAINING_ALLOWED_PHI_STATUSES:
                blockers.append("corpus SFT data_safety.phi_status must be no_phi or deidentified")
            if data_safety.get("user_phi_allowed") is not False:
                blockers.append("corpus SFT data_safety.user_phi_allowed must be false")
            if data_safety.get("requires_training_eligible_manifest_records") is not True:
                blockers.append("corpus SFT manifest must require training-eligible manifest records")
            if data_safety.get("requires_privacy_review") is not True:
                blockers.append("corpus SFT manifest must require privacy review")
            if data_safety.get("requires_zero_phi_scan_findings") is not True:
                blockers.append("corpus SFT manifest must require zero PHI scan findings")
        if not isinstance(coverage_counts, dict):
            blockers.append("corpus SFT manifest coverage_counts must be an object")
        else:
            for category in REQUIRED_CORPUS_COVERAGE:
                values = coverage_counts.get(category)
                if not isinstance(values, dict) or not values:
                    blockers.append(f"corpus SFT manifest must report coverage_counts.{category}")
                elif set(values) == {"unknown"}:
                    warnings.append(f"corpus SFT coverage_counts.{category} contains only unknown")
        source_manifest = manifest.get("source_manifest")
        if isinstance(source_manifest, str) and source_manifest:
            resolved_source = Path(source_manifest)
            if not resolved_source.is_absolute():
                resolved_source = (REPO_ROOT / resolved_source).resolve()
            if resolved_source != corpus_manifest_path.resolve():
                warnings.append("corpus SFT manifest source_manifest differs from configured corpus manifest path")
        else:
            blockers.append("corpus SFT manifest must include source_manifest")
    else:
        blockers.append("corpus SFT manifest must be a JSON object")
    return requirement(
        requirement_id="phase6_corpus_sft_export",
        phase="safe_corpus",
        name="Approved corpus entries are exported to guarded MLX chat SFT splits",
        status=status_from_blockers(blockers, warnings),
        blockers=blockers,
        warnings=warnings,
        evidence=evidence,
    )


def synthetic_900_corpus_requirement(
    generation_report_path: Path,
    manifest_path: Path,
    *,
    min_pairs: int,
    max_pairs: int,
) -> dict[str, Any]:
    report, report_errors = load_json(generation_report_path)
    records, manifest_errors, manifest_payload = load_manifest_records(manifest_path)
    blockers = [*report_errors, *manifest_errors]
    warnings: list[str] = []
    report_pair_count = None
    report_letter_count = None
    counts: dict[str, Any] = {}
    safety: dict[str, Any] = {}
    phi_scan: dict[str, Any] = {}
    output_dir = generation_report_path.parent
    if isinstance(report, dict):
        report_pair_count = report.get("pair_count")
        report_letter_count = report.get("letter_count")
        counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
        safety = report.get("safety") if isinstance(report.get("safety"), dict) else {}
        phi_scan = report.get("phi_scan") if isinstance(report.get("phi_scan"), dict) else {}
        if report.get("artifact") != "synthetic_denial_appeal_corpus":
            blockers.append("synthetic-900 generation report artifact is invalid")
        if not isinstance(report_pair_count, int) or not min_pairs <= report_pair_count <= max_pairs:
            blockers.append(
                f"synthetic corpus pair_count must be between {min_pairs} and {max_pairs}"
            )
        if not isinstance(report_letter_count, int) or report_letter_count != (report_pair_count or 0) * 2:
            blockers.append("synthetic corpus letter_count must equal pair_count * 2")
        if not isinstance(phi_scan, dict) or phi_scan.get("finding_count") != 0:
            blockers.append("synthetic corpus generation report PHI/PII scan must have zero findings")
        if safety.get("synthetic_only") is not True:
            blockers.append("synthetic corpus safety.synthetic_only must be true")
        if safety.get("real_patient_data_used") is not False:
            blockers.append("synthetic corpus safety.real_patient_data_used must be false")
        if safety.get("real_claim_data_used") is not False:
            blockers.append("synthetic corpus safety.real_claim_data_used must be false")
        if safety.get("training_allowed_only_after_export_gates") is not True:
            blockers.append("synthetic corpus must require export gates before training use")
        expected_count_families = {
            "denial_format": 8,
            "appeal_format": 8,
            "layout_profile": 12,
            "typography_profile": 8,
            "length_profile": 6,
        }
        for family, minimum in expected_count_families.items():
            values = counts.get(family)
            if not isinstance(values, dict) or len(values) < minimum:
                blockers.append(f"synthetic corpus counts.{family} must contain at least {minimum} variants")
        if isinstance(report.get("output_dir"), str):
            output_dir = resolve_report_path(report["output_dir"], generation_report_path.parent)
    else:
        blockers.append("synthetic-900 generation report must be a JSON object")

    letter_dir = output_dir / "letters"
    letter_scan = phi_scan_tree(letter_dir)
    if letter_scan["finding_count"]:
        blockers.append("synthetic-900 letter files PHI/PII scan must have zero findings")
    if letter_scan["read_errors"]:
        blockers.extend(letter_scan["read_errors"])

    role_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {}
    pair_roles: dict[str, set[str]] = {}
    missing_files: list[str] = []
    training_eligible_count = 0
    for record in records:
        role = str(record.get("document_role", "unknown"))
        split = str(record.get("split", "unknown"))
        role_counts[role] = role_counts.get(role, 0) + 1
        split_counts[split] = split_counts.get(split, 0) + 1
        if record.get("training_eligible") is True:
            training_eligible_count += 1
        if record.get("phi_status") != "no_phi":
            blockers.append(f"{record.get('document_id', 'unknown_document')}: phi_status must be no_phi")
        pair_id = record.get("pair_id")
        if isinstance(pair_id, str) and pair_id:
            pair_roles.setdefault(pair_id, set()).add(role)
        source_path = record.get("source_url_or_path")
        if isinstance(source_path, str) and source_path:
            resolved_source = resolve_report_path(source_path, REPO_ROOT)
            if not resolved_source.exists():
                missing_files.append(source_path)
    complete_pair_ids = sorted(
        pair_id for pair_id, roles in pair_roles.items() if REQUIRED_CORPUS_ROLES.issubset(roles)
    )
    if report_letter_count is not None and len(records) != report_letter_count:
        blockers.append("synthetic-900 manifest record count must match generation report letter_count")
    if report_pair_count is not None and len(complete_pair_ids) != report_pair_count:
        blockers.append("synthetic-900 manifest must preserve all denial/appeal pair relationships")
    if training_eligible_count != len(records):
        blockers.append("synthetic-900 manifest records must all remain training_eligible=true")
    if missing_files:
        blockers.append(f"synthetic-900 manifest references missing letter files: {missing_files[:5]}")
    for split in REQUIRED_SPLITS:
        if split_counts.get(split, 0) <= 0:
            blockers.append(f"synthetic-900 manifest split {split} must contain records")
    if letter_scan["file_count"] and report_letter_count and letter_scan["file_count"] != report_letter_count:
        blockers.append("synthetic-900 letter file count must match generation report letter_count")
    if isinstance(manifest_payload, dict) and not manifest_payload.get("version"):
        warnings.append("synthetic-900 manifest should include a version")

    return requirement(
        requirement_id="phase6_synthetic_900_stress_corpus",
        phase="synthetic_data",
        name="Generated 900-pair denial/appeal stress corpus is present, varied, paired, and PHI-clean",
        status=status_from_blockers(blockers, warnings),
        blockers=blockers,
        warnings=warnings,
        evidence={
            "generation_report": str(generation_report_path),
            "manifest": str(manifest_path),
            "pair_count": report_pair_count,
            "letter_count": report_letter_count,
            "manifest_record_count": len(records),
            "training_eligible_count": training_eligible_count,
            "complete_pair_count": len(complete_pair_ids),
            "counts": counts,
            "safety": safety,
            "generation_report_phi_scan": phi_scan,
            "letter_tree_phi_scan": letter_scan,
            "counts_by_document_role": dict(sorted(role_counts.items())),
            "counts_by_split": dict(sorted(split_counts.items())),
            "missing_file_count": len(missing_files),
        },
    )


def synthetic_900_format_contract_requirement(
    path: Path,
    *,
    min_pairs: int,
    max_pairs: int,
) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    warnings: list[str] = []
    evidence: dict[str, Any] = {}
    report_blockers: list[str] = []
    report_warnings: list[str] = []
    if isinstance(report, dict):
        evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
        report_blockers = [
            blocker for blocker in report.get("blockers", []) if isinstance(blocker, str)
        ]
        report_warnings = [
            warning for warning in report.get("warnings", []) if isinstance(warning, str)
        ]
        if report.get("artifact") != "synthetic_denial_appeal_corpus_format_audit":
            blockers.append("synthetic corpus format audit artifact is invalid")
        if report.get("ready") is not True:
            blockers.append("synthetic corpus format audit report must be ready")
        blockers.extend(report_blockers)
        warnings.extend(report_warnings)
        pair_count = evidence.get("pair_count")
        letter_count = evidence.get("letter_count")
        unique_text_count = evidence.get("unique_text_count")
        complete_pair_count = evidence.get("complete_pair_count")
        content_contract = (
            evidence.get("content_contract")
            if isinstance(evidence.get("content_contract"), dict)
            else {}
        )
        documentation = (
            evidence.get("documentation")
            if isinstance(evidence.get("documentation"), dict)
            else {}
        )
        phi_scan = evidence.get("phi_scan") if isinstance(evidence.get("phi_scan"), dict) else {}
        word_count = (
            evidence.get("word_count") if isinstance(evidence.get("word_count"), dict) else {}
        )
        profile_matrix = (
            evidence.get("profile_matrix_coverage")
            if isinstance(evidence.get("profile_matrix_coverage"), dict)
            else {}
        )
        appeal_quality_contract = (
            evidence.get("appeal_quality_contract")
            if isinstance(evidence.get("appeal_quality_contract"), dict)
            else {}
        )
        if not isinstance(pair_count, int) or not min_pairs <= pair_count <= max_pairs:
            blockers.append(f"format audit pair_count must be between {min_pairs} and {max_pairs}")
        if not isinstance(letter_count, int) or letter_count != (pair_count or 0) * 2:
            blockers.append("format audit letter_count must equal pair_count * 2")
        if unique_text_count != letter_count:
            blockers.append("format audit must prove all generated letters have unique text")
        if complete_pair_count != pair_count:
            blockers.append("format audit must prove every denial has a paired appeal")
        for key in [
            "missing_file_count",
            "checksum_mismatch_count",
            "profile_missing_count",
            "profile_mismatch_count",
            "missing_marker_count",
            "invalid_training_gate_count",
            "split_path_mismatch_count",
        ]:
            if content_contract.get(key) != 0:
                blockers.append(f"format audit content_contract.{key} must be 0")
        if documentation.get("ready") is not True:
            blockers.append("format audit documentation evidence must be ready")
        if phi_scan.get("finding_count") != 0:
            blockers.append("format audit PHI/PII scan finding_count must be 0")
        if isinstance(word_count.get("range"), int) and word_count["range"] < 50:
            blockers.append("format audit must prove document length variation of at least 50 words")
        if appeal_quality_contract.get("ready") is not True:
            blockers.append("format audit appeal_quality_contract must be ready")
        for key in [
            "missing_draft_status_count",
            "missing_human_review_header_count",
            "missing_not_filing_ready_notice_count",
            "missing_source_grounding_count",
            "missing_deadline_verification_count",
            "missing_phi_minimization_count",
            "missing_route_alignment_count",
            "missing_appeal_level_alignment_count",
            "missing_denial_type_alignment_count",
            "unsupported_deadline_or_citation_claim_count",
        ]:
            if appeal_quality_contract.get(key) != 0:
                blockers.append(f"format audit appeal_quality_contract.{key} must be 0")
        required_profile_matrix = {
            "document_role": {
                "denial_letter": {
                    "layout_profile": 12,
                    "typography_profile": 8,
                    "length_profile": 6,
                },
                "appeal_letter": {
                    "layout_profile": 12,
                    "typography_profile": 8,
                    "length_profile": 6,
                },
            },
            "split": {
                "train": {
                    "layout_profile": 12,
                    "typography_profile": 8,
                    "length_profile": 6,
                },
                "valid": {
                    "layout_profile": 12,
                    "typography_profile": 8,
                    "length_profile": 6,
                },
                "test": {
                    "layout_profile": 12,
                    "typography_profile": 8,
                    "length_profile": 6,
                },
            },
        }
        for dimension, groups in required_profile_matrix.items():
            dimension_evidence = profile_matrix.get(dimension)
            if not isinstance(dimension_evidence, dict):
                blockers.append(f"format audit profile_matrix_coverage.{dimension} must be present")
                continue
            for group_name, families in groups.items():
                group_evidence = dimension_evidence.get(group_name)
                if not isinstance(group_evidence, dict):
                    blockers.append(
                        f"format audit profile_matrix_coverage.{dimension}.{group_name} must be present"
                    )
                    continue
                for family, required_variant_count in families.items():
                    family_evidence = group_evidence.get(family)
                    if not isinstance(family_evidence, dict):
                        blockers.append(
                            "format audit profile_matrix_coverage."
                            f"{dimension}.{group_name}.{family} must be present"
                        )
                        continue
                    if family_evidence.get("ready") is not True:
                        blockers.append(
                            "format audit profile_matrix_coverage."
                            f"{dimension}.{group_name}.{family} must be ready"
                        )
                    variant_count = family_evidence.get("variant_count")
                    if not isinstance(variant_count, int) or variant_count < required_variant_count:
                        blockers.append(
                            "format audit profile_matrix_coverage."
                            f"{dimension}.{group_name}.{family} must include at least "
                            f"{required_variant_count} variants"
                        )
    elif not errors:
        blockers.append("synthetic corpus format audit report must be a JSON object")
    return requirement(
        requirement_id="phase6_synthetic_900_format_contract_audit",
        phase="synthetic_data",
        name="Generated synthetic denial/appeal letters pass file-level format and variation audit",
        status=status_from_blockers(blockers, warnings),
        blockers=blockers,
        warnings=warnings,
        evidence={
            "path": str(path),
            "report_blocker_count": len(report_blockers),
            "report_warning_count": len(report_warnings),
            **evidence,
        },
    )


def resolve_report_path(raw_path: str, base_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def synthetic_document_analysis_extraction_requirement(path: Path, min_denials: int) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    warnings: list[str] = []
    evidence: dict[str, Any] = {}
    report_blockers: list[str] = []
    report_warnings: list[str] = []
    if isinstance(report, dict):
        evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
        report_blockers = [
            blocker for blocker in report.get("blockers", []) if isinstance(blocker, str)
        ]
        report_warnings = [
            warning for warning in report.get("warnings", []) if isinstance(warning, str)
        ]
        if report.get("artifact") != "synthetic_document_analysis_extraction_audit":
            blockers.append("synthetic document-analysis extraction audit artifact is invalid")
        if report.get("ready") is not True:
            blockers.append("synthetic document-analysis extraction audit report must be ready")
        blockers.extend(report_blockers)
        warnings.extend(report_warnings)
        if not isinstance(evidence.get("checked_denial_count"), int) or evidence["checked_denial_count"] < min_denials:
            blockers.append(f"document-analysis extraction audit must check at least {min_denials} denials")
        for key in [
            "missing_file_count",
            "read_error_count",
            "phi_finding_count",
            "missing_payer_name_count",
            "missing_denial_reason_count",
            "missing_claim_amount_count",
            "missing_procedure_code_count",
            "unexpected_patient_name_count",
            "unexpected_policy_number_count",
        ]:
            if evidence.get(key) != 0:
                blockers.append(f"document-analysis extraction audit {key} must be 0")
    elif not errors:
        blockers.append("synthetic document-analysis extraction audit report must be a JSON object")
    return requirement(
        requirement_id="phase6_synthetic_document_analysis_extraction",
        phase="synthetic_data",
        name="Generated synthetic denial notices parse through the app document-analysis extractor",
        status=status_from_blockers(blockers, warnings),
        blockers=blockers,
        warnings=warnings,
        evidence={
            "path": str(path),
            "report_blocker_count": len(report_blockers),
            "report_warning_count": len(report_warnings),
            **evidence,
        },
    )


def synthetic_900_sft_export_requirement(
    manifest_path: Path,
    synthetic_manifest_path: Path,
    min_pairs: int,
) -> dict[str, Any]:
    item = corpus_sft_export_requirement(manifest_path, synthetic_manifest_path, min_pairs)
    item["requirement_id"] = "phase6_synthetic_900_sft_export"
    item["phase"] = "synthetic_data"
    item["name"] = "Generated 900-pair corpus is exported to guarded MLX chat SFT splits"
    item["evidence"]["expected_min_pair_count"] = min_pairs
    return item


def synthetic_900_mlx_runtime_gate_requirement(path: Path) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    warnings: list[str] = []
    summary = fine_tune_report_summary(report)
    runtime_error = None
    runtime_ready = None
    adapter_exists_currently = None
    if isinstance(report, dict):
        checks = report.get("checks", {})
        lora = checks.get("mlx_lm_lora", {}) if isinstance(checks, dict) else {}
        data = checks.get("data", {}) if isinstance(checks, dict) else {}
        manifest = checks.get("manifest", {}) if isinstance(checks, dict) else {}
        adapter = checks.get("adapter_output", {}) if isinstance(checks, dict) else {}
        runtime_ready = lora.get("runtime_ready") if isinstance(lora, dict) else None
        runtime_error = lora.get("error") if isinstance(lora, dict) else None
        adapter_path = adapter.get("path") if isinstance(adapter, dict) else None
        if isinstance(adapter_path, str) and adapter_path:
            adapter_exists_currently = Path(adapter_path).exists()
        if report.get("mode") != "run":
            blockers.append("synthetic-900 MLX evidence must come from --run mode")
        if not isinstance(data, dict) or data.get("ready") is not True:
            blockers.append("synthetic-900 MLX report data checks must be ready")
        if not isinstance(manifest, dict) or manifest.get("training_allowed") is not True:
            blockers.append("synthetic-900 MLX report manifest must have training_allowed=true")
        no_metal_blocker = any(
            isinstance(reason, str) and "cannot access a Metal device" in reason
            for reason in report.get("blocked_reasons", [])
        )
        if report.get("training_attempted") is True:
            if report.get("training_succeeded") is not True:
                blockers.append("synthetic-900 MLX training was attempted but did not succeed")
        elif no_metal_blocker and runtime_ready is False:
            warnings.append(
                "synthetic-900 LoRA training is blocked in this session because MLX cannot access Metal"
            )
        else:
            blockers.append("synthetic-900 MLX report must show training attempted or a no-Metal runtime gate")
        if report.get("training_attempted") is False and adapter_exists_currently:
            blockers.append("synthetic-900 adapter path exists even though training was not attempted")
        for reason in report.get("blocked_reasons", []):
            if isinstance(reason, str) and "cannot access a Metal device" not in reason:
                blockers.append(reason)
    else:
        blockers.append("synthetic-900 MLX run report must be a JSON object")
    return requirement(
        requirement_id="phase7_synthetic_900_mlx_runtime_gate",
        phase="fine_tuning",
        name="Synthetic-900 LoRA run evidence is guarded by the current MLX runtime state",
        status=status_from_blockers(blockers, warnings),
        blockers=blockers,
        warnings=warnings,
        evidence={
            "path": str(path),
            "summary": summary,
            "runtime_ready": runtime_ready,
            "runtime_error": runtime_error,
            "adapter_exists_currently": adapter_exists_currently,
        },
    )


def synthetic_seed_requirement(
    seed_path: Path,
    teacher_path: Path,
    min_records: int,
) -> dict[str, Any]:
    seed_count, seed_errors = count_jsonl(seed_path)
    teacher_count, teacher_errors = count_jsonl(teacher_path)
    seed_scan = phi_scan_file(seed_path)
    teacher_scan = phi_scan_file(teacher_path)
    blockers = [*seed_errors, *teacher_errors]
    if not isinstance(seed_count, int) or seed_count < min_records:
        blockers.append(f"synthetic seed dataset must contain at least {min_records} records")
    if seed_count != teacher_count:
        blockers.append("teacher request count must match synthetic seed record count")
    if seed_scan["finding_count"]:
        blockers.append("synthetic seed dataset PHI/PII scan must have zero findings")
    if teacher_scan["finding_count"]:
        blockers.append("teacher request JSONL PHI/PII scan must have zero findings")
    return requirement(
        requirement_id="phase6_synthetic_seed_dataset",
        phase="synthetic_data",
        name="Synthetic seed dataset and teacher requests cover the current scenario set",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={
            "seed_records": str(seed_path),
            "seed_record_count": seed_count,
            "teacher_requests": str(teacher_path),
            "teacher_request_count": teacher_count,
            "seed_phi_scan": seed_scan,
            "teacher_request_phi_scan": teacher_scan,
        },
    )


def micro_skill_coverage_requirement(manifest_path: Path, expected_records: int) -> dict[str, Any]:
    manifest, errors = load_json(manifest_path)
    blockers = list(errors)
    evidence: dict[str, Any] = {"path": str(manifest_path)}
    if isinstance(manifest, dict):
        skill_counts = manifest.get("micro_skill_counts", {})
        missing_skill_ids = manifest.get("missing_required_micro_skill_ids")
        evidence.update(
            {
                "record_count": manifest.get("record_count"),
                "required_micro_skill_ids": manifest.get("required_micro_skill_ids"),
                "micro_skill_counts": skill_counts,
                "micro_skill_coverage_complete": manifest.get("micro_skill_coverage_complete"),
                "missing_required_micro_skill_ids": missing_skill_ids,
                "data_safety": manifest.get("data_safety"),
            }
        )
        if manifest.get("record_count") != expected_records:
            blockers.append("SFT manifest record_count must match the synthetic seed record count")
        if manifest.get("micro_skill_coverage_complete") is not True:
            blockers.append("SFT manifest must show complete required micro-skill coverage")
        if missing_skill_ids:
            blockers.append(f"SFT manifest is missing micro-skills: {missing_skill_ids}")
        if isinstance(skill_counts, dict):
            for skill_id in REQUIRED_MICRO_SKILLS:
                if skill_counts.get(skill_id, 0) <= 0:
                    blockers.append(f"missing required micro-skill coverage: {skill_id}")
        else:
            blockers.append("SFT manifest must include micro_skill_counts")
        safety = manifest.get("data_safety", {})
        if not isinstance(safety, dict) or safety.get("phi_status") != "no_phi":
            blockers.append("SFT manifest must report data_safety.phi_status=no_phi")
        if not isinstance(safety, dict) or safety.get("user_phi_allowed") is not False:
            blockers.append("SFT manifest must report user_phi_allowed=false")
    else:
        blockers.append("SFT manifest must be a JSON object")
    return requirement(
        requirement_id="phase6_micro_skill_coverage",
        phase="synthetic_data",
        name="Seed data covers ClaimGuard denial and appeal-generation micro-skills MS01-MS12",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence=evidence,
    )


def workflow_baseline_requirement(path: Path, min_score: float, min_records: int) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    summary = report.get("summary") if isinstance(report, dict) else None
    if not isinstance(summary, dict):
        blockers.append("workflow report must contain summary")
        summary = {}
    scenario_count = summary.get("scenario_count")
    passed_count = summary.get("passed_count")
    score_ratio = summary.get("score_ratio")
    if not isinstance(scenario_count, int) or scenario_count < min_records:
        blockers.append(f"workflow baseline must cover at least {min_records} scenarios")
    if passed_count != scenario_count:
        blockers.append("workflow baseline must pass every scenario")
    if not isinstance(score_ratio, (int, float)) or score_ratio < min_score:
        blockers.append(f"workflow baseline score_ratio must be >= {min_score}")
    return requirement(
        requirement_id="phase4_5_workflow_baseline",
        phase="workflow_regression",
        name="Source-grounded denial workflow and appeal draft baseline passes",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={"path": str(path), "summary": summary},
    )


def teacher_request_preflight_requirement(path: Path, expected_records: int) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    warnings: list[str] = []
    summary: dict[str, Any] = {}
    if isinstance(report, dict):
        phi = report.get("phi_scan", {})
        summary = {
            "mode": report.get("mode"),
            "request_count": report.get("request_count"),
            "planned_request_count": report.get("planned_request_count"),
            "validation_error_count": report.get("validation_error_count"),
            "phi_scan": phi,
            "base_url_configured": report.get("base_url_configured"),
            "model": report.get("model"),
            "response_success_count": report.get("response_success_count"),
            "run_attempted": report.get("run_attempted"),
            "run_blocked": report.get("run_blocked"),
        }
        if report.get("request_count") != expected_records:
            blockers.append("teacher batch request_count must match synthetic seed record count")
        if report.get("validation_error_count") != 0:
            blockers.append("teacher batch request validation must have zero errors")
        if not isinstance(phi, dict) or phi.get("finding_count") != 0:
            blockers.append("teacher batch PHI scan must have zero findings")
        if report.get("base_url_configured") is not True:
            warnings.append("teacher endpoint is not configured; preflight is valid but labels are not generated")
    else:
        blockers.append("teacher batch report must be a JSON object")
    return requirement(
        requirement_id="phase6_teacher_request_preflight",
        phase="teacher_labeling",
        name="Large-teacher request batch is valid before compliant execution",
        status=status_from_blockers(blockers, warnings),
        blockers=blockers,
        warnings=warnings,
        evidence={"path": str(path), "summary": summary},
    )


def teacher_review_packet_requirement(
    packet_path: Path,
    report_path: Path,
    expected_records: int,
) -> dict[str, Any]:
    report, errors = load_json(report_path)
    blockers = list(errors)
    warnings: list[str] = []
    packet_scan = phi_scan_file(packet_path)
    summary: dict[str, Any] = {}
    if isinstance(report, dict):
        summary = {
            "review_packet_ready": report.get("review_packet_ready"),
            "response_export_ready": report.get("response_export_ready"),
            "training_ready": report.get("training_ready"),
            "packet_record_count": report.get("packet_record_count"),
            "approved_count": report.get("approved_count"),
            "pending_count": report.get("pending_count"),
            "validation_error_count": report.get("validation_error_count"),
            "export_error_count": report.get("export_error_count"),
            "packet_phi_scan": report.get("packet_phi_scan"),
        }
        if report.get("review_packet_ready") is not True:
            blockers.append("offline teacher review packet is not ready")
        if report.get("packet_record_count") != expected_records:
            blockers.append("offline teacher review packet record count must match synthetic seed count")
        if report.get("validation_error_count") != 0:
            blockers.append("offline teacher review packet validation must have zero errors")
        if report.get("export_error_count") not in {0, None}:
            blockers.append("offline teacher review packet export errors must be zero")
        approved_count = report.get("approved_count")
        if not isinstance(approved_count, int) or approved_count < expected_records:
            warnings.append("offline review packet is generated but labels still need human or large-teacher approval")
    else:
        blockers.append("teacher review packet report must be a JSON object")
    if packet_scan["finding_count"]:
        blockers.append("offline teacher review packet PHI/PII scan must have zero findings")
    return requirement(
        requirement_id="phase6_teacher_review_packet",
        phase="teacher_labeling",
        name="Offline teacher/human review packet is ready for label approval",
        status=status_from_blockers(blockers, warnings),
        blockers=blockers,
        warnings=warnings,
        evidence={
            "packet": str(packet_path),
            "report": str(report_path),
            "summary": summary,
            "packet_phi_scan": packet_scan,
        },
    )


def pipeline_stage(report: Any, stage_name: str) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None
    stages = report.get("stages", [])
    if not isinstance(stages, list):
        return None
    for stage in stages:
        if isinstance(stage, dict) and stage.get("stage") == stage_name:
            return stage
    return None


def stage_blockers(report: Any, stage_names: list[str]) -> list[str]:
    blockers: list[str] = []
    for stage_name in stage_names:
        stage = pipeline_stage(report, stage_name)
        if not stage:
            blockers.append(f"{stage_name}: pipeline stage is missing")
            continue
        if stage.get("ready") is not True:
            for blocker in stage.get("blockers", []):
                if isinstance(blocker, str):
                    blockers.append(f"{stage_name}: {blocker}")
    return blockers


def reviewed_teacher_labels_requirement(
    manifest_path: Path,
    pipeline_path: Path,
    expected_records: int,
) -> dict[str, Any]:
    manifest, manifest_errors = load_json(manifest_path)
    pipeline, pipeline_errors = load_json(pipeline_path)
    blockers = [*manifest_errors, *pipeline_errors]
    status_counts: dict[str, Any] = {}
    reviewed_count = 0
    if isinstance(manifest, dict):
        status_counts = manifest.get("teacher_review_status_counts", {})
        if isinstance(status_counts, dict):
            reviewed_count = sum(
                count
                for key, count in status_counts.items()
                if key in REVIEWED_STATUS_KEYS and isinstance(count, int)
            )
            pending_count = sum(
                count
                for key, count in status_counts.items()
                if "pending" in key and isinstance(count, int)
            )
            if pending_count:
                blockers.append(f"{pending_count} record(s) are still pending large-teacher or human review")
            if reviewed_count < expected_records:
                blockers.append(
                    f"reviewed label count must be at least {expected_records}; current reviewed count is {reviewed_count}"
                )
        else:
            blockers.append("SFT manifest teacher_review_status_counts must be an object")
    else:
        blockers.append("SFT manifest must be a JSON object")
    blockers.extend(stage_blockers(pipeline, ["teacher_responses", "ingest_reviewed_labels"]))
    return requirement(
        requirement_id="phase6_reviewed_teacher_labels",
        phase="teacher_labeling",
        name="Reviewed large-teacher or human-approved labels are available for all records",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={
            "sft_manifest": str(manifest_path),
            "teacher_review_status_counts": status_counts,
            "reviewed_count": reviewed_count,
            "pipeline_report": str(pipeline_path),
            "pipeline_stages": {
                "teacher_responses": pipeline_stage(pipeline, "teacher_responses"),
                "ingest_reviewed_labels": pipeline_stage(pipeline, "ingest_reviewed_labels"),
            },
        },
    )


def reviewed_sft_export_requirement(pipeline_path: Path) -> dict[str, Any]:
    pipeline, errors = load_json(pipeline_path)
    blockers = list(errors)
    blockers.extend(stage_blockers(pipeline, ["export_reviewed_mlx_sft"]))
    return requirement(
        requirement_id="phase6_reviewed_sft_export",
        phase="teacher_labeling",
        name="Reviewed labels are exported to MLX chat SFT splits with training_allowed=true",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={
            "pipeline_report": str(pipeline_path),
            "pipeline_stage": pipeline_stage(pipeline, "export_reviewed_mlx_sft"),
        },
    )


def fine_tune_report_summary(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    checks = report.get("checks", {})
    lora = checks.get("mlx_lm_lora", {}) if isinstance(checks, dict) else {}
    data = checks.get("data", {}) if isinstance(checks, dict) else {}
    manifest = checks.get("manifest", {}) if isinstance(checks, dict) else {}
    adapter = checks.get("adapter_output", {}) if isinstance(checks, dict) else {}
    return {
        "ready": report.get("ready"),
        "mode": report.get("mode"),
        "training_attempted": report.get("training_attempted"),
        "training_succeeded": report.get("training_succeeded"),
        "blocked_reasons": report.get("blocked_reasons"),
        "data_ready": data.get("ready") if isinstance(data, dict) else None,
        "manifest_training_allowed": manifest.get("training_allowed") if isinstance(manifest, dict) else None,
        "mlx_lm_lora_available": lora.get("available") if isinstance(lora, dict) else None,
        "adapter_path": adapter.get("path") if isinstance(adapter, dict) else None,
        "adapter_exists_before_run": adapter.get("exists_before_run") if isinstance(adapter, dict) else None,
        "adapter_exists_after_run": adapter.get("exists_after_run") if isinstance(adapter, dict) else None,
    }


def mlx_runtime_requirement(path: Path) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    summary: dict[str, Any] = {}
    if isinstance(report, dict):
        checks = report.get("checks", {})
        commands = checks.get("commands", {}) if isinstance(checks, dict) else {}
        server = checks.get("server", {}) if isinstance(checks, dict) else {}
        package = checks.get("python_package", {}) if isinstance(checks, dict) else {}
        summary = {
            "ready": report.get("ready"),
            "blocked_reasons": report.get("blocked_reasons"),
            "warnings": report.get("warnings"),
            "base_url": report.get("base_url"),
            "model": report.get("model"),
            "package_installed": package.get("installed") if isinstance(package, dict) else None,
            "server_available": server.get("available") if isinstance(server, dict) else None,
            "commands_available": {
                command: status.get("available")
                for command, status in commands.items()
                if isinstance(status, dict)
            }
            if isinstance(commands, dict)
            else {},
        }
        if report.get("ready") is not True:
            blockers.append("MLX runtime preflight is not ready")
            for reason in report.get("blocked_reasons", []):
                if isinstance(reason, str):
                    blockers.append(reason)
    else:
        blockers.append("MLX runtime preflight report must be a JSON object")
    return requirement(
        requirement_id="phase5_7_mlx_runtime_preflight",
        phase="benchmarking",
        name="Local MLX-LM package, CLI tools, and server endpoint are available",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={"path": str(path), "summary": summary},
    )


def local_mlx_environment_requirement(path: Path) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    summary = fine_tune_report_summary(report)
    if isinstance(report, dict):
        checks = report.get("checks", {})
        lora = checks.get("mlx_lm_lora", {}) if isinstance(checks, dict) else {}
        host = checks.get("host", {}) if isinstance(checks, dict) else {}
        if not isinstance(lora, dict) or lora.get("available") is not True:
            blockers.append("mlx_lm.lora must be installed and available on PATH")
        if isinstance(host, dict) and host.get("machine") not in {None, "arm64"}:
            blockers.append("MLX training target should be Apple Silicon arm64")
    else:
        blockers.append("fine-tune preflight report must be a JSON object")
    return requirement(
        requirement_id="phase7_local_mlx_environment",
        phase="fine_tuning",
        name="Local MLX-LM training environment is available",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={"path": str(path), "summary": summary},
    )


def student_fine_tune_run_requirement(path: Path) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    summary = fine_tune_report_summary(report)
    if isinstance(report, dict):
        if report.get("mode") != "run":
            blockers.append("fine-tune report must come from --run mode")
        if report.get("training_attempted") is not True:
            blockers.append("fine-tune report must show training_attempted=true")
        if report.get("training_succeeded") is not True:
            blockers.append("fine-tune report must show training_succeeded=true")
        for reason in report.get("blocked_reasons", []):
            if isinstance(reason, str):
                blockers.append(reason)
    else:
        blockers.append("fine-tune report must be a JSON object")
    return requirement(
        requirement_id="phase7_student_fine_tune_run",
        phase="fine_tuning",
        name="Reviewed-label LoRA fine-tune has produced a student adapter",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={"path": str(path), "summary": summary},
    )


def benchmark_summary(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    summary = report.get("summary")
    if isinstance(summary, dict):
        return summary
    return {}


def live_benchmark_requirement(
    *,
    requirement_id: str,
    phase: str,
    name: str,
    path: Path,
    min_records: int,
    min_score: float | None,
) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    summary = benchmark_summary(report)
    if not summary:
        blockers.append("benchmark report must contain summary")
    else:
        if summary.get("endpoint_available") is not True:
            blockers.append("benchmark endpoint_available must be true")
        if summary.get("dry_run") is True:
            blockers.append("benchmark must be a live endpoint run, not dry-run")
        if summary.get("endpoint_error_count") not in {0, None}:
            blockers.append("benchmark endpoint_error_count must be 0")
        if not isinstance(summary.get("record_count"), int) or summary["record_count"] < min_records:
            blockers.append(f"benchmark must cover at least {min_records} records")
        score_ratio = summary.get("score_ratio")
        if not isinstance(score_ratio, (int, float)):
            blockers.append("benchmark must report score_ratio")
        elif min_score is not None and score_ratio < min_score:
            blockers.append(f"benchmark score_ratio must be >= {min_score}")
    return requirement(
        requirement_id=requirement_id,
        phase=phase,
        name=name,
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={"path": str(path), "summary": summary},
    )


def student_acceptance_requirement(path: Path) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    summary: dict[str, Any] = {}
    if isinstance(report, dict):
        summary = {
            "release_ready": report.get("release_ready"),
            "blocked_reasons": report.get("blocked_reasons"),
            "thresholds": report.get("thresholds"),
        }
        if report.get("release_ready") is not True:
            blockers.append("student acceptance report is not release-ready")
            for reason in report.get("blocked_reasons", []):
                if isinstance(reason, str):
                    blockers.append(reason)
    else:
        blockers.append("student acceptance report must be a JSON object")
    return requirement(
        requirement_id="phase7_student_acceptance",
        phase="acceptance",
        name="Student model passes release gate for ClaimGuard denial and appeal tasks",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={"path": str(path), "summary": summary},
    )


def quantization_promotion_requirement(
    acceptance_path: Path,
    fine_tune_path: Path,
) -> dict[str, Any]:
    acceptance, acceptance_errors = load_json(acceptance_path)
    fine_tune, fine_tune_errors = load_json(fine_tune_path)
    blockers = [*acceptance_errors, *fine_tune_errors]
    fine_tune_summary = fine_tune_report_summary(fine_tune)
    if not isinstance(acceptance, dict) or acceptance.get("release_ready") is not True:
        blockers.append("student acceptance must be release-ready before quantization or adapter promotion")
    if fine_tune_summary.get("training_succeeded") is not True:
        blockers.append("successful trained adapter evidence is required before quantization")
    adapter_path = fine_tune_summary.get("adapter_path")
    adapter_exists_after = fine_tune_summary.get("adapter_exists_after_run")
    adapter_exists_before = fine_tune_summary.get("adapter_exists_before_run")
    if adapter_path and adapter_exists_after is not True and adapter_exists_before is False:
        blockers.append("trained adapter output path does not exist in current evidence")
    return requirement(
        requirement_id="phase8_quantization_promotion",
        phase="promotion",
        name="Accepted adapter is ready for quantization, promotion, or default-model changes",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={
            "acceptance_report": str(acceptance_path),
            "acceptance_release_ready": acceptance.get("release_ready") if isinstance(acceptance, dict) else None,
            "fine_tune_report": str(fine_tune_path),
            "fine_tune_summary": fine_tune_summary,
        },
    )


def phi_safety_requirement(paths: list[Path]) -> dict[str, Any]:
    scans = [phi_scan_file(path) for path in paths]
    blockers = [
        f"{scan['path']} has {scan['finding_count']} PHI/PII finding(s)"
        for scan in scans
        if scan["finding_count"]
    ]
    return requirement(
        requirement_id="safety_phi_artifact_scan",
        phase="safety_and_specification",
        name="Checked-in distillation data and evidence reports remain PHI/PII-clean",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={"scans": scans},
    )


def file_ingestion_surface_requirement(path: Path) -> dict[str, Any]:
    report, errors = load_json(path)
    blockers = list(errors)
    summary: dict[str, Any] = {}
    if isinstance(report, dict):
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        if report.get("ready") is not True:
            blockers.append("file-ingestion surface audit must be ready")
        for reason in report.get("blocked_reasons", []):
            if isinstance(reason, str):
                blockers.append(reason)
    else:
        blockers.append("file-ingestion surface audit report must be a JSON object")
    return requirement(
        requirement_id="safety_file_ingestion_surface_audit",
        phase="safety_and_specification",
        name="Automated file-ingestion endpoints have registered PHI inspection and governance coverage",
        status=status_from_blockers(blockers),
        blockers=blockers,
        evidence={
            "path": str(path),
            "summary": summary,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--source-registry", type=Path, default=DEFAULT_SOURCE_REGISTRY)
    parser.add_argument("--corpus-manifest", type=Path, default=DEFAULT_CORPUS_MANIFEST)
    parser.add_argument("--corpus-sft-manifest", type=Path, default=DEFAULT_CORPUS_SFT_MANIFEST)
    parser.add_argument(
        "--synthetic-900-generation-report",
        type=Path,
        default=DEFAULT_SYNTHETIC_900_GENERATION_REPORT,
    )
    parser.add_argument("--synthetic-900-manifest", type=Path, default=DEFAULT_SYNTHETIC_900_MANIFEST)
    parser.add_argument(
        "--synthetic-900-sft-manifest",
        type=Path,
        default=DEFAULT_SYNTHETIC_900_SFT_MANIFEST,
    )
    parser.add_argument(
        "--synthetic-900-format-audit-report",
        type=Path,
        default=DEFAULT_SYNTHETIC_900_FORMAT_AUDIT_REPORT,
    )
    parser.add_argument(
        "--synthetic-document-analysis-extraction-report",
        type=Path,
        default=DEFAULT_SYNTHETIC_DOCUMENT_ANALYSIS_EXTRACTION_REPORT,
    )
    parser.add_argument(
        "--synthetic-900-fine-tune-report",
        type=Path,
        default=DEFAULT_SYNTHETIC_900_FINE_TUNE_REPORT,
    )
    parser.add_argument("--seed-records", type=Path, default=DEFAULT_SEED_RECORDS)
    parser.add_argument("--teacher-requests", type=Path, default=DEFAULT_TEACHER_REQUESTS)
    parser.add_argument("--sft-manifest", type=Path, default=default_sft_manifest())
    parser.add_argument("--workflow-report", type=Path, default=DEFAULT_WORKFLOW_REPORT)
    parser.add_argument("--teacher-batch-report", type=Path, default=DEFAULT_TEACHER_BATCH_REPORT)
    parser.add_argument("--teacher-review-packet", type=Path, default=DEFAULT_TEACHER_REVIEW_PACKET)
    parser.add_argument("--teacher-review-packet-report", type=Path, default=DEFAULT_TEACHER_REVIEW_PACKET_REPORT)
    parser.add_argument("--file-ingestion-surface-report", type=Path, default=DEFAULT_FILE_INGESTION_SURFACE_REPORT)
    parser.add_argument("--mlx-runtime-report", type=Path, default=DEFAULT_MLX_RUNTIME_REPORT)
    parser.add_argument("--fine-tune-report", type=Path, default=DEFAULT_FINE_TUNE_REPORT)
    parser.add_argument("--base-benchmark", type=Path, default=DEFAULT_BASE_BENCHMARK)
    parser.add_argument("--student-benchmark", type=Path, default=DEFAULT_STUDENT_BENCHMARK)
    parser.add_argument("--acceptance-report", type=Path, default=DEFAULT_ACCEPTANCE_REPORT)
    parser.add_argument("--pipeline-report", type=Path, default=DEFAULT_PIPELINE_REPORT)
    parser.add_argument("--workflow-min-score", type=float, default=0.95)
    parser.add_argument("--benchmark-min-score", type=float, default=0.95)
    parser.add_argument("--min-sources", type=int, default=7)
    parser.add_argument("--min-scenarios", type=int, default=10)
    parser.add_argument("--min-corpus-pairs", type=int, default=3)
    parser.add_argument("--min-synthetic-900-pairs", type=int, default=800)
    parser.add_argument("--max-synthetic-900-pairs", type=int, default=1000)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    seed_count, _ = count_jsonl(args.seed_records)
    expected_records = seed_count or args.min_scenarios
    requirements = [
        source_registry_requirement(args.source_registry, args.min_sources),
        compliance_docs_requirement(),
        corpus_manifest_requirement(args.corpus_manifest, args.min_corpus_pairs),
        corpus_sft_export_requirement(
            args.corpus_sft_manifest,
            args.corpus_manifest,
            args.min_corpus_pairs,
        ),
        synthetic_900_corpus_requirement(
            args.synthetic_900_generation_report,
            args.synthetic_900_manifest,
            min_pairs=args.min_synthetic_900_pairs,
            max_pairs=args.max_synthetic_900_pairs,
        ),
        synthetic_900_format_contract_requirement(
            args.synthetic_900_format_audit_report,
            min_pairs=args.min_synthetic_900_pairs,
            max_pairs=args.max_synthetic_900_pairs,
        ),
        synthetic_document_analysis_extraction_requirement(
            args.synthetic_document_analysis_extraction_report,
            args.min_synthetic_900_pairs,
        ),
        synthetic_900_sft_export_requirement(
            args.synthetic_900_sft_manifest,
            args.synthetic_900_manifest,
            args.min_synthetic_900_pairs,
        ),
        synthetic_900_mlx_runtime_gate_requirement(args.synthetic_900_fine_tune_report),
        synthetic_seed_requirement(args.seed_records, args.teacher_requests, args.min_scenarios),
        micro_skill_coverage_requirement(args.sft_manifest, expected_records),
        workflow_baseline_requirement(args.workflow_report, args.workflow_min_score, args.min_scenarios),
        teacher_request_preflight_requirement(args.teacher_batch_report, expected_records),
        teacher_review_packet_requirement(
            args.teacher_review_packet,
            args.teacher_review_packet_report,
            expected_records,
        ),
        reviewed_teacher_labels_requirement(args.sft_manifest, args.pipeline_report, expected_records),
        reviewed_sft_export_requirement(args.pipeline_report),
        file_ingestion_surface_requirement(args.file_ingestion_surface_report),
        mlx_runtime_requirement(args.mlx_runtime_report),
        local_mlx_environment_requirement(args.fine_tune_report),
        student_fine_tune_run_requirement(args.fine_tune_report),
        live_benchmark_requirement(
            requirement_id="phase7_base_model_live_benchmark",
            phase="benchmarking",
            name="Base lightweight model has a live benchmark over the full ClaimGuard set",
            path=args.base_benchmark,
            min_records=args.min_scenarios,
            min_score=None,
        ),
        live_benchmark_requirement(
            requirement_id="phase7_student_live_benchmark",
            phase="benchmarking",
            name="Fine-tuned student model has a live benchmark over the full ClaimGuard set",
            path=args.student_benchmark,
            min_records=args.min_scenarios,
            min_score=args.benchmark_min_score,
        ),
        student_acceptance_requirement(args.acceptance_report),
        quantization_promotion_requirement(args.acceptance_report, args.fine_tune_report),
        phi_safety_requirement(
            [
                args.source_registry,
                args.corpus_manifest,
                args.corpus_sft_manifest,
                args.synthetic_900_generation_report,
                args.synthetic_900_manifest,
                args.synthetic_900_format_audit_report,
                args.synthetic_document_analysis_extraction_report,
                args.synthetic_900_sft_manifest,
                args.synthetic_900_fine_tune_report,
                args.seed_records,
                args.teacher_requests,
                args.sft_manifest,
                args.workflow_report,
                args.teacher_batch_report,
                args.teacher_review_packet,
                args.teacher_review_packet_report,
                args.file_ingestion_surface_report,
                args.mlx_runtime_report,
                args.fine_tune_report,
                args.base_benchmark,
                args.student_benchmark,
                args.acceptance_report,
                args.pipeline_report,
            ]
        ),
    ]
    blocked = [item for item in requirements if item["status"] == "blocked"]
    warnings = [item for item in requirements if item["status"] == "warning"]
    ready = [item for item in requirements if item["status"] == "ready"]
    blocked_items = [
        {
            "requirement_id": item["requirement_id"],
            "phase": item["phase"],
            "name": item["name"],
            "blockers": item["blockers"],
        }
        for item in blocked
    ]
    warning_items = [
        {
            "requirement_id": item["requirement_id"],
            "phase": item["phase"],
            "name": item["name"],
            "warnings": item["warnings"],
        }
        for item in warnings
    ]
    acceptance_release_ready = next(
        (
            item["evidence"]["summary"].get("release_ready")
            for item in requirements
            if item["requirement_id"] == "phase7_student_acceptance"
        ),
        False,
    )
    distillation_ready = not blocked
    release_ready = distillation_ready and acceptance_release_ready is True

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objective": "Distill a larger LLM into a smaller lightweight ClaimGuard student model for denial-claim processing and appeal-letter generation.",
        "distillation_ready": distillation_ready,
        "release_ready": release_ready,
        "blocked_item_count": len(blocked_items),
        "blocked_items": blocked_items,
        "warning_item_count": len(warning_items),
        "warning_items": warning_items,
        "summary": {
            "requirement_count": len(requirements),
            "ready_count": len(ready),
            "warning_count": len(warnings),
            "blocked_count": len(blocked),
            "blocked_requirement_ids": [item["requirement_id"] for item in blocked],
            "warning_requirement_ids": [item["requirement_id"] for item in warnings],
        },
        "requirements": requirements,
        "next_required_actions": build_next_required_actions(blocked_items, release_ready),
        "notes": [
            "This audit does not call teacher endpoints, train models, benchmark endpoints, download weights, quantize, or write adapter files.",
            "A valid synthetic seed dataset proves format and micro-skill coverage only; it is not a reviewed training set or a trained student model.",
            "The synthetic 900-pair stress corpus must remain generated, paired, varied, file-level format-audited, PHI-clean, and SFT-exported before it can be used for model stress testing.",
            "Generated synthetic denial notices must keep passing the app document-analysis extraction audit before being used as denial-document stress fixtures.",
            "A passing synthetic corpus export clears this audit gate but does not complete production corpus, admin review/import UI, retention/deletion/audit, legal/BAA/consent, or default-model cutover work.",
            "Default student use is also controlled by CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED, CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE, CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED, and CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    safe_payload = sanitize_report_value(payload)
    args.output.write_text(json.dumps(safe_payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote distillation readiness audit report to {args.output}")
    if blocked and args.fail_on_blocked:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
