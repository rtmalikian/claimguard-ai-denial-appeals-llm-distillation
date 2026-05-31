#!/usr/bin/env python3
"""Render a private retrieval vector backend env file without printing values."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path("/private/tmp/claimguard-retrieval-vector.private.env")
DEFAULT_EMBEDDING_BACKEND_ENV = "RETRIEVAL_PRODUCTION_EMBEDDING_BACKEND"
DEFAULT_EMBEDDING_MODEL_ENV = "RETRIEVAL_PRODUCTION_EMBEDDING_MODEL"
DEFAULT_VECTOR_BACKEND_ENV = "RETRIEVAL_PRODUCTION_VECTOR_BACKEND"
HASH_EMBEDDING_MODEL = "claimguard-hash-embedding-v1"
HASH_BACKENDS = {"hash", "local_hash", "deterministic_hash"}
LOCAL_VECTOR_BACKENDS = {
    "encrypted_local_metadata",
    "local_encrypted_metadata",
    "local_metadata",
}
REQUIRED_ATTESTATIONS = {
    "semantic_backend_attested": "semantic backend attestation is required",
    "embedding_model_approved_attested": "embedding model approval attestation is required",
    "production_vector_backend_attested": "production vector backend attestation is required",
    "hash_fallback_disabled_attested": "hash fallback disablement attestation is required",
    "reindex_completed_attested": "reindex completion attestation is required",
    "vector_health_attested": "vector backend health attestation is required",
    "retrieval_quality_smoke_attested": "retrieval quality smoke attestation is required",
    "rollback_reviewed": "rollback or disable path review is required",
    "no_raw_values_attested": "no raw source text or vector values attestation is required",
}
ALLOWED_ENV_KEYS = {
    DEFAULT_EMBEDDING_BACKEND_ENV,
    DEFAULT_EMBEDDING_MODEL_ENV,
    DEFAULT_VECTOR_BACKEND_ENV,
}
OUTPUT_ENV_KEYS = {
    "RETRIEVAL_EMBEDDING_BACKEND",
    "RETRIEVAL_EMBEDDING_MODEL",
    "RETRIEVAL_EMBEDDING_MODEL_APPROVED",
    "RETRIEVAL_VECTOR_BACKEND",
    "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED",
    "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION",
}
FORBIDDEN_TEXT_FRAGMENTS = {
    "api_key",
    "authorization",
    "bearer",
    "credential",
    "password",
    "secret",
    "token",
}
SAFE_PRIVATE_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/=@+-]{2,255}$")
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")


class RenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderConfig:
    output_path: Path
    approved_vector_backend: bool = False
    embedding_backend_env: str = DEFAULT_EMBEDDING_BACKEND_ENV
    embedding_model_env: str = DEFAULT_EMBEDDING_MODEL_ENV
    vector_backend_env: str = DEFAULT_VECTOR_BACKEND_ENV
    semantic_backend_attested: bool = False
    embedding_model_approved_attested: bool = False
    production_vector_backend_attested: bool = False
    hash_fallback_disabled_attested: bool = False
    reindex_completed_attested: bool = False
    vector_health_attested: bool = False
    retrieval_quality_smoke_attested: bool = False
    rollback_reviewed: bool = False
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
    if any(fragment in name.lower() for fragment in FORBIDDEN_TEXT_FRAGMENTS):
        raise RenderError("secret-like environment key requested")


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and (parsed.netloc or parsed.path))


def _validate_private_value(value: str, label: str) -> None:
    if not value:
        raise RenderError(f"{label} env var is required for approved vector backend")
    if "\n" in value or "\r" in value or "\t" in value or " " in value:
        raise RenderError(f"{label} must not contain whitespace or control characters")
    if "#" in value:
        raise RenderError(f"{label} must not contain comment delimiters")
    if _looks_like_url(value):
        raise RenderError(f"{label} must not contain service URLs")
    if any(fragment in value.lower() for fragment in FORBIDDEN_TEXT_FRAGMENTS):
        raise RenderError(f"{label} contains secret-like text")
    if not SAFE_PRIVATE_VALUE_RE.match(value):
        raise RenderError(f"{label} contains unsupported characters")


def _load_private_value(env_name: str, label: str) -> str:
    _validate_env_key(env_name)
    value = os.environ.get(env_name, "").strip()
    _validate_private_value(value, label)
    return value


def _validate_approved_attestations(config: RenderConfig) -> None:
    missing = [
        message
        for flag, message in REQUIRED_ATTESTATIONS.items()
        if getattr(config, flag) is not True
    ]
    if missing:
        raise RenderError("approved vector backend requires explicit attestations")


def _build_environment(config: RenderConfig) -> dict[str, str]:
    if config.approved_vector_backend:
        _validate_approved_attestations(config)
        embedding_backend = _load_private_value(
            config.embedding_backend_env,
            "embedding backend",
        )
        embedding_model = _load_private_value(
            config.embedding_model_env,
            "embedding model",
        )
        vector_backend = _load_private_value(
            config.vector_backend_env,
            "vector backend",
        )
        if embedding_backend.lower() in HASH_BACKENDS:
            raise RenderError("approved vector backend cannot use hash embedding backend")
        if embedding_model == HASH_EMBEDDING_MODEL:
            raise RenderError("approved vector backend cannot use hash embedding model")
        if vector_backend.lower() in LOCAL_VECTOR_BACKENDS:
            raise RenderError("approved vector backend cannot use local metadata vector backend")
        env = {
            "RETRIEVAL_EMBEDDING_BACKEND": embedding_backend,
            "RETRIEVAL_EMBEDDING_MODEL": embedding_model,
            "RETRIEVAL_EMBEDDING_MODEL_APPROVED": "true",
            "RETRIEVAL_VECTOR_BACKEND": vector_backend,
            "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED": "true",
            "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION": "true",
        }
    else:
        env = {
            "RETRIEVAL_EMBEDDING_BACKEND": "hash",
            "RETRIEVAL_EMBEDDING_MODEL": HASH_EMBEDDING_MODEL,
            "RETRIEVAL_EMBEDDING_MODEL_APPROVED": "false",
            "RETRIEVAL_VECTOR_BACKEND": "encrypted_local_metadata",
            "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED": "false",
            "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION": "false",
        }
    unexpected = set(env) - OUTPUT_ENV_KEYS
    if unexpected:
        raise RenderError("unexpected environment keys would be written")
    return env


def _env_file_text(env: dict[str, str]) -> str:
    lines = [
        "# ClaimGuard AI private retrieval vector backend environment.",
        "# Do not commit this file. Store it outside source control.",
    ]
    lines.extend(f"{key}={value}" for key, value in env.items())
    return "\n".join(lines) + "\n"


def render_private_env(config: RenderConfig) -> dict[str, Any]:
    output_path = config.output_path.resolve()
    if path_is_within(output_path, REPO_ROOT):
        raise RenderError("refusing_to_write_inside_source_control")

    env = _build_environment(config)
    summary = {
        "dry_run": config.dry_run,
        "rendered": not config.dry_run,
        "approved_vector_backend_requested": config.approved_vector_backend,
        "semantic_backend_configured": (
            env["RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED"] == "true"
        ),
        "embedding_model_configured": bool(env["RETRIEVAL_EMBEDDING_MODEL"]),
        "embedding_model_approved": (
            env["RETRIEVAL_EMBEDDING_MODEL_APPROVED"] == "true"
        ),
        "production_vector_backend_configured": (
            env["RETRIEVAL_VECTOR_BACKEND"].lower() not in LOCAL_VECTOR_BACKENDS
        ),
        "hash_fallback_disabled_for_production": (
            env["RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION"] == "true"
        ),
        "hash_embedding_backend_active": (
            env["RETRIEVAL_EMBEDDING_BACKEND"].lower() in HASH_BACKENDS
        ),
        "hash_embedding_model_active": (
            env["RETRIEVAL_EMBEDDING_MODEL"] == HASH_EMBEDDING_MODEL
        ),
        "environment_variable_count": len(env),
        "output_path_in_source_control": False,
        "raw_env_values_included": False,
        "embedding_backend_value_included": False,
        "embedding_model_value_included": False,
        "vector_backend_value_included": False,
        "raw_source_text_or_vector_values_included": False,
        "service_urls_included": False,
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
        approved_vector_backend=args.approved_vector_backend,
        embedding_backend_env=args.embedding_backend_env,
        embedding_model_env=args.embedding_model_env,
        vector_backend_env=args.vector_backend_env,
        semantic_backend_attested=args.semantic_backend_attested,
        embedding_model_approved_attested=args.embedding_model_approved_attested,
        production_vector_backend_attested=args.production_vector_backend_attested,
        hash_fallback_disabled_attested=args.hash_fallback_disabled_attested,
        reindex_completed_attested=args.reindex_completed_attested,
        vector_health_attested=args.vector_health_attested,
        retrieval_quality_smoke_attested=args.retrieval_quality_smoke_attested,
        rollback_reviewed=args.rollback_reviewed,
        no_raw_values_attested=args.no_raw_values_attested,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--approved-vector-backend", action="store_true")
    parser.add_argument("--embedding-backend-env", default=DEFAULT_EMBEDDING_BACKEND_ENV)
    parser.add_argument("--embedding-model-env", default=DEFAULT_EMBEDDING_MODEL_ENV)
    parser.add_argument("--vector-backend-env", default=DEFAULT_VECTOR_BACKEND_ENV)
    parser.add_argument("--semantic-backend-attested", action="store_true")
    parser.add_argument("--embedding-model-approved-attested", action="store_true")
    parser.add_argument("--production-vector-backend-attested", action="store_true")
    parser.add_argument("--hash-fallback-disabled-attested", action="store_true")
    parser.add_argument("--reindex-completed-attested", action="store_true")
    parser.add_argument("--vector-health-attested", action="store_true")
    parser.add_argument("--retrieval-quality-smoke-attested", action="store_true")
    parser.add_argument("--rollback-reviewed", action="store_true")
    parser.add_argument("--no-raw-values-attested", action="store_true")
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
