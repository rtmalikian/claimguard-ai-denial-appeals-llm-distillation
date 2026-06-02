#!/usr/bin/env python3
"""Validate the PHIplan private evidence bundle template safely."""

from __future__ import annotations

import argparse
import json
import re
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
from validate_phi_plan_private_evidence_handoff import (  # noqa: E402
    PRIVATE_EVIDENCE_DOMAINS,
    safe_path,
)

DEFAULT_TEMPLATE = (
    DISTILL_DIR / "data" / "production_gate_evidence" / "private_evidence_bundle.template.json"
)
DEFAULT_REPORT = REPORT_DIR / "phi_plan_private_evidence_bundle_template_report.json"

PRIVATE_INPUT_ENV_BY_REQUIREMENT = {
    "student_default_cutover_external_approval": (
        "CLAIMGUARD_PRIVATE_RUNTIME_SUPERVISOR_EVIDENCE_PATH"
    ),
    "user_data_model_improvement_external_approval": (
        "CLAIMGUARD_PRIVATE_MODEL_IMPROVEMENT_EVIDENCE_PATH"
    ),
    "production_semantic_vector_backend": (
        "CLAIMGUARD_PRIVATE_RETRIEVAL_VECTOR_EVIDENCE_PATH"
    ),
    "production_corpus_expansion_beyond_synthetic": (
        "CLAIMGUARD_PRIVATE_PRODUCTION_CORPUS_EVIDENCE_PATH"
    ),
    "production_prediction_fairness_monitoring": (
        "CLAIMGUARD_PRIVATE_PREDICTION_FAIRNESS_EVIDENCE_PATH"
    ),
    "backup_disaster_recovery_evidence": "CLAIMGUARD_PRIVATE_BACKUP_DR_EVIDENCE_PATH",
    "dependency_security_evidence": "CLAIMGUARD_PRIVATE_DEPENDENCY_SECURITY_EVIDENCE_PATH",
    "clearinghouse_submission_evidence": (
        "CLAIMGUARD_PRIVATE_CLEARINGHOUSE_SUBMISSION_EVIDENCE_PATH"
    ),
    "manual_production_gate_packet_evidence": "CLAIMGUARD_PRIVATE_MANUAL_GATE_PACKET_PATH",
}
REQUIRED_BOUNDARY_FLAGS = (
    "raw_approval_values_included",
    "raw_document_content_included",
    "raw_phi_included",
    "raw_private_paths_included",
    "raw_secret_included",
)
ENV_NAME_RE = re.compile(r"^CLAIMGUARD_PRIVATE_[A-Z0-9_]+_PATH$")
RAW_PATH_MARKERS = ("/Users/", "/private/", "/Volumes/", "file://")
SECRET_MARKER_RE = re.compile(
    r"(?:[A-Z0-9_]*_)?(?:API|SECRET|ACCESS)_KEY|BEGIN\s+PRIVATE\s+KEY"
)


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing file: {safe_path(path)}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {safe_path(path)}: {type(exc).__name__}"]


def expected_domain(domain: dict[str, Any]) -> dict[str, Any]:
    requirement_id = str(domain["requirement_id"])
    validator_paths = tuple(domain["validator_paths"])
    return {
        "requirement_id": requirement_id,
        "execution_order": int(domain["execution_order"]),
        "private_input_env": PRIVATE_INPUT_ENV_BY_REQUIREMENT[requirement_id],
        "private_input_flag": domain["private_input_flag"],
        "validator_path": safe_path(validator_paths[0]),
        "renderer_paths": [safe_path(path) for path in domain["renderer_paths"]],
        "source_control_report_path": safe_path(domain["report_path"]),
        "ready_key": domain["ready_key"],
        "copy_private_input_outside_source_control": True,
    }


def boundary_flags_are_false(value: Any) -> tuple[bool, list[str]]:
    if not isinstance(value, dict):
        return False, list(REQUIRED_BOUNDARY_FLAGS)
    invalid_flags = [
        flag for flag in REQUIRED_BOUNDARY_FLAGS if value.get(flag) is not False
    ]
    return not invalid_flags, invalid_flags


def build_report(template_path: Path = DEFAULT_TEMPLATE) -> dict[str, Any]:
    blockers: list[str] = []
    missing_domains: list[str] = []
    extra_domains: list[str] = []
    invalid_domains: list[str] = []
    invalid_boundary_flags: dict[str, list[str]] = {}
    private_input_envs: list[str] = []
    raw_private_paths_included = False
    raw_secret_markers_included = False
    template_inside_source_control = path_is_within(template_path, REPO_ROOT)
    if not template_inside_source_control:
        blockers.append("private_evidence_bundle_template_outside_source_control")

    payload, errors = load_json(template_path)
    blockers.extend(errors)
    expected_by_requirement = {
        domain["requirement_id"]: expected_domain(domain)
        for domain in PRIVATE_EVIDENCE_DOMAINS
    }
    observed_domain_count = 0
    source_control_safe = False
    copy_template_outside_source_control = False

    if isinstance(payload, dict):
        serialized = json.dumps(payload, sort_keys=True)
        raw_private_paths_included = any(marker in serialized for marker in RAW_PATH_MARKERS)
        raw_secret_markers_included = bool(SECRET_MARKER_RE.search(serialized))
        source_control_safe = bool(payload.get("source_control_safe"))
        copy_template_outside_source_control = bool(
            payload.get("copy_template_outside_source_control")
        )
        if payload.get("artifact") != "claimguard_phi_plan_private_evidence_bundle_template":
            blockers.append("private_evidence_bundle_template_artifact_invalid")
        if not source_control_safe:
            blockers.append("private_evidence_bundle_template_not_marked_safe")
        if not copy_template_outside_source_control:
            blockers.append("private_evidence_bundle_template_copy_instruction_missing")
        raw_domain_count = payload.get("domain_count")
        if raw_domain_count != len(PRIVATE_EVIDENCE_DOMAINS):
            blockers.append("private_evidence_bundle_template_domain_count_invalid")
        boundary_ok, invalid_flags = boundary_flags_are_false(
            payload.get("source_control_boundary")
        )
        if not boundary_ok:
            blockers.append("private_evidence_bundle_template_boundary_flags_invalid")
            invalid_boundary_flags["template"] = invalid_flags

        domains = payload.get("domains")
        if isinstance(domains, list):
            observed_domain_count = len(domains)
            observed_by_requirement = {
                str(item.get("requirement_id")): item
                for item in domains
                if isinstance(item, dict) and item.get("requirement_id")
            }
            missing_domains = sorted(
                set(expected_by_requirement) - set(observed_by_requirement)
            )
            extra_domains = sorted(
                set(observed_by_requirement) - set(expected_by_requirement)
            )
            if missing_domains:
                blockers.append("private_evidence_bundle_template_domains_missing")
            if extra_domains:
                blockers.append("private_evidence_bundle_template_extra_domains")
            for requirement_id, expected in sorted(expected_by_requirement.items()):
                observed = observed_by_requirement.get(requirement_id)
                if not isinstance(observed, dict):
                    continue
                private_input_env = observed.get("private_input_env")
                if isinstance(private_input_env, str):
                    private_input_envs.append(private_input_env)
                domain_invalid = False
                for key, expected_value in expected.items():
                    if observed.get(key) != expected_value:
                        domain_invalid = True
                if not isinstance(private_input_env, str) or not ENV_NAME_RE.match(
                    private_input_env
                ):
                    domain_invalid = True
                boundary_ok, invalid_flags = boundary_flags_are_false(
                    observed.get("source_control_boundary")
                )
                if not boundary_ok:
                    domain_invalid = True
                    invalid_boundary_flags[requirement_id] = invalid_flags
                if domain_invalid:
                    invalid_domains.append(requirement_id)
            if invalid_domains:
                blockers.append("private_evidence_bundle_template_domain_metadata_invalid")
            if len(set(private_input_envs)) != len(private_input_envs):
                blockers.append("private_evidence_bundle_template_env_vars_not_unique")
        else:
            blockers.append("private_evidence_bundle_template_domains_missing")
    elif payload is not None:
        blockers.append("private_evidence_bundle_template_invalid_json_shape")

    if raw_private_paths_included:
        blockers.append("private_evidence_bundle_template_raw_private_paths_included")
    if raw_secret_markers_included:
        blockers.append("private_evidence_bundle_template_secret_markers_included")

    template_ready = not blockers
    return {
        "artifact": "claimguard_phi_plan_private_evidence_bundle_template_report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safe_to_review": True,
        "template_ready": template_ready,
        "source_control_ready": template_ready,
        "template_path": safe_path(template_path),
        "template_inside_source_control": template_inside_source_control,
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "required_domain_count": len(PRIVATE_EVIDENCE_DOMAINS),
        "domain_count": observed_domain_count,
        "missing_domains": missing_domains,
        "extra_domains": extra_domains,
        "invalid_domains": sorted(set(invalid_domains)),
        "private_input_env_count": len(set(private_input_envs)),
        "copy_template_outside_source_control": copy_template_outside_source_control,
        "source_control_safe": source_control_safe,
        "invalid_boundary_flags": invalid_boundary_flags,
        "raw_approval_values_included": False,
        "raw_document_content_included": False,
        "raw_phi_included": False,
        "raw_private_paths_included": raw_private_paths_included,
        "raw_secret_included": raw_secret_markers_included,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = build_report(args.template)
    write_source_controlled_report_json(args.report, report, REPO_ROOT)
    print(
        "private_evidence_bundle_template "
        f"template_ready={report['template_ready']} "
        f"domain_count={report['domain_count']} "
        f"blockers={report['blocker_count']}"
    )
    if args.fail_on_blocked and not report["template_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
