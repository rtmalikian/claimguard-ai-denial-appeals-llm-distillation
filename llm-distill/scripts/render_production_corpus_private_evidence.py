#!/usr/bin/env python3
"""Render private production-corpus evidence without printing values."""

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
DEFAULT_OUTPUT = Path("/private/tmp/claimguard-production-corpus.private.evidence.json")
DEFAULT_MANIFEST_PATH = "llm-distill/data/corpus/manifest.json"
DEFAULT_PRIVATE_MANIFEST_PATH_ENV = "PRODUCTION_CORPUS_PRIVATE_MANIFEST_PATH"
DEFAULT_PRIVACY_REVIEW_REFERENCE_ENV = "PRODUCTION_CORPUS_PRIVACY_REVIEW_REFERENCE"
DEFAULT_LICENSE_REVIEW_REFERENCE_ENV = "PRODUCTION_CORPUS_LICENSE_REVIEW_REFERENCE"
DEFAULT_RESIDUAL_RISK_REVIEW_REFERENCE_ENV = (
    "PRODUCTION_CORPUS_RESIDUAL_RISK_REVIEW_REFERENCE"
)
DEFAULT_TRAINING_SCOPE_REVIEW_REFERENCE_ENV = (
    "PRODUCTION_CORPUS_TRAINING_SCOPE_REVIEW_REFERENCE"
)
DEFAULT_PAIR_SOURCE_REVIEW_REFERENCE_ENV = (
    "PRODUCTION_CORPUS_PAIR_SOURCE_REVIEW_REFERENCE"
)
DEFAULT_PRIVATE_EVIDENCE_RENDERER_PATH = (
    "llm-distill/scripts/render_production_corpus_private_evidence.py"
)
REQUIRED_ATTESTATIONS = {
    "approved_non_synthetic_pair_attested": (
        "approved non-synthetic denial/appeal pair attestation is required"
    ),
    "privacy_review_attested": "privacy review attestation is required",
    "license_review_attested": "license review attestation is required",
    "residual_risk_review_attested": "residual-risk review attestation is required",
    "training_scope_reviewed": "training-scope review attestation is required",
    "no_phi_review_attested": "no-PHI review attestation is required",
    "source_license_scope_documented": (
        "source-license scope documentation attestation is required"
    ),
    "pair_ids_reviewed_outside_source_control": (
        "pair-id review outside source control attestation is required"
    ),
    "source_documents_reviewed_outside_source_control": (
        "source-document review outside source control attestation is required"
    ),
    "metadata_only_manifest_attested": (
        "metadata-only manifest attestation is required"
    ),
    "no_raw_document_content_attested": (
        "no raw document content attestation is required"
    ),
    "no_raw_values_attested": "no raw values attestation is required",
}
ALLOWED_ENV_KEYS = {
    DEFAULT_PRIVATE_MANIFEST_PATH_ENV,
    DEFAULT_PRIVACY_REVIEW_REFERENCE_ENV,
    DEFAULT_LICENSE_REVIEW_REFERENCE_ENV,
    DEFAULT_RESIDUAL_RISK_REVIEW_REFERENCE_ENV,
    DEFAULT_TRAINING_SCOPE_REVIEW_REFERENCE_ENV,
    DEFAULT_PAIR_SOURCE_REVIEW_REFERENCE_ENV,
}
FORBIDDEN_ENV_KEY_FRAGMENTS = {
    "api_key",
    "authorization",
    "credential",
    "password",
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
    approved_production_corpus: bool = False
    private_manifest_path_env: str = DEFAULT_PRIVATE_MANIFEST_PATH_ENV
    privacy_review_reference_env: str = DEFAULT_PRIVACY_REVIEW_REFERENCE_ENV
    license_review_reference_env: str = DEFAULT_LICENSE_REVIEW_REFERENCE_ENV
    residual_risk_review_reference_env: str = (
        DEFAULT_RESIDUAL_RISK_REVIEW_REFERENCE_ENV
    )
    training_scope_review_reference_env: str = (
        DEFAULT_TRAINING_SCOPE_REVIEW_REFERENCE_ENV
    )
    pair_source_review_reference_env: str = DEFAULT_PAIR_SOURCE_REVIEW_REFERENCE_ENV
    approved_non_synthetic_pair_attested: bool = False
    privacy_review_attested: bool = False
    license_review_attested: bool = False
    residual_risk_review_attested: bool = False
    training_scope_reviewed: bool = False
    no_phi_review_attested: bool = False
    source_license_scope_documented: bool = False
    pair_ids_reviewed_outside_source_control: bool = False
    source_documents_reviewed_outside_source_control: bool = False
    metadata_only_manifest_attested: bool = False
    no_raw_document_content_attested: bool = False
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
        raise RenderError(f"{label} env var is required for approved corpus")
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


def _load_private_manifest_path(env_name: str) -> Path:
    _validate_env_key(env_name)
    raw_path = os.environ.get(env_name, "").strip()
    if not raw_path:
        raise RenderError("private manifest path env var is required")
    if "\n" in raw_path or "\r" in raw_path or "\t" in raw_path or "#" in raw_path:
        raise RenderError("private manifest path contains unsupported characters")
    manifest_path = Path(raw_path).expanduser().resolve()
    if path_is_within(manifest_path, REPO_ROOT):
        raise RenderError("private manifest path must be outside source control")
    if not manifest_path.exists():
        raise RenderError("private manifest path does not exist")
    if not manifest_path.is_file():
        raise RenderError("private manifest path must be a file")
    return manifest_path


def _validate_approved_attestations(config: RenderConfig) -> None:
    missing = [
        message
        for flag, message in REQUIRED_ATTESTATIONS.items()
        if getattr(config, flag) is not True
    ]
    if missing:
        raise RenderError("approved corpus requires explicit attestations")


def _load_private_references(config: RenderConfig) -> list[str]:
    reference_specs = [
        (config.privacy_review_reference_env, "privacy review reference"),
        (config.license_review_reference_env, "license review reference"),
        (config.residual_risk_review_reference_env, "residual-risk review reference"),
        (config.training_scope_review_reference_env, "training-scope review reference"),
        (config.pair_source_review_reference_env, "pair/source review reference"),
    ]
    return [
        _load_private_reference(env_name, label)
        for env_name, label in reference_specs
    ]


def _evidence_payload(config: RenderConfig) -> tuple[dict[str, Any], int]:
    private_reference_count = 0
    if config.approved_production_corpus:
        _validate_approved_attestations(config)
        private_manifest_path = _load_private_manifest_path(
            config.private_manifest_path_env
        )
        private_reference_count = len(_load_private_references(config))
        status = "production_corpus_ready_private_review_complete"
        manifest_path = str(private_manifest_path)
        corpus_ready = True
    else:
        status = "private_renderer_default_non_synthetic_pair_blocked"
        manifest_path = DEFAULT_MANIFEST_PATH
        corpus_ready = False

    evidence = {
        "artifact": "claimguard_production_corpus_evidence",
        "version": "1.0",
        "evidence_status": status,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "no_phi_or_secret_values_attested": True,
        "no_raw_document_content_attested": True,
        "manifest_path": manifest_path,
        "corpus_review": {
            "source_control_review_runbook_documented": True,
            "source_control_review_runbook_path": (
                "llm-distill/docs/production-corpus-review-runbook.md"
            ),
            "source_control_collection_license_checklist_documented": True,
            "source_control_collection_license_checklist_path": (
                "llm-distill/docs/production-corpus-collection-license-checklist.md"
            ),
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": DEFAULT_PRIVATE_EVIDENCE_RENDERER_PATH,
            "privacy_review_attested": corpus_ready,
            "license_review_attested": corpus_ready,
            "residual_risk_review_attested": corpus_ready,
            "training_scope_reviewed": corpus_ready,
            "no_phi_review_attested": corpus_ready,
            "source_license_scope_documented": corpus_ready,
            "contains_approval_reference_values": False,
            "contains_raw_document_content": False,
        },
        "pairing_requirements": {
            "source_control_pair_source_checklist_documented": True,
            "source_control_pair_source_checklist_path": (
                "llm-distill/docs/production-corpus-pair-source-checklist.md"
            ),
            "minimum_approved_non_synthetic_pair_count": 1,
            "denial_and_appeal_roles_required": True,
            "pair_ids_reviewed_outside_source_control": corpus_ready,
            "source_documents_reviewed_outside_source_control": corpus_ready,
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
    review = evidence["corpus_review"]
    pairing = evidence["pairing_requirements"]
    summary = {
        "dry_run": config.dry_run,
        "rendered": not config.dry_run,
        "approved_production_corpus_requested": config.approved_production_corpus,
        "privacy_review_attested": review["privacy_review_attested"],
        "license_review_attested": review["license_review_attested"],
        "residual_risk_review_attested": review["residual_risk_review_attested"],
        "training_scope_reviewed": review["training_scope_reviewed"],
        "no_phi_review_attested": review["no_phi_review_attested"],
        "source_license_scope_documented": review["source_license_scope_documented"],
        "approved_non_synthetic_pair_attested": (
            config.approved_non_synthetic_pair_attested
        ),
        "pair_ids_reviewed_outside_source_control": (
            pairing["pair_ids_reviewed_outside_source_control"]
        ),
        "source_documents_reviewed_outside_source_control": (
            pairing["source_documents_reviewed_outside_source_control"]
        ),
        "private_reference_count": private_reference_count,
        "manifest_path_configured": bool(evidence["manifest_path"]),
        "private_manifest_path_value_included": False,
        "raw_private_values_included": False,
        "approval_reference_value_included": False,
        "raw_document_content_included": False,
        "source_document_values_included": False,
        "values_redacted": True,
        "output_path_in_source_control": False,
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
        approved_production_corpus=args.approved_production_corpus,
        private_manifest_path_env=args.private_manifest_path_env,
        privacy_review_reference_env=args.privacy_review_reference_env,
        license_review_reference_env=args.license_review_reference_env,
        residual_risk_review_reference_env=args.residual_risk_review_reference_env,
        training_scope_review_reference_env=args.training_scope_review_reference_env,
        pair_source_review_reference_env=args.pair_source_review_reference_env,
        approved_non_synthetic_pair_attested=args.approved_non_synthetic_pair_attested,
        privacy_review_attested=args.privacy_review_attested,
        license_review_attested=args.license_review_attested,
        residual_risk_review_attested=args.residual_risk_review_attested,
        training_scope_reviewed=args.training_scope_reviewed,
        no_phi_review_attested=args.no_phi_review_attested,
        source_license_scope_documented=args.source_license_scope_documented,
        pair_ids_reviewed_outside_source_control=(
            args.pair_ids_reviewed_outside_source_control
        ),
        source_documents_reviewed_outside_source_control=(
            args.source_documents_reviewed_outside_source_control
        ),
        metadata_only_manifest_attested=args.metadata_only_manifest_attested,
        no_raw_document_content_attested=args.no_raw_document_content_attested,
        no_raw_values_attested=args.no_raw_values_attested,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--approved-production-corpus", action="store_true")
    parser.add_argument(
        "--private-manifest-path-env",
        default=DEFAULT_PRIVATE_MANIFEST_PATH_ENV,
    )
    parser.add_argument(
        "--privacy-review-reference-env",
        default=DEFAULT_PRIVACY_REVIEW_REFERENCE_ENV,
    )
    parser.add_argument(
        "--license-review-reference-env",
        default=DEFAULT_LICENSE_REVIEW_REFERENCE_ENV,
    )
    parser.add_argument(
        "--residual-risk-review-reference-env",
        default=DEFAULT_RESIDUAL_RISK_REVIEW_REFERENCE_ENV,
    )
    parser.add_argument(
        "--training-scope-review-reference-env",
        default=DEFAULT_TRAINING_SCOPE_REVIEW_REFERENCE_ENV,
    )
    parser.add_argument(
        "--pair-source-review-reference-env",
        default=DEFAULT_PAIR_SOURCE_REVIEW_REFERENCE_ENV,
    )
    parser.add_argument("--approved-non-synthetic-pair-attested", action="store_true")
    parser.add_argument("--privacy-review-attested", action="store_true")
    parser.add_argument("--license-review-attested", action="store_true")
    parser.add_argument("--residual-risk-review-attested", action="store_true")
    parser.add_argument("--training-scope-reviewed", action="store_true")
    parser.add_argument("--no-phi-review-attested", action="store_true")
    parser.add_argument("--source-license-scope-documented", action="store_true")
    parser.add_argument("--pair-ids-reviewed-outside-source-control", action="store_true")
    parser.add_argument(
        "--source-documents-reviewed-outside-source-control",
        action="store_true",
    )
    parser.add_argument("--metadata-only-manifest-attested", action="store_true")
    parser.add_argument("--no-raw-document-content-attested", action="store_true")
    parser.add_argument("--no-raw-values-attested", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        summary = render_private_evidence(build_config(args))
    except RenderError as exc:
        print(json.dumps({"error": str(exc), "values_redacted": True}, sort_keys=True))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
