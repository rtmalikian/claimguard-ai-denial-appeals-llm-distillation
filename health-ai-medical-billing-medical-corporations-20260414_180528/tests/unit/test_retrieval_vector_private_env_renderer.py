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
    assert summary["values_redacted"] is True
    assert "RETRIEVAL_EMBEDDING_MODEL_APPROVED=true" in output_text
    assert "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=true" in output_text
    assert "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=true" in output_text
    for private_value in private_values.values():
        assert private_value in output_text
        assert private_value not in serialized


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "retrieval-vector.private.env",
            )
        )
