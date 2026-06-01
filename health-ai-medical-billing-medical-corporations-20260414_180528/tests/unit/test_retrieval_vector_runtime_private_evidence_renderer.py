import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
RENDERER_SCRIPT = SCRIPT_DIR / "render_retrieval_vector_runtime_private_evidence.py"
VALIDATOR_SCRIPT = SCRIPT_DIR / "validate_retrieval_vector_backend.py"


def _load_module(path: Path, name: str) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_renderer() -> ModuleType:
    return _load_module(RENDERER_SCRIPT, "render_retrieval_vector_runtime_private_evidence")


def _load_validator() -> ModuleType:
    return _load_module(VALIDATOR_SCRIPT, "validate_retrieval_vector_backend")


def _approved_config(renderer: ModuleType, output_path: Path):
    return renderer.RenderConfig(
        output_path=output_path,
        approved_runtime_validation=True,
        semantic_backend_attested=True,
        embedding_model_approved_attested=True,
        production_vector_backend_attested=True,
        hash_fallback_disabled_attested=True,
        reindex_completed_attested=True,
        vector_health_attested=True,
        retrieval_quality_smoke_attested=True,
        backup_restore_reviewed=True,
        disable_or_rollback_reviewed=True,
        no_raw_values_attested=True,
    )


def _runtime_summary_payload(**overrides):
    payload = {
        "semantic_backend_configured": True,
        "embedding_model_approved": True,
        "production_vector_backend_configured": True,
        "hash_fallback_disabled_for_production": True,
        "active_retrieval_chunks_indexed": True,
        "stored_hash_embeddings_absent": True,
        "reindex_job_completed": True,
        "reindex_audit_checked": True,
        "vector_backend_health_checked": True,
        "retrieval_quality_smoke_passed": True,
        "backup_restore_reviewed": True,
        "disable_or_rollback_path_reviewed": True,
        "no_phi_or_secret_values_attested": True,
        "no_source_text_or_vector_values_attested": True,
        "raw_source_text_included": False,
        "raw_vector_values_included": False,
        "endpoint_values_included": False,
        "credential_values_included": False,
        "service_urls_included": False,
        "values_redacted": True,
        "reindexed_chunk_count": 18,
        "vector_health_check_count": 2,
        "retrieval_quality_query_count": 5,
        "backup_restore_check_count": 1,
    }
    payload.update(overrides)
    return payload


def _write_private_summary(path: Path, **overrides) -> None:
    path.write_text(
        json.dumps(_runtime_summary_payload(**overrides), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _set_private_references(
    monkeypatch,
    renderer: ModuleType,
    summary_path: Path,
) -> dict[str, str]:
    values = {
        "RETRIEVAL_VECTOR_HEALTH_EVIDENCE_REF": "rv-health-ref-001",
        "RETRIEVAL_QUALITY_SMOKE_EVIDENCE_REF": "rv-quality-ref-001",
        "RETRIEVAL_VECTOR_REINDEX_AUDIT_EVIDENCE_REF": "rv-reindex-ref-001",
        renderer.DEFAULT_RUNTIME_SUMMARY_PATH_ENV: str(summary_path),
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def test_conservative_dry_run_redacts_values(tmp_path):
    renderer = _load_renderer()
    output_path = tmp_path / "retrieval-runtime-private.json"

    summary = renderer.render_private_evidence(
        renderer.RenderConfig(output_path=output_path, dry_run=True)
    )
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["dry_run"] is True
    assert summary["rendered"] is False
    assert summary["vector_backend_ready_if_validated"] is False
    assert summary["private_reference_values_included"] is False
    assert summary["raw_source_text_included"] is False
    assert summary["raw_vector_values_included"] is False
    assert "RETRIEVAL_VECTOR_HEALTH_EVIDENCE_REF" not in serialized
    assert not output_path.exists()


def test_approved_runtime_evidence_requires_attestations(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError) as exc_info:
        renderer.render_private_evidence(
            renderer.RenderConfig(
                output_path=tmp_path / "retrieval-runtime-private.json",
                approved_runtime_validation=True,
            )
        )

    assert "approved runtime evidence requires explicit attestations" in str(
        exc_info.value
    )


def test_approved_runtime_evidence_requires_private_summary_path(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError) as exc_info:
        renderer.render_private_evidence(
            _approved_config(renderer, tmp_path / "retrieval-runtime-private.json")
        )

    assert "private runtime summary path env var is required" in str(exc_info.value)


def test_approved_runtime_evidence_requires_private_references_without_emitting_them(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    summary_path = tmp_path / "retrieval-runtime-summary.json"
    _write_private_summary(summary_path)
    monkeypatch.setenv(renderer.DEFAULT_RUNTIME_SUMMARY_PATH_ENV, str(summary_path))
    raw_reference = "rv-health-ref-001"

    with pytest.raises(renderer.RenderError) as exc_info:
        renderer.render_private_evidence(
            _approved_config(renderer, tmp_path / "retrieval-runtime-private.json")
        )

    assert raw_reference not in str(exc_info.value)
    assert "private runtime evidence reference is required" in str(exc_info.value)


def test_approved_runtime_evidence_rejects_source_control_summary_path(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    monkeypatch.setenv(renderer.DEFAULT_RUNTIME_SUMMARY_PATH_ENV, str(RENDERER_SCRIPT))

    with pytest.raises(renderer.RenderError, match="outside source control"):
        renderer.render_private_evidence(
            _approved_config(renderer, tmp_path / "retrieval-runtime-private.json")
        )


def test_approved_runtime_evidence_rejects_incomplete_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    summary_path = tmp_path / "retrieval-runtime-summary.json"
    _write_private_summary(summary_path, retrieval_quality_smoke_passed=False)
    _set_private_references(monkeypatch, renderer, summary_path)

    with pytest.raises(
        renderer.RenderError,
        match="retrieval_quality_smoke_passed=true",
    ):
        renderer.render_private_evidence(
            _approved_config(renderer, tmp_path / "retrieval-runtime-private.json")
        )


def test_approved_runtime_evidence_rejects_summary_raw_value_flags(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    summary_path = tmp_path / "retrieval-runtime-summary.json"
    _write_private_summary(summary_path, raw_vector_values_included=True)
    _set_private_references(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="raw_vector_values_included=false"):
        renderer.render_private_evidence(
            _approved_config(renderer, tmp_path / "retrieval-runtime-private.json")
        )


def test_approved_runtime_evidence_rejects_unsupported_summary_fields(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    summary_path = tmp_path / "retrieval-runtime-summary.json"
    _write_private_summary(summary_path, raw_source_text=["redacted"])
    _set_private_references(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="unsupported fields"):
        renderer.render_private_evidence(
            _approved_config(renderer, tmp_path / "retrieval-runtime-private.json")
        )


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError) as exc_info:
        renderer.render_private_evidence(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "llm-distill" / "runtime-private.json"
            )
        )

    assert "refusing_to_write_inside_source_control" in str(exc_info.value)


def test_approved_runtime_evidence_writes_private_ready_packet_without_values(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    validator = _load_validator()
    output_path = tmp_path / "retrieval-runtime-private.json"
    summary_path = tmp_path / "retrieval-runtime-summary.json"
    _write_private_summary(summary_path)
    private_values = _set_private_references(monkeypatch, renderer, summary_path)

    summary = renderer.render_private_evidence(_approved_config(renderer, output_path))
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    report = validator.build_report(output_path)
    serialized_summary = json.dumps(summary, sort_keys=True)
    serialized_payload = json.dumps(payload, sort_keys=True)

    assert summary["rendered"] is True
    assert summary["vector_backend_ready_if_validated"] is True
    assert summary["private_reference_values_included"] is False
    assert summary["private_runtime_summary_checked"] is True
    assert summary["private_runtime_summary_path_env_configured"] is True
    assert summary["private_runtime_summary_path_value_included"] is False
    assert summary["private_runtime_summary_reindexed_chunk_count"] == 18
    assert summary["private_runtime_summary_vector_health_check_count"] == 2
    assert summary["private_runtime_summary_retrieval_quality_query_count"] == 5
    assert summary["private_runtime_summary_backup_restore_check_count"] == 1
    assert summary["private_runtime_summary_raw_values_included"] is False
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is True
    assert report["blocked_item_count"] == 0
    assert payload["runtime_validation"]["vector_backend_health_checked"] is True
    assert payload["runtime_validation"]["retrieval_quality_smoke_passed"] is True
    assert payload["runtime_validation"]["health_evidence_reference_configured"] is True
    assert (
        payload["private_runtime_summary_path_env"]
        == renderer.DEFAULT_RUNTIME_SUMMARY_PATH_ENV
    )
    assert payload["private_runtime_summary_path_value_included"] is False
    assert payload["private_runtime_summary_checked"] is True
    assert payload["private_runtime_summary_reindexed_chunk_count"] == 18
    assert str(summary_path) not in serialized_summary
    assert str(summary_path) not in serialized_payload
    for key, value in private_values.items():
        if key == renderer.DEFAULT_RUNTIME_SUMMARY_PATH_ENV:
            continue
        assert value not in serialized_summary
        assert value not in serialized_payload
