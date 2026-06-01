import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
VALIDATOR_SCRIPT = SCRIPT_DIR / "validate_retrieval_vector_backend.py"


def _load_validator() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "validate_retrieval_vector_backend",
        VALIDATOR_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _requirement(report: dict, requirement_id: str) -> dict:
    return next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == requirement_id
    )


def _allow_tmp_source_control_path(monkeypatch, validator: ModuleType, path: Path) -> None:
    original_path_is_within = validator.path_is_within
    allowed_path = path.resolve()

    def path_is_within(candidate: Path, parent: Path) -> bool:
        if candidate.resolve() == allowed_path:
            return True
        return original_path_is_within(candidate, parent)

    monkeypatch.setattr(validator, "path_is_within", path_is_within)


def _write_marker_file(path: Path, markers: tuple[str, ...], unique_text: str) -> None:
    path.write_text("\n".join([*markers, unique_text, ""]), encoding="utf-8")


def _ready_evidence() -> dict:
    return {
        "artifact": "claimguard_retrieval_vector_backend_evidence",
        "version": "1.0",
        "evidence_status": "ready_for_private_operator_review",
        "prepared_at": "2026-05-30T18:54:28-07:00",
        "no_phi_or_secret_values_attested": True,
        "no_source_text_or_vector_values_attested": True,
        "private_runtime_summary_path_configured": True,
        "private_runtime_summary_path_value_included": False,
        "private_runtime_summary_checked": True,
        "private_runtime_summary_reindexed_chunk_count": 18,
        "private_runtime_summary_vector_health_check_count": 2,
        "private_runtime_summary_retrieval_quality_query_count": 5,
        "private_runtime_summary_backup_restore_check_count": 1,
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
            "semantic_backend_configured": True,
            "embedding_model_configured": True,
            "embedding_model_approved": True,
            "production_vector_backend_configured": True,
            "hash_fallback_disabled_for_production": True,
            "contains_secrets": False,
        },
        "index_state": {
            "source_control_reindex_checklist_documented": True,
            "source_control_reindex_checklist_path": (
                "llm-distill/docs/retrieval-vector-reindex-checklist.md"
            ),
            "application_reindex_operation_available": True,
            "active_retrieval_chunks_indexed": True,
            "stored_hash_embeddings_absent": True,
            "reindex_job_completed": True,
            "reindex_audit_checked": True,
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
            "runtime_private_evidence_renderer_path": (
                "llm-distill/scripts/"
                "render_retrieval_vector_runtime_private_evidence.py"
            ),
            "vector_backend_health_checked": True,
            "retrieval_quality_smoke_passed": True,
            "backup_restore_reviewed": True,
            "disable_or_rollback_path_reviewed": True,
            "health_evidence_reference_configured": True,
            "quality_evidence_reference_configured": True,
            "reindex_evidence_reference_configured": True,
        },
    }


def test_vector_backend_template_is_safe_to_review_but_not_ready():
    validator = _load_validator()
    template_path = (
        REPO_ROOT
        / "llm-distill"
        / "data"
        / "retrieval_vector_backend"
        / "vector_backend_evidence.template.json"
    )

    report = validator.build_report(template_path)

    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert "retrieval_vector_backend_no_phi_secret_or_values" not in blocked_ids
    assert "retrieval_vector_backend_configuration" in blocked_ids
    assert "retrieval_vector_backend_private_env_renderer" not in blocked_ids
    assert "retrieval_vector_backend_private_provider_loader" not in blocked_ids
    assert "retrieval_vector_backend_operator_runbook" not in blocked_ids
    assert "retrieval_vector_backend_reindex_checklist" not in blocked_ids
    assert "retrieval_vector_backend_index_state" in blocked_ids
    assert "retrieval_vector_backend_runtime_smoke_checklist" not in blocked_ids
    assert (
        "retrieval_vector_backend_runtime_private_evidence_renderer"
        not in blocked_ids
    )
    assert "retrieval_vector_backend_runtime_validation" in blocked_ids
    private_renderer_requirement = _requirement(
        report,
        "retrieval_vector_backend_private_env_renderer",
    )
    assert private_renderer_requirement["status"] == "ready"
    assert (
        private_renderer_requirement["evidence"][
            "source_control_private_env_renderer_documented"
        ]
        is True
    )
    assert private_renderer_requirement["evidence"]["private_env_renderer_exists"] is True
    assert (
        private_renderer_requirement["evidence"][
            "private_env_renderer_inside_source_control"
        ]
        is True
    )
    assert private_renderer_requirement["evidence"]["missing_marker_count"] == 0
    assert private_renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert private_renderer_requirement["evidence"]["raw_env_values_included"] is False
    private_loader_requirement = _requirement(
        report,
        "retrieval_vector_backend_private_provider_loader",
    )
    assert private_loader_requirement["status"] == "ready"
    assert (
        private_loader_requirement["evidence"][
            "source_control_private_embedding_provider_loader_documented"
        ]
        is True
    )
    assert (
        private_loader_requirement["evidence"][
            "private_embedding_provider_loader_exists"
        ]
        is True
    )
    assert (
        private_loader_requirement["evidence"][
            "private_embedding_provider_loader_inside_source_control"
        ]
        is True
    )
    assert private_loader_requirement["evidence"]["missing_marker_count"] == 0
    assert private_loader_requirement["evidence"]["raw_loader_text_included"] is False
    assert (
        private_loader_requirement["evidence"][
            "raw_endpoint_or_token_values_included"
        ]
        is False
    )
    assert (
        private_loader_requirement["evidence"][
            "raw_source_text_or_vector_values_included"
        ]
        is False
    )
    runbook_requirement = _requirement(
        report,
        "retrieval_vector_backend_operator_runbook",
    )
    assert runbook_requirement["status"] == "ready"
    assert runbook_requirement["evidence"]["source_control_runbook_documented"] is True
    assert runbook_requirement["evidence"]["runbook_exists"] is True
    assert runbook_requirement["evidence"]["runbook_inside_source_control"] is True
    assert runbook_requirement["evidence"]["missing_marker_count"] == 0
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False
    checklist_requirement = _requirement(
        report,
        "retrieval_vector_backend_reindex_checklist",
    )
    assert checklist_requirement["status"] == "ready"
    assert (
        checklist_requirement["evidence"]["source_control_reindex_checklist_documented"]
        is True
    )
    assert checklist_requirement["evidence"]["checklist_exists"] is True
    assert (
        checklist_requirement["evidence"]["reindex_checklist_inside_source_control"]
        is True
    )
    assert checklist_requirement["evidence"]["missing_marker_count"] == 0
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    runtime_smoke_requirement = _requirement(
        report,
        "retrieval_vector_backend_runtime_smoke_checklist",
    )
    assert runtime_smoke_requirement["status"] == "ready"
    assert (
        runtime_smoke_requirement["evidence"][
            "source_control_runtime_smoke_checklist_documented"
        ]
        is True
    )
    assert runtime_smoke_requirement["evidence"]["checklist_exists"] is True
    assert (
        runtime_smoke_requirement["evidence"][
            "runtime_smoke_checklist_inside_source_control"
        ]
        is True
    )
    assert runtime_smoke_requirement["evidence"]["missing_marker_count"] == 0
    assert runtime_smoke_requirement["evidence"]["raw_checklist_text_included"] is False
    runtime_private_renderer_requirement = _requirement(
        report,
        "retrieval_vector_backend_runtime_private_evidence_renderer",
    )
    assert runtime_private_renderer_requirement["status"] == "ready"
    assert (
        runtime_private_renderer_requirement["evidence"][
            "source_control_runtime_private_evidence_renderer_documented"
        ]
        is True
    )
    assert (
        runtime_private_renderer_requirement["evidence"][
            "runtime_private_evidence_renderer_inside_source_control"
        ]
        is True
    )
    assert (
        runtime_private_renderer_requirement["evidence"][
            "runtime_private_evidence_renderer_exists"
        ]
        is True
    )
    assert runtime_private_renderer_requirement["evidence"]["missing_marker_count"] == 0
    assert (
        runtime_private_renderer_requirement["evidence"]["raw_renderer_text_included"]
        is False
    )
    assert (
        runtime_private_renderer_requirement["evidence"][
            "raw_private_reference_values_included"
        ]
        is False
    )
    governance_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "retrieval_vector_backend_governance"
    )
    assert "source_control_runbook_not_documented" not in governance_requirement["blockers"]
    assert governance_requirement["evidence"]["source_control_runbook_documented"] is True
    runtime_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "retrieval_vector_backend_runtime_validation"
    )
    assert "backup_restore_not_reviewed" not in runtime_requirement["blockers"]
    assert "disable_or_rollback_path_not_reviewed" not in runtime_requirement["blockers"]
    assert runtime_requirement["evidence"]["backup_restore_reviewed"] is True
    assert runtime_requirement["evidence"]["disable_or_rollback_path_reviewed"] is True
    assert (
        "health_evidence_reference_not_configured"
        in runtime_requirement["blockers"]
    )
    assert (
        "private_runtime_summary_not_checked"
        in runtime_requirement["blockers"]
    )
    index_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "retrieval_vector_backend_index_state"
    )
    assert (
        "application_reindex_operation_not_available"
        not in index_requirement["blockers"]
    )
    assert index_requirement["evidence"]["application_reindex_operation_available"] is True


def test_vector_backend_private_env_renderer_markers_are_required_when_documented(
    tmp_path,
    monkeypatch,
):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    renderer_path = tmp_path / "render_retrieval_vector_private_env.py"
    renderer_path.write_text(
        "#!/usr/bin/env python3\nprint('not a safe renderer')\n",
        encoding="utf-8",
    )
    _allow_tmp_source_control_path(monkeypatch, validator, renderer_path)
    evidence = _ready_evidence()
    evidence["backend_configuration"]["source_control_private_env_renderer_path"] = str(
        renderer_path
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    renderer_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "retrieval_vector_backend_private_env_renderer"
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert (
        "source_control_private_env_renderer_required_markers_missing"
        in renderer_requirement["blockers"]
    )
    assert renderer_requirement["evidence"]["private_env_renderer_exists"] is True
    assert renderer_requirement["evidence"]["missing_marker_count"] > 0
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert "not a safe renderer" not in serialized


def test_vector_backend_private_provider_loader_markers_are_required_when_documented(
    tmp_path,
    monkeypatch,
):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    loader_path = tmp_path / "retrieval_semantic_provider.py"
    loader_text = "class PrivateSemanticEmbeddingProvider: pass\n"
    loader_path.write_text(loader_text, encoding="utf-8")
    _allow_tmp_source_control_path(monkeypatch, validator, loader_path)
    evidence = _ready_evidence()
    evidence["backend_configuration"][
        "source_control_private_embedding_provider_loader_path"
    ] = str(loader_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    loader_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "retrieval_vector_backend_private_provider_loader"
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert (
        "source_control_private_embedding_provider_loader_required_markers_missing"
        in loader_requirement["blockers"]
    )
    assert (
        loader_requirement["evidence"]["private_embedding_provider_loader_exists"]
        is True
    )
    assert loader_requirement["evidence"]["missing_marker_count"] > 0
    assert loader_requirement["evidence"]["raw_loader_text_included"] is False
    assert loader_text.strip() not in serialized


def test_vector_backend_runtime_private_renderer_markers_are_required_when_documented(
    tmp_path,
    monkeypatch,
):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    renderer_path = tmp_path / "render_retrieval_vector_runtime_private_evidence.py"
    renderer_text = "class RenderConfig: pass\n"
    renderer_path.write_text(renderer_text, encoding="utf-8")
    _allow_tmp_source_control_path(monkeypatch, validator, renderer_path)
    evidence = _ready_evidence()
    evidence["runtime_validation"][
        "runtime_private_evidence_renderer_path"
    ] = str(renderer_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    renderer_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"]
        == "retrieval_vector_backend_runtime_private_evidence_renderer"
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert (
        "source_control_runtime_private_evidence_renderer_required_markers_missing"
        in renderer_requirement["blockers"]
    )
    assert (
        renderer_requirement["evidence"][
            "runtime_private_evidence_renderer_exists"
        ]
        is True
    )
    assert renderer_requirement["evidence"]["missing_marker_count"] > 0
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert renderer_text.strip() not in serialized


def test_retrieval_private_env_renderer_must_stay_inside_source_control(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    renderer_path = tmp_path / "render_retrieval_vector_private_env.py"
    unique_text = "outside private env renderer marker should not leak"
    _write_marker_file(
        renderer_path,
        validator.PRIVATE_ENV_RENDERER_REQUIRED_MARKERS,
        unique_text,
    )
    evidence = _ready_evidence()
    evidence["backend_configuration"]["source_control_private_env_renderer_path"] = str(
        renderer_path
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    renderer_requirement = _requirement(
        report,
        "retrieval_vector_backend_private_env_renderer",
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert (
        "source_control_private_env_renderer_must_be_inside_repo"
        in renderer_requirement["blockers"]
    )
    assert (
        "source_control_private_env_renderer_required_markers_missing"
        not in renderer_requirement["blockers"]
    )
    assert renderer_requirement["evidence"]["private_env_renderer_exists"] is True
    assert (
        renderer_requirement["evidence"]["private_env_renderer_inside_source_control"]
        is False
    )
    assert renderer_requirement["evidence"]["present_marker_count"] == 0
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert unique_text not in serialized


def test_retrieval_private_provider_loader_must_stay_inside_source_control(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    loader_path = tmp_path / "retrieval_semantic_provider.py"
    unique_text = "outside private provider loader marker should not leak"
    _write_marker_file(
        loader_path,
        validator.PRIVATE_PROVIDER_LOADER_REQUIRED_MARKERS,
        unique_text,
    )
    evidence = _ready_evidence()
    evidence["backend_configuration"][
        "source_control_private_embedding_provider_loader_path"
    ] = str(loader_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    loader_requirement = _requirement(
        report,
        "retrieval_vector_backend_private_provider_loader",
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert (
        "source_control_private_embedding_provider_loader_must_be_inside_repo"
        in loader_requirement["blockers"]
    )
    assert (
        "source_control_private_embedding_provider_loader_required_markers_missing"
        not in loader_requirement["blockers"]
    )
    assert (
        loader_requirement["evidence"]["private_embedding_provider_loader_exists"]
        is True
    )
    assert (
        loader_requirement["evidence"][
            "private_embedding_provider_loader_inside_source_control"
        ]
        is False
    )
    assert loader_requirement["evidence"]["present_marker_count"] == 0
    assert loader_requirement["evidence"]["raw_loader_text_included"] is False
    assert unique_text not in serialized


def test_retrieval_operator_runbook_must_stay_inside_source_control(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    runbook_path = tmp_path / "retrieval-vector-backend-runbook.md"
    unique_text = "outside retrieval runbook marker should not leak"
    _write_marker_file(runbook_path, validator.RUNBOOK_REQUIRED_MARKERS, unique_text)
    evidence = _ready_evidence()
    evidence["governance_controls"]["source_control_runbook_path"] = str(runbook_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    runbook_requirement = _requirement(
        report,
        "retrieval_vector_backend_operator_runbook",
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert "source_control_runbook_must_be_inside_repo" in runbook_requirement["blockers"]
    assert (
        "source_control_runbook_required_markers_missing"
        not in runbook_requirement["blockers"]
    )
    assert runbook_requirement["evidence"]["runbook_exists"] is True
    assert runbook_requirement["evidence"]["runbook_inside_source_control"] is False
    assert runbook_requirement["evidence"]["present_marker_count"] == 0
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False
    assert unique_text not in serialized


def test_retrieval_reindex_checklist_must_stay_inside_source_control(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    checklist_path = tmp_path / "retrieval-vector-reindex-checklist.md"
    unique_text = "outside reindex checklist marker should not leak"
    _write_marker_file(
        checklist_path,
        validator.REINDEX_CHECKLIST_REQUIRED_MARKERS,
        unique_text,
    )
    evidence = _ready_evidence()
    evidence["index_state"]["source_control_reindex_checklist_path"] = str(
        checklist_path
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    checklist_requirement = _requirement(
        report,
        "retrieval_vector_backend_reindex_checklist",
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert (
        "source_control_reindex_checklist_must_be_inside_repo"
        in checklist_requirement["blockers"]
    )
    assert (
        "source_control_reindex_checklist_required_markers_missing"
        not in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["checklist_exists"] is True
    assert (
        checklist_requirement["evidence"]["reindex_checklist_inside_source_control"]
        is False
    )
    assert checklist_requirement["evidence"]["present_marker_count"] == 0
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert unique_text not in serialized


def test_retrieval_runtime_smoke_checklist_must_stay_inside_source_control(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    checklist_path = tmp_path / "retrieval-vector-runtime-smoke-checklist.md"
    unique_text = "outside runtime smoke checklist marker should not leak"
    _write_marker_file(
        checklist_path,
        validator.RUNTIME_SMOKE_CHECKLIST_REQUIRED_MARKERS,
        unique_text,
    )
    evidence = _ready_evidence()
    evidence["runtime_validation"]["source_control_runtime_smoke_checklist_path"] = str(
        checklist_path
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    checklist_requirement = _requirement(
        report,
        "retrieval_vector_backend_runtime_smoke_checklist",
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert (
        "source_control_runtime_smoke_checklist_must_be_inside_repo"
        in checklist_requirement["blockers"]
    )
    assert (
        "source_control_runtime_smoke_checklist_required_markers_missing"
        not in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["checklist_exists"] is True
    assert (
        checklist_requirement["evidence"][
            "runtime_smoke_checklist_inside_source_control"
        ]
        is False
    )
    assert checklist_requirement["evidence"]["present_marker_count"] == 0
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert unique_text not in serialized


def test_retrieval_runtime_private_evidence_renderer_must_stay_inside_source_control(
    tmp_path,
):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    renderer_path = tmp_path / "render_retrieval_vector_runtime_private_evidence.py"
    unique_text = "outside runtime private renderer marker should not leak"
    _write_marker_file(
        renderer_path,
        validator.RUNTIME_PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS,
        unique_text,
    )
    evidence = _ready_evidence()
    evidence["runtime_validation"][
        "runtime_private_evidence_renderer_path"
    ] = str(renderer_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    renderer_requirement = _requirement(
        report,
        "retrieval_vector_backend_runtime_private_evidence_renderer",
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert (
        "source_control_runtime_private_evidence_renderer_must_be_inside_repo"
        in renderer_requirement["blockers"]
    )
    assert (
        "source_control_runtime_private_evidence_renderer_required_markers_missing"
        not in renderer_requirement["blockers"]
    )
    assert (
        renderer_requirement["evidence"]["runtime_private_evidence_renderer_exists"]
        is True
    )
    assert (
        renderer_requirement["evidence"][
            "runtime_private_evidence_renderer_inside_source_control"
        ]
        is False
    )
    assert renderer_requirement["evidence"]["present_marker_count"] == 0
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert unique_text not in serialized


def test_ready_vector_backend_evidence_passes_all_requirements(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    _write_json(evidence_path, _ready_evidence())

    report = validator.build_report(evidence_path)

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is True
    assert report["blocked_item_count"] == 0


def test_vector_backend_evidence_blocks_missing_private_runtime_references(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    evidence = _ready_evidence()
    evidence["runtime_validation"]["health_evidence_reference_configured"] = False
    evidence["runtime_validation"]["quality_evidence_reference_configured"] = False
    evidence["runtime_validation"]["reindex_evidence_reference_configured"] = False
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    runtime_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "retrieval_vector_backend_runtime_validation"
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert "health_evidence_reference_not_configured" in runtime_requirement["blockers"]
    assert "quality_evidence_reference_not_configured" in runtime_requirement["blockers"]
    assert "reindex_evidence_reference_not_configured" in runtime_requirement["blockers"]
    assert runtime_requirement["evidence"]["private_runtime_reference_values_included"] is False


def test_vector_backend_evidence_blocks_missing_private_runtime_summary(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    evidence = _ready_evidence()
    evidence["private_runtime_summary_path_configured"] = False
    evidence["private_runtime_summary_checked"] = False
    evidence["private_runtime_summary_reindexed_chunk_count"] = 0
    evidence["private_runtime_summary_vector_health_check_count"] = 0
    evidence["private_runtime_summary_retrieval_quality_query_count"] = 0
    evidence["private_runtime_summary_backup_restore_check_count"] = 0
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    runtime_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "retrieval_vector_backend_runtime_validation"
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert "private_runtime_summary_path_not_configured" in runtime_requirement["blockers"]
    assert "private_runtime_summary_not_checked" in runtime_requirement["blockers"]
    assert (
        "private_runtime_summary_reindexed_chunk_count_missing"
        in runtime_requirement["blockers"]
    )
    assert (
        runtime_requirement["evidence"]["private_runtime_summary_path_value_included"]
        is False
    )
    assert (
        runtime_requirement["evidence"]["private_runtime_summary_raw_values_included"]
        is False
    )


def test_vector_backend_evidence_blocks_private_runtime_summary_value_leak(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    evidence = _ready_evidence()
    evidence["private_runtime_summary_path_value_included"] = True
    evidence["private_runtime_summary_raw_values_included"] = True
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    runtime_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "retrieval_vector_backend_runtime_validation"
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert "private_runtime_summary_path_value_included" in runtime_requirement["blockers"]
    assert "private_runtime_summary_raw_values_included" in runtime_requirement["blockers"]
    assert (
        runtime_requirement["evidence"]["private_runtime_summary_path_value_included"]
        is True
    )
    assert (
        runtime_requirement["evidence"]["private_runtime_summary_raw_values_included"]
        is True
    )


def test_vector_backend_evidence_blocks_hash_fallback(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    evidence = _ready_evidence()
    evidence["backend_configuration"]["hash_fallback_disabled_for_production"] = False
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)

    assert report["vector_backend_ready"] is False
    assert "hash_fallback_not_disabled_for_production" in serialized


def test_vector_backend_evidence_blocks_raw_vector_values_without_emitting_them(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    raw_vector = [0.125, 0.25, 0.5]
    evidence = _ready_evidence()
    evidence["vector_values"] = raw_vector
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)

    assert report["safe_to_review"] is False
    assert report["vector_backend_ready"] is False
    assert "raw vector, source text, secret, or document value key is not allowed" in serialized
    assert "0.125" not in serialized


def test_vector_backend_evidence_blocks_incomplete_runbook_without_emitting_text(
    tmp_path,
    monkeypatch,
):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    incomplete_runbook = tmp_path / "retrieval-vector-runbook.md"
    raw_runbook_text = "ClaimGuard AI is architected by Raphael Malikian"
    incomplete_runbook.write_text(raw_runbook_text, encoding="utf-8")
    _allow_tmp_source_control_path(monkeypatch, validator, incomplete_runbook)
    evidence = _ready_evidence()
    evidence["governance_controls"]["source_control_runbook_path"] = str(incomplete_runbook)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    runbook_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "retrieval_vector_backend_operator_runbook"
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert "source_control_runbook_required_markers_missing" in runbook_requirement["blockers"]
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False
    assert raw_runbook_text not in serialized


def test_vector_backend_evidence_blocks_incomplete_reindex_checklist_without_emitting_text(
    tmp_path,
    monkeypatch,
):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    incomplete_checklist = tmp_path / "retrieval-vector-reindex-checklist.md"
    raw_checklist_text = "ClaimGuard AI is architected by Raphael Malikian"
    incomplete_checklist.write_text(raw_checklist_text, encoding="utf-8")
    _allow_tmp_source_control_path(monkeypatch, validator, incomplete_checklist)
    evidence = _ready_evidence()
    evidence["index_state"]["source_control_reindex_checklist_path"] = str(
        incomplete_checklist
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "retrieval_vector_backend_reindex_checklist"
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert (
        "source_control_reindex_checklist_required_markers_missing"
        in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert raw_checklist_text not in serialized


def test_vector_backend_evidence_blocks_incomplete_runtime_smoke_checklist_without_emitting_text(
    tmp_path,
    monkeypatch,
):
    validator = _load_validator()
    evidence_path = tmp_path / "vector_backend_evidence.json"
    incomplete_checklist = tmp_path / "retrieval-vector-runtime-smoke-checklist.md"
    raw_checklist_text = "ClaimGuard AI is architected by Raphael Malikian"
    incomplete_checklist.write_text(raw_checklist_text, encoding="utf-8")
    _allow_tmp_source_control_path(monkeypatch, validator, incomplete_checklist)
    evidence = _ready_evidence()
    evidence["runtime_validation"]["source_control_runtime_smoke_checklist_path"] = str(
        incomplete_checklist
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "retrieval_vector_backend_runtime_smoke_checklist"
    )

    assert report["safe_to_review"] is True
    assert report["vector_backend_ready"] is False
    assert (
        "source_control_runtime_smoke_checklist_required_markers_missing"
        in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert raw_checklist_text not in serialized
