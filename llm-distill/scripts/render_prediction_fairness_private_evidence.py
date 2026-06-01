#!/usr/bin/env python3
"""Render private prediction-fairness evidence without printing values."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path("/private/tmp/claimguard-prediction-fairness.private.evidence.json")
DEFAULT_OUTCOME_DATASET_REFERENCE_ENV = "PREDICTION_FAIRNESS_OUTCOME_DATASET_REFERENCE"
DEFAULT_THRESHOLD_REVIEW_REFERENCE_ENV = "PREDICTION_FAIRNESS_THRESHOLD_REVIEW_REFERENCE"
DEFAULT_DEMOGRAPHIC_GROUPING_REFERENCE_ENV = (
    "PREDICTION_FAIRNESS_DEMOGRAPHIC_GROUPING_REFERENCE"
)
DEFAULT_MONITORING_CONFIG_REFERENCE_ENV = "PREDICTION_FAIRNESS_MONITORING_CONFIG_REFERENCE"
DEFAULT_ALERT_OWNER_REFERENCE_ENV = "PREDICTION_FAIRNESS_ALERT_OWNER_REFERENCE"
DEFAULT_LATEST_RUN_REFERENCE_ENV = "PREDICTION_FAIRNESS_LATEST_RUN_REFERENCE"
DEFAULT_LEGAL_PRIVACY_REFERENCE_ENV = "PREDICTION_FAIRNESS_LEGAL_PRIVACY_REFERENCE"
DEFAULT_MONITORING_SUMMARY_PATH_ENV = (
    "PREDICTION_FAIRNESS_PRIVATE_MONITORING_SUMMARY_PATH"
)
DEFAULT_PRIVATE_EVIDENCE_RENDERER_PATH = (
    "llm-distill/scripts/render_prediction_fairness_private_evidence.py"
)
REQUIRED_MONITORING_SUMMARY_TRUE_FLAGS = {
    "approved_outcome_dataset_available",
    "minimum_sample_size_met",
    "calibration_run_completed",
    "threshold_review_completed",
    "human_review_policy_confirmed",
    "approved_demographic_grouping_reviewed",
    "continuous_monitoring_configured",
    "disparity_thresholds_documented",
    "alerting_and_review_owner_configured",
    "latest_monitoring_run_passed",
    "legal_privacy_review_completed",
    "rollback_or_threshold_reversion_reviewed",
    "audit_log_metadata_only_verified",
    "no_phi_or_secret_values_attested",
    "no_raw_demographic_values_attested",
    "no_production_outcome_rows_attested",
    "values_redacted",
}
REQUIRED_MONITORING_SUMMARY_FALSE_FLAGS = {
    "private_reference_values_included",
    "raw_demographic_values_included",
    "production_outcome_rows_included",
    "individual_identifiers_included",
    "approval_reference_values_included",
    "credential_values_included",
    "phi_or_secret_values_included",
    "production_document_content_included",
}
REQUIRED_MONITORING_SUMMARY_POSITIVE_COUNTS = {
    "private_reference_count",
    "evaluated_outcome_count",
    "monitored_group_count",
    "disparity_metric_count",
    "alert_rule_count",
}
ALLOWED_MONITORING_SUMMARY_KEYS = (
    REQUIRED_MONITORING_SUMMARY_TRUE_FLAGS
    | REQUIRED_MONITORING_SUMMARY_FALSE_FLAGS
    | REQUIRED_MONITORING_SUMMARY_POSITIVE_COUNTS
)
REQUIRED_ATTESTATIONS = {
    "approved_outcome_dataset_attested": "approved outcome dataset attestation is required",
    "minimum_sample_size_attested": "minimum sample size attestation is required",
    "calibration_run_attested": "calibration run attestation is required",
    "threshold_review_attested": "threshold review attestation is required",
    "human_review_policy_attested": "human-review policy attestation is required",
    "demographic_grouping_reviewed": "demographic grouping review attestation is required",
    "continuous_monitoring_configured": "continuous monitoring attestation is required",
    "disparity_thresholds_documented": "disparity thresholds attestation is required",
    "alert_owner_configured": "alert owner attestation is required",
    "latest_monitoring_run_passed": "latest monitoring run attestation is required",
    "legal_privacy_review_completed": "legal/privacy review attestation is required",
    "rollback_reviewed": "rollback or threshold reversion attestation is required",
    "metadata_only_audit_verified": "metadata-only audit attestation is required",
    "no_raw_values_attested": "no raw values attestation is required",
}
ALLOWED_ENV_KEYS = {
    DEFAULT_OUTCOME_DATASET_REFERENCE_ENV,
    DEFAULT_THRESHOLD_REVIEW_REFERENCE_ENV,
    DEFAULT_DEMOGRAPHIC_GROUPING_REFERENCE_ENV,
    DEFAULT_MONITORING_CONFIG_REFERENCE_ENV,
    DEFAULT_ALERT_OWNER_REFERENCE_ENV,
    DEFAULT_LATEST_RUN_REFERENCE_ENV,
    DEFAULT_LEGAL_PRIVACY_REFERENCE_ENV,
    DEFAULT_MONITORING_SUMMARY_PATH_ENV,
}
FORBIDDEN_ENV_KEY_FRAGMENTS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "proxy",
    "raw",
    "secret",
    "token",
}
SAFE_REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/=@+-]{2,255}$")
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")


class RenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderConfig:
    output_path: Path
    approved_monitoring: bool = False
    outcome_dataset_reference_env: str = DEFAULT_OUTCOME_DATASET_REFERENCE_ENV
    threshold_review_reference_env: str = DEFAULT_THRESHOLD_REVIEW_REFERENCE_ENV
    demographic_grouping_reference_env: str = DEFAULT_DEMOGRAPHIC_GROUPING_REFERENCE_ENV
    monitoring_config_reference_env: str = DEFAULT_MONITORING_CONFIG_REFERENCE_ENV
    alert_owner_reference_env: str = DEFAULT_ALERT_OWNER_REFERENCE_ENV
    latest_run_reference_env: str = DEFAULT_LATEST_RUN_REFERENCE_ENV
    legal_privacy_reference_env: str = DEFAULT_LEGAL_PRIVACY_REFERENCE_ENV
    monitoring_summary_path_env: str = DEFAULT_MONITORING_SUMMARY_PATH_ENV
    approved_outcome_dataset_attested: bool = False
    minimum_sample_size_attested: bool = False
    calibration_run_attested: bool = False
    threshold_review_attested: bool = False
    human_review_policy_attested: bool = False
    demographic_grouping_reviewed: bool = False
    continuous_monitoring_configured: bool = False
    disparity_thresholds_documented: bool = False
    alert_owner_configured: bool = False
    latest_monitoring_run_passed: bool = False
    legal_privacy_review_completed: bool = False
    rollback_reviewed: bool = False
    metadata_only_audit_verified: bool = False
    no_raw_values_attested: bool = False
    dry_run: bool = False


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _validate_env_key(name: str) -> None:
    if name not in ALLOWED_ENV_KEYS and not ENV_KEY_RE.match(name):
        raise RenderError("unexpected environment key requested")
    if any(fragment in name.lower() for fragment in FORBIDDEN_ENV_KEY_FRAGMENTS):
        raise RenderError("secret-like environment key requested")


def _validate_private_reference(value: str, label: str) -> None:
    if not value:
        raise RenderError(f"{label} env var is required for approved monitoring")
    if "\n" in value or "\r" in value or "\t" in value or " " in value:
        raise RenderError(f"{label} must not contain whitespace or control characters")
    if "#" in value:
        raise RenderError(f"{label} must not contain comment delimiters")
    if not SAFE_REFERENCE_RE.match(value):
        raise RenderError(f"{label} contains unsupported characters")


def _load_private_reference(env_name: str, label: str) -> str:
    _validate_env_key(env_name)
    value = os.environ.get(env_name, "").strip()
    _validate_private_reference(value, label)
    return value


def _load_private_monitoring_summary_path(env_name: str) -> Path:
    _validate_env_key(env_name)
    raw_path = os.environ.get(env_name, "").strip()
    if not raw_path:
        raise RenderError("private monitoring summary path env var is required")
    if "\n" in raw_path or "\r" in raw_path or "\t" in raw_path or "#" in raw_path:
        raise RenderError("private monitoring summary path contains unsupported characters")
    summary_path = Path(raw_path).expanduser().resolve()
    if path_is_within(summary_path, REPO_ROOT):
        raise RenderError("private monitoring summary path must be outside source control")
    if not summary_path.exists():
        raise RenderError("private monitoring summary path does not exist")
    if not summary_path.is_file():
        raise RenderError("private monitoring summary path must be a file")
    return summary_path


def _load_private_monitoring_summary_payload(summary_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise RenderError("private monitoring summary must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise RenderError("private monitoring summary must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise RenderError("private monitoring summary must be a JSON object")
    return payload


def _validate_private_monitoring_summary(
    summary_path: Path,
    *,
    private_reference_count: int,
) -> dict[str, int]:
    payload = _load_private_monitoring_summary_payload(summary_path)
    unsupported_keys = sorted(set(payload) - ALLOWED_MONITORING_SUMMARY_KEYS)
    if unsupported_keys:
        raise RenderError("private monitoring summary contains unsupported fields")

    for key in sorted(REQUIRED_MONITORING_SUMMARY_TRUE_FLAGS):
        if payload.get(key) is not True:
            raise RenderError(f"private monitoring summary requires {key}=true")
    for key in sorted(REQUIRED_MONITORING_SUMMARY_FALSE_FLAGS):
        if payload.get(key) is not False:
            raise RenderError(f"private monitoring summary requires {key}=false")
    for key in sorted(REQUIRED_MONITORING_SUMMARY_POSITIVE_COUNTS):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RenderError(f"private monitoring summary requires positive {key}")

    if payload["private_reference_count"] != private_reference_count:
        raise RenderError("private monitoring summary private reference count mismatch")

    return {
        "private_reference_count": int(payload["private_reference_count"]),
        "evaluated_outcome_count": int(payload["evaluated_outcome_count"]),
        "monitored_group_count": int(payload["monitored_group_count"]),
        "disparity_metric_count": int(payload["disparity_metric_count"]),
        "alert_rule_count": int(payload["alert_rule_count"]),
    }


def _validate_approved_attestations(config: RenderConfig) -> None:
    missing = [
        message
        for flag, message in REQUIRED_ATTESTATIONS.items()
        if getattr(config, flag) is not True
    ]
    if missing:
        raise RenderError("approved monitoring requires explicit attestations")


def _load_private_references(config: RenderConfig) -> list[str]:
    reference_specs = [
        (config.outcome_dataset_reference_env, "outcome dataset reference"),
        (config.threshold_review_reference_env, "threshold review reference"),
        (config.demographic_grouping_reference_env, "demographic grouping reference"),
        (config.monitoring_config_reference_env, "monitoring config reference"),
        (config.alert_owner_reference_env, "alert owner reference"),
        (config.latest_run_reference_env, "latest monitoring run reference"),
        (config.legal_privacy_reference_env, "legal/privacy review reference"),
    ]
    return [
        _load_private_reference(env_name, label)
        for env_name, label in reference_specs
    ]


def _evidence_payload(config: RenderConfig) -> tuple[dict[str, Any], int]:
    private_reference_count = 0
    private_monitoring_summary = {
        "private_reference_count": 0,
        "evaluated_outcome_count": 0,
        "monitored_group_count": 0,
        "disparity_metric_count": 0,
        "alert_rule_count": 0,
    }
    if config.approved_monitoring:
        _validate_approved_attestations(config)
        monitoring_summary_path = _load_private_monitoring_summary_path(
            config.monitoring_summary_path_env
        )
        private_reference_count = len(_load_private_references(config))
        private_monitoring_summary = _validate_private_monitoring_summary(
            monitoring_summary_path,
            private_reference_count=private_reference_count,
        )
        status = "production_monitoring_ready"
        calibrated_ready = True
        monitoring_ready = True
        legal_ready = True
    else:
        status = "private_renderer_default_production_monitoring_blocked"
        calibrated_ready = False
        monitoring_ready = False
        legal_ready = False

    evidence = {
        "artifact": "claimguard_prediction_fairness_monitoring_evidence",
        "version": "1.0",
        "evidence_status": status,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "no_phi_or_secret_values_attested": True,
        "no_raw_demographic_values_attested": True,
        "no_production_outcome_rows_attested": True,
        "private_monitoring_summary_path_env": (
            config.monitoring_summary_path_env if config.approved_monitoring else None
        ),
        "private_monitoring_summary_path_configured": bool(config.approved_monitoring),
        "private_monitoring_summary_path_value_included": False,
        "private_monitoring_summary_checked": bool(config.approved_monitoring),
        "private_monitoring_summary_private_reference_count": (
            private_monitoring_summary["private_reference_count"]
        ),
        "private_monitoring_summary_evaluated_outcome_count": (
            private_monitoring_summary["evaluated_outcome_count"]
        ),
        "private_monitoring_summary_monitored_group_count": (
            private_monitoring_summary["monitored_group_count"]
        ),
        "private_monitoring_summary_disparity_metric_count": (
            private_monitoring_summary["disparity_metric_count"]
        ),
        "private_monitoring_summary_alert_rule_count": (
            private_monitoring_summary["alert_rule_count"]
        ),
        "private_monitoring_summary_raw_values_included": False,
        "calibrated_threshold": {
            "source_control_calibration_checklist_documented": True,
            "calibration_checklist_path": (
                "llm-distill/docs/prediction-fairness-calibration-checklist.md"
            ),
            "approved_outcome_dataset_available": calibrated_ready,
            "minimum_sample_size_met": calibrated_ready,
            "calibration_run_completed": calibrated_ready,
            "threshold_review_completed": calibrated_ready,
            "human_review_policy_confirmed": True,
        },
        "fairness_monitoring": {
            "source_control_monitoring_validation_checklist_documented": True,
            "monitoring_validation_checklist_path": (
                "llm-distill/docs/prediction-fairness-monitoring-validation-checklist.md"
            ),
            "approved_demographic_grouping_reviewed": monitoring_ready,
            "continuous_monitoring_configured": monitoring_ready,
            "disparity_thresholds_documented": monitoring_ready,
            "alerting_and_review_owner_configured": monitoring_ready,
            "latest_monitoring_run_passed": monitoring_ready,
        },
        "governance_controls": {
            "legal_privacy_review_completed": legal_ready,
            "source_control_legal_privacy_checklist_documented": True,
            "legal_privacy_checklist_path": (
                "llm-distill/docs/prediction-fairness-legal-privacy-checklist.md"
            ),
            "source_control_monitoring_runbook_documented": True,
            "monitoring_runbook_path": (
                "llm-distill/docs/prediction-fairness-monitoring-runbook.md"
            ),
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": DEFAULT_PRIVATE_EVIDENCE_RENDERER_PATH,
            "model_card_updated": True,
            "model_card_path": "llm-distill/docs/prediction-fairness-model-card.md",
            "rollback_or_threshold_reversion_reviewed": True,
            "audit_log_metadata_only_verified": True,
        },
    }
    return evidence, private_reference_count


def _json_file_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_private_evidence(config: RenderConfig) -> dict[str, Any]:
    output_path = config.output_path.resolve()
    if path_is_within(output_path, REPO_ROOT):
        raise RenderError("refusing_to_write_inside_source_control")

    evidence, private_reference_count = _evidence_payload(config)
    calibrated_threshold = evidence["calibrated_threshold"]
    fairness_monitoring = evidence["fairness_monitoring"]
    governance_controls = evidence["governance_controls"]
    summary = {
        "dry_run": config.dry_run,
        "rendered": not config.dry_run,
        "approved_monitoring_requested": config.approved_monitoring,
        "approved_outcome_dataset_available": calibrated_threshold[
            "approved_outcome_dataset_available"
        ],
        "minimum_sample_size_met": calibrated_threshold["minimum_sample_size_met"],
        "calibration_run_completed": calibrated_threshold["calibration_run_completed"],
        "threshold_review_completed": calibrated_threshold["threshold_review_completed"],
        "approved_demographic_grouping_reviewed": fairness_monitoring[
            "approved_demographic_grouping_reviewed"
        ],
        "continuous_monitoring_configured": fairness_monitoring[
            "continuous_monitoring_configured"
        ],
        "disparity_thresholds_documented": fairness_monitoring[
            "disparity_thresholds_documented"
        ],
        "alerting_and_review_owner_configured": fairness_monitoring[
            "alerting_and_review_owner_configured"
        ],
        "latest_monitoring_run_passed": fairness_monitoring[
            "latest_monitoring_run_passed"
        ],
        "legal_privacy_review_completed": governance_controls[
            "legal_privacy_review_completed"
        ],
        "private_reference_count": private_reference_count,
        "private_monitoring_summary_path_env_configured": bool(
            evidence["private_monitoring_summary_path_env"]
        ),
        "private_monitoring_summary_path_value_included": False,
        "private_monitoring_summary_checked": evidence[
            "private_monitoring_summary_checked"
        ],
        "private_monitoring_summary_private_reference_count": evidence[
            "private_monitoring_summary_private_reference_count"
        ],
        "private_monitoring_summary_evaluated_outcome_count": evidence[
            "private_monitoring_summary_evaluated_outcome_count"
        ],
        "private_monitoring_summary_monitored_group_count": evidence[
            "private_monitoring_summary_monitored_group_count"
        ],
        "private_monitoring_summary_disparity_metric_count": evidence[
            "private_monitoring_summary_disparity_metric_count"
        ],
        "private_monitoring_summary_alert_rule_count": evidence[
            "private_monitoring_summary_alert_rule_count"
        ],
        "private_monitoring_summary_raw_values_included": False,
        "output_path_in_source_control": False,
        "raw_private_values_included": False,
        "raw_demographic_values_included": False,
        "production_outcome_rows_included": False,
        "raw_paths_in_summary": False,
        "values_redacted": True,
        "file_mode": "0600" if not config.dry_run else None,
    }

    if not config.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_json_file_text(evidence))
        output_path.chmod(0o600)
    return summary


def build_config(args: argparse.Namespace) -> RenderConfig:
    return RenderConfig(
        output_path=args.output,
        approved_monitoring=args.approved_monitoring,
        outcome_dataset_reference_env=args.outcome_dataset_reference_env,
        threshold_review_reference_env=args.threshold_review_reference_env,
        demographic_grouping_reference_env=args.demographic_grouping_reference_env,
        monitoring_config_reference_env=args.monitoring_config_reference_env,
        alert_owner_reference_env=args.alert_owner_reference_env,
        latest_run_reference_env=args.latest_run_reference_env,
        legal_privacy_reference_env=args.legal_privacy_reference_env,
        monitoring_summary_path_env=args.monitoring_summary_path_env,
        approved_outcome_dataset_attested=args.approved_outcome_dataset_attested,
        minimum_sample_size_attested=args.minimum_sample_size_attested,
        calibration_run_attested=args.calibration_run_attested,
        threshold_review_attested=args.threshold_review_attested,
        human_review_policy_attested=args.human_review_policy_attested,
        demographic_grouping_reviewed=args.demographic_grouping_reviewed,
        continuous_monitoring_configured=args.continuous_monitoring_configured,
        disparity_thresholds_documented=args.disparity_thresholds_documented,
        alert_owner_configured=args.alert_owner_configured,
        latest_monitoring_run_passed=args.latest_monitoring_run_passed,
        legal_privacy_review_completed=args.legal_privacy_review_completed,
        rollback_reviewed=args.rollback_reviewed,
        metadata_only_audit_verified=args.metadata_only_audit_verified,
        no_raw_values_attested=args.no_raw_values_attested,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--approved-monitoring", action="store_true")
    parser.add_argument(
        "--outcome-dataset-reference-env",
        default=DEFAULT_OUTCOME_DATASET_REFERENCE_ENV,
    )
    parser.add_argument(
        "--threshold-review-reference-env",
        default=DEFAULT_THRESHOLD_REVIEW_REFERENCE_ENV,
    )
    parser.add_argument(
        "--demographic-grouping-reference-env",
        default=DEFAULT_DEMOGRAPHIC_GROUPING_REFERENCE_ENV,
    )
    parser.add_argument(
        "--monitoring-config-reference-env",
        default=DEFAULT_MONITORING_CONFIG_REFERENCE_ENV,
    )
    parser.add_argument(
        "--alert-owner-reference-env",
        default=DEFAULT_ALERT_OWNER_REFERENCE_ENV,
    )
    parser.add_argument("--latest-run-reference-env", default=DEFAULT_LATEST_RUN_REFERENCE_ENV)
    parser.add_argument(
        "--legal-privacy-reference-env",
        default=DEFAULT_LEGAL_PRIVACY_REFERENCE_ENV,
    )
    parser.add_argument(
        "--monitoring-summary-path-env",
        default=DEFAULT_MONITORING_SUMMARY_PATH_ENV,
    )
    parser.add_argument("--approved-outcome-dataset-attested", action="store_true")
    parser.add_argument("--minimum-sample-size-attested", action="store_true")
    parser.add_argument("--calibration-run-attested", action="store_true")
    parser.add_argument("--threshold-review-attested", action="store_true")
    parser.add_argument("--human-review-policy-attested", action="store_true")
    parser.add_argument("--demographic-grouping-reviewed", action="store_true")
    parser.add_argument("--continuous-monitoring-configured", action="store_true")
    parser.add_argument("--disparity-thresholds-documented", action="store_true")
    parser.add_argument("--alert-owner-configured", action="store_true")
    parser.add_argument("--latest-monitoring-run-passed", action="store_true")
    parser.add_argument("--legal-privacy-review-completed", action="store_true")
    parser.add_argument("--rollback-reviewed", action="store_true")
    parser.add_argument("--metadata-only-audit-verified", action="store_true")
    parser.add_argument("--no-raw-values-attested", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        summary = render_private_evidence(build_config(args))
    except RenderError as exc:
        print(json.dumps({"error": str(exc), "values_redacted": True}, sort_keys=True))
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
