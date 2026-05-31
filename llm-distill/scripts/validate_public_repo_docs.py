#!/usr/bin/env python3
"""Validate public GitHub docs for the distillation evidence summary."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHITECT_NAME = "Raphael Malikian"
ARCHITECT_EMAIL_LOCAL = "rtmalikian"
ARCHITECT_EMAIL_DOMAIN = "gmail.com"
README_PATH = Path("README.md")
TECHNICAL_DOC_PATH = Path("docs/technical-llm-distillation-analysis.md")

REQUIRED_README_MARKERS = (
    "Healthcare Claim Denial Prediction",
    "HIPAA-Safe LLM Distillation",
    "SEO description:",
    "docs/technical-llm-distillation-analysis.md",
    "Commercial License And Use Restrictions",
)

REQUIRED_TECHNICAL_SECTIONS = (
    "## Scope",
    "## Distillation Pipeline",
    "## Analysis Statistics",
    "### Synthetic Denial And Appeal Stress Corpus",
    "### Reviewed-Label Student Distillation",
    "### Benchmark And Acceptance Results",
    "### Production-Readiness State",
    "## Tools Used",
    "## Reproduce The Core Checks",
)

REQUIRED_REPORT_LINKS = (
    "../llm-distill/evals/reports/distillation_readiness_audit_report.json",
    "../llm-distill/evals/reports/synthetic_denial_appeal_corpus_format_audit_report.json",
    "../llm-distill/evals/reports/student_acceptance_report.json",
    "../llm-distill/evals/reports/phi_plan_production_readiness_report.json",
)

REQUIRED_TOOL_MARKERS = (
    "FastAPI",
    "React",
    "Vite",
    "Docker Compose",
    "Playwright",
    "NVIDIA NIM",
    "MLX-LM",
    "Qwen/Qwen3-4B-MLX-4bit",
    "llm-distill/scripts/run_phi_scan.py",
    "llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py",
    "llm-distill/scripts/run_distillation_readiness_audit.py",
    "llm-distill/scripts/run_phi_plan_production_readiness_audit.py",
)

SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "bearer_value": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"),
}

PHI_OR_PRIVATE_PATTERNS = {
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_like": re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    "absolute_user_path": re.compile(r"/Users/[^\s)`]+"),
    "private_tmp_path": re.compile(r"/private/tmp/[^\s)`]+"),
}


def _load_json(repo_root: Path, relative_path: str) -> dict[str, Any]:
    path = repo_root / relative_path
    return json.loads(path.read_text(encoding="utf-8"))


def _formatted_numbers(value: int | float) -> set[str]:
    if isinstance(value, bool):
        return {str(value).lower()}
    if isinstance(value, int):
        return {str(value), f"{value:,}"}
    return {str(value)}


def _contains_number(text: str, value: int | float) -> bool:
    return any(number in text for number in _formatted_numbers(value))


def _append_missing_markers(blockers: list[str], text: str, markers: tuple[str, ...], prefix: str) -> None:
    for marker in markers:
        if marker not in text:
            blockers.append(f"{prefix}:{marker}")


def _has_architect_attribution(text: str) -> bool:
    return (
        ARCHITECT_NAME in text
        and ARCHITECT_EMAIL_LOCAL in text
        and ARCHITECT_EMAIL_DOMAIN in text
    )


def _collect_expected_stats(repo_root: Path) -> dict[str, int | float | bool]:
    synthetic_audit = _load_json(
        repo_root,
        "llm-distill/evals/reports/synthetic_denial_appeal_corpus_format_audit_report.json",
    )
    extraction_audit = _load_json(
        repo_root,
        "llm-distill/evals/reports/synthetic_document_analysis_extraction_report.json",
    )
    workflow = _load_json(repo_root, "llm-distill/evals/reports/workflow_baseline_report.json")
    student_acceptance = _load_json(
        repo_root,
        "llm-distill/evals/reports/student_acceptance_report.json",
    )
    student_benchmark = _load_json(
        repo_root,
        "llm-distill/evals/reports/student_mlx_benchmark_report.json",
    )
    distillation = _load_json(
        repo_root,
        "llm-distill/evals/reports/distillation_readiness_audit_report.json",
    )
    production = _load_json(
        repo_root,
        "llm-distill/evals/reports/phi_plan_production_readiness_report.json",
    )
    corpus_manifest = _load_json(
        repo_root,
        "llm-distill/data/distillation/mlx_sft_corpus/manifest.json",
    )

    evidence = synthetic_audit.get("evidence", {})
    counts = evidence.get("counts", {})
    split_counts = counts.get("split", {})
    student_summary = student_benchmark.get("summary", {})
    workflow_summary = workflow.get("summary", {})
    distillation_summary = distillation.get("summary", {})

    return {
        "complete_pair_count": int(evidence.get("complete_pair_count", 0)),
        "letter_count": int(evidence.get("letter_count", 0)),
        "denial_letter_count": int(counts.get("document_role", {}).get("denial_letter", 0)),
        "appeal_letter_count": int(counts.get("document_role", {}).get("appeal_letter", 0)),
        "train_split_letters": int(split_counts.get("train", 0)),
        "valid_split_letters": int(split_counts.get("valid", 0)),
        "test_split_letters": int(split_counts.get("test", 0)),
        "duplicate_text_group_count": int(evidence.get("duplicate_text_group_count", 0)),
        "duplicate_pair_group_count": int(evidence.get("duplicate_pair_group_count", 0)),
        "phi_scan_findings": int(evidence.get("phi_scan", {}).get("finding_count", 0)),
        "layout_profiles": int(len(counts.get("layout_profile", {}))),
        "typography_profiles": int(len(counts.get("typography_profile", {}))),
        "length_profiles": int(len(counts.get("length_profile", {}))),
        "checked_denial_count": int(extraction_audit.get("evidence", {}).get("checked_denial_count", 0)),
        "approved_corpus_pair_count": int(corpus_manifest.get("pair_count", 0)),
        "approved_corpus_exported_documents": int(corpus_manifest.get("exported_document_count", 0)),
        "required_micro_skills": int(len(corpus_manifest.get("required_micro_skill_ids", []))),
        "missing_required_micro_skills": int(len(corpus_manifest.get("missing_required_micro_skill_ids", []))),
        "workflow_scenarios": int(workflow_summary.get("scenario_count", 0)),
        "workflow_score_ratio": float(workflow_summary.get("score_ratio", 0.0)),
        "student_benchmark_records": int(student_summary.get("record_count", 0)),
        "student_score_ratio": float(student_summary.get("score_ratio", 0.0)),
        "student_min_score_threshold": float(student_acceptance.get("thresholds", {}).get("student_min_score", 0.0)),
        "student_release_ready": bool(student_acceptance.get("release_ready", False)),
        "distillation_ready_count": int(distillation_summary.get("ready_count", 0)),
        "distillation_requirement_count": int(distillation_summary.get("requirement_count", 0)),
        "safe_current_state": bool(production.get("safe_current_state", False)),
        "production_ready": bool(production.get("production_ready", True)),
        "production_blocked_items": int(production.get("blocked_item_count", 0)),
        "production_warning_items": int(production.get("warning_item_count", 0)),
    }


def _validate_no_sensitive_values(
    blockers: list[str],
    relative_path: Path,
    text: str,
) -> None:
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            blockers.append(f"{relative_path}:secret_pattern:{label}")
    for label, pattern in PHI_OR_PRIVATE_PATTERNS.items():
        if pattern.search(text):
            blockers.append(f"{relative_path}:private_or_phi_pattern:{label}")


def validate_public_docs(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    blockers: list[str] = []
    repo_root = repo_root.resolve()
    readme_path = repo_root / README_PATH
    technical_doc_path = repo_root / TECHNICAL_DOC_PATH

    if not readme_path.exists():
        blockers.append("missing:README.md")
        readme_text = ""
    else:
        readme_text = readme_path.read_text(encoding="utf-8")

    if not technical_doc_path.exists():
        blockers.append(f"missing:{TECHNICAL_DOC_PATH}")
        technical_text = ""
    else:
        technical_text = technical_doc_path.read_text(encoding="utf-8")

    readme_has_architect = _has_architect_attribution(readme_text)
    technical_doc_has_architect = _has_architect_attribution(technical_text)

    if not readme_has_architect:
        blockers.append("README.md:missing_architect_attribution")
    if not technical_doc_has_architect:
        blockers.append(f"{TECHNICAL_DOC_PATH}:missing_architect_attribution")

    _append_missing_markers(blockers, readme_text, REQUIRED_README_MARKERS, "README.md:missing_marker")
    _append_missing_markers(
        blockers,
        technical_text,
        REQUIRED_TECHNICAL_SECTIONS,
        f"{TECHNICAL_DOC_PATH}:missing_section",
    )
    _append_missing_markers(
        blockers,
        technical_text,
        REQUIRED_REPORT_LINKS,
        f"{TECHNICAL_DOC_PATH}:missing_report_link",
    )
    _append_missing_markers(
        blockers,
        technical_text,
        REQUIRED_TOOL_MARKERS,
        f"{TECHNICAL_DOC_PATH}:missing_tool_marker",
    )

    _validate_no_sensitive_values(blockers, README_PATH, readme_text)
    _validate_no_sensitive_values(blockers, TECHNICAL_DOC_PATH, technical_text)

    expected_stats = _collect_expected_stats(repo_root)
    for stat_name, expected_value in expected_stats.items():
        if isinstance(expected_value, bool):
            if str(expected_value).lower() not in technical_text.lower():
                blockers.append(f"{TECHNICAL_DOC_PATH}:missing_boolean_stat:{stat_name}")
            continue
        if not _contains_number(technical_text, expected_value):
            blockers.append(f"{TECHNICAL_DOC_PATH}:missing_numeric_stat:{stat_name}")

    return {
        "artifact": "public_repo_docs_validation",
        "ready": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "evidence": {
            "readme": str(README_PATH),
            "technical_breakdown": str(TECHNICAL_DOC_PATH),
            "readme_links_technical_breakdown": "docs/technical-llm-distillation-analysis.md"
            in readme_text,
            "architect_attribution_present": readme_has_architect and technical_doc_has_architect,
            "required_tool_marker_count": len(REQUIRED_TOOL_MARKERS),
            "expected_stat_count": len(expected_stats),
            "values_redacted": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = validate_public_docs(args.repo_root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "public_repo_docs_validation "
            f"ready={report['ready']} blocked={report['blocker_count']}"
        )
    if args.fail_on_blocked and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
