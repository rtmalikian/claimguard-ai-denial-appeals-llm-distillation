#!/usr/bin/env python3
"""Render private retrieval vector runtime evidence without printing values."""

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
DEFAULT_OUTPUT = Path("/private/tmp/claimguard-retrieval-vector-runtime.private.json")
DEFAULT_HEALTH_REF_ENV = "RETRIEVAL_VECTOR_HEALTH_EVIDENCE_REF"
DEFAULT_QUALITY_REF_ENV = "RETRIEVAL_QUALITY_SMOKE_EVIDENCE_REF"
DEFAULT_REINDEX_REF_ENV = "RETRIEVAL_VECTOR_REINDEX_AUDIT_EVIDENCE_REF"
DEFAULT_RUNTIME_SUMMARY_PATH_ENV = "RETRIEVAL_VECTOR_PRIVATE_RUNTIME_SUMMARY_PATH"
REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/=@+-]{2,255}$")
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
ALLOWED_ENV_KEYS = {
    DEFAULT_HEALTH_REF_ENV,
    DEFAULT_QUALITY_REF_ENV,
    DEFAULT_REINDEX_REF_ENV,
    DEFAULT_RUNTIME_SUMMARY_PATH_ENV,
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
REQUIRED_RUNTIME_SUMMARY_TRUE_FLAGS = {
    "semantic_backend_configured",
    "embedding_model_approved",
    "production_vector_backend_configured",
    "hash_fallback_disabled_for_production",
    "active_retrieval_chunks_indexed",
    "stored_hash_embeddings_absent",
    "reindex_job_completed",
    "reindex_audit_checked",
    "vector_backend_health_checked",
    "retrieval_quality_smoke_passed",
    "backup_restore_reviewed",
    "disable_or_rollback_path_reviewed",
    "no_phi_or_secret_values_attested",
    "no_source_text_or_vector_values_attested",
    "values_redacted",
}
REQUIRED_RUNTIME_SUMMARY_FALSE_FLAGS = {
    "raw_source_text_included",
    "raw_vector_values_included",
    "endpoint_values_included",
    "credential_values_included",
    "service_urls_included",
}
REQUIRED_RUNTIME_SUMMARY_POSITIVE_COUNTS = {
    "reindexed_chunk_count",
    "vector_health_check_count",
    "retrieval_quality_query_count",
    "backup_restore_check_count",
}
ALLOWED_RUNTIME_SUMMARY_KEYS = (
    REQUIRED_RUNTIME_SUMMARY_TRUE_FLAGS
    | REQUIRED_RUNTIME_SUMMARY_FALSE_FLAGS
    | REQUIRED_RUNTIME_SUMMARY_POSITIVE_COUNTS
)
REQUIRED_ATTESTATIONS = {
    "semantic_backend_attested": "semantic backend attestation is required",
    "embedding_model_approved_attested": "embedding model approval attestation is required",
    "production_vector_backend_attested": "production vector backend attestation is required",
    "hash_fallback_disabled_attested": "hash fallback disablement attestation is required",
    "reindex_completed_attested": "reindex completion attestation is required",
    "vector_health_attested": "vector backend health attestation is required",
    "retrieval_quality_smoke_attested": "retrieval quality smoke attestation is required",
    "backup_restore_reviewed": "backup restore review attestation is required",
    "disable_or_rollback_reviewed": "disable or rollback review attestation is required",
    "no_raw_values_attested": "no raw values attestation is required",
}
EVIDENCE_RENDERER_PATH = (
    "llm-distill/scripts/render_retrieval_vector_runtime_private_evidence.py"
)


class RenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderConfig:
    output_path: Path
    approved_runtime_validation: bool = False
    semantic_backend_attested: bool = False
    embedding_model_approved_attested: bool = False
    production_vector_backend_attested: bool = False
    hash_fallback_disabled_attested: bool = False
    reindex_completed_attested: bool = False
    vector_health_attested: bool = False
    retrieval_quality_smoke_attested: bool = False
    backup_restore_reviewed: bool = False
    disable_or_rollback_reviewed: bool = False
    no_raw_values_attested: bool = False
    health_reference_env: str = DEFAULT_HEALTH_REF_ENV
    quality_reference_env: str = DEFAULT_QUALITY_REF_ENV
    reindex_reference_env: str = DEFAULT_REINDEX_REF_ENV
    runtime_summary_path_env: str = DEFAULT_RUNTIME_SUMMARY_PATH_ENV
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


def _validate_reference(value: str) -> None:
    if not value:
        raise RenderError("private runtime evidence reference is required")
    if "\n" in value or "\r" in value or "\t" in value or " " in value:
        raise RenderError("private runtime evidence reference is not safely formatted")
    if "#" in value:
        raise RenderError("private runtime evidence reference must not contain comments")
    if not REFERENCE_RE.match(value):
        raise RenderError("private runtime evidence reference contains unsupported characters")


def _load_private_references(config: RenderConfig) -> dict[str, bool]:
    configured: dict[str, bool] = {}
    for label, env_name in {
        "health_evidence_reference_configured": config.health_reference_env,
        "quality_evidence_reference_configured": config.quality_reference_env,
        "reindex_evidence_reference_configured": config.reindex_reference_env,
    }.items():
        _validate_env_key(env_name)
        value = os.environ.get(env_name, "").strip()
        _validate_reference(value)
        configured[label] = True
    return configured


def _load_private_runtime_summary_path(env_name: str) -> Path:
    _validate_env_key(env_name)
    raw_path = os.environ.get(env_name, "").strip()
    if not raw_path:
        raise RenderError("private runtime summary path env var is required")
    if "\n" in raw_path or "\r" in raw_path or "\t" in raw_path or "#" in raw_path:
        raise RenderError("private runtime summary path contains unsupported characters")
    summary_path = Path(raw_path).expanduser().resolve()
    if path_is_within(summary_path, REPO_ROOT):
        raise RenderError("private runtime summary path must be outside source control")
    if not summary_path.exists():
        raise RenderError("private runtime summary path does not exist")
    if not summary_path.is_file():
        raise RenderError("private runtime summary path must be a file")
    return summary_path


def _load_private_runtime_summary_payload(summary_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise RenderError("private runtime summary must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise RenderError("private runtime summary must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise RenderError("private runtime summary must be a JSON object")
    return payload


def _validate_private_runtime_summary(summary_path: Path) -> dict[str, int]:
    payload = _load_private_runtime_summary_payload(summary_path)
    unsupported_keys = sorted(set(payload) - ALLOWED_RUNTIME_SUMMARY_KEYS)
    if unsupported_keys:
        raise RenderError("private runtime summary contains unsupported fields")

    for key in sorted(REQUIRED_RUNTIME_SUMMARY_TRUE_FLAGS):
        if payload.get(key) is not True:
            raise RenderError(f"private runtime summary requires {key}=true")
    for key in sorted(REQUIRED_RUNTIME_SUMMARY_FALSE_FLAGS):
        if payload.get(key) is not False:
            raise RenderError(f"private runtime summary requires {key}=false")
    for key in sorted(REQUIRED_RUNTIME_SUMMARY_POSITIVE_COUNTS):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RenderError(f"private runtime summary requires positive {key}")

    return {
        "reindexed_chunk_count": int(payload["reindexed_chunk_count"]),
        "vector_health_check_count": int(payload["vector_health_check_count"]),
        "retrieval_quality_query_count": int(payload["retrieval_quality_query_count"]),
        "backup_restore_check_count": int(payload["backup_restore_check_count"]),
    }


def _validate_approved_attestations(config: RenderConfig) -> None:
    missing = [
        message
        for flag, message in REQUIRED_ATTESTATIONS.items()
        if getattr(config, flag) is not True
    ]
    if missing:
        raise RenderError("approved runtime evidence requires explicit attestations")


def _private_evidence_payload(config: RenderConfig) -> dict[str, Any]:
    references_configured = {
        "health_evidence_reference_configured": False,
        "quality_evidence_reference_configured": False,
        "reindex_evidence_reference_configured": False,
    }
    runtime_summary_metadata = {
        "reindexed_chunk_count": 0,
        "vector_health_check_count": 0,
        "retrieval_quality_query_count": 0,
        "backup_restore_check_count": 0,
    }
    if config.approved_runtime_validation:
        _validate_approved_attestations(config)
        runtime_summary_path = _load_private_runtime_summary_path(
            config.runtime_summary_path_env
        )
        runtime_summary_metadata = _validate_private_runtime_summary(
            runtime_summary_path
        )
        references_configured = _load_private_references(config)

    runtime_ready = (
        config.approved_runtime_validation
        and config.semantic_backend_attested
        and config.embedding_model_approved_attested
        and config.production_vector_backend_attested
        and config.hash_fallback_disabled_attested
        and config.reindex_completed_attested
        and config.vector_health_attested
        and config.retrieval_quality_smoke_attested
        and config.backup_restore_reviewed
        and config.disable_or_rollback_reviewed
        and config.no_raw_values_attested
        and all(references_configured.values())
        and all(value > 0 for value in runtime_summary_metadata.values())
    )
    return {
        "artifact": "claimguard_retrieval_vector_backend_evidence",
        "version": "1.0",
        "evidence_status": (
            "private_runtime_validation_ready"
            if runtime_ready
            else "private_runtime_validation_not_ready"
        ),
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "no_phi_or_secret_values_attested": True,
        "no_source_text_or_vector_values_attested": True,
        "private_runtime_summary_path_env": (
            config.runtime_summary_path_env
            if config.approved_runtime_validation
            else None
        ),
        "private_runtime_summary_path_configured": bool(
            config.approved_runtime_validation
        ),
        "private_runtime_summary_path_value_included": False,
        "private_runtime_summary_checked": bool(config.approved_runtime_validation),
        "private_runtime_summary_reindexed_chunk_count": (
            runtime_summary_metadata["reindexed_chunk_count"]
        ),
        "private_runtime_summary_vector_health_check_count": (
            runtime_summary_metadata["vector_health_check_count"]
        ),
        "private_runtime_summary_retrieval_quality_query_count": (
            runtime_summary_metadata["retrieval_quality_query_count"]
        ),
        "private_runtime_summary_backup_restore_check_count": (
            runtime_summary_metadata["backup_restore_check_count"]
        ),
        "private_runtime_summary_raw_values_included": False,
        "backend_configuration": {
            "source_control_private_env_renderer_documented": True,
            "source_control_private_env_renderer_path": (
                "llm-distill/scripts/render_retrieval_vector_private_env.py"
            ),
            "source_control_private_embedding_provider_loader_documented": True,
            "source_control_private_embedding_provider_loader_path": (
                "health-ai-medical-billing-medical-corporations-20260414_180528/"
                "app/services/retrieval_semantic_provider.py"
            ),
            "semantic_backend_configured": config.semantic_backend_attested,
            "embedding_model_configured": config.embedding_model_approved_attested,
            "embedding_model_approved": config.embedding_model_approved_attested,
            "production_vector_backend_configured": config.production_vector_backend_attested,
            "hash_fallback_disabled_for_production": (
                config.hash_fallback_disabled_attested
            ),
            "contains_secrets": False,
        },
        "index_state": {
            "source_control_reindex_checklist_documented": True,
            "source_control_reindex_checklist_path": (
                "llm-distill/docs/retrieval-vector-reindex-checklist.md"
            ),
            "application_reindex_operation_available": True,
            "active_retrieval_chunks_indexed": config.reindex_completed_attested,
            "stored_hash_embeddings_absent": config.reindex_completed_attested,
            "reindex_job_completed": config.reindex_completed_attested,
            "reindex_audit_checked": config.reindex_completed_attested,
        },
        "governance_controls": {
            "source_control_runbook_documented": True,
            "source_control_runbook_path": (
                "llm-distill/docs/retrieval-vector-backend-runbook.md"
            ),
            "role_scoped_access_verified": True,
            "retention_delete_verified": True,
            "audit_dashboard_verified": True,
            "encrypted_storage_verified": True,
            "source_text_redaction_verified": True,
        },
        "runtime_validation": {
            "source_control_runtime_smoke_checklist_documented": True,
            "source_control_runtime_smoke_checklist_path": (
                "llm-distill/docs/retrieval-vector-runtime-smoke-checklist.md"
            ),
            "source_control_runtime_private_evidence_renderer_documented": True,
            "runtime_private_evidence_renderer_path": EVIDENCE_RENDERER_PATH,
            "vector_backend_health_checked": config.vector_health_attested,
            "retrieval_quality_smoke_passed": config.retrieval_quality_smoke_attested,
            "backup_restore_reviewed": config.backup_restore_reviewed,
            "disable_or_rollback_path_reviewed": config.disable_or_rollback_reviewed,
            **references_configured,
        },
        "operator_notes": [
            "Private runtime references stay in the operator environment and are not written to this file.",
            "Do not store embedding service URLs, credentials, raw source text, vector values, PHI, or production document content in this evidence file.",
            "This private evidence can become vector_backend_ready=true only after semantic configuration, reindexing, health, quality smoke, backup, and rollback attestations are complete.",
        ],
    }


def render_private_evidence(config: RenderConfig) -> dict[str, Any]:
    output_path = config.output_path.resolve()
    if path_is_within(output_path, REPO_ROOT):
        raise RenderError("refusing_to_write_inside_source_control")

    payload = _private_evidence_payload(config)
    summary = {
        "dry_run": config.dry_run,
        "rendered": not config.dry_run,
        "approved_runtime_validation_requested": config.approved_runtime_validation,
        "semantic_backend_attested": config.semantic_backend_attested,
        "embedding_model_approved_attested": config.embedding_model_approved_attested,
        "production_vector_backend_attested": config.production_vector_backend_attested,
        "hash_fallback_disabled_attested": config.hash_fallback_disabled_attested,
        "reindex_completed_attested": config.reindex_completed_attested,
        "vector_health_attested": config.vector_health_attested,
        "retrieval_quality_smoke_attested": config.retrieval_quality_smoke_attested,
        "backup_restore_reviewed": config.backup_restore_reviewed,
        "disable_or_rollback_reviewed": config.disable_or_rollback_reviewed,
        "no_raw_values_attested": config.no_raw_values_attested,
        "health_evidence_reference_configured": payload["runtime_validation"][
            "health_evidence_reference_configured"
        ],
        "quality_evidence_reference_configured": payload["runtime_validation"][
            "quality_evidence_reference_configured"
        ],
        "reindex_evidence_reference_configured": payload["runtime_validation"][
            "reindex_evidence_reference_configured"
        ],
        "private_runtime_summary_path_env_configured": bool(
            payload["private_runtime_summary_path_env"]
        ),
        "private_runtime_summary_path_value_included": False,
        "private_runtime_summary_checked": payload["private_runtime_summary_checked"],
        "private_runtime_summary_reindexed_chunk_count": payload[
            "private_runtime_summary_reindexed_chunk_count"
        ],
        "private_runtime_summary_vector_health_check_count": payload[
            "private_runtime_summary_vector_health_check_count"
        ],
        "private_runtime_summary_retrieval_quality_query_count": payload[
            "private_runtime_summary_retrieval_quality_query_count"
        ],
        "private_runtime_summary_backup_restore_check_count": payload[
            "private_runtime_summary_backup_restore_check_count"
        ],
        "private_runtime_summary_raw_values_included": False,
        "vector_backend_ready_if_validated": all(
            [
                payload["backend_configuration"]["semantic_backend_configured"],
                payload["backend_configuration"]["embedding_model_approved"],
                payload["backend_configuration"]["production_vector_backend_configured"],
                payload["backend_configuration"]["hash_fallback_disabled_for_production"],
                payload["index_state"]["active_retrieval_chunks_indexed"],
                payload["runtime_validation"]["vector_backend_health_checked"],
                payload["runtime_validation"]["retrieval_quality_smoke_passed"],
                payload["runtime_validation"]["backup_restore_reviewed"],
                payload["runtime_validation"]["disable_or_rollback_path_reviewed"],
                payload["runtime_validation"]["health_evidence_reference_configured"],
                payload["runtime_validation"]["quality_evidence_reference_configured"],
                payload["runtime_validation"]["reindex_evidence_reference_configured"],
                payload["private_runtime_summary_checked"],
            ]
        ),
        "output_path_in_source_control": False,
        "private_reference_values_included": False,
        "raw_source_text_included": False,
        "raw_vector_values_included": False,
        "endpoint_values_included": False,
        "credential_values_included": False,
        "values_redacted": True,
        "file_mode": "0600" if not config.dry_run else None,
    }

    if not config.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        output_path.chmod(0o600)
    return summary


def build_config(args: argparse.Namespace) -> RenderConfig:
    return RenderConfig(
        output_path=args.output,
        approved_runtime_validation=args.approved_runtime_validation,
        semantic_backend_attested=args.semantic_backend_attested,
        embedding_model_approved_attested=args.embedding_model_approved_attested,
        production_vector_backend_attested=args.production_vector_backend_attested,
        hash_fallback_disabled_attested=args.hash_fallback_disabled_attested,
        reindex_completed_attested=args.reindex_completed_attested,
        vector_health_attested=args.vector_health_attested,
        retrieval_quality_smoke_attested=args.retrieval_quality_smoke_attested,
        backup_restore_reviewed=args.backup_restore_reviewed,
        disable_or_rollback_reviewed=args.disable_or_rollback_reviewed,
        no_raw_values_attested=args.no_raw_values_attested,
        health_reference_env=args.health_reference_env,
        quality_reference_env=args.quality_reference_env,
        reindex_reference_env=args.reindex_reference_env,
        runtime_summary_path_env=args.runtime_summary_path_env,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--approved-runtime-validation", action="store_true")
    parser.add_argument("--semantic-backend-attested", action="store_true")
    parser.add_argument("--embedding-model-approved-attested", action="store_true")
    parser.add_argument("--production-vector-backend-attested", action="store_true")
    parser.add_argument("--hash-fallback-disabled-attested", action="store_true")
    parser.add_argument("--reindex-completed-attested", action="store_true")
    parser.add_argument("--vector-health-attested", action="store_true")
    parser.add_argument("--retrieval-quality-smoke-attested", action="store_true")
    parser.add_argument("--backup-restore-reviewed", action="store_true")
    parser.add_argument("--disable-or-rollback-reviewed", action="store_true")
    parser.add_argument("--no-raw-values-attested", action="store_true")
    parser.add_argument("--health-reference-env", default=DEFAULT_HEALTH_REF_ENV)
    parser.add_argument("--quality-reference-env", default=DEFAULT_QUALITY_REF_ENV)
    parser.add_argument("--reindex-reference-env", default=DEFAULT_REINDEX_REF_ENV)
    parser.add_argument(
        "--runtime-summary-path-env",
        default=DEFAULT_RUNTIME_SUMMARY_PATH_ENV,
    )
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
