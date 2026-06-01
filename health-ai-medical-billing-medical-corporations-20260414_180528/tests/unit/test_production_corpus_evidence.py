import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
VALIDATOR_SCRIPT = SCRIPT_DIR / "validate_production_corpus_evidence.py"


def _load_validator() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "validate_production_corpus_evidence",
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


def _write_marker_file(
    path: Path,
    markers: tuple[str, ...],
    unique_text: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([*markers, unique_text]), encoding="utf-8")


def _requirement(report: dict, requirement_id: str) -> dict:
    return next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == requirement_id
    )


def _allow_tmp_source_control_path(
    monkeypatch,
    validator: ModuleType,
    path: Path,
) -> None:
    original_path_is_within = validator.path_is_within
    allowed_path = path.resolve()

    def path_is_within(candidate: Path, parent: Path) -> bool:
        if candidate.resolve() == allowed_path:
            return True
        return original_path_is_within(candidate, parent)

    monkeypatch.setattr(validator, "path_is_within", path_is_within)


def _record(*, role: str, source_type: str = "real_deidentified_pair") -> dict:
    return {
        "source_id": f"SRC-PAIR-REAL-1-{role}",
        "document_id": f"DOC-PAIR-REAL-1-{role}",
        "pair_id": "PAIR-REAL-1",
        "source_type": source_type,
        "document_role": role,
        "source_url_or_path": "private-review://redacted",
        "checksum": f"sha256:synthetic-test-{role}",
        "phi_status": "deidentified",
        "deidentification_status": "training_eligible",
        "license_status": "approved",
        "review_status": "training_approved",
        "residual_risk_score": 0.0,
        "training_eligible": True,
        "split": "train",
        "micro_skill_ids": ["MS01"],
    }


def _ready_evidence(manifest_path: Path | None) -> dict:
    return {
        "artifact": "claimguard_production_corpus_evidence",
        "version": "1.0",
        "evidence_status": "ready_for_private_operator_review",
        "prepared_at": "2026-05-30T19:02:43-07:00",
        "no_phi_or_secret_values_attested": True,
        "no_raw_document_content_attested": True,
        "manifest_path": str(manifest_path) if manifest_path else None,
        "private_manifest_path_env": "PRODUCTION_CORPUS_PRIVATE_MANIFEST_PATH",
        "private_summary_path_env": "PRODUCTION_CORPUS_PRIVATE_SUMMARY_PATH",
        "private_manifest_path_configured": True,
        "private_manifest_path_value_included": False,
        "private_summary_path_configured": True,
        "private_summary_path_value_included": False,
        "private_manifest_metadata_checked": True,
        "private_production_corpus_summary_checked": True,
        "private_manifest_record_count": 2,
        "private_manifest_candidate_role_count": 2,
        "private_manifest_complete_pair_count": 1,
        "private_production_corpus_summary_manifest_record_count": 2,
        "private_production_corpus_summary_candidate_role_count": 2,
        "private_production_corpus_summary_complete_pair_count": 1,
        "private_production_corpus_summary_private_reference_count": 5,
        "private_production_corpus_summary_pair_review_count": 1,
        "private_production_corpus_summary_source_document_review_count": 2,
        "private_production_corpus_summary_privacy_review_count": 1,
        "private_production_corpus_summary_license_review_count": 1,
        "private_production_corpus_summary_residual_risk_review_count": 1,
        "private_production_corpus_summary_training_scope_review_count": 1,
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
        "corpus_review": {
            "source_control_review_runbook_documented": True,
            "source_control_review_runbook_path": str(
                REPO_ROOT / "llm-distill" / "docs" / "production-corpus-review-runbook.md"
            ),
            "source_control_collection_license_checklist_documented": True,
            "source_control_collection_license_checklist_path": (
                "llm-distill/docs/production-corpus-collection-license-checklist.md"
            ),
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_production_corpus_private_evidence.py"
            ),
            "privacy_review_attested": True,
            "license_review_attested": True,
            "residual_risk_review_attested": True,
            "training_scope_reviewed": True,
            "no_phi_review_attested": True,
            "source_license_scope_documented": True,
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
            "pair_ids_reviewed_outside_source_control": True,
            "source_documents_reviewed_outside_source_control": True,
        },
    }


def test_production_corpus_template_is_safe_to_review_but_not_ready():
    validator = _load_validator()
    template_path = (
        REPO_ROOT
        / "llm-distill"
        / "data"
        / "production_corpus_evidence"
        / "corpus_evidence.template.json"
    )

    report = validator.build_report(template_path)

    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert "production_corpus_no_phi_secret_or_document_values" not in blocked_ids
    assert "production_corpus_manual_review_attestations" not in blocked_ids
    assert "production_corpus_operator_runbook" not in blocked_ids
    assert "production_corpus_collection_license_checklist" not in blocked_ids
    assert "production_corpus_pair_source_checklist" not in blocked_ids
    assert "production_corpus_private_evidence_renderer" not in blocked_ids
    assert "production_corpus_private_summary_metadata" in blocked_ids
    assert "production_corpus_manifest_pair_evidence" in blocked_ids
    runbook_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "production_corpus_operator_runbook"
    )
    assert runbook_requirement["status"] == "ready"
    assert runbook_requirement["evidence"]["source_control_review_runbook_documented"] is True
    assert runbook_requirement["evidence"]["runbook_exists"] is True
    assert runbook_requirement["evidence"]["runbook_inside_source_control"] is True
    assert runbook_requirement["evidence"]["missing_marker_count"] == 0
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False
    collection_license_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "production_corpus_collection_license_checklist"
    )
    assert collection_license_requirement["status"] == "ready"
    assert (
        collection_license_requirement["evidence"][
            "source_control_collection_license_checklist_documented"
        ]
        is True
    )
    assert (
        collection_license_requirement["evidence"][
            "collection_license_checklist_exists"
        ]
        is True
    )
    assert (
        collection_license_requirement["evidence"][
            "collection_license_checklist_inside_source_control"
        ]
        is True
    )
    assert collection_license_requirement["evidence"]["missing_marker_count"] == 0
    assert (
        collection_license_requirement["evidence"]["raw_checklist_text_included"]
        is False
    )
    checklist_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "production_corpus_pair_source_checklist"
    )
    assert checklist_requirement["status"] == "ready"
    assert (
        checklist_requirement["evidence"][
            "source_control_pair_source_checklist_documented"
        ]
        is True
    )
    assert checklist_requirement["evidence"]["pair_source_checklist_exists"] is True
    assert (
        checklist_requirement["evidence"][
            "pair_source_checklist_inside_source_control"
        ]
        is True
    )
    assert checklist_requirement["evidence"]["missing_marker_count"] == 0
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    corpus_review_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "production_corpus_manual_review_attestations"
    )
    assert corpus_review_requirement["status"] == "ready"
    assert corpus_review_requirement["evidence"]["source_control_review_runbook_documented"] is True
    assert (
        corpus_review_requirement["evidence"][
            "source_control_collection_license_checklist_documented"
        ]
        is True
    )
    for key in [
        "privacy_review_attested",
        "license_review_attested",
        "residual_risk_review_attested",
        "training_scope_reviewed",
        "no_phi_review_attested",
        "source_license_scope_documented",
        "source_control_private_evidence_renderer_documented",
    ]:
        assert corpus_review_requirement["evidence"][key] is True
    private_renderer_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "production_corpus_private_evidence_renderer"
    )
    assert private_renderer_requirement["status"] == "ready"
    assert (
        private_renderer_requirement["evidence"][
            "source_control_private_evidence_renderer_documented"
        ]
        is True
    )
    assert private_renderer_requirement["evidence"]["private_evidence_renderer_exists"] is True
    assert (
        private_renderer_requirement["evidence"][
            "private_evidence_renderer_inside_source_control"
        ]
        is True
    )
    assert private_renderer_requirement["evidence"]["missing_marker_count"] == 0
    assert private_renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    private_summary_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_corpus_private_summary_metadata"
    )
    assert (
        "private_manifest_path_not_configured"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_production_corpus_summary_not_checked"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_manifest_record_count_missing"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_manifest_path_env_required_for_ready_evidence"
        in private_summary_requirement["blockers"]
    )
    assert (
        private_summary_requirement["evidence"]["private_summary_path_value_included"]
        is False
    )
    manifest_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_corpus_manifest_pair_evidence"
    )
    assert "approved_non_synthetic_pair_count_below_minimum" in manifest_requirement["blockers"]
    assert "pair_ids_not_reviewed_outside_source_control" in manifest_requirement["blockers"]
    assert "source_documents_not_reviewed_outside_source_control" in manifest_requirement["blockers"]


def test_ready_production_corpus_evidence_passes_all_requirements(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    manifest_path = tmp_path / "manifest.json"
    evidence_path = tmp_path / "corpus_evidence.json"
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    evidence = _ready_evidence(None)
    _write_json(evidence_path, evidence)
    monkeypatch.setenv(
        evidence["private_manifest_path_env"],
        str(manifest_path),
    )

    report = validator.build_report(evidence_path)

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is True
    assert report["blocked_item_count"] == 0


def test_private_manifest_env_evidence_passes_without_emitting_path(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    env_name = "PRODUCTION_CORPUS_PRIVATE_MANIFEST_PATH"
    manifest_path = tmp_path / "private-manifest.json"
    evidence_path = tmp_path / "corpus_evidence.json"
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    evidence = _ready_evidence(None)
    evidence["manifest_path"] = None
    evidence["private_manifest_path_env"] = env_name
    evidence["private_manifest_path_configured"] = True
    evidence["private_manifest_path_value_included"] = False
    _write_json(evidence_path, evidence)
    monkeypatch.setenv(env_name, str(manifest_path))

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    manifest_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "production_corpus_manifest_pair_evidence"
    )

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is True
    assert manifest_requirement["status"] == "ready"
    assert manifest_requirement["evidence"]["manifest_path_source"] == "private_env"
    assert manifest_requirement["evidence"]["private_manifest_path_env"] == env_name
    assert manifest_requirement["evidence"]["manifest_path_value_included"] is False
    assert str(manifest_path) not in serialized


def test_ready_evidence_requires_private_summary_metadata(monkeypatch, tmp_path):
    validator = _load_validator()
    manifest_path = tmp_path / "private-manifest.json"
    evidence_path = tmp_path / "corpus_missing_private_summary.json"
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    evidence = _ready_evidence(None)
    evidence["private_manifest_path_configured"] = False
    evidence["private_summary_path_configured"] = False
    evidence["private_manifest_metadata_checked"] = False
    evidence["private_production_corpus_summary_checked"] = False
    for key in [
        "private_manifest_record_count",
        "private_manifest_candidate_role_count",
        "private_manifest_complete_pair_count",
        "private_production_corpus_summary_manifest_record_count",
        "private_production_corpus_summary_candidate_role_count",
        "private_production_corpus_summary_complete_pair_count",
        "private_production_corpus_summary_private_reference_count",
        "private_production_corpus_summary_pair_review_count",
        "private_production_corpus_summary_source_document_review_count",
        "private_production_corpus_summary_privacy_review_count",
        "private_production_corpus_summary_license_review_count",
        "private_production_corpus_summary_residual_risk_review_count",
        "private_production_corpus_summary_training_scope_review_count",
    ]:
        evidence[key] = 0
    _write_json(evidence_path, evidence)
    monkeypatch.setenv(
        evidence["private_manifest_path_env"],
        str(manifest_path),
    )

    report = validator.build_report(evidence_path)
    private_summary_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_corpus_private_summary_metadata"
    )

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert (
        "private_manifest_path_not_configured"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_production_corpus_summary_not_checked"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_production_corpus_summary_private_reference_count_missing"
        in private_summary_requirement["blockers"]
    )
    assert (
        private_summary_requirement["evidence"]["private_manifest_path_value_included"]
        is False
    )


def test_private_summary_value_flags_are_blocked(monkeypatch, tmp_path):
    validator = _load_validator()
    manifest_path = tmp_path / "private-manifest.json"
    evidence_path = tmp_path / "corpus_private_values.json"
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    evidence = _ready_evidence(None)
    evidence["private_summary_path_value_included"] = True
    evidence["raw_document_content_included"] = True
    _write_json(evidence_path, evidence)
    monkeypatch.setenv(
        evidence["private_manifest_path_env"],
        str(manifest_path),
    )

    report = validator.build_report(evidence_path)
    private_summary_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_corpus_private_summary_metadata"
    )

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert (
        "private_summary_path_value_included"
        in private_summary_requirement["blockers"]
    )
    assert "raw_document_content_included" in private_summary_requirement["blockers"]
    assert (
        private_summary_requirement["evidence"]["private_summary_path_value_included"]
        is True
    )


def test_production_corpus_evidence_blocks_synthetic_only_manifest(tmp_path):
    validator = _load_validator()
    manifest_path = tmp_path / "manifest.json"
    evidence_path = tmp_path / "corpus_evidence.json"
    _write_json(
        manifest_path,
        {
            "records": [
                _record(role="denial_letter", source_type="synthetic_deidentified_pair"),
                _record(role="appeal_letter", source_type="synthetic_deidentified_pair"),
            ]
        },
    )
    _write_json(evidence_path, _ready_evidence(manifest_path))

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert "approved_non_synthetic_pair_count_below_minimum" in serialized


def test_production_corpus_evidence_blocks_raw_approval_values_without_emitting_them(tmp_path):
    validator = _load_validator()
    manifest_path = tmp_path / "manifest.json"
    evidence_path = tmp_path / "corpus_evidence.json"
    raw_reference = "production-corpus-approval-reference-do-not-write"
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    evidence = _ready_evidence(manifest_path)
    evidence["approval_reference_value"] = raw_reference
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)

    assert report["safe_to_review"] is False
    assert report["production_corpus_ready"] is False
    assert "raw approval, source, checksum, secret, or document value key is not allowed" in serialized
    assert raw_reference not in serialized


def test_production_corpus_evidence_blocks_incomplete_runbook_without_emitting_text(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    manifest_path = tmp_path / "manifest.json"
    evidence_path = tmp_path / "corpus_evidence.json"
    incomplete_runbook = tmp_path / "production-corpus-review-runbook.md"
    raw_runbook_text = "ClaimGuard AI is architected by Raphael Malikian"
    incomplete_runbook.write_text(raw_runbook_text, encoding="utf-8")
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    evidence = _ready_evidence(manifest_path)
    evidence["corpus_review"]["source_control_review_runbook_path"] = str(incomplete_runbook)
    _write_json(evidence_path, evidence)
    _allow_tmp_source_control_path(monkeypatch, validator, incomplete_runbook)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    runbook_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_corpus_operator_runbook"
    )

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert "source_control_review_runbook_required_markers_missing" in runbook_requirement["blockers"]
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False
    assert raw_runbook_text not in serialized


def test_production_corpus_evidence_blocks_incomplete_collection_license_checklist_without_emitting_text(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    manifest_path = tmp_path / "manifest.json"
    evidence_path = tmp_path / "corpus_evidence.json"
    incomplete_checklist = tmp_path / "production-corpus-collection-license-checklist.md"
    raw_checklist_text = "ClaimGuard AI is architected by Raphael Malikian"
    incomplete_checklist.write_text(raw_checklist_text, encoding="utf-8")
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    evidence = _ready_evidence(manifest_path)
    evidence["corpus_review"][
        "source_control_collection_license_checklist_path"
    ] = str(incomplete_checklist)
    _write_json(evidence_path, evidence)
    _allow_tmp_source_control_path(monkeypatch, validator, incomplete_checklist)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_corpus_collection_license_checklist"
    )

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert (
        "source_control_collection_license_checklist_required_markers_missing"
        in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert raw_checklist_text not in serialized


def test_production_corpus_evidence_blocks_incomplete_pair_source_checklist_without_emitting_text(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    manifest_path = tmp_path / "manifest.json"
    evidence_path = tmp_path / "corpus_evidence.json"
    incomplete_checklist = tmp_path / "production-corpus-pair-source-checklist.md"
    raw_checklist_text = "ClaimGuard AI is architected by Raphael Malikian"
    incomplete_checklist.write_text(raw_checklist_text, encoding="utf-8")
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    evidence = _ready_evidence(manifest_path)
    evidence["pairing_requirements"]["source_control_pair_source_checklist_path"] = str(
        incomplete_checklist
    )
    _write_json(evidence_path, evidence)
    _allow_tmp_source_control_path(monkeypatch, validator, incomplete_checklist)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_corpus_pair_source_checklist"
    )

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert (
        "source_control_pair_source_checklist_required_markers_missing"
        in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert raw_checklist_text not in serialized


def test_production_corpus_evidence_blocks_incomplete_private_renderer_without_emitting_text(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    manifest_path = tmp_path / "manifest.json"
    evidence_path = tmp_path / "corpus_evidence.json"
    incomplete_renderer = tmp_path / "render_production_corpus_private_evidence.py"
    raw_renderer_text = "RenderConfig"
    incomplete_renderer.write_text(raw_renderer_text, encoding="utf-8")
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    evidence = _ready_evidence(manifest_path)
    evidence["corpus_review"]["private_evidence_renderer_path"] = str(
        incomplete_renderer
    )
    _write_json(evidence_path, evidence)
    _allow_tmp_source_control_path(monkeypatch, validator, incomplete_renderer)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    renderer_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_corpus_private_evidence_renderer"
    )

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert (
        "source_control_private_evidence_renderer_markers_missing"
        in renderer_requirement["blockers"]
    )
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert raw_renderer_text not in serialized


def test_production_corpus_runbook_must_stay_inside_source_control(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    manifest_path = tmp_path / "private-manifest.json"
    evidence_path = tmp_path / "corpus_outside_runbook.json"
    runbook_path = tmp_path / "production-corpus-review-runbook.md"
    unique_text = "outside production corpus runbook marker should not leak"
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    _write_marker_file(runbook_path, validator.RUNBOOK_REQUIRED_MARKERS, unique_text)
    evidence = _ready_evidence(None)
    evidence["corpus_review"]["source_control_review_runbook_path"] = str(runbook_path)
    _write_json(evidence_path, evidence)
    monkeypatch.setenv(evidence["private_manifest_path_env"], str(manifest_path))

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    runbook_requirement = _requirement(report, "production_corpus_operator_runbook")

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert (
        "source_control_review_runbook_must_be_inside_repo"
        in runbook_requirement["blockers"]
    )
    assert (
        "source_control_review_runbook_required_markers_missing"
        not in runbook_requirement["blockers"]
    )
    assert runbook_requirement["evidence"]["runbook_exists"] is True
    assert runbook_requirement["evidence"]["runbook_inside_source_control"] is False
    assert runbook_requirement["evidence"]["present_marker_count"] == 0
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False
    assert unique_text not in serialized


def test_production_corpus_collection_license_checklist_must_stay_inside_source_control(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    manifest_path = tmp_path / "private-manifest.json"
    evidence_path = tmp_path / "corpus_outside_collection_license.json"
    checklist_path = tmp_path / "production-corpus-collection-license-checklist.md"
    unique_text = "outside production corpus collection checklist marker should not leak"
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    _write_marker_file(
        checklist_path,
        validator.COLLECTION_LICENSE_CHECKLIST_REQUIRED_MARKERS,
        unique_text,
    )
    evidence = _ready_evidence(None)
    evidence["corpus_review"][
        "source_control_collection_license_checklist_path"
    ] = str(checklist_path)
    _write_json(evidence_path, evidence)
    monkeypatch.setenv(evidence["private_manifest_path_env"], str(manifest_path))

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    checklist_requirement = _requirement(
        report,
        "production_corpus_collection_license_checklist",
    )

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert (
        "source_control_collection_license_checklist_must_be_inside_repo"
        in checklist_requirement["blockers"]
    )
    assert (
        "source_control_collection_license_checklist_required_markers_missing"
        not in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["collection_license_checklist_exists"] is True
    assert (
        checklist_requirement["evidence"][
            "collection_license_checklist_inside_source_control"
        ]
        is False
    )
    assert checklist_requirement["evidence"]["present_marker_count"] == 0
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert unique_text not in serialized


def test_production_corpus_pair_source_checklist_must_stay_inside_source_control(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    manifest_path = tmp_path / "private-manifest.json"
    evidence_path = tmp_path / "corpus_outside_pair_source.json"
    checklist_path = tmp_path / "production-corpus-pair-source-checklist.md"
    unique_text = "outside production corpus pair checklist marker should not leak"
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    _write_marker_file(
        checklist_path,
        validator.PAIR_SOURCE_CHECKLIST_REQUIRED_MARKERS,
        unique_text,
    )
    evidence = _ready_evidence(None)
    evidence["pairing_requirements"][
        "source_control_pair_source_checklist_path"
    ] = str(checklist_path)
    _write_json(evidence_path, evidence)
    monkeypatch.setenv(evidence["private_manifest_path_env"], str(manifest_path))

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    checklist_requirement = _requirement(
        report,
        "production_corpus_pair_source_checklist",
    )

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert (
        "source_control_pair_source_checklist_must_be_inside_repo"
        in checklist_requirement["blockers"]
    )
    assert (
        "source_control_pair_source_checklist_required_markers_missing"
        not in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["pair_source_checklist_exists"] is True
    assert (
        checklist_requirement["evidence"][
            "pair_source_checklist_inside_source_control"
        ]
        is False
    )
    assert checklist_requirement["evidence"]["present_marker_count"] == 0
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert unique_text not in serialized


def test_production_corpus_private_renderer_must_stay_inside_source_control(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    manifest_path = tmp_path / "private-manifest.json"
    evidence_path = tmp_path / "corpus_outside_private_renderer.json"
    renderer_path = tmp_path / "render_production_corpus_private_evidence.py"
    unique_text = "outside production corpus private renderer marker should not leak"
    _write_json(
        manifest_path,
        {"records": [_record(role="denial_letter"), _record(role="appeal_letter")]},
    )
    _write_marker_file(
        renderer_path,
        validator.PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS,
        unique_text,
    )
    evidence = _ready_evidence(None)
    evidence["corpus_review"]["private_evidence_renderer_path"] = str(renderer_path)
    _write_json(evidence_path, evidence)
    monkeypatch.setenv(evidence["private_manifest_path_env"], str(manifest_path))

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    renderer_requirement = _requirement(
        report,
        "production_corpus_private_evidence_renderer",
    )

    assert report["safe_to_review"] is True
    assert report["production_corpus_ready"] is False
    assert (
        "source_control_private_evidence_renderer_must_be_inside_repo"
        in renderer_requirement["blockers"]
    )
    assert (
        "source_control_private_evidence_renderer_markers_missing"
        not in renderer_requirement["blockers"]
    )
    assert renderer_requirement["evidence"]["private_evidence_renderer_exists"] is True
    assert (
        renderer_requirement["evidence"][
            "private_evidence_renderer_inside_source_control"
        ]
        is False
    )
    assert renderer_requirement["evidence"]["present_marker_count"] == 0
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert unique_text not in serialized
