import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
RENDERER_SCRIPT = SCRIPT_DIR / "render_production_corpus_private_evidence.py"


def _load_renderer() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "render_production_corpus_private_evidence",
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
        approved_production_corpus=True,
        approved_non_synthetic_pair_attested=True,
        privacy_review_attested=True,
        license_review_attested=True,
        residual_risk_review_attested=True,
        training_scope_reviewed=True,
        no_phi_review_attested=True,
        source_license_scope_documented=True,
        pair_ids_reviewed_outside_source_control=True,
        source_documents_reviewed_outside_source_control=True,
        metadata_only_manifest_attested=True,
        no_raw_document_content_attested=True,
        no_raw_values_attested=True,
    )


def _set_private_references(
    monkeypatch,
    renderer: ModuleType,
    manifest_path: Path,
) -> dict[str, str]:
    values = {
        renderer.DEFAULT_PRIVATE_MANIFEST_PATH_ENV: str(manifest_path),
        renderer.DEFAULT_PRIVACY_REVIEW_REFERENCE_ENV: "PRIVACY-REVIEW-REF-TEST",
        renderer.DEFAULT_LICENSE_REVIEW_REFERENCE_ENV: "LICENSE-REVIEW-REF-TEST",
        renderer.DEFAULT_RESIDUAL_RISK_REVIEW_REFERENCE_ENV: (
            "RESIDUAL-RISK-REF-TEST"
        ),
        renderer.DEFAULT_TRAINING_SCOPE_REVIEW_REFERENCE_ENV: (
            "TRAINING-SCOPE-REF-TEST"
        ),
        renderer.DEFAULT_PAIR_SOURCE_REVIEW_REFERENCE_ENV: "PAIR-SOURCE-REF-TEST",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def _write_private_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "source_type": "real_deidentified_pair",
                        "document_role": "denial_letter",
                        "pair_id": "PAIR-PRIVATE-TEST",
                        "training_eligible": True,
                        "phi_status": "deidentified",
                        "review_status": "training_approved",
                    },
                    {
                        "source_type": "real_deidentified_pair",
                        "document_role": "appeal_letter",
                        "pair_id": "PAIR-PRIVATE-TEST",
                        "training_eligible": True,
                        "phi_status": "deidentified",
                        "review_status": "training_approved",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_private_summary(
    path: Path,
    *,
    overrides: dict | None = None,
) -> None:
    payload = {
        "approved_non_synthetic_pair_attested": True,
        "privacy_review_attested": True,
        "license_review_attested": True,
        "residual_risk_review_attested": True,
        "training_scope_reviewed": True,
        "no_phi_review_attested": True,
        "source_license_scope_documented": True,
        "pair_ids_reviewed_outside_source_control": True,
        "source_documents_reviewed_outside_source_control": True,
        "metadata_only_manifest_attested": True,
        "no_raw_document_content_attested": True,
        "no_raw_values_attested": True,
        "private_manifest_path_configured": True,
        "private_manifest_metadata_checked": True,
        "approved_non_synthetic_pair_metadata_ready": True,
        "no_phi_or_secret_values_attested": True,
        "values_redacted": True,
        "private_summary_path_value_included": False,
        "private_manifest_path_value_included": False,
        "approval_reference_value_included": False,
        "raw_private_values_included": False,
        "raw_document_content_included": False,
        "source_document_values_included": False,
        "pair_id_values_included": False,
        "source_paths_or_urls_included": False,
        "checksum_values_included": False,
        "credential_values_included": False,
        "phi_or_secret_values_included": False,
        "production_document_content_included": False,
        "private_manifest_record_count": 2,
        "private_manifest_candidate_role_count": 2,
        "private_manifest_complete_pair_count": 1,
        "private_reference_count": 5,
        "pair_review_count": 1,
        "source_document_review_count": 2,
        "privacy_review_count": 1,
        "license_review_count": 1,
        "residual_risk_review_count": 1,
        "training_scope_review_count": 1,
    }
    if overrides:
        payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_synthetic_only_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "source_type": "synthetic_deidentified_pair",
                        "document_role": "denial_letter",
                        "pair_id": "PAIR-SYNTHETIC-TEST",
                        "training_eligible": True,
                        "phi_status": "deidentified",
                        "review_status": "training_approved",
                    },
                    {
                        "source_type": "synthetic_deidentified_pair",
                        "document_role": "appeal_letter",
                        "pair_id": "PAIR-SYNTHETIC-TEST",
                        "training_eligible": True,
                        "phi_status": "deidentified",
                        "review_status": "training_approved",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


def test_conservative_dry_run_redacts_values(tmp_path):
    renderer = _load_renderer()
    output_path = tmp_path / "production-corpus.private.json"

    summary = renderer.render_private_evidence(
        renderer.RenderConfig(output_path=output_path, dry_run=True)
    )
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["dry_run"] is True
    assert summary["rendered"] is False
    assert summary["approved_production_corpus_requested"] is False
    assert summary["privacy_review_attested"] is False
    assert summary["pair_ids_reviewed_outside_source_control"] is False
    assert summary["source_documents_reviewed_outside_source_control"] is False
    assert summary["raw_private_values_included"] is False
    assert summary["approval_reference_value_included"] is False
    assert summary["raw_document_content_included"] is False
    assert "PRIVACY-REVIEW-REF-TEST" not in serialized
    assert not output_path.exists()


def test_approved_mode_requires_explicit_attestations(monkeypatch, tmp_path):
    renderer = _load_renderer()
    manifest_path = tmp_path / "private-manifest.json"
    _write_private_manifest(manifest_path)
    _set_private_references(monkeypatch, renderer, manifest_path)

    with pytest.raises(renderer.RenderError, match="explicit attestations"):
        renderer.render_private_evidence(
            renderer.RenderConfig(
                output_path=tmp_path / "production-corpus.private.json",
                approved_production_corpus=True,
            )
        )


def test_approved_mode_requires_private_manifest_path(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="private manifest path"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "production-corpus.private.json",
            )
        )


def test_approved_mode_rejects_source_control_manifest(monkeypatch, tmp_path):
    renderer = _load_renderer()
    source_control_manifest = (
        REPO_ROOT / "llm-distill" / "data" / "corpus" / "manifest.json"
    )
    _set_private_references(monkeypatch, renderer, source_control_manifest)

    with pytest.raises(renderer.RenderError, match="outside source control"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "production-corpus.private.json",
            )
        )


def test_approved_mode_rejects_synthetic_only_private_manifest(monkeypatch, tmp_path):
    renderer = _load_renderer()
    manifest_path = tmp_path / "private-manifest.json"
    _write_synthetic_only_manifest(manifest_path)
    _set_private_references(monkeypatch, renderer, manifest_path)

    with pytest.raises(renderer.RenderError, match="non-synthetic denial/appeal pair"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "production-corpus.private.json",
            )
        )


def test_approved_mode_rejects_private_manifest_without_complete_pair(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    manifest_path = tmp_path / "private-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "source_type": "real_deidentified_pair",
                        "document_role": "denial_letter",
                        "pair_id": "PAIR-PRIVATE-TEST",
                        "training_eligible": True,
                        "phi_status": "deidentified",
                        "review_status": "training_approved",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _set_private_references(monkeypatch, renderer, manifest_path)

    with pytest.raises(renderer.RenderError, match="non-synthetic denial/appeal pair"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "production-corpus.private.json",
            )
        )


def test_approved_mode_requires_private_summary_path(monkeypatch, tmp_path):
    renderer = _load_renderer()
    manifest_path = tmp_path / "private-manifest.json"
    _write_private_manifest(manifest_path)
    _set_private_references(monkeypatch, renderer, manifest_path)

    with pytest.raises(renderer.RenderError, match="production corpus summary path"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "production-corpus.private.json",
            )
        )


def test_approved_mode_rejects_source_control_private_summary(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    manifest_path = tmp_path / "private-manifest.json"
    _write_private_manifest(manifest_path)
    _set_private_references(monkeypatch, renderer, manifest_path)
    monkeypatch.setenv(
        renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV,
        str(REPO_ROOT / "PHIplan.md"),
    )

    with pytest.raises(renderer.RenderError, match="outside source control"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "production-corpus.private.json",
            )
        )


def test_approved_mode_rejects_incomplete_private_summary(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    manifest_path = tmp_path / "private-manifest.json"
    summary_path = tmp_path / "private-summary.json"
    _write_private_manifest(manifest_path)
    _write_private_summary(summary_path, overrides={"privacy_review_attested": False})
    _set_private_references(monkeypatch, renderer, manifest_path)
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(summary_path))

    with pytest.raises(
        renderer.RenderError,
        match="private production corpus summary requires privacy_review_attested=true",
    ):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "production-corpus.private.json",
            )
        )


def test_approved_mode_rejects_raw_value_private_summary_flag(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    manifest_path = tmp_path / "private-manifest.json"
    summary_path = tmp_path / "private-summary.json"
    _write_private_manifest(manifest_path)
    _write_private_summary(
        summary_path,
        overrides={"raw_document_content_included": True},
    )
    _set_private_references(monkeypatch, renderer, manifest_path)
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(summary_path))

    with pytest.raises(
        renderer.RenderError,
        match="private production corpus summary requires raw_document_content_included=false",
    ):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "production-corpus.private.json",
            )
        )


def test_approved_mode_rejects_private_summary_unsupported_fields(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    manifest_path = tmp_path / "private-manifest.json"
    summary_path = tmp_path / "private-summary.json"
    _write_private_manifest(manifest_path)
    _write_private_summary(summary_path, overrides={"approval_reference": "REF"})
    _set_private_references(monkeypatch, renderer, manifest_path)
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(summary_path))

    with pytest.raises(renderer.RenderError, match="unsupported fields"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "production-corpus.private.json",
            )
        )


def test_approved_mode_rejects_private_summary_count_mismatch(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    manifest_path = tmp_path / "private-manifest.json"
    summary_path = tmp_path / "private-summary.json"
    _write_private_manifest(manifest_path)
    _write_private_summary(
        summary_path,
        overrides={"private_manifest_record_count": 3},
    )
    _set_private_references(monkeypatch, renderer, manifest_path)
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(summary_path))

    with pytest.raises(renderer.RenderError, match="count mismatch"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "production-corpus.private.json",
            )
        )


def test_approved_mode_writes_private_evidence_and_redacts_values(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    manifest_path = tmp_path / "private-manifest.json"
    summary_path = tmp_path / "private-summary.json"
    _write_private_manifest(manifest_path)
    _write_private_summary(summary_path)
    private_values = _set_private_references(monkeypatch, renderer, manifest_path)
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(summary_path))
    output_path = tmp_path / "production-corpus.private.json"

    summary = renderer.render_private_evidence(
        _approved_config(renderer, output_path)
    )

    output_mode = stat.S_IMODE(output_path.stat().st_mode)
    output_text = output_path.read_text(encoding="utf-8")
    payload = json.loads(output_text)
    serialized_summary = json.dumps(summary, sort_keys=True)

    assert output_mode == 0o600
    assert summary["privacy_review_attested"] is True
    assert summary["license_review_attested"] is True
    assert summary["residual_risk_review_attested"] is True
    assert summary["training_scope_reviewed"] is True
    assert summary["approved_non_synthetic_pair_attested"] is True
    assert summary["pair_ids_reviewed_outside_source_control"] is True
    assert summary["source_documents_reviewed_outside_source_control"] is True
    assert summary["private_reference_count"] == len(private_values) - 1
    assert summary["private_manifest_path_env_configured"] is True
    assert summary["private_manifest_metadata_checked"] is True
    assert summary["private_manifest_record_count"] == 2
    assert summary["private_manifest_candidate_role_count"] == 2
    assert summary["private_manifest_complete_pair_count"] == 1
    assert summary["private_production_corpus_summary_checked"] is True
    assert summary["private_production_corpus_summary_path_env_configured"] is True
    assert summary["private_production_corpus_summary_path_value_included"] is False
    assert summary["private_production_corpus_summary_manifest_record_count"] == 2
    assert summary["private_production_corpus_summary_candidate_role_count"] == 2
    assert summary["private_production_corpus_summary_complete_pair_count"] == 1
    assert summary["private_production_corpus_summary_private_reference_count"] == 5
    assert summary["private_production_corpus_summary_pair_review_count"] == 1
    assert (
        summary["private_production_corpus_summary_source_document_review_count"]
        == 2
    )
    assert summary["private_production_corpus_summary_raw_values_included"] is False
    assert summary["private_manifest_path_value_included"] is False
    assert summary["values_redacted"] is True
    assert str(manifest_path) not in serialized_summary
    assert str(summary_path) not in serialized_summary
    assert str(manifest_path) not in output_text
    assert str(summary_path) not in output_text
    assert payload["evidence_status"] == "production_corpus_ready_private_review_complete"
    assert payload["manifest_path"] is None
    assert (
        payload["private_manifest_path_env"]
        == renderer.DEFAULT_PRIVATE_MANIFEST_PATH_ENV
    )
    assert (
        payload["private_summary_path_env"]
        == renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV
    )
    assert payload["private_manifest_path_configured"] is True
    assert payload["private_manifest_path_value_included"] is False
    assert payload["private_summary_path_configured"] is True
    assert payload["private_summary_path_value_included"] is False
    assert payload["private_manifest_metadata_checked"] is True
    assert payload["private_production_corpus_summary_checked"] is True
    assert payload["private_manifest_record_count"] == 2
    assert payload["private_manifest_candidate_role_count"] == 2
    assert payload["private_manifest_complete_pair_count"] == 1
    assert payload["corpus_review"]["privacy_review_attested"] is True
    assert payload["pairing_requirements"][
        "pair_ids_reviewed_outside_source_control"
    ] is True
    for key, private_value in private_values.items():
        assert private_value not in output_text
        assert private_value not in serialized_summary


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_evidence(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "production-corpus.private.json",
            )
        )
