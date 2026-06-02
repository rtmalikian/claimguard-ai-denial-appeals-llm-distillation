#!/usr/bin/env python3
"""Validate the PHIplan private evidence handoff without exposing values."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
REPORT_DIR = DISTILL_DIR / "evals" / "reports"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import write_source_controlled_report_json  # noqa: E402

DEFAULT_HANDOFF = DISTILL_DIR / "docs" / "phi-plan-private-evidence-handoff.md"
DEFAULT_REPORT = REPORT_DIR / "phi_plan_private_evidence_handoff_report.json"

PRIVATE_EVIDENCE_DOMAINS = (
    {
        "requirement_id": "manual_production_gate_packet_evidence",
        "report_path": REPORT_DIR / "phi_plan_manual_gate_packet_report.json",
        "ready_key": "production_gate_ready",
        "validator_paths": (
            DISTILL_DIR / "scripts" / "validate_phi_plan_manual_gate_packet.py",
        ),
        "renderer_paths": (
            DISTILL_DIR / "scripts" / "render_phi_plan_manual_gate_private_packet.py",
        ),
        "private_input_flag": "--packet",
        "private_input_placeholder": "<private-manual-gate-packet-json-outside-source-control>",
        "execution_order": 9,
    },
    {
        "requirement_id": "student_default_cutover_external_approval",
        "report_path": REPORT_DIR / "mlx_runtime_supervisor_report.json",
        "ready_key": "supervisor_ready",
        "validator_paths": (
            DISTILL_DIR / "scripts" / "validate_mlx_runtime_supervisor.py",
        ),
        "renderer_paths": (
            DISTILL_DIR / "scripts" / "render_student_cutover_private_env.py",
            DISTILL_DIR / "scripts" / "render_mlx_runtime_supervisor_private_evidence.py",
        ),
        "private_input_flag": "--evidence",
        "private_input_placeholder": "<private-runtime-supervisor-evidence-json-outside-source-control>",
        "execution_order": 1,
    },
    {
        "requirement_id": "user_data_model_improvement_external_approval",
        "report_path": REPORT_DIR / "model_improvement_evidence_report.json",
        "ready_key": "model_improvement_ready",
        "validator_paths": (
            DISTILL_DIR / "scripts" / "validate_model_improvement_evidence.py",
        ),
        "renderer_paths": (
            DISTILL_DIR / "scripts" / "render_model_improvement_private_env.py",
        ),
        "private_input_flag": "--evidence",
        "private_input_placeholder": "<private-model-improvement-evidence-json-outside-source-control>",
        "execution_order": 2,
    },
    {
        "requirement_id": "production_semantic_vector_backend",
        "report_path": REPORT_DIR / "retrieval_vector_backend_report.json",
        "ready_key": "vector_backend_ready",
        "validator_paths": (
            DISTILL_DIR / "scripts" / "validate_retrieval_vector_backend.py",
        ),
        "renderer_paths": (
            DISTILL_DIR / "scripts" / "render_retrieval_vector_private_env.py",
            DISTILL_DIR / "scripts" / "render_retrieval_vector_runtime_private_evidence.py",
        ),
        "private_input_flag": "--evidence",
        "private_input_placeholder": "<private-retrieval-vector-evidence-json-outside-source-control>",
        "execution_order": 3,
    },
    {
        "requirement_id": "production_corpus_expansion_beyond_synthetic",
        "report_path": REPORT_DIR / "production_corpus_evidence_report.json",
        "ready_key": "production_corpus_ready",
        "validator_paths": (
            DISTILL_DIR / "scripts" / "validate_production_corpus_evidence.py",
        ),
        "renderer_paths": (
            DISTILL_DIR / "scripts" / "render_production_corpus_private_evidence.py",
        ),
        "private_input_flag": "--evidence",
        "private_input_placeholder": "<private-production-corpus-evidence-json-outside-source-control>",
        "execution_order": 4,
    },
    {
        "requirement_id": "production_prediction_fairness_monitoring",
        "report_path": REPORT_DIR / "prediction_fairness_evidence_report.json",
        "ready_key": "prediction_fairness_monitoring_ready",
        "validator_paths": (
            DISTILL_DIR / "scripts" / "validate_prediction_fairness_evidence.py",
        ),
        "renderer_paths": (
            DISTILL_DIR / "scripts" / "render_prediction_fairness_private_evidence.py",
        ),
        "private_input_flag": "--evidence",
        "private_input_placeholder": "<private-prediction-fairness-evidence-json-outside-source-control>",
        "execution_order": 5,
    },
    {
        "requirement_id": "backup_disaster_recovery_evidence",
        "report_path": REPORT_DIR / "backup_disaster_recovery_evidence_report.json",
        "ready_key": "backup_disaster_recovery_ready",
        "validator_paths": (
            DISTILL_DIR / "scripts" / "validate_backup_disaster_recovery_evidence.py",
        ),
        "renderer_paths": (
            DISTILL_DIR / "scripts" / "render_backup_disaster_recovery_private_evidence.py",
        ),
        "private_input_flag": "--evidence",
        "private_input_placeholder": "<private-backup-disaster-recovery-evidence-json-outside-source-control>",
        "execution_order": 6,
    },
    {
        "requirement_id": "dependency_security_evidence",
        "report_path": REPORT_DIR / "dependency_security_evidence_report.json",
        "ready_key": "dependency_security_ready",
        "validator_paths": (
            DISTILL_DIR / "scripts" / "validate_dependency_security_evidence.py",
        ),
        "renderer_paths": (
            DISTILL_DIR / "scripts" / "render_dependency_security_private_evidence.py",
        ),
        "private_input_flag": "--evidence",
        "private_input_placeholder": "<private-dependency-security-evidence-json-outside-source-control>",
        "execution_order": 7,
    },
    {
        "requirement_id": "clearinghouse_submission_evidence",
        "report_path": REPORT_DIR / "clearinghouse_submission_evidence_report.json",
        "ready_key": "clearinghouse_submission_ready",
        "validator_paths": (
            DISTILL_DIR / "scripts" / "validate_clearinghouse_submission_evidence.py",
        ),
        "renderer_paths": (
            DISTILL_DIR / "scripts" / "render_clearinghouse_submission_private_evidence.py",
        ),
        "private_input_flag": "--evidence",
        "private_input_placeholder": "<private-clearinghouse-submission-evidence-json-outside-source-control>",
        "execution_order": 8,
    },
)

REQUIRED_HANDOFF_MARKERS = (
    "PHIplan Private Evidence Handoff",
    "Current status: source-control-ready but production-blocked.",
    "boolean-only evidence",
    "approval references outside source control",
    "private summary paths outside source control",
    "raw report paths outside source control",
    "operator run plan",
    "command skeletons",
    "no PHI",
    "no secrets",
    "no production document content",
)

PRIVATE_RENDER_OUTPUT_PLACEHOLDER = "<private-render-output-outside-source-control>"


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def safe_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return "external_path_redacted"


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing file: {safe_path(path)}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {safe_path(path)}: {type(exc).__name__}"]


def blocked_requirement_ids(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    blocked_items = payload.get("blocked_items")
    if not isinstance(blocked_items, list):
        return []
    return sorted(
        {
            str(item.get("requirement_id"))
            for item in blocked_items
            if isinstance(item, dict) and item.get("requirement_id")
        }
    )


def render_command_skeleton(renderer_path: Path) -> str:
    return (
        f"python3 {safe_path(renderer_path)} --output "
        f"{PRIVATE_RENDER_OUTPUT_PLACEHOLDER} "
        "[add approved private flags only after governance review]"
    )


def validate_command_skeleton(domain: dict[str, Any], validator_path: Path) -> str:
    return (
        f"python3 {safe_path(validator_path)} {domain['private_input_flag']} "
        f"{domain['private_input_placeholder']} "
        f"--report {safe_path(domain['report_path'])} --fail-on-blocked"
    )


def build_operator_run_step(domain: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_order": int(domain["execution_order"]),
        "requirement_id": domain["requirement_id"],
        "render_command_skeletons": [
            render_command_skeleton(path) for path in domain["renderer_paths"]
        ],
        "validate_command_skeletons": [
            validate_command_skeleton(domain, path) for path in domain["validator_paths"]
        ],
        "source_control_report_path": safe_path(domain["report_path"]),
        "private_input_placeholder": domain["private_input_placeholder"],
        "private_output_placeholder": PRIVATE_RENDER_OUTPUT_PLACEHOLDER,
        "values_redacted": True,
    }


def validate_handoff_markers(handoff_path: Path) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    missing_markers: list[str] = []
    marker_count = 0
    if not path_is_within(handoff_path, REPO_ROOT):
        blockers.append("handoff_document_outside_source_control")
    if not handoff_path.exists():
        blockers.append("handoff_document_missing")
        missing_markers = sorted(REQUIRED_HANDOFF_MARKERS)
    else:
        source = handoff_path.read_text(encoding="utf-8")
        present_markers = {marker for marker in REQUIRED_HANDOFF_MARKERS if marker in source}
        marker_count = len(present_markers)
        missing_markers = sorted(set(REQUIRED_HANDOFF_MARKERS) - present_markers)
        if missing_markers:
            blockers.append("handoff_document_required_markers_missing")
    return (
        {
            "handoff_path": safe_path(handoff_path),
            "path_inside_source_control": path_is_within(handoff_path, REPO_ROOT),
            "required_marker_count": len(REQUIRED_HANDOFF_MARKERS),
            "marker_count": marker_count,
            "missing_markers": missing_markers,
        },
        blockers,
    )


def build_domain_status(domain: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    validator_paths = tuple(domain["validator_paths"])
    renderer_paths = tuple(domain["renderer_paths"])
    report_path = domain["report_path"]
    ready_key = str(domain["ready_key"])
    missing_validator_paths = [
        safe_path(path) for path in validator_paths if not path.exists()
    ]
    missing_renderer_paths = [
        safe_path(path) for path in renderer_paths if not path.exists()
    ]
    outside_source_control_paths = [
        safe_path(path)
        for path in (*validator_paths, *renderer_paths, report_path)
        if not path_is_within(path, REPO_ROOT)
    ]
    if missing_validator_paths:
        blockers.append("domain_validator_missing")
    if missing_renderer_paths:
        blockers.append("domain_private_renderer_missing")
    if outside_source_control_paths:
        blockers.append("domain_artifact_outside_source_control")

    payload, errors = load_json(report_path)
    blockers.extend(errors)
    safe_to_review = False
    ready = False
    blocked_ids: list[str] = []
    blocked_count = 0
    if isinstance(payload, dict):
        safe_to_review = bool(payload.get("safe_to_review"))
        ready = bool(payload.get(ready_key))
        blocked_ids = blocked_requirement_ids(payload)
        raw_blocked_count = payload.get("blocked_item_count")
        if not isinstance(raw_blocked_count, bool) and isinstance(raw_blocked_count, int):
            blocked_count = raw_blocked_count
    if not safe_to_review:
        blockers.append("domain_report_not_safe_to_review")
    if not ready:
        blockers.append("domain_private_evidence_not_complete")

    return (
        {
            "requirement_id": domain["requirement_id"],
            "execution_order": int(domain["execution_order"]),
            "report_path": safe_path(report_path),
            "ready_key": ready_key,
            "validator_paths": [safe_path(path) for path in validator_paths],
            "renderer_paths": [safe_path(path) for path in renderer_paths],
            "missing_validator_paths": missing_validator_paths,
            "missing_renderer_paths": missing_renderer_paths,
            "outside_source_control_paths": outside_source_control_paths,
            "report_safe_to_review": safe_to_review,
            "private_evidence_ready": ready,
            "blocked_item_count": blocked_count,
            "blocked_requirement_ids": blocked_ids,
            "raw_report_values_included": False,
            "raw_private_values_included": False,
        },
        blockers,
    )


def build_report(handoff_path: Path = DEFAULT_HANDOFF) -> dict[str, Any]:
    handoff_evidence, handoff_blockers = validate_handoff_markers(handoff_path)
    domain_statuses = []
    blocked_domains = []
    source_control_blockers = list(handoff_blockers)
    for domain in PRIVATE_EVIDENCE_DOMAINS:
        status, blockers = build_domain_status(domain)
        domain_statuses.append(status)
        if blockers:
            blocked_domains.append(
                {
                    "requirement_id": status["requirement_id"],
                    "blockers": blockers,
                    "blocked_requirement_ids": status["blocked_requirement_ids"],
                }
            )
        for blocker in blockers:
            if blocker in {
                "domain_validator_missing",
                "domain_private_renderer_missing",
                "domain_artifact_outside_source_control",
                "domain_report_not_safe_to_review",
            } or blocker.startswith(("missing file:", "invalid JSON:")):
                source_control_blockers.append(blocker)

    private_evidence_complete = not blocked_domains
    source_control_ready = not source_control_blockers
    operator_run_plan_steps = sorted(
        (build_operator_run_step(domain) for domain in PRIVATE_EVIDENCE_DOMAINS),
        key=lambda item: item["execution_order"],
    )
    return {
        "artifact": "claimguard_phi_plan_private_evidence_handoff_status",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safe_to_review": True,
        "handoff_ready": source_control_ready,
        "private_evidence_complete": private_evidence_complete,
        "source_control_blocker_count": len(source_control_blockers),
        "source_control_blockers": sorted(set(source_control_blockers)),
        "private_blocker_count": len(blocked_domains),
        "private_blockers": blocked_domains,
        "domain_count": len(domain_statuses),
        "domain_statuses": domain_statuses,
        "operator_run_plan": {
            "ready": source_control_ready,
            "step_count": len(operator_run_plan_steps),
            "domain_order": [
                step["requirement_id"] for step in operator_run_plan_steps
            ],
            "steps": operator_run_plan_steps,
            "manual_production_gate_runs_last": (
                operator_run_plan_steps[-1]["requirement_id"]
                == "manual_production_gate_packet_evidence"
            ),
            "raw_private_values_included": False,
            "raw_private_paths_included": False,
        },
        "handoff_document": handoff_evidence,
        "raw_approval_values_included": False,
        "raw_private_summary_paths_included": False,
        "raw_report_paths_included": False,
        "raw_phi_or_secret_values_included": False,
        "raw_document_content_included": False,
        "notes": [
            "This report is source-control handoff evidence, not private approval evidence.",
            "Private evidence remains incomplete until every domain-specific report is ready.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-on-source-control-blocked", action="store_true")
    args = parser.parse_args()

    report = build_report(args.handoff)
    write_source_controlled_report_json(args.report, report, REPO_ROOT)
    print(
        "private_evidence_handoff "
        f"handoff_ready={report['handoff_ready']} "
        f"private_evidence_complete={report['private_evidence_complete']} "
        f"private_blockers={report['private_blocker_count']}"
    )
    if args.fail_on_source_control_blocked and not report["handoff_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
