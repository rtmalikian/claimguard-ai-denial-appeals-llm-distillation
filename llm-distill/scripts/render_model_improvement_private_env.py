#!/usr/bin/env python3
"""Render a private model-improvement env file without printing values."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path("/private/tmp/claimguard-model-improvement.private.env")
DEFAULT_APPROVAL_REFERENCE_ENV = "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE"
DEFAULT_CONSENT_NOTICE_ENV = "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION"
DEFAULT_PRIVATE_SUMMARY_PATH_ENV = "USER_DATA_MODEL_IMPROVEMENT_PRIVATE_SUMMARY_PATH"
DEFAULT_EVIDENCE_REPORT = "llm-distill/evals/reports/model_improvement_evidence_report.json"
REQUIRED_ATTESTATIONS = {
    "model_improvement_request_attested": "model-improvement request attestation is required",
    "legal_approval_attested": "legal approval attestation is required",
    "baa_confirmed_attested": "BAA confirmation attestation is required",
    "consent_notice_attested": "consent notice version attestation is required",
    "retention_reviewed": "retention review attestation is required",
    "revocation_reviewed": "revocation review attestation is required",
    "per_request_attestations_reviewed": "per-request attestation review is required",
    "evidence_ready_attested": "model-improvement evidence readiness attestation is required",
}
ALLOWED_ENV_KEYS = {
    "USER_DATA_MODEL_IMPROVEMENT_ENABLED",
    "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED",
    "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED",
    "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION",
    "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE",
    "USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT",
    DEFAULT_PRIVATE_SUMMARY_PATH_ENV,
}
FORBIDDEN_ENV_KEY_FRAGMENTS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}
SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/=@+-]{2,255}$")
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
REQUIRED_PRIVATE_SUMMARY_TRUE_FLAGS = {
    "model_improvement_request_attested",
    "legal_approval_attested",
    "baa_confirmed_attested",
    "consent_notice_attested",
    "retention_reviewed",
    "revocation_reviewed",
    "per_request_attestations_reviewed",
    "evidence_ready_attested",
    "approval_reference_configured",
    "consent_notice_version_configured",
    "model_improvement_evidence_report_ready",
    "data_use_scope_reviewed",
    "approved_corpus_only_attested",
    "no_external_phi_deidentification_attested",
    "raw_phi_training_disabled_attested",
    "revocation_blocks_future_training_attested",
    "no_phi_or_secret_values_attested",
    "values_redacted",
}
REQUIRED_PRIVATE_SUMMARY_FALSE_FLAGS = {
    "approval_reference_value_included",
    "consent_notice_value_included",
    "raw_env_values_included",
    "raw_evidence_report_included",
    "raw_user_data_included",
    "raw_document_content_included",
    "phi_or_secret_values_included",
    "credential_values_included",
    "endpoint_values_included",
    "legal_document_values_included",
    "baa_document_values_included",
}
REQUIRED_PRIVATE_SUMMARY_POSITIVE_COUNTS = {
    "environment_variable_count",
    "private_reference_count",
    "private_consent_notice_count",
    "evidence_report_count",
    "retention_review_count",
    "revocation_review_count",
    "per_request_gate_count",
}
ALLOWED_PRIVATE_SUMMARY_KEYS = (
    REQUIRED_PRIVATE_SUMMARY_TRUE_FLAGS
    | REQUIRED_PRIVATE_SUMMARY_FALSE_FLAGS
    | REQUIRED_PRIVATE_SUMMARY_POSITIVE_COUNTS
)


class RenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderConfig:
    output_path: Path
    approved_model_improvement: bool = False
    approval_reference_env: str = DEFAULT_APPROVAL_REFERENCE_ENV
    consent_notice_env: str = DEFAULT_CONSENT_NOTICE_ENV
    private_summary_path_env: str = DEFAULT_PRIVATE_SUMMARY_PATH_ENV
    evidence_report: str = DEFAULT_EVIDENCE_REPORT
    model_improvement_request_attested: bool = False
    legal_approval_attested: bool = False
    baa_confirmed_attested: bool = False
    consent_notice_attested: bool = False
    retention_reviewed: bool = False
    revocation_reviewed: bool = False
    per_request_attestations_reviewed: bool = False
    evidence_ready_attested: bool = False
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


def _validate_safe_private_value(value: str, label: str) -> None:
    if not value:
        raise RenderError(f"{label} env var is required for approved model improvement")
    if "\n" in value or "\r" in value or "\t" in value or " " in value:
        raise RenderError(f"{label} must not contain whitespace or control characters")
    if "#" in value:
        raise RenderError(f"{label} must not contain comment delimiters")
    if not SAFE_VALUE_RE.match(value):
        raise RenderError(f"{label} contains unsupported characters")


def _load_private_value(env_name: str, label: str) -> str:
    _validate_env_key(env_name)
    value = os.environ.get(env_name, "").strip()
    _validate_safe_private_value(value, label)
    return value


def _load_private_summary_path(env_name: str) -> Path:
    _validate_env_key(env_name)
    raw_path = os.environ.get(env_name, "").strip()
    if not raw_path:
        raise RenderError("private model-improvement summary path env var is required")
    if "\n" in raw_path or "\r" in raw_path or "\t" in raw_path or "#" in raw_path:
        raise RenderError("private model-improvement summary path contains unsupported characters")
    summary_path = Path(raw_path).expanduser().resolve()
    if path_is_within(summary_path, REPO_ROOT):
        raise RenderError("private model-improvement summary path must be outside source control")
    if not summary_path.exists():
        raise RenderError("private model-improvement summary path does not exist")
    if not summary_path.is_file():
        raise RenderError("private model-improvement summary path must be a file")
    return summary_path


def _load_private_summary_payload(summary_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise RenderError("private model-improvement summary must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise RenderError("private model-improvement summary must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise RenderError("private model-improvement summary must be a JSON object")
    return payload


def _validate_evidence_report(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise RenderError("evidence report path is required")
    if "\n" in cleaned or "\r" in cleaned or "\t" in cleaned or "#" in cleaned:
        raise RenderError("evidence report path contains unsupported characters")
    if Path(cleaned).is_absolute():
        raise RenderError("evidence report path must be repository-relative")
    report_path = (REPO_ROOT / cleaned).resolve()
    if not path_is_within(report_path, REPO_ROOT):
        raise RenderError("evidence report path must stay inside source control")
    return cleaned


def _validate_approved_attestations(config: RenderConfig) -> None:
    missing = [
        message
        for flag, message in REQUIRED_ATTESTATIONS.items()
        if getattr(config, flag) is not True
    ]
    if missing:
        raise RenderError("approved model improvement requires explicit attestations")


def _load_evidence_report(report_path: Path) -> dict[str, Any]:
    if not report_path.exists():
        raise RenderError("model-improvement evidence report is unavailable")
    if not report_path.is_file():
        raise RenderError("model-improvement evidence report path must be a file")
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RenderError("model-improvement evidence report is unreadable") from exc
    if not isinstance(payload, dict):
        raise RenderError("model-improvement evidence report must be a JSON object")
    return payload


def _validate_evidence_report_ready(evidence_report: str) -> None:
    report_path = (REPO_ROOT / evidence_report).resolve()
    report = _load_evidence_report(report_path)
    blocked_items = report.get("blocked_items")
    blocked_item_count = report.get("blocked_item_count")
    if report.get("safe_to_review") is not True:
        raise RenderError("model-improvement evidence report is not safe to review")
    if report.get("model_improvement_ready") is not True:
        raise RenderError("model-improvement evidence report is not ready")
    if blocked_item_count not in (0, None):
        raise RenderError("model-improvement evidence report has blocked requirements")
    if isinstance(blocked_items, list) and blocked_items:
        raise RenderError("model-improvement evidence report has blocked requirements")


def _validate_private_model_improvement_summary(
    summary_path: Path,
    environment_variable_count: int,
) -> dict[str, int]:
    payload = _load_private_summary_payload(summary_path)
    unsupported_keys = sorted(set(payload) - ALLOWED_PRIVATE_SUMMARY_KEYS)
    if unsupported_keys:
        raise RenderError("private model-improvement summary contains unsupported fields")

    for key in sorted(REQUIRED_PRIVATE_SUMMARY_TRUE_FLAGS):
        if payload.get(key) is not True:
            raise RenderError(f"private model-improvement summary requires {key}=true")
    for key in sorted(REQUIRED_PRIVATE_SUMMARY_FALSE_FLAGS):
        if payload.get(key) is not False:
            raise RenderError(f"private model-improvement summary requires {key}=false")
    counts: dict[str, int] = {}
    for key in sorted(REQUIRED_PRIVATE_SUMMARY_POSITIVE_COUNTS):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RenderError(f"private model-improvement summary requires positive {key}")
        counts[key] = int(value)

    if counts["environment_variable_count"] != environment_variable_count:
        raise RenderError("private model-improvement summary environment variable count mismatch")
    if counts["private_reference_count"] != 1:
        raise RenderError("private model-improvement summary private reference count mismatch")
    if counts["private_consent_notice_count"] != 1:
        raise RenderError("private model-improvement summary consent notice count mismatch")
    if counts["evidence_report_count"] != 1:
        raise RenderError("private model-improvement summary evidence report count mismatch")
    return counts


def _build_environment(config: RenderConfig) -> dict[str, str]:
    evidence_report = _validate_evidence_report(config.evidence_report)
    if config.approved_model_improvement:
        _validate_approved_attestations(config)
        _validate_evidence_report_ready(evidence_report)
        approval_reference = _load_private_value(
            config.approval_reference_env,
            "approval reference",
        )
        consent_notice_version = _load_private_value(
            config.consent_notice_env,
            "consent notice version",
        )
        env = {
            "USER_DATA_MODEL_IMPROVEMENT_ENABLED": "true",
            "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED": "true",
            "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED": "true",
            "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION": consent_notice_version,
            "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE": approval_reference,
            "USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT": evidence_report,
        }
    else:
        env = {
            "USER_DATA_MODEL_IMPROVEMENT_ENABLED": "false",
            "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED": "false",
            "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED": "false",
            "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION": "",
            "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE": "",
            "USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT": evidence_report,
        }
    unexpected = set(env) - ALLOWED_ENV_KEYS
    if unexpected:
        raise RenderError("unexpected environment keys would be written")
    for key in env:
        _validate_env_key(key)
    return env


def _env_file_text(env: dict[str, str]) -> str:
    lines = [
        "# ClaimGuard AI private model-improvement environment.",
        "# Do not commit this file. Store it outside source control.",
    ]
    lines.extend(f"{key}={value}" for key, value in env.items())
    return "\n".join(lines) + "\n"


def render_private_env(config: RenderConfig) -> dict[str, Any]:
    output_path = config.output_path.resolve()
    if path_is_within(output_path, REPO_ROOT):
        raise RenderError("refusing_to_write_inside_source_control")

    env = _build_environment(config)
    private_summary_counts = {
        "environment_variable_count": 0,
        "private_reference_count": 0,
        "private_consent_notice_count": 0,
        "evidence_report_count": 0,
        "retention_review_count": 0,
        "revocation_review_count": 0,
        "per_request_gate_count": 0,
    }
    if config.approved_model_improvement:
        private_summary_counts = _validate_private_model_improvement_summary(
            _load_private_summary_path(config.private_summary_path_env),
            len(env),
        )
    summary = {
        "dry_run": config.dry_run,
        "rendered": not config.dry_run,
        "approved_model_improvement_requested": config.approved_model_improvement,
        "model_improvement_enabled": (
            env["USER_DATA_MODEL_IMPROVEMENT_ENABLED"] == "true"
        ),
        "legal_approval_confirmed": (
            env["USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED"] == "true"
        ),
        "baa_confirmed": env["USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED"] == "true",
        "consent_notice_version_configured": bool(
            env["USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION"]
        ),
        "approval_reference_configured": bool(
            env["USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE"]
        ),
        "evidence_report_configured": bool(
            env["USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT"]
        ),
        "evidence_report_checked": config.approved_model_improvement,
        "evidence_report_ready": config.approved_model_improvement,
        "environment_variable_count": len(env),
        "private_model_improvement_summary_checked": (
            config.approved_model_improvement
        ),
        "private_model_improvement_summary_path_env_configured": (
            bool(config.private_summary_path_env)
            if config.approved_model_improvement
            else False
        ),
        "private_model_improvement_summary_path_value_included": False,
        "private_model_improvement_summary_environment_variable_count": (
            private_summary_counts["environment_variable_count"]
        ),
        "private_model_improvement_summary_private_reference_count": (
            private_summary_counts["private_reference_count"]
        ),
        "private_model_improvement_summary_consent_notice_count": (
            private_summary_counts["private_consent_notice_count"]
        ),
        "private_model_improvement_summary_evidence_report_count": (
            private_summary_counts["evidence_report_count"]
        ),
        "private_model_improvement_summary_retention_review_count": (
            private_summary_counts["retention_review_count"]
        ),
        "private_model_improvement_summary_revocation_review_count": (
            private_summary_counts["revocation_review_count"]
        ),
        "private_model_improvement_summary_per_request_gate_count": (
            private_summary_counts["per_request_gate_count"]
        ),
        "private_model_improvement_summary_raw_values_included": False,
        "output_path_in_source_control": False,
        "raw_env_values_included": False,
        "approval_reference_value_included": False,
        "consent_notice_value_included": False,
        "raw_paths_in_summary": False,
        "values_redacted": True,
        "file_mode": "0600" if not config.dry_run else None,
    }

    if not config.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_env_file_text(env))
        output_path.chmod(0o600)
    return summary


def build_config(args: argparse.Namespace) -> RenderConfig:
    return RenderConfig(
        output_path=args.output,
        approved_model_improvement=args.approved_model_improvement,
        approval_reference_env=args.approval_reference_env,
        consent_notice_env=args.consent_notice_env,
        private_summary_path_env=args.private_summary_path_env,
        evidence_report=args.evidence_report,
        model_improvement_request_attested=args.model_improvement_request_attested,
        legal_approval_attested=args.legal_approval_attested,
        baa_confirmed_attested=args.baa_confirmed_attested,
        consent_notice_attested=args.consent_notice_attested,
        retention_reviewed=args.retention_reviewed,
        revocation_reviewed=args.revocation_reviewed,
        per_request_attestations_reviewed=args.per_request_attestations_reviewed,
        evidence_ready_attested=args.evidence_ready_attested,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--approved-model-improvement", action="store_true")
    parser.add_argument("--approval-reference-env", default=DEFAULT_APPROVAL_REFERENCE_ENV)
    parser.add_argument("--consent-notice-env", default=DEFAULT_CONSENT_NOTICE_ENV)
    parser.add_argument(
        "--private-summary-path-env",
        default=DEFAULT_PRIVATE_SUMMARY_PATH_ENV,
    )
    parser.add_argument("--evidence-report", default=DEFAULT_EVIDENCE_REPORT)
    parser.add_argument("--model-improvement-request-attested", action="store_true")
    parser.add_argument("--legal-approval-attested", action="store_true")
    parser.add_argument("--baa-confirmed-attested", action="store_true")
    parser.add_argument("--consent-notice-attested", action="store_true")
    parser.add_argument("--retention-reviewed", action="store_true")
    parser.add_argument("--revocation-reviewed", action="store_true")
    parser.add_argument("--per-request-attestations-reviewed", action="store_true")
    parser.add_argument("--evidence-ready-attested", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        summary = render_private_env(build_config(args))
    except RenderError as exc:
        print(json.dumps({"error": str(exc), "values_redacted": True}, sort_keys=True))
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
