#!/usr/bin/env python3
"""Audit PHIplan production readiness without exposing approval values."""

from __future__ import annotations

import argparse
import json
import re
import sys
import importlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = REPO_ROOT / "health-ai-medical-billing-medical-corporations-20260414_180528"
REPORT_DIR = REPO_ROOT / "llm-distill" / "evals" / "reports"
DEFAULT_REPORT = REPORT_DIR / "phi_plan_production_readiness_report.json"
DEFAULT_CORPUS_MANIFEST = REPO_ROOT / "llm-distill" / "data" / "corpus" / "manifest.json"
DEFAULT_DISTILLATION_READINESS_REPORT = REPORT_DIR / "distillation_readiness_audit_report.json"
DEFAULT_SYNTHETIC_900_RUN_REPORT = REPORT_DIR / "mlx_finetune_synthetic_900_run_report.json"
DEFAULT_MANUAL_GATE_PACKET_REPORT = REPORT_DIR / "phi_plan_manual_gate_packet_report.json"
DEFAULT_RUNTIME_SUPERVISOR_REPORT = REPORT_DIR / "mlx_runtime_supervisor_report.json"
DEFAULT_VECTOR_BACKEND_REPORT = REPORT_DIR / "retrieval_vector_backend_report.json"
DEFAULT_PRODUCTION_CORPUS_EVIDENCE_REPORT = REPORT_DIR / "production_corpus_evidence_report.json"
DEFAULT_MODEL_IMPROVEMENT_EVIDENCE_REPORT = REPORT_DIR / "model_improvement_evidence_report.json"
DEFAULT_FILE_INGESTION_SURFACE_REPORT = REPORT_DIR / "file_ingestion_surface_audit_report.json"
DEFAULT_PREDICTION_FAIRNESS_EVIDENCE_REPORT = REPORT_DIR / "prediction_fairness_evidence_report.json"
DEFAULT_BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT = (
    REPORT_DIR / "backup_disaster_recovery_evidence_report.json"
)
DEFAULT_DEPENDENCY_SECURITY_EVIDENCE_REPORT = (
    REPORT_DIR / "dependency_security_evidence_report.json"
)
DEFAULT_PRODUCTION_COMPOSE = APP_ROOT / "docker-compose.production.yml"
DEFAULT_MONITORING_MODULE = APP_ROOT / "app" / "api" / "v1" / "monitoring.py"

DEFAULT_SETTINGS = SimpleNamespace(
    LLM_PROVIDER="nvidia_nim",
    CLAIMGUARD_STUDENT_USE_BY_DEFAULT=False,
    CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=False,
    CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE="",
    CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=False,
    CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA=False,
    CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH=False,
    USER_DATA_MODEL_IMPROVEMENT_ENABLED=False,
    USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=False,
    USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=False,
    USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION="",
    USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE="",
    RETRIEVAL_EMBEDDING_BACKEND="hash",
    RETRIEVAL_EMBEDDING_MODEL="claimguard-hash-embedding-v1",
    RETRIEVAL_EMBEDDING_MODEL_APPROVED=False,
    RETRIEVAL_VECTOR_BACKEND="encrypted_local_metadata",
    RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=False,
    RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=False,
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import write_source_controlled_report_json  # noqa: E402

PRODUCTION_PAIR_SOURCE_TYPES = {
    "real_deidentified_pair",
    "real_world_deidentified_pair",
    "public_government_deidentified_pair",
    "public_government_denial_appeal_pair",
    "approved_public_denial_appeal_pair",
}
TRAINING_ALLOWED_REVIEW_STATUSES = {"privacy_review_passed", "training_approved"}
TRAINING_ALLOWED_PHI_STATUSES = {"no_phi", "deidentified"}
REQUIRED_PAIR_ROLES = {"denial_letter", "appeal_letter"}
HASH_EMBEDDING_BACKENDS = {"hash", "local_hash", "deterministic_hash"}
HASH_EMBEDDING_MODEL = "claimguard-hash-embedding-v1"
LOCAL_VECTOR_BACKENDS = {
    "encrypted_local_metadata",
    "local_encrypted_metadata",
    "local_metadata",
}
REQUIRED_PRODUCTION_COMPOSE_GUARD_DEFAULTS = {
    "CLAIMGUARD_STUDENT_USE_BY_DEFAULT": "false",
    "CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED": "false",
    "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE": "",
    "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED": "false",
    "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA": "true",
    "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH": "false",
    "USER_DATA_MODEL_IMPROVEMENT_ENABLED": "false",
    "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED": "false",
    "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED": "false",
    "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION": "",
    "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE": "",
    "USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT": (
        "llm-distill/evals/reports/model_improvement_evidence_report.json"
    ),
    "PREDICTION_FAIRNESS_EVIDENCE_REPORT": (
        "llm-distill/evals/reports/prediction_fairness_evidence_report.json"
    ),
    "RETRIEVAL_EMBEDDING_BACKEND": "hash",
    "RETRIEVAL_EMBEDDING_MODEL": HASH_EMBEDDING_MODEL,
    "RETRIEVAL_EMBEDDING_MODEL_APPROVED": "false",
    "RETRIEVAL_VECTOR_BACKEND": "encrypted_local_metadata",
    "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED": "false",
    "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION": "false",
}
FORBIDDEN_PRODUCTION_COMPOSE_GUARD_ENV_VARS = {
    "CLAIMGUARD_ALLOW_MODEL_IMPROVEMENT",
}
REQUIRED_MONITORING_GATE_METRICS = {
    "claimguard_student_default_enabled",
    "claimguard_student_auto_launch_requested",
    "claimguard_student_cutover_approved",
    "claimguard_student_approval_reference_configured",
    "claimguard_student_runtime_supervised",
    "claimguard_student_rollback_to_nvidia_enabled",
    "claimguard_model_improvement_enabled",
    "claimguard_model_improvement_legal_approved",
    "claimguard_model_improvement_baa_confirmed",
    "claimguard_model_improvement_consent_notice_configured",
    "claimguard_model_improvement_approval_reference_configured",
    "claimguard_prediction_fairness_evidence_report_configured",
    "claimguard_retrieval_semantic_backend_configured",
    "claimguard_retrieval_embedding_model_approved",
    "claimguard_retrieval_hash_fallback_disabled_for_production",
    "claimguard_retrieval_hash_embedding_backend_active",
    "claimguard_conservative_runtime_defaults",
    "claimguard_prometheus_no_phi_context",
}
MONITORING_RUNTIME_SENTINELS = {
    "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE": (
        "synthetic-student-reference-not-for-metrics"
    ),
    "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION": (
        "synthetic-consent-version-not-for-metrics"
    ),
    "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE": (
        "synthetic-model-reference-not-for-metrics"
    ),
    "PREDICTION_FAIRNESS_EVIDENCE_REPORT": (
        "/private/tmp/synthetic-fairness-report-not-for-metrics.json"
    ),
}
REQUIRED_MONITORING_READINESS_ENDPOINT_MARKERS = {
    '@router.get("/phi-plan-readiness")',
    "_safe_phi_plan_readiness_payload",
    "blocked_requirement_ids",
    "ready_requirement_ids",
    "raw_report_paths_included",
    "raw_evidence_included",
    "raw_approval_or_reference_values_included",
}
MONITORING_READINESS_RUNTIME_SENTINELS = {
    "raw_report_path": "/private/tmp/synthetic-readiness-report-not-for-endpoint.json",
    "raw_approval_reference": "synthetic-approval-reference-not-for-endpoint",
    "raw_evidence_value": "synthetic-raw-evidence-not-for-endpoint",
}
PRIVATE_OR_EXTERNAL_BLOCKER_REQUIREMENT_IDS = {
    "manual_production_gate_packet_evidence",
    "student_default_cutover_external_approval",
    "user_data_model_improvement_external_approval",
    "production_semantic_vector_backend",
    "production_corpus_expansion_beyond_synthetic",
    "production_prediction_fairness_monitoring",
    "backup_disaster_recovery_evidence",
    "dependency_security_evidence",
}
SOURCE_CONTROL_READY_REQUIREMENT_IDS = {
    "current_runtime_default_safe",
    "production_compose_startup_guard_env",
    "file_ingestion_surface_audit_ready",
    "monitoring_gate_metrics_ready",
    "monitoring_readiness_endpoint_ready",
    "external_phi_service_guard",
}
COMPOSE_ENV_INTERPOLATION_RE = re.compile(
    r"^\$\{(?P<name>[A-Z0-9_]+)(?::-(?P<default>.*))?\}$"
)
PROMETHEUS_METRIC_RE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)\s+[-+]?\d", re.MULTILINE)
EXTERNAL_PATH_REDACTION = "external_path_redacted"


def safe_report_path(path: Path | None) -> str | None:
    if path is None:
        return None
    resolved_path = path.expanduser().resolve()
    try:
        return resolved_path.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return EXTERNAL_PATH_REDACTION


def load_runtime_settings() -> Any:
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))
    try:
        from app.core.config import settings
    except Exception:
        return DEFAULT_SETTINGS
    return settings


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing file: {safe_report_path(path)}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {safe_report_path(path)}: {exc}"]


def attr_bool(settings_like: Any, name: str, default: bool = False) -> bool:
    return bool(getattr(settings_like, name, default))


def attr_str(settings_like: Any, name: str, default: str = "") -> str:
    value = getattr(settings_like, name, default)
    if value is None:
        return ""
    return str(value)


def configured(value: str) -> bool:
    return bool(value.strip())


def looks_like_url_or_secret_bearing_backend(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and (parsed.netloc or parsed.path))


def requirement(
    *,
    requirement_id: str,
    name: str,
    status: str,
    evidence: dict[str, Any],
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "name": name,
        "status": status,
        "blockers": blockers or [],
        "warnings": warnings or [],
        "evidence": evidence,
    }


def parse_production_compose_api_environment(
    compose_path: Path,
) -> tuple[dict[str, str], list[str]]:
    if not compose_path.exists():
        return {}, [f"production compose file not found: {compose_path}"]
    values: dict[str, str] = {}
    in_api = False
    in_environment = False
    for line in compose_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("  api:"):
            in_api = True
            continue
        if in_api and line.startswith("  frontend:"):
            break
        if in_api and line.strip() == "environment:":
            in_environment = True
            continue
        if in_environment and re.match(r"^    [a-z_]+:", line):
            break
        if not in_environment:
            continue
        match = re.match(r"^\s{6}([A-Z0-9_]+):\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip()

    errors: list[str] = []
    if not in_api:
        errors.append("production_compose_api_service_not_found")
    if not in_environment:
        errors.append("production_compose_api_environment_not_found")
    return values, errors


def production_compose_startup_guard_env_requirement(compose_path: Path) -> dict[str, Any]:
    env_values, errors = parse_production_compose_api_environment(compose_path)
    required_names = set(REQUIRED_PRODUCTION_COMPOSE_GUARD_DEFAULTS)
    missing_names = sorted(required_names - set(env_values))
    forbidden_names = sorted(
        set(env_values).intersection(FORBIDDEN_PRODUCTION_COMPOSE_GUARD_ENV_VARS)
    )
    wrong_reference_names: list[str] = []
    unsafe_default_names: list[str] = []
    for name, expected_default in REQUIRED_PRODUCTION_COMPOSE_GUARD_DEFAULTS.items():
        raw_value = env_values.get(name)
        if raw_value is None:
            continue
        match = COMPOSE_ENV_INTERPOLATION_RE.match(raw_value)
        if match is None or match.group("name") != name:
            wrong_reference_names.append(name)
            continue
        actual_default = match.group("default") if match.group("default") is not None else ""
        if actual_default != expected_default:
            unsafe_default_names.append(name)

    blockers = list(errors)
    if missing_names:
        blockers.append("production_compose_missing_startup_guard_env_vars")
    if forbidden_names:
        blockers.append("production_compose_has_unconsumed_guard_aliases")
    if wrong_reference_names:
        blockers.append("production_compose_guard_env_not_self_referenced")
    if unsafe_default_names:
        blockers.append("production_compose_guard_env_defaults_not_conservative")

    return requirement(
        requirement_id="production_compose_startup_guard_env",
        name="Production compose forwards startup guard settings with conservative defaults",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "compose_path": safe_report_path(compose_path),
            "api_environment_found": bool(env_values),
            "required_guard_env_var_count": len(required_names),
            "configured_guard_env_var_count": len(required_names - set(missing_names)),
            "missing_guard_env_vars": missing_names,
            "forbidden_guard_env_vars": forbidden_names,
            "non_self_referenced_guard_env_vars": wrong_reference_names,
            "non_conservative_default_guard_env_vars": unsafe_default_names,
            "raw_env_values_included": False,
            "raw_secrets_included": False,
            "approval_reference_values_included": False,
        },
    )


def metric_names_from_prometheus_text(metrics_text: str) -> set[str]:
    return {match.group(1) for match in PROMETHEUS_METRIC_RE.finditer(metrics_text)}


class _FakePrometheusQuery:
    def filter(self, *args: Any, **kwargs: Any) -> "_FakePrometheusQuery":
        _ = args, kwargs
        return self

    def scalar(self) -> int:
        return 0


class _FakePrometheusSession:
    def query(self, *args: Any, **kwargs: Any) -> _FakePrometheusQuery:
        _ = args, kwargs
        return _FakePrometheusQuery()


def monitoring_gate_metrics_requirement(monitoring_module_path: Path) -> dict[str, Any]:
    blockers: list[str] = []
    metric_names_in_source: set[str] = set()
    runtime_metric_names: set[str] = set()
    runtime_check_performed = False
    runtime_error_type: str | None = None
    raw_sentinel_values_included = False

    if not monitoring_module_path.exists():
        blockers.append("monitoring_metrics_module_missing")
    else:
        source = monitoring_module_path.read_text(encoding="utf-8")
        metric_names_in_source = {
            metric_name
            for metric_name in REQUIRED_MONITORING_GATE_METRICS
            if metric_name in source
        }

    missing_source_metrics = sorted(
        REQUIRED_MONITORING_GATE_METRICS - metric_names_in_source
    )
    if missing_source_metrics:
        blockers.append("monitoring_gate_metrics_missing_from_source")

    if monitoring_module_path.resolve() == DEFAULT_MONITORING_MODULE.resolve():
        runtime_check_performed = True
        if str(APP_ROOT) not in sys.path:
            sys.path.insert(0, str(APP_ROOT))
        try:
            monitoring_module = importlib.import_module("app.api.v1.monitoring")
            monitoring_settings = monitoring_module.settings
            original_values = {
                name: getattr(monitoring_settings, name, None)
                for name in MONITORING_RUNTIME_SENTINELS
            }
            try:
                for name, value in MONITORING_RUNTIME_SENTINELS.items():
                    setattr(monitoring_settings, name, value)
                metrics_text = monitoring_module.build_prometheus_metrics(
                    _FakePrometheusSession()
                )
            finally:
                for name, value in original_values.items():
                    setattr(monitoring_settings, name, value)
            runtime_metric_names = metric_names_from_prometheus_text(metrics_text)
            raw_sentinel_values_included = any(
                value in metrics_text for value in MONITORING_RUNTIME_SENTINELS.values()
            )
        except Exception as exc:  # pragma: no cover - defensive production audit path
            runtime_error_type = type(exc).__name__
            blockers.append("monitoring_gate_metrics_runtime_check_failed")

    missing_runtime_metrics = sorted(
        REQUIRED_MONITORING_GATE_METRICS - runtime_metric_names
    )
    if runtime_check_performed and runtime_error_type is None and missing_runtime_metrics:
        blockers.append("monitoring_gate_metrics_missing_from_runtime_output")
    if raw_sentinel_values_included:
        blockers.append("monitoring_gate_metrics_emit_raw_values")

    return requirement(
        requirement_id="monitoring_gate_metrics_ready",
        name="Admin Prometheus metrics expose PHIplan gate state without raw values",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "monitoring_module_path": safe_report_path(monitoring_module_path),
            "required_metric_count": len(REQUIRED_MONITORING_GATE_METRICS),
            "source_metric_count": len(metric_names_in_source),
            "runtime_metric_count": len(runtime_metric_names),
            "missing_source_metrics": missing_source_metrics,
            "missing_runtime_metrics": missing_runtime_metrics
            if runtime_check_performed
            else [],
            "runtime_check_performed": runtime_check_performed,
            "runtime_error_type": runtime_error_type,
            "raw_approval_or_report_values_included": raw_sentinel_values_included,
            "raw_phi_included": False,
            "raw_document_text_included": False,
            "raw_secret_included": False,
            "raw_metric_output_included": False,
        },
    )


def monitoring_readiness_endpoint_requirement(
    monitoring_module_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    source_markers_present: set[str] = set()
    runtime_check_performed = False
    runtime_error_type: str | None = None
    missing_payload_keys: list[str] = []
    unsafe_safe_context_flags: list[str] = []
    raw_sentinel_values_included = False
    required_payload_keys = {
        "report_available",
        "status",
        "safe_current_state",
        "production_ready",
        "blocked_item_count",
        "warning_item_count",
        "blocked_requirement_ids",
        "warning_requirement_ids",
        "ready_requirement_ids",
        "blocked_items",
        "warning_items",
        "safe_context",
    }
    required_safe_context_false_flags = {
        "raw_report_paths_included",
        "raw_evidence_included",
        "raw_approval_or_reference_values_included",
        "raw_phi_included",
        "raw_document_text_included",
        "raw_secret_included",
    }

    if not monitoring_module_path.exists():
        blockers.append("monitoring_readiness_endpoint_module_missing")
    else:
        source = monitoring_module_path.read_text(encoding="utf-8")
        source_markers_present = {
            marker
            for marker in REQUIRED_MONITORING_READINESS_ENDPOINT_MARKERS
            if marker in source
        }

    missing_source_markers = sorted(
        REQUIRED_MONITORING_READINESS_ENDPOINT_MARKERS - source_markers_present
    )
    if missing_source_markers:
        blockers.append("monitoring_readiness_endpoint_missing_from_source")

    if monitoring_module_path.resolve() == DEFAULT_MONITORING_MODULE.resolve():
        runtime_check_performed = True
        if str(APP_ROOT) not in sys.path:
            sys.path.insert(0, str(APP_ROOT))
        try:
            monitoring_module = importlib.import_module("app.api.v1.monitoring")
            payload_builder = getattr(
                monitoring_module,
                "_safe_phi_plan_readiness_payload",
            )
            with tempfile.TemporaryDirectory(
                prefix="claimguard_phi_plan_readiness_"
            ) as tmp_dir:
                readiness_report_path = Path(tmp_dir) / "readiness.json"
                readiness_report_path.write_text(
                    json.dumps(
                        {
                            "safe_current_state": True,
                            "production_ready": False,
                            "blocked_items": [
                                {
                                    "requirement_id": "manual_production_gate_packet_evidence",
                                    "name": (
                                        "Manual gate packet "
                                        + MONITORING_READINESS_RUNTIME_SENTINELS[
                                            "raw_approval_reference"
                                        ]
                                    ),
                                    "status": "blocked",
                                    "blockers": [
                                        "missing file: "
                                        + MONITORING_READINESS_RUNTIME_SENTINELS[
                                            "raw_report_path"
                                        ]
                                    ],
                                    "warnings": [],
                                    "evidence": {
                                        "report_path": MONITORING_READINESS_RUNTIME_SENTINELS[
                                            "raw_report_path"
                                        ],
                                        "approval_reference": (
                                            MONITORING_READINESS_RUNTIME_SENTINELS[
                                                "raw_approval_reference"
                                            ]
                                        ),
                                        "raw_value": MONITORING_READINESS_RUNTIME_SENTINELS[
                                            "raw_evidence_value"
                                        ],
                                    },
                                }
                            ],
                            "warning_items": [],
                            "requirements": [
                                {
                                    "requirement_id": "current_runtime_default_safe",
                                    "name": "Current runtime",
                                    "status": "ready",
                                }
                            ],
                            "next_required_actions": [
                                "Review "
                                + MONITORING_READINESS_RUNTIME_SENTINELS[
                                    "raw_report_path"
                                ]
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                payload = payload_builder(readiness_report_path)
            if not isinstance(payload, dict):
                blockers.append("monitoring_readiness_endpoint_payload_not_object")
                payload = {}
            missing_payload_keys = sorted(required_payload_keys - set(payload))
            safe_context = payload.get("safe_context")
            if not isinstance(safe_context, dict):
                unsafe_safe_context_flags = sorted(required_safe_context_false_flags)
            else:
                unsafe_safe_context_flags = sorted(
                    flag
                    for flag in required_safe_context_false_flags
                    if safe_context.get(flag) is not False
                )
            serialized_payload = json.dumps(payload, sort_keys=True)
            raw_sentinel_values_included = any(
                value in serialized_payload
                for value in MONITORING_READINESS_RUNTIME_SENTINELS.values()
            )
        except Exception as exc:  # pragma: no cover - defensive production audit path
            runtime_error_type = type(exc).__name__
            blockers.append("monitoring_readiness_endpoint_runtime_check_failed")

    if runtime_check_performed and runtime_error_type is None and missing_payload_keys:
        blockers.append("monitoring_readiness_endpoint_missing_payload_keys")
    if runtime_check_performed and runtime_error_type is None and unsafe_safe_context_flags:
        blockers.append("monitoring_readiness_endpoint_unsafe_context_flags")
    if raw_sentinel_values_included:
        blockers.append("monitoring_readiness_endpoint_emits_raw_values")

    return requirement(
        requirement_id="monitoring_readiness_endpoint_ready",
        name="Admin PHIplan readiness endpoint exposes sanitized metadata only",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "monitoring_module_path": safe_report_path(monitoring_module_path),
            "required_source_marker_count": len(REQUIRED_MONITORING_READINESS_ENDPOINT_MARKERS),
            "source_marker_count": len(source_markers_present),
            "missing_source_markers": missing_source_markers,
            "runtime_check_performed": runtime_check_performed,
            "runtime_error_type": runtime_error_type,
            "missing_payload_keys": missing_payload_keys,
            "unsafe_safe_context_flags": unsafe_safe_context_flags,
            "raw_approval_or_report_values_included": raw_sentinel_values_included,
            "raw_phi_included": False,
            "raw_document_text_included": False,
            "raw_secret_included": False,
            "raw_evidence_included": False,
            "raw_report_paths_included": False,
        },
    )


def blocked_requirement_ids_from_report(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    raw_blocked_items = payload.get("blocked_items")
    if not isinstance(raw_blocked_items, list):
        return []
    return sorted(
        {
            str(item.get("requirement_id"))
            for item in raw_blocked_items
            if isinstance(item, dict) and item.get("requirement_id")
        }
    )


def current_runtime_default_requirement(settings_like: Any) -> dict[str, Any]:
    provider = attr_str(settings_like, "LLM_PROVIDER")
    student_default = attr_bool(settings_like, "CLAIMGUARD_STUDENT_USE_BY_DEFAULT")
    blockers: list[str] = []
    if provider != "nvidia_nim":
        blockers.append("llm_provider_not_nvidia_default")

    return requirement(
        requirement_id="current_runtime_default_safe",
        name="Current base runtime remains NVIDIA while student routing is separately gated",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "llm_provider": provider,
            "student_use_by_default": student_default,
            "safe_default_expected_provider": "nvidia_nim",
        },
    )


def student_cutover_requirement(
    settings_like: Any,
    distillation_report_path: Path,
    runtime_supervisor_report_path: Path | None = None,
) -> dict[str, Any]:
    distillation_report, errors = load_json(distillation_report_path)
    distillation_release_ready = False
    if isinstance(distillation_report, dict):
        distillation_release_ready = bool(
            distillation_report.get("release_ready")
            or distillation_report.get("distillation_ready")
        )

    student_use_default = attr_bool(settings_like, "CLAIMGUARD_STUDENT_USE_BY_DEFAULT")
    student_auto_launch = attr_bool(settings_like, "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH")
    cutover_approved = attr_bool(settings_like, "CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED")
    approval_reference_configured = configured(
        attr_str(settings_like, "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE")
    )
    runtime_supervised = attr_bool(settings_like, "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED")
    rollback_to_nvidia = attr_bool(settings_like, "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA")
    supervisor_report_path: str | None = None
    supervisor_safe_to_review: bool | None = None
    supervisor_ready: bool | None = None
    supervisor_blocked_requirement_ids: list[str] = []
    if runtime_supervisor_report_path is not None:
        supervisor_report_path = safe_report_path(runtime_supervisor_report_path)
        supervisor_report, supervisor_errors = load_json(runtime_supervisor_report_path)
        errors.extend(supervisor_errors)
        if isinstance(supervisor_report, dict):
            supervisor_safe_to_review = bool(supervisor_report.get("safe_to_review"))
            supervisor_ready = bool(supervisor_report.get("supervisor_ready"))
            supervisor_blocked_requirement_ids = blocked_requirement_ids_from_report(
                supervisor_report
            )

    blockers = list(errors)
    if not distillation_release_ready:
        blockers.append("distillation_release_evidence_not_ready")
    if not student_use_default:
        blockers.append("student_default_not_requested_or_disabled")
    if not cutover_approved:
        blockers.append("student_cutover_approval_missing")
    if not approval_reference_configured:
        blockers.append("student_cutover_approval_reference_missing")
    if not runtime_supervised:
        blockers.append("student_runtime_supervision_missing")
    if supervisor_ready is False:
        blockers.append("student_runtime_supervisor_report_not_ready")
    if supervisor_safe_to_review is False:
        blockers.append("student_runtime_supervisor_report_not_safe_to_review")
    if rollback_to_nvidia:
        blockers.append("rollback_to_nvidia_flag_enabled")

    return requirement(
        requirement_id="student_default_cutover_external_approval",
        name="Student default cutover has external approval and supervised runtime gates",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "distillation_report_path": safe_report_path(distillation_report_path),
            "distillation_release_ready": distillation_release_ready,
            "student_use_by_default": student_use_default,
            "student_auto_launch_requested": student_auto_launch,
            "cutover_approved": cutover_approved,
            "approval_reference_configured": approval_reference_configured,
            "runtime_supervised": runtime_supervised,
            "runtime_supervisor_report_path": supervisor_report_path,
            "runtime_supervisor_safe_to_review": supervisor_safe_to_review,
            "runtime_supervisor_ready": supervisor_ready,
            "runtime_supervisor_blocked_requirement_ids": supervisor_blocked_requirement_ids,
            "rollback_to_nvidia": rollback_to_nvidia,
        },
    )


def model_improvement_requirement(
    settings_like: Any,
    model_improvement_report_path: Path | None = None,
) -> dict[str, Any]:
    enabled = attr_bool(settings_like, "USER_DATA_MODEL_IMPROVEMENT_ENABLED")
    legal_approved = attr_bool(settings_like, "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED")
    baa_confirmed = attr_bool(settings_like, "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED")
    consent_notice_configured = configured(
        attr_str(settings_like, "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION")
    )
    approval_reference_configured = configured(
        attr_str(settings_like, "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE")
    )
    report_path: str | None = None
    report_safe_to_review: bool | None = None
    report_ready: bool | None = None
    report_blocked_requirement_ids: list[str] = []
    errors: list[str] = []
    if model_improvement_report_path is not None:
        report_path = safe_report_path(model_improvement_report_path)
        model_improvement_report, model_improvement_errors = load_json(model_improvement_report_path)
        errors.extend(model_improvement_errors)
        if isinstance(model_improvement_report, dict):
            report_safe_to_review = bool(model_improvement_report.get("safe_to_review"))
            report_ready = bool(model_improvement_report.get("model_improvement_ready"))
            report_blocked_requirement_ids = blocked_requirement_ids_from_report(
                model_improvement_report
            )

    blockers: list[str] = list(errors)
    if not enabled:
        blockers.append("user_data_model_improvement_disabled")
    if not legal_approved:
        blockers.append("legal_approval_missing")
    if not baa_confirmed:
        blockers.append("baa_confirmation_missing")
    if not consent_notice_configured:
        blockers.append("consent_notice_version_missing")
    if not approval_reference_configured:
        blockers.append("approval_reference_missing")
    if report_ready is False:
        blockers.append("model_improvement_evidence_report_not_ready")
    if report_safe_to_review is False:
        blockers.append("model_improvement_evidence_report_not_safe_to_review")

    return requirement(
        requirement_id="user_data_model_improvement_external_approval",
        name="User-data model improvement has legal, BAA, consent, and approval gates",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "enabled": enabled,
            "legal_approval_confirmed": legal_approved,
            "baa_confirmed": baa_confirmed,
            "consent_notice_version_configured": consent_notice_configured,
            "approval_reference_configured": approval_reference_configured,
            "model_improvement_report_path": report_path,
            "model_improvement_report_safe_to_review": report_safe_to_review,
            "model_improvement_report_ready": report_ready,
            "model_improvement_blocked_requirement_ids": report_blocked_requirement_ids,
        },
    )


def prediction_fairness_monitoring_requirement(
    prediction_fairness_report_path: Path | None = None,
) -> dict[str, Any]:
    report_path: str | None = None
    report_safe_to_review: bool | None = None
    report_ready: bool | None = None
    report_blocked_requirement_ids: list[str] = []
    errors: list[str] = []
    if prediction_fairness_report_path is not None:
        report_path = safe_report_path(prediction_fairness_report_path)
        fairness_report, fairness_errors = load_json(prediction_fairness_report_path)
        errors.extend(fairness_errors)
        if isinstance(fairness_report, dict):
            report_safe_to_review = bool(fairness_report.get("safe_to_review"))
            report_ready = bool(
                fairness_report.get("prediction_fairness_monitoring_ready")
            )
            report_blocked_requirement_ids = blocked_requirement_ids_from_report(
                fairness_report
            )

    blockers: list[str] = list(errors)
    if report_ready is False:
        blockers.append("prediction_fairness_evidence_report_not_ready")
    if report_safe_to_review is False:
        blockers.append("prediction_fairness_evidence_report_not_safe_to_review")

    return requirement(
        requirement_id="production_prediction_fairness_monitoring",
        name="Production threshold calibration and continuous fairness monitoring are ready",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "prediction_fairness_report_path": report_path,
            "prediction_fairness_report_safe_to_review": report_safe_to_review,
            "prediction_fairness_report_ready": report_ready,
            "prediction_fairness_blocked_requirement_ids": report_blocked_requirement_ids,
            "values_redacted": True,
        },
    )


def backup_disaster_recovery_requirement(
    backup_disaster_recovery_report_path: Path | None = DEFAULT_BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT,
) -> dict[str, Any]:
    report_path: str | None = None
    report_safe_to_review: bool | None = None
    report_ready: bool | None = None
    report_blocked_requirement_ids: list[str] = []
    errors: list[str] = []
    if backup_disaster_recovery_report_path is not None:
        report_path = safe_report_path(backup_disaster_recovery_report_path)
        backup_report, backup_errors = load_json(backup_disaster_recovery_report_path)
        errors.extend(backup_errors)
        if isinstance(backup_report, dict):
            report_safe_to_review = bool(backup_report.get("safe_to_review"))
            report_ready = bool(backup_report.get("backup_disaster_recovery_ready"))
            report_blocked_requirement_ids = blocked_requirement_ids_from_report(backup_report)

    blockers: list[str] = list(errors)
    if report_ready is False:
        blockers.append("backup_disaster_recovery_evidence_report_not_ready")
    if report_safe_to_review is False:
        blockers.append("backup_disaster_recovery_evidence_report_not_safe_to_review")

    return requirement(
        requirement_id="backup_disaster_recovery_evidence",
        name="Backup and disaster-recovery evidence is ready",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "backup_disaster_recovery_report_path": report_path,
            "backup_disaster_recovery_report_safe_to_review": report_safe_to_review,
            "backup_disaster_recovery_report_ready": report_ready,
            "backup_disaster_recovery_blocked_requirement_ids": report_blocked_requirement_ids,
            "values_redacted": True,
        },
    )


def dependency_security_requirement(
    dependency_security_report_path: Path | None = DEFAULT_DEPENDENCY_SECURITY_EVIDENCE_REPORT,
) -> dict[str, Any]:
    report_path: str | None = None
    report_safe_to_review: bool | None = None
    report_ready: bool | None = None
    report_blocked_requirement_ids: list[str] = []
    errors: list[str] = []
    if dependency_security_report_path is not None:
        report_path = safe_report_path(dependency_security_report_path)
        dependency_report, dependency_errors = load_json(dependency_security_report_path)
        errors.extend(dependency_errors)
        if isinstance(dependency_report, dict):
            report_safe_to_review = bool(dependency_report.get("safe_to_review"))
            report_ready = bool(dependency_report.get("dependency_security_ready"))
            report_blocked_requirement_ids = blocked_requirement_ids_from_report(dependency_report)

    blockers: list[str] = list(errors)
    if report_ready is False:
        blockers.append("dependency_security_evidence_report_not_ready")
    if report_safe_to_review is False:
        blockers.append("dependency_security_evidence_report_not_safe_to_review")

    return requirement(
        requirement_id="dependency_security_evidence",
        name="Dependency security scan and remediation evidence is ready",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "dependency_security_report_path": report_path,
            "dependency_security_report_safe_to_review": report_safe_to_review,
            "dependency_security_report_ready": report_ready,
            "dependency_security_blocked_requirement_ids": report_blocked_requirement_ids,
            "values_redacted": True,
        },
    )


def vector_backend_requirement(
    settings_like: Any,
    vector_backend_report_path: Path | None = None,
) -> dict[str, Any]:
    embedding_backend = attr_str(settings_like, "RETRIEVAL_EMBEDDING_BACKEND", "hash").strip().lower()
    embedding_model = attr_str(
        settings_like,
        "RETRIEVAL_EMBEDDING_MODEL",
        HASH_EMBEDDING_MODEL,
    ).strip() or HASH_EMBEDDING_MODEL
    embedding_model_approved = attr_bool(
        settings_like,
        "RETRIEVAL_EMBEDDING_MODEL_APPROVED",
    )
    vector_backend_raw = attr_str(
        settings_like,
        "RETRIEVAL_VECTOR_BACKEND",
        "encrypted_local_metadata",
    ).strip()
    vector_backend = vector_backend_raw.lower()
    semantic_backend_configured = attr_bool(
        settings_like,
        "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED",
    )
    hash_fallback_disabled_for_production = attr_bool(
        settings_like,
        "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION",
    )
    vector_backend_has_url_or_credentials = looks_like_url_or_secret_bearing_backend(
        vector_backend_raw
    )
    safe_vector_backend = (
        "redacted_url_or_credentials"
        if vector_backend_has_url_or_credentials
        else vector_backend
    )
    report_path: str | None = None
    report_safe_to_review: bool | None = None
    report_ready: bool | None = None
    report_blocked_requirement_ids: list[str] = []
    errors: list[str] = []
    if vector_backend_report_path is not None:
        report_path = safe_report_path(vector_backend_report_path)
        vector_report, vector_errors = load_json(vector_backend_report_path)
        errors.extend(vector_errors)
        if isinstance(vector_report, dict):
            report_safe_to_review = bool(vector_report.get("safe_to_review"))
            report_ready = bool(vector_report.get("vector_backend_ready"))
            report_blocked_requirement_ids = blocked_requirement_ids_from_report(vector_report)

    blockers: list[str] = list(errors)
    if not semantic_backend_configured:
        blockers.append("semantic_embedding_backend_not_configured")
    if embedding_backend in HASH_EMBEDDING_BACKENDS or embedding_model == HASH_EMBEDDING_MODEL:
        blockers.append("hash_embedding_backend_is_fallback_only")
    if not embedding_model_approved:
        blockers.append("embedding_model_not_approved_for_production")
    if vector_backend in LOCAL_VECTOR_BACKENDS:
        blockers.append("production_vector_backend_not_configured")
    if not hash_fallback_disabled_for_production:
        blockers.append("hash_fallback_not_disabled_for_production")
    if vector_backend_has_url_or_credentials:
        blockers.append("vector_backend_setting_must_not_store_url_or_credentials")
    if report_ready is False:
        blockers.append("retrieval_vector_backend_report_not_ready")
    if report_safe_to_review is False:
        blockers.append("retrieval_vector_backend_report_not_safe_to_review")

    return requirement(
        requirement_id="production_semantic_vector_backend",
        name="Production semantic embeddings and vector backend are configured",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "embedding_backend": embedding_backend,
            "embedding_model": embedding_model,
            "embedding_model_approved": embedding_model_approved,
            "vector_backend": safe_vector_backend,
            "vector_backend_has_url_or_credentials": vector_backend_has_url_or_credentials,
            "semantic_backend_configured": semantic_backend_configured,
            "hash_fallback_disabled_for_production": hash_fallback_disabled_for_production,
            "hash_fallback_configured": (
                embedding_backend in HASH_EMBEDDING_BACKENDS
                or embedding_model == HASH_EMBEDDING_MODEL
            ),
            "vector_backend_report_path": report_path,
            "vector_backend_report_safe_to_review": report_safe_to_review,
            "vector_backend_report_ready": report_ready,
            "vector_backend_blocked_requirement_ids": report_blocked_requirement_ids,
        },
    )


def is_training_pair_candidate(record: dict[str, Any]) -> bool:
    source_type = str(record.get("source_type") or "")
    if source_type not in PRODUCTION_PAIR_SOURCE_TYPES:
        return False
    return (
        bool(record.get("training_eligible"))
        and str(record.get("document_role") or "") in REQUIRED_PAIR_ROLES
        and str(record.get("phi_status") or "") in TRAINING_ALLOWED_PHI_STATUSES
        and str(record.get("review_status") or "") in TRAINING_ALLOWED_REVIEW_STATUSES
        and bool(record.get("pair_id"))
    )


def production_corpus_requirement(
    corpus_manifest_path: Path,
    min_production_pairs: int = 1,
    production_corpus_report_path: Path | None = None,
) -> dict[str, Any]:
    payload, errors = load_json(corpus_manifest_path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    blockers = list(errors)
    report_path: str | None = None
    report_safe_to_review: bool | None = None
    report_ready: bool | None = None
    report_blocked_requirement_ids: list[str] = []
    if production_corpus_report_path is not None:
        report_path = safe_report_path(production_corpus_report_path)
        corpus_report, corpus_errors = load_json(production_corpus_report_path)
        blockers.extend(corpus_errors)
        if isinstance(corpus_report, dict):
            report_safe_to_review = bool(corpus_report.get("safe_to_review"))
            report_ready = bool(corpus_report.get("production_corpus_ready"))
            report_blocked_requirement_ids = blocked_requirement_ids_from_report(corpus_report)
    if not isinstance(records, list):
        records = []
        blockers.append("manifest_records_not_list")

    counts_by_source_type: dict[str, int] = {}
    training_source_types: dict[str, int] = {}
    production_pair_roles: dict[str, set[str]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        source_type = str(record.get("source_type") or "unknown")
        counts_by_source_type[source_type] = counts_by_source_type.get(source_type, 0) + 1
        if record.get("training_eligible"):
            training_source_types[source_type] = training_source_types.get(source_type, 0) + 1
        if is_training_pair_candidate(record):
            pair_id = str(record["pair_id"])
            production_pair_roles.setdefault(pair_id, set()).add(str(record.get("document_role")))

    complete_production_pair_ids = sorted(
        pair_id
        for pair_id, roles in production_pair_roles.items()
        if REQUIRED_PAIR_ROLES.issubset(roles)
    )
    if len(complete_production_pair_ids) < min_production_pairs:
        blockers.append("production_training_corpus_has_only_synthetic_or_unpaired_records")
    if report_ready is False:
        blockers.append("production_corpus_evidence_report_not_ready")
    if report_safe_to_review is False:
        blockers.append("production_corpus_evidence_report_not_safe_to_review")

    return requirement(
        requirement_id="production_corpus_expansion_beyond_synthetic",
        name="Production corpus includes non-synthetic approved denial/appeal training pairs",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "manifest_path": safe_report_path(corpus_manifest_path),
            "record_count": len(records),
            "counts_by_source_type": counts_by_source_type,
            "training_source_types": training_source_types,
            "accepted_production_source_types": sorted(PRODUCTION_PAIR_SOURCE_TYPES),
            "complete_production_pair_count": len(complete_production_pair_ids),
            "complete_production_pair_ids": complete_production_pair_ids,
            "minimum_required_production_pair_count": min_production_pairs,
            "production_corpus_report_path": report_path,
            "production_corpus_report_safe_to_review": report_safe_to_review,
            "production_corpus_report_ready": report_ready,
            "production_corpus_blocked_requirement_ids": report_blocked_requirement_ids,
        },
    )


def synthetic_900_adapter_requirement(run_report_path: Path) -> dict[str, Any]:
    payload, errors = load_json(run_report_path)
    warnings = list(errors)
    evidence: dict[str, Any] = {"run_report_path": safe_report_path(run_report_path)}
    if isinstance(payload, dict):
        blocked_reasons = [
            str(reason) for reason in payload.get("blocked_reasons", []) if str(reason).strip()
        ]
        data_ready = bool(payload.get("checks", {}).get("data", {}).get("ready"))
        manifest_ready = bool(payload.get("checks", {}).get("manifest", {}).get("ready"))
        training_succeeded = payload.get("training_succeeded")
        training_attempted = bool(payload.get("training_attempted"))
        no_metal = any("Metal device" in reason for reason in blocked_reasons)
        if training_succeeded is not True:
            if no_metal:
                warnings.append("synthetic_900_training_not_run_no_metal_device")
            else:
                warnings.append("synthetic_900_adapter_training_not_successful")
        evidence.update(
            {
                "data_ready": data_ready,
                "manifest_ready": manifest_ready,
                "training_attempted": training_attempted,
                "training_succeeded": training_succeeded,
                "blocked_reasons": blocked_reasons,
                "no_metal_device": no_metal,
                "adapter_written": bool(
                    payload.get("checks", {})
                    .get("adapter_output", {})
                    .get("exists_after_run")
                ),
            }
        )
    else:
        warnings.append("synthetic_900_run_report_unreadable")

    return requirement(
        requirement_id="synthetic_900_adapter_training_status",
        name="Synthetic-900 adapter training evidence is current",
        status="warning" if warnings else "ready",
        warnings=warnings,
        evidence=evidence,
    )


def external_phi_service_guard_requirement(settings_like: Any) -> dict[str, Any]:
    model_improvement_enabled = attr_bool(settings_like, "USER_DATA_MODEL_IMPROVEMENT_ENABLED")
    return requirement(
        requirement_id="external_phi_service_guard",
        name="No independent external PHI de-identification service is enabled by default",
        status="ready",
        evidence={
            "user_data_model_improvement_enabled": model_improvement_enabled,
            "external_deidentification_service_configured": False,
            "raw_phi_training_allowed": False,
        },
    )


def manual_gate_packet_requirement(packet_report_path: Path) -> dict[str, Any]:
    payload, errors = load_json(packet_report_path)
    blockers = list(errors)
    safe_to_review = False
    production_gate_ready = False
    blocked_item_count: int | None = None
    blocked_requirement_ids: list[str] = []
    if isinstance(payload, dict):
        safe_to_review = bool(payload.get("safe_to_review"))
        production_gate_ready = bool(payload.get("production_gate_ready"))
        raw_blocked_count = payload.get("blocked_item_count")
        blocked_item_count = raw_blocked_count if isinstance(raw_blocked_count, int) else None
        blocked_requirement_ids = blocked_requirement_ids_from_report(payload)
    if not safe_to_review:
        blockers.append("manual_gate_packet_not_safe_to_review")
    if not production_gate_ready:
        blockers.append("manual_gate_packet_production_gates_not_ready")

    return requirement(
        requirement_id="manual_production_gate_packet_evidence",
        name="Manual PHIplan production-gate packet is safe and production-ready",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "packet_report_path": safe_report_path(packet_report_path),
            "safe_to_review": safe_to_review,
            "production_gate_ready": production_gate_ready,
            "blocked_item_count": blocked_item_count,
            "blocked_requirement_ids": blocked_requirement_ids,
        },
    )


def file_ingestion_surface_requirement(surface_report_path: Path) -> dict[str, Any]:
    payload, errors = load_json(surface_report_path)
    blockers = list(errors)
    ready = False
    summary: dict[str, Any] = {}
    blocked_reasons: list[str] = []
    if isinstance(payload, dict):
        ready = payload.get("ready") is True
        raw_summary = payload.get("summary")
        summary = raw_summary if isinstance(raw_summary, dict) else {}
        blocked_reasons = [
            reason
            for reason in payload.get("blocked_reasons", [])
            if isinstance(reason, str)
        ]
        if not ready:
            blockers.append("file_ingestion_surface_audit_not_ready")
        blockers.extend(blocked_reasons)
    else:
        blockers.append("file_ingestion_surface_audit_report_not_json")

    return requirement(
        requirement_id="file_ingestion_surface_audit_ready",
        name="Automated file-ingestion endpoints have PHI surface and governance coverage",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "surface_report_path": safe_report_path(surface_report_path),
            "ready": ready,
            "summary": summary,
            "blocked_reasons": blocked_reasons,
            "values_redacted": True,
        },
    )


def build_next_required_actions(requirements: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    blocked_ids = {item["requirement_id"] for item in requirements if item["status"] == "blocked"}
    warning_ids = {item["requirement_id"] for item in requirements if item["status"] == "warning"}
    if "manual_production_gate_packet_evidence" in blocked_ids:
        actions.append(
            "Complete llm-distill/data/production_gate_evidence/manual_gate_packet.template.json "
            "with boolean-only evidence for student cutover, user-data model improvement, "
            "production corpus, retrieval-vector backend, and prediction fairness monitoring gates; validate it with "
            "validate_phi_plan_manual_gate_packet.py, and keep approval references outside source control."
        )
    if "student_default_cutover_external_approval" in blocked_ids:
        actions.append(
            "Keep CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false until Raphael approves cutover, "
            "a non-secret approval reference is configured, supervised MLX runtime evidence "
            "is present via validate_mlx_runtime_supervisor.py, rollback-to-NVIDIA is not enabled, "
            "and distillation evidence remains ready."
        )
    if "user_data_model_improvement_external_approval" in blocked_ids:
        actions.append(
            "Keep user-data model improvement disabled until legal approval, BAA confirmation, "
            "consent notice version, approval reference, per-request attestations, and "
            "boolean-only evidence from validate_model_improvement_evidence.py are complete."
        )
    if "production_semantic_vector_backend" in blocked_ids:
        actions.append(
            "Configure a production semantic embedding backend and vector store, then reindex retrieval/corpus chunks "
            "and validate boolean-only evidence with validate_retrieval_vector_backend.py before treating retrieval "
            "as production semantic search."
        )
    if "production_corpus_expansion_beyond_synthetic" in blocked_ids:
        actions.append(
            "Add approved non-synthetic denial/appeal training pairs only after public/government "
            "licensing or Raphael-approved de-identification review is complete, then validate "
            "boolean-only evidence with validate_production_corpus_evidence.py."
        )
    if "production_prediction_fairness_monitoring" in blocked_ids:
        actions.append(
            "Keep production threshold calibration and continuous fairness monitoring blocked until "
            "approved real-world outcome data, minimum sample size, threshold review, demographic "
            "grouping review, monitoring ownership, latest run evidence, legal/privacy review, "
            "and boolean-only evidence from validate_prediction_fairness_evidence.py are complete."
        )
    if "backup_disaster_recovery_evidence" in blocked_ids:
        actions.append(
            "Keep PHIplan production readiness blocked until off-repository encrypted backup storage, "
            "metadata-only restore verification, encryption-key recovery, retention approval, disaster-recovery "
            "smoke evidence, and boolean-only evidence from validate_backup_disaster_recovery_evidence.py are complete."
        )
    if "dependency_security_evidence" in blocked_ids:
        actions.append(
            "Keep PHIplan production readiness blocked until Python, frontend, and container dependency scans, "
            "critical/high finding remediation or private approval, rebuild/retest evidence, and boolean-only evidence "
            "from validate_dependency_security_evidence.py are complete."
        )
    if "file_ingestion_surface_audit_ready" in blocked_ids:
        actions.append(
            "Run llm-distill/scripts/audit_file_ingestion_surfaces.py and keep every UploadFile/File "
            "endpoint registered with metadata-only PHI surface inspection, governance, and safe audit markers."
        )
    if "production_compose_startup_guard_env" in blocked_ids:
        actions.append(
            "Fix health-ai-medical-billing-medical-corporations-20260414_180528/docker-compose.production.yml "
            "so the API service forwards the exact startup guard environment variables consumed by app/core/config.py "
            "with conservative defaults and no unconsumed aliases."
        )
    if "monitoring_gate_metrics_ready" in blocked_ids:
        actions.append(
            "Restore /api/v1/monitoring/metrics coverage for boolean-only PHIplan gate metrics "
            "without emitting approval references, report paths, PHI, secrets, source text, vectors, or raw documents."
        )
    if "monitoring_readiness_endpoint_ready" in blocked_ids:
        actions.append(
            "Restore /api/v1/monitoring/phi-plan-readiness coverage for sanitized PHIplan "
            "readiness counts, requirement IDs, and blocker tokens without emitting raw report "
            "paths, evidence, approval references, PHI, secrets, source text, vectors, or raw documents."
        )
    if "synthetic_900_adapter_training_status" in warning_ids:
        actions.append(
            "Rerun the guarded synthetic-900 MLX LoRA command from a local macOS session with Metal access "
            "before promoting a synthetic-900 adapter."
        )
    if not actions:
        actions.append("Keep PHIplan production evidence current before enabling production defaults.")
    return actions


def build_completion_audit(
    requirements: list[dict[str, Any]],
    *,
    safe_current_state: bool,
    production_ready: bool,
) -> dict[str, Any]:
    ready_requirement_ids = sorted(
        item["requirement_id"]
        for item in requirements
        if item["status"] == "ready"
    )
    blocked_requirement_ids = sorted(
        item["requirement_id"]
        for item in requirements
        if item["status"] == "blocked"
    )
    warning_requirement_ids = sorted(
        item["requirement_id"]
        for item in requirements
        if item["status"] == "warning"
    )
    private_or_external_blocker_ids = sorted(
        requirement_id
        for requirement_id in blocked_requirement_ids
        if requirement_id in PRIVATE_OR_EXTERNAL_BLOCKER_REQUIREMENT_IDS
    )
    source_control_ready_requirement_ids = sorted(
        requirement_id
        for requirement_id in ready_requirement_ids
        if requirement_id in SOURCE_CONTROL_READY_REQUIREMENT_IDS
    )
    completion_proven = production_ready and not blocked_requirement_ids
    completion_status = (
        "complete"
        if completion_proven
        else "not_complete_private_or_external_evidence_required"
        if private_or_external_blocker_ids
        else "not_complete_source_control_requirements_blocked"
    )
    non_completion_reason = (
        None
        if completion_proven
        else (
            "PHIplan production readiness is blocked by private/manual or external "
            "production evidence that must remain outside source control."
            if private_or_external_blocker_ids
            else "PHIplan production readiness has source-controlled blockers."
        )
    )
    return {
        "artifact": "phi_plan_completion_audit_matrix",
        "schema_version": "1.0",
        "completion_proven": completion_proven,
        "completion_status": completion_status,
        "non_completion_reason": non_completion_reason,
        "safe_current_state": safe_current_state,
        "production_ready": production_ready,
        "total_requirement_count": len(requirements),
        "ready_requirement_count": len(ready_requirement_ids),
        "blocked_requirement_count": len(blocked_requirement_ids),
        "warning_requirement_count": len(warning_requirement_ids),
        "ready_requirement_ids": ready_requirement_ids,
        "blocked_requirement_ids": blocked_requirement_ids,
        "warning_requirement_ids": warning_requirement_ids,
        "private_or_external_blocker_ids": private_or_external_blocker_ids,
        "private_or_external_blocker_count": len(private_or_external_blocker_ids),
        "source_control_ready_requirement_ids": source_control_ready_requirement_ids,
        "source_control_ready_requirement_count": len(source_control_ready_requirement_ids),
        "source_control_ready_expected_ids": sorted(SOURCE_CONTROL_READY_REQUIREMENT_IDS),
        "raw_approval_values_included": False,
        "raw_evidence_values_included": False,
        "raw_report_paths_included": False,
        "raw_phi_or_secret_values_included": False,
    }


def build_report(
    *,
    settings_like: Any,
    corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST,
    distillation_report_path: Path = DEFAULT_DISTILLATION_READINESS_REPORT,
    synthetic_900_run_report_path: Path = DEFAULT_SYNTHETIC_900_RUN_REPORT,
    manual_gate_packet_report_path: Path = DEFAULT_MANUAL_GATE_PACKET_REPORT,
    runtime_supervisor_report_path: Path | None = None,
    vector_backend_report_path: Path | None = None,
    production_corpus_report_path: Path | None = None,
    model_improvement_report_path: Path | None = None,
    file_ingestion_surface_report_path: Path = DEFAULT_FILE_INGESTION_SURFACE_REPORT,
    prediction_fairness_report_path: Path | None = DEFAULT_PREDICTION_FAIRNESS_EVIDENCE_REPORT,
    backup_disaster_recovery_report_path: Path | None = DEFAULT_BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT,
    dependency_security_report_path: Path | None = DEFAULT_DEPENDENCY_SECURITY_EVIDENCE_REPORT,
    production_compose_path: Path = DEFAULT_PRODUCTION_COMPOSE,
    monitoring_module_path: Path = DEFAULT_MONITORING_MODULE,
) -> dict[str, Any]:
    requirements = [
        current_runtime_default_requirement(settings_like),
        production_compose_startup_guard_env_requirement(production_compose_path),
        file_ingestion_surface_requirement(file_ingestion_surface_report_path),
        monitoring_gate_metrics_requirement(monitoring_module_path),
        monitoring_readiness_endpoint_requirement(monitoring_module_path),
        manual_gate_packet_requirement(manual_gate_packet_report_path),
        student_cutover_requirement(
            settings_like,
            distillation_report_path,
            runtime_supervisor_report_path,
        ),
        model_improvement_requirement(settings_like, model_improvement_report_path),
        vector_backend_requirement(settings_like, vector_backend_report_path),
        production_corpus_requirement(
            corpus_manifest_path,
            production_corpus_report_path=production_corpus_report_path,
        ),
        prediction_fairness_monitoring_requirement(prediction_fairness_report_path),
        backup_disaster_recovery_requirement(backup_disaster_recovery_report_path),
        dependency_security_requirement(dependency_security_report_path),
        synthetic_900_adapter_requirement(synthetic_900_run_report_path),
        external_phi_service_guard_requirement(settings_like),
    ]
    blocked_items = [item for item in requirements if item["status"] == "blocked"]
    warning_items = [item for item in requirements if item["status"] == "warning"]

    student_default_requested = attr_bool(settings_like, "CLAIMGUARD_STUDENT_USE_BY_DEFAULT")
    student_auto_launch_requested = attr_bool(settings_like, "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH")
    model_improvement_enabled = attr_bool(settings_like, "USER_DATA_MODEL_IMPROVEMENT_ENABLED")
    student_cutover_ready = not any(
        item["requirement_id"] == "student_default_cutover_external_approval"
        and item["status"] == "blocked"
        for item in requirements
    )
    model_improvement_ready = not any(
        item["requirement_id"] == "user_data_model_improvement_external_approval"
        and item["status"] == "blocked"
        for item in requirements
    )
    runtime_safe = not any(
        item["requirement_id"] == "current_runtime_default_safe"
        and item["status"] == "blocked"
        for item in requirements
    )
    external_phi_guard_safe = not any(
        item["requirement_id"] == "external_phi_service_guard"
        and item["status"] == "blocked"
        for item in requirements
    )
    file_ingestion_surface_safe = not any(
        item["requirement_id"] == "file_ingestion_surface_audit_ready"
        and item["status"] == "blocked"
        for item in requirements
    )
    production_compose_safe = not any(
        item["requirement_id"] == "production_compose_startup_guard_env"
        and item["status"] == "blocked"
        for item in requirements
    )
    monitoring_metrics_safe = not any(
        item["requirement_id"] == "monitoring_gate_metrics_ready"
        and item["status"] == "blocked"
        for item in requirements
    )
    monitoring_readiness_endpoint_safe = not any(
        item["requirement_id"] == "monitoring_readiness_endpoint_ready"
        and item["status"] == "blocked"
        for item in requirements
    )

    safe_current_state = (
        runtime_safe
        and (not student_default_requested or student_cutover_ready)
        and (not student_auto_launch_requested or student_cutover_ready)
        and (not model_improvement_enabled or model_improvement_ready)
        and external_phi_guard_safe
        and file_ingestion_surface_safe
        and production_compose_safe
        and monitoring_metrics_safe
        and monitoring_readiness_endpoint_safe
    )
    production_ready = not blocked_items

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objective": (
            "Audit PHIplan production-readiness gates separately from the passing "
            "synthetic/reviewed distillation evidence."
        ),
        "safe_current_state": safe_current_state,
        "production_ready": production_ready,
        "blocked_item_count": len(blocked_items),
        "warning_item_count": len(warning_items),
        "blocked_items": blocked_items,
        "warning_items": warning_items,
        "requirements": requirements,
        "completion_audit": build_completion_audit(
            requirements,
            safe_current_state=safe_current_state,
            production_ready=production_ready,
        ),
        "next_required_actions": build_next_required_actions(requirements),
        "notes": [
            "This audit does not enable student default routing, call external services, train models, or write adapter files.",
            "Approval and consent reference values are reduced to configured/not-configured booleans and are not written to the report.",
            "safe_current_state=true means the current defaults remain conservative; production_ready=false means external production gates remain open.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--corpus-manifest", type=Path, default=DEFAULT_CORPUS_MANIFEST)
    parser.add_argument("--distillation-report", type=Path, default=DEFAULT_DISTILLATION_READINESS_REPORT)
    parser.add_argument("--synthetic-900-run-report", type=Path, default=DEFAULT_SYNTHETIC_900_RUN_REPORT)
    parser.add_argument("--manual-gate-packet-report", type=Path, default=DEFAULT_MANUAL_GATE_PACKET_REPORT)
    parser.add_argument("--runtime-supervisor-report", type=Path, default=DEFAULT_RUNTIME_SUPERVISOR_REPORT)
    parser.add_argument("--vector-backend-report", type=Path, default=DEFAULT_VECTOR_BACKEND_REPORT)
    parser.add_argument("--production-corpus-report", type=Path, default=DEFAULT_PRODUCTION_CORPUS_EVIDENCE_REPORT)
    parser.add_argument("--model-improvement-report", type=Path, default=DEFAULT_MODEL_IMPROVEMENT_EVIDENCE_REPORT)
    parser.add_argument("--file-ingestion-surface-report", type=Path, default=DEFAULT_FILE_INGESTION_SURFACE_REPORT)
    parser.add_argument("--prediction-fairness-report", type=Path, default=DEFAULT_PREDICTION_FAIRNESS_EVIDENCE_REPORT)
    parser.add_argument(
        "--backup-disaster-recovery-report",
        type=Path,
        default=DEFAULT_BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT,
    )
    parser.add_argument(
        "--dependency-security-report",
        type=Path,
        default=DEFAULT_DEPENDENCY_SECURITY_EVIDENCE_REPORT,
    )
    parser.add_argument("--production-compose", type=Path, default=DEFAULT_PRODUCTION_COMPOSE)
    parser.add_argument("--monitoring-module", type=Path, default=DEFAULT_MONITORING_MODULE)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = build_report(
        settings_like=load_runtime_settings(),
        corpus_manifest_path=args.corpus_manifest,
        distillation_report_path=args.distillation_report,
        synthetic_900_run_report_path=args.synthetic_900_run_report,
        manual_gate_packet_report_path=args.manual_gate_packet_report,
        runtime_supervisor_report_path=args.runtime_supervisor_report,
        vector_backend_report_path=args.vector_backend_report,
        production_corpus_report_path=args.production_corpus_report,
        model_improvement_report_path=args.model_improvement_report,
        file_ingestion_surface_report_path=args.file_ingestion_surface_report,
        prediction_fairness_report_path=args.prediction_fairness_report,
        backup_disaster_recovery_report_path=args.backup_disaster_recovery_report,
        dependency_security_report_path=args.dependency_security_report,
        production_compose_path=args.production_compose,
        monitoring_module_path=args.monitoring_module,
    )
    write_source_controlled_report_json(args.report, report, REPO_ROOT)
    print(
        f"Wrote {args.report} production_ready={report['production_ready']} "
        f"safe_current_state={report['safe_current_state']} "
        f"blocked={report['blocked_item_count']} warnings={report['warning_item_count']}"
    )
    if args.fail_on_blocked and report["blocked_item_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
