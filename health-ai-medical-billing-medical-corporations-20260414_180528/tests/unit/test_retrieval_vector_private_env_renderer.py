import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
RENDERER_SCRIPT = SCRIPT_DIR / "render_retrieval_vector_private_env.py"
READY_EVIDENCE_REPORT_FIXTURE = (
    "health-ai-medical-billing-medical-corporations-20260414_180528/"
    "tests/fixtures/retrieval_vector_backend_ready_report.json"
)


def _load_renderer() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "render_retrieval_vector_private_env",
        RENDERER_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _approved_config(renderer: ModuleType, output_path: Path):
    return renderer.RenderConfig(
        output_path=output_path,
        approved_vector_backend=True,
        semantic_backend_attested=True,
        embedding_model_approved_attested=True,
        production_vector_backend_attested=True,
        hash_fallback_disabled_attested=True,
        reindex_completed_attested=True,
        vector_health_attested=True,
        retrieval_quality_smoke_attested=True,
        rollback_reviewed=True,
        no_raw_values_attested=True,
        evidence_report=READY_EVIDENCE_REPORT_FIXTURE,
    )


def _set_private_values(monkeypatch, renderer: ModuleType) -> dict[str, str]:
    values = {
        renderer.DEFAULT_EMBEDDING_BACKEND_ENV: "semantic_private_provider",
        renderer.DEFAULT_EMBEDDING_MODEL_ENV: "approved_embedding_model_v1",
        renderer.DEFAULT_VECTOR_BACKEND_ENV: "private_vector_store",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def _private_summary_payload(**overrides):
    payload = {
        "semantic_backend_attested": True,
        "embedding_model_approved_attested": True,
        "production_vector_backend_attested": True,
        "hash_fallback_disabled_attested": True,
        "reindex_completed_attested": True,
        "vector_health_attested": True,
        "retrieval_quality_smoke_attested": True,
        "rollback_reviewed": True,
        "evidence_report_ready": True,
        "private_backend_values_configured": True,
        "hash_backend_disabled": True,
        "hash_model_disabled": True,
        "local_vector_backend_disabled": True,
        "service_url_values_excluded": True,
        "no_raw_values_attested": True,
        "values_redacted": True,
        "private_summary_path_value_included": False,
        "embedding_backend_value_included": False,
        "embedding_model_value_included": False,
        "vector_backend_value_included": False,
        "raw_env_values_included": False,
        "raw_source_text_included": False,
        "raw_vector_values_included": False,
        "service_urls_included": False,
        "credential_values_included": False,
        "phi_or_secret_values_included": False,
        "production_document_content_included": False,
        "environment_variable_count": 6,
        "private_backend_value_count": 3,
        "evidence_report_count": 1,
        "reindex_review_count": 1,
        "vector_health_check_count": 1,
        "retrieval_quality_smoke_count": 1,
        "rollback_review_count": 1,
    }
    payload.update(overrides)
    return payload


def _write_private_summary(path: Path, **overrides) -> None:
    path.write_text(
        json.dumps(
            _private_summary_payload(**overrides),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _set_private_summary(monkeypatch, renderer: ModuleType, summary_path: Path) -> None:
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(summary_path))


def test_conservative_dry_run_redacts_values(tmp_path):
    renderer = _load_renderer()
    output_path = tmp_path / "retrieval-vector.private.env"

    summary = renderer.render_private_env(
        renderer.RenderConfig(output_path=output_path, dry_run=True)
    )
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["dry_run"] is True
    assert summary["rendered"] is False
    assert summary["approved_vector_backend_requested"] is False
    assert summary["semantic_backend_configured"] is False
    assert summary["embedding_model_approved"] is False
    assert summary["production_vector_backend_configured"] is False
    assert summary["hash_fallback_disabled_for_production"] is False
    assert summary["hash_embedding_backend_active"] is True
    assert summary["evidence_report_checked"] is False
    assert summary["evidence_report_ready"] is False
    assert summary["private_retrieval_vector_summary_checked"] is False
    assert summary["private_retrieval_vector_summary_path_value_included"] is False
    assert summary["private_retrieval_vector_summary_raw_values_included"] is False
    assert summary["raw_env_values_included"] is False
    assert summary["embedding_backend_value_included"] is False
    assert summary["embedding_model_value_included"] is False
    assert summary["vector_backend_value_included"] is False
    assert "semantic_private_provider" not in serialized
    assert not output_path.exists()


def test_approved_mode_requires_explicit_attestations(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)

    with pytest.raises(renderer.RenderError, match="explicit attestations"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "retrieval-vector.private.env",
                approved_vector_backend=True,
            )
        )


def test_approved_mode_requires_private_backend_values(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="embedding backend"):
        renderer.render_private_env(
            _approved_config(
                renderer,
                tmp_path / "retrieval-vector.private.env",
            )
        )


def test_approved_mode_requires_ready_evidence_report(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)

    with pytest.raises(renderer.RenderError, match="retrieval vector evidence report is not ready"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "retrieval-vector.private.env",
                approved_vector_backend=True,
                semantic_backend_attested=True,
                embedding_model_approved_attested=True,
                production_vector_backend_attested=True,
                hash_fallback_disabled_attested=True,
                reindex_completed_attested=True,
                vector_health_attested=True,
                retrieval_quality_smoke_attested=True,
                rollback_reviewed=True,
                no_raw_values_attested=True,
            )
        )


def test_approved_mode_requires_private_summary_path(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)

    with pytest.raises(
        renderer.RenderError,
        match="private retrieval vector summary path env var is required",
    ):
        renderer.render_private_env(
            _approved_config(
                renderer,
                tmp_path / "retrieval-vector.private.env",
            )
        )


def test_approved_mode_rejects_source_control_summary_path(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    _set_private_summary(monkeypatch, renderer, RENDERER_SCRIPT)

    with pytest.raises(renderer.RenderError, match="outside source control"):
        renderer.render_private_env(
            _approved_config(
                renderer,
                tmp_path / "retrieval-vector.private.env",
            )
        )


def test_approved_mode_rejects_incomplete_private_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    summary_path = tmp_path / "retrieval-vector-summary.json"
    _write_private_summary(summary_path, service_url_values_excluded=False)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(
        renderer.RenderError,
        match="service_url_values_excluded=true",
    ):
        renderer.render_private_env(
            _approved_config(
                renderer,
                tmp_path / "retrieval-vector.private.env",
            )
        )


def test_approved_mode_rejects_private_summary_raw_value_flags(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    summary_path = tmp_path / "retrieval-vector-summary.json"
    _write_private_summary(summary_path, raw_vector_values_included=True)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="raw_vector_values_included=false"):
        renderer.render_private_env(
            _approved_config(
                renderer,
                tmp_path / "retrieval-vector.private.env",
            )
        )


def test_approved_mode_rejects_unsupported_private_summary_fields(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    summary_path = tmp_path / "retrieval-vector-summary.json"
    _write_private_summary(summary_path, vector_backend="redacted")
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="unsupported fields"):
        renderer.render_private_env(
            _approved_config(
                renderer,
                tmp_path / "retrieval-vector.private.env",
            )
        )


def test_approved_mode_rejects_private_summary_count_mismatch(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    summary_path = tmp_path / "retrieval-vector-summary.json"
    _write_private_summary(summary_path, environment_variable_count=7)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="environment variable count mismatch"):
        renderer.render_private_env(
            _approved_config(
                renderer,
                tmp_path / "retrieval-vector.private.env",
            )
        )


def test_approved_mode_rejects_hash_or_url_like_values(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    monkeypatch.setenv(renderer.DEFAULT_EMBEDDING_BACKEND_ENV, "hash")

    with pytest.raises(renderer.RenderError, match="hash embedding backend"):
        renderer.render_private_env(
            _approved_config(
                renderer,
                tmp_path / "retrieval-vector.private.env",
            )
        )

    monkeypatch.setenv(renderer.DEFAULT_EMBEDDING_BACKEND_ENV, "https://example.invalid")
    with pytest.raises(renderer.RenderError, match="service URLs"):
        renderer.render_private_env(
            _approved_config(
                renderer,
                tmp_path / "retrieval-vector.private.env",
            )
        )


def test_approved_mode_writes_private_env_and_redacts_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    private_values = _set_private_values(monkeypatch, renderer)
    summary_path = tmp_path / "retrieval-vector-summary.json"
    _write_private_summary(summary_path)
    _set_private_summary(monkeypatch, renderer, summary_path)
    output_path = tmp_path / "retrieval-vector.private.env"

    summary = renderer.render_private_env(
        _approved_config(renderer, output_path)
    )

    output_mode = stat.S_IMODE(output_path.stat().st_mode)
    output_text = output_path.read_text(encoding="utf-8")
    serialized = json.dumps(summary, sort_keys=True)

    assert output_mode == 0o600
    assert summary["semantic_backend_configured"] is True
    assert summary["embedding_model_configured"] is True
    assert summary["embedding_model_approved"] is True
    assert summary["production_vector_backend_configured"] is True
    assert summary["hash_fallback_disabled_for_production"] is True
    assert summary["hash_embedding_backend_active"] is False
    assert summary["hash_embedding_model_active"] is False
    assert summary["evidence_report_checked"] is True
    assert summary["evidence_report_ready"] is True
    assert summary["private_retrieval_vector_summary_checked"] is True
    assert summary["private_retrieval_vector_summary_path_env_configured"] is True
    assert summary["private_retrieval_vector_summary_path_value_included"] is False
    assert summary["private_retrieval_vector_summary_environment_variable_count"] == 6
    assert summary["private_retrieval_vector_summary_backend_value_count"] == 3
    assert summary["private_retrieval_vector_summary_evidence_report_count"] == 1
    assert summary["private_retrieval_vector_summary_reindex_review_count"] == 1
    assert summary["private_retrieval_vector_summary_health_check_count"] == 1
    assert summary["private_retrieval_vector_summary_quality_smoke_count"] == 1
    assert summary["private_retrieval_vector_summary_rollback_review_count"] == 1
    assert summary["private_retrieval_vector_summary_raw_values_included"] is False
    assert summary["values_redacted"] is True
    assert "RETRIEVAL_EMBEDDING_MODEL_APPROVED=true" in output_text
    assert "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=true" in output_text
    assert "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=true" in output_text
    for private_value in private_values.values():
        assert private_value in output_text
        assert private_value not in serialized
    assert str(summary_path) not in output_text
    assert str(summary_path) not in serialized


def test_evidence_report_path_must_stay_inside_source_control(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="inside source control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "retrieval-vector.private.env",
                evidence_report="../private-retrieval-vector-report.json",
            )
        )


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "retrieval-vector.private.env",
            )
        )
