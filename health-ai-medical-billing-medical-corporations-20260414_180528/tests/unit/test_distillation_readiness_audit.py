import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "run_distillation_readiness_audit.py"
SCRIPT_DIR = AUDIT_SCRIPT.parent


def _load_audit() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("run_distillation_readiness_audit", AUDIT_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_report_sanitizer_emits_repo_relative_paths_and_redacts_external_paths(
    monkeypatch,
    tmp_path,
):
    audit = _load_audit()
    repo_root = tmp_path / "repo"
    monkeypatch.setattr(audit, "REPO_ROOT", repo_root)
    payload = {
        "direct_path": str(repo_root / "llm-distill" / "evals" / "reports" / "report.json"),
        "embedded_path": (
            "wrote "
            + str(repo_root / "llm-distill" / "models" / "adapters" / "adapter.safetensors")
        ),
        "outside_path": str(tmp_path / "private" / "approval-summary.json"),
        "nested": [
            {
                "error": "missing file: "
                + str(tmp_path / "outside" / "private-report.json")
            }
        ],
    }

    sanitized = audit.sanitize_report_value(payload)
    serialized = json.dumps(sanitized, sort_keys=True)

    assert sanitized["direct_path"] == "llm-distill/evals/reports/report.json"
    assert "llm-distill/models/adapters/adapter.safetensors" in sanitized["embedded_path"]
    assert sanitized["outside_path"] == "external_path_redacted"
    assert sanitized["nested"][0]["error"] == "missing file: external_path_redacted"
    assert str(repo_root) not in serialized
    assert str(tmp_path) not in serialized


def _approved_record(
    *,
    document_id: str,
    role: str,
    pair_id: str,
    split: str,
) -> dict:
    return {
        "source_id": f"SRC-{document_id}",
        "document_id": document_id,
        "pair_id": pair_id,
        "source_type": "synthetic_deidentified_pair",
        "document_role": role,
        "source_url_or_path": f"synthetic://{document_id}",
        "checksum": f"sha256:{document_id}",
        "phi_status": "deidentified",
        "deidentification_status": "training_eligible",
        "license_status": "synthetic_allowed",
        "review_status": "training_approved",
        "residual_risk_score": 0.0,
        "training_eligible": True,
        "split": split,
        "micro_skill_ids": [f"MS{index:02d}" for index in range(1, 13)],
        "payer_type": "commercial",
        "denial_type": "medical_necessity",
        "appeal_route": "internal_appeal",
        "appeal_level": "first_level",
        "outcome": "drafted_appeal" if role == "appeal_letter" else "denied",
    }


def _write_split(path: Path, split: str, pair_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "messages": [
            {"role": "system", "content": "ClaimGuard synthetic corpus SFT test."},
            {"role": "user", "content": f"Deidentified denial pair {pair_id}."},
            {"role": "assistant", "content": "{\"human_review_required\": true}"},
        ],
        "metadata": {"pair_id": pair_id, "split": split},
    }
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")


def _write_synthetic_900_fixture(tmp_path: Path, pair_count: int = 2) -> tuple[Path, Path]:
    corpus_dir = tmp_path / "generated_synthetic_pairs"
    letters_dir = corpus_dir / "letters"
    records = []
    split_names = ["train", "valid", "test"]
    for index in range(1, pair_count + 1):
        pair_id = f"PAIR-SYN-LARGE-{index:04d}"
        split = split_names[(index - 1) % len(split_names)]
        for role in ["denial_letter", "appeal_letter"]:
            suffix = "denial" if role == "denial_letter" else "appeal"
            letter_path = letters_dir / split / f"pair-syn-large-{index:04d}_{suffix}.txt"
            letter_path.parent.mkdir(parents=True, exist_ok=True)
            letter_path.write_text(
                f"Synthetic corpus pair {pair_id}. Layout profile fixture. draft_for_human_review.\n",
                encoding="utf-8",
            )
            records.append(
                {
                    "source_id": f"SRC-{pair_id}-{suffix.upper()}",
                    "document_id": f"DOC-{pair_id}-{suffix.upper()}",
                    "pair_id": pair_id,
                    "source_type": "synthetic_deidentified_pair",
                    "document_role": role,
                    "source_url_or_path": str(letter_path),
                    "checksum": f"sha256:{pair_id}-{suffix}",
                    "phi_status": "no_phi",
                    "deidentification_status": "training_eligible",
                    "license_status": "synthetic_allowed",
                    "review_status": "training_approved",
                    "residual_risk_score": 0.0,
                    "training_eligible": True,
                    "split": split,
                    "micro_skill_ids": [f"MS{skill_index:02d}" for skill_index in range(1, 13)],
                }
            )
    manifest_path = corpus_dir / "manifest_synthetic_900.json"
    report_path = corpus_dir / "generation_report.json"
    _write_json(manifest_path, {"version": "synthetic-large-test", "records": records})
    _write_json(
        report_path,
        {
            "artifact": "synthetic_denial_appeal_corpus",
            "pair_count": pair_count,
            "letter_count": pair_count * 2,
            "output_dir": str(corpus_dir),
            "phi_scan": {"finding_count": 0, "findings": [], "values_redacted": True},
            "safety": {
                "synthetic_only": True,
                "real_patient_data_used": False,
                "real_claim_data_used": False,
                "training_allowed_only_after_export_gates": True,
            },
            "counts": {
                "denial_format": {f"denial_{index}": 1 for index in range(8)},
                "appeal_format": {f"appeal_{index}": 1 for index in range(8)},
                "layout_profile": {f"layout_{index}": 1 for index in range(12)},
                "typography_profile": {f"type_{index}": 1 for index in range(8)},
                "length_profile": {f"length_{index}": 1 for index in range(6)},
                "split": {split: 1 for split in split_names},
            },
        },
    )
    return report_path, manifest_path


def test_corpus_manifest_requirement_blocks_empty_starter_manifest(tmp_path):
    audit = _load_audit()
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, {"version": "1.0", "records": []})

    requirement = audit.corpus_manifest_requirement(manifest, min_pairs=3)

    assert requirement["status"] == "blocked"
    assert requirement["evidence"]["record_count"] == 0
    assert any("training-eligible denial/appeal pairs" in blocker for blocker in requirement["blockers"])


def test_corpus_manifest_requirement_accepts_reviewed_pairs(tmp_path):
    audit = _load_audit()
    manifest = tmp_path / "manifest.json"
    records = []
    for split in ["train", "valid", "test"]:
        pair_id = f"PAIR-{split.upper()}"
        records.append(
            _approved_record(
                document_id=f"DOC-{pair_id}-DENIAL",
                role="denial_letter",
                pair_id=pair_id,
                split=split,
            )
        )
        records.append(
            _approved_record(
                document_id=f"DOC-{pair_id}-APPEAL",
                role="appeal_letter",
                pair_id=pair_id,
                split=split,
            )
        )
    _write_json(manifest, {"version": "1.0", "records": records})

    requirement = audit.corpus_manifest_requirement(manifest, min_pairs=3)

    assert requirement["status"] == "ready"
    assert requirement["evidence"]["complete_training_pair_count"] == 3
    assert requirement["blockers"] == []


def test_corpus_manifest_requirement_reports_public_government_sources(tmp_path):
    audit = _load_audit()
    manifest = tmp_path / "manifest.json"
    records = []
    for split in ["train", "valid", "test"]:
        pair_id = f"PAIR-{split.upper()}"
        records.append(
            _approved_record(
                document_id=f"DOC-{pair_id}-DENIAL",
                role="denial_letter",
                pair_id=pair_id,
                split=split,
            )
        )
        records.append(
            _approved_record(
                document_id=f"DOC-{pair_id}-APPEAL",
                role="appeal_letter",
                pair_id=pair_id,
                split=split,
            )
        )
    records.append(
        {
            "source_id": "SRC-PUBLIC-1",
            "document_id": "DOC-PUBLIC-1",
            "pair_id": None,
            "source_type": "public_government_source",
            "document_role": "rule_source",
            "source_url_or_path": "synthetic://public-source-note",
            "checksum": "sha256:public-source-note",
            "phi_status": "no_phi",
            "deidentification_status": "privacy_review_passed",
            "license_status": "public_government_source",
            "review_status": "privacy_review_passed",
            "residual_risk_score": 0.0,
            "training_eligible": False,
            "split": "none",
            "micro_skill_ids": ["MS01", "MS03"],
        }
    )
    _write_json(manifest, {"version": "1.2", "records": records})

    requirement = audit.corpus_manifest_requirement(manifest, min_pairs=3)

    assert requirement["status"] == "ready"
    assert requirement["evidence"]["training_eligible_count"] == 6
    assert requirement["evidence"]["public_government_source_count"] == 1
    assert requirement["evidence"]["counts_by_source_type"] == {
        "public_government_source": 1,
        "synthetic_deidentified_pair": 6,
    }


def test_corpus_sft_requirement_blocks_missing_generated_manifest(tmp_path):
    audit = _load_audit()
    requirement = audit.corpus_sft_export_requirement(
        tmp_path / "missing" / "manifest.json",
        tmp_path / "corpus" / "manifest.json",
        min_pairs=3,
    )

    assert requirement["status"] == "blocked"
    assert any("missing file" in blocker for blocker in requirement["blockers"])


def test_corpus_sft_requirement_accepts_training_allowed_export(tmp_path):
    audit = _load_audit()
    corpus_manifest = tmp_path / "corpus" / "manifest.json"
    sft_dir = tmp_path / "sft"
    _write_json(corpus_manifest, {"version": "1.0", "records": []})
    for split in ["train", "valid", "test"]:
        _write_split(sft_dir / f"{split}.jsonl", split, f"PAIR-{split.upper()}")
    _write_json(
        sft_dir / "manifest.json",
        {
            "artifact": "claimguard_mlx_sft_corpus",
            "training_allowed": True,
            "blocked_reasons": [],
            "source_manifest": str(corpus_manifest),
            "pair_count": 3,
            "record_count": 3,
            "split_counts": {"train": 1, "valid": 1, "test": 1},
            "micro_skill_coverage_complete": True,
            "missing_required_micro_skill_ids": [],
            "micro_skill_counts": {f"MS{index:02d}": 3 for index in range(1, 13)},
            "coverage_counts": {
                "payer_type": {"commercial": 3},
                "denial_type": {"medical_necessity": 3},
                "appeal_route": {"internal_appeal": 3},
                "appeal_level": {"first_level": 3},
                "outcome": {"drafted_appeal": 3},
                "source_type": {"synthetic_deidentified_pair": 3},
                "document_role": {"denial_letter": 3, "appeal_letter": 3},
            },
            "data_safety": {
                "data_tier": "approved_deidentified_corpus",
                "phi_status": "deidentified",
                "user_phi_allowed": False,
                "requires_training_eligible_manifest_records": True,
                "requires_privacy_review": True,
                "requires_zero_phi_scan_findings": True,
            },
        },
    )

    requirement = audit.corpus_sft_export_requirement(
        sft_dir / "manifest.json",
        corpus_manifest,
        min_pairs=3,
    )

    assert requirement["status"] == "ready"
    assert requirement["blockers"] == []
    assert requirement["evidence"]["split_file_counts"] == {"train": 1, "valid": 1, "test": 1}


def test_synthetic_900_corpus_requirement_accepts_varied_clean_pairs(tmp_path):
    audit = _load_audit()
    report_path, manifest_path = _write_synthetic_900_fixture(tmp_path, pair_count=3)

    requirement = audit.synthetic_900_corpus_requirement(
        report_path,
        manifest_path,
        min_pairs=2,
        max_pairs=3,
    )

    assert requirement["status"] == "ready"
    assert requirement["evidence"]["pair_count"] == 3
    assert requirement["evidence"]["letter_count"] == 6
    assert requirement["evidence"]["complete_pair_count"] == 3
    assert requirement["evidence"]["letter_tree_phi_scan"]["finding_count"] == 0


def _ready_synthetic_profile_matrix() -> dict:
    profile_requirements = {
        "layout_profile": 12,
        "typography_profile": 8,
        "length_profile": 6,
    }

    def _family_items(record_count: int) -> dict:
        return {
            family: {
                "record_count": record_count,
                "variant_count": required,
                "required_variant_count": required,
                "ready": True,
                "counts": {f"{family}_variant_{index}": 1 for index in range(required)},
            }
            for family, required in profile_requirements.items()
        }

    return {
        "document_role": {
            "denial_letter": _family_items(900),
            "appeal_letter": _family_items(900),
        },
        "split": {
            "train": _family_items(1440),
            "valid": _family_items(180),
            "test": _family_items(180),
        },
    }


def _ready_appeal_quality_contract() -> dict:
    return {
        "checked_appeal_count": 900,
        "missing_draft_status_count": 0,
        "missing_human_review_header_count": 0,
        "missing_not_filing_ready_notice_count": 0,
        "missing_source_grounding_count": 0,
        "missing_deadline_verification_count": 0,
        "missing_phi_minimization_count": 0,
        "missing_route_alignment_count": 0,
        "missing_appeal_level_alignment_count": 0,
        "missing_denial_type_alignment_count": 0,
        "unsupported_deadline_or_citation_claim_count": 0,
        "ready": True,
    }


def test_synthetic_900_format_contract_requirement_accepts_ready_report(tmp_path):
    audit = _load_audit()
    report_path = tmp_path / "synthetic_denial_appeal_corpus_format_audit_report.json"
    _write_json(
        report_path,
        {
            "artifact": "synthetic_denial_appeal_corpus_format_audit",
            "ready": True,
            "blockers": [],
            "warnings": [],
            "evidence": {
                "pair_count": 900,
                "letter_count": 1800,
                "unique_text_count": 1800,
                "complete_pair_count": 900,
                "content_contract": {
                    "missing_file_count": 0,
                    "checksum_mismatch_count": 0,
                    "profile_missing_count": 0,
                    "profile_mismatch_count": 0,
                    "missing_marker_count": 0,
                    "invalid_training_gate_count": 0,
                    "split_path_mismatch_count": 0,
                },
                "documentation": {"ready": True},
                "phi_scan": {"finding_count": 0},
                "word_count": {"range": 180},
                "profile_matrix_coverage": _ready_synthetic_profile_matrix(),
                "appeal_quality_contract": _ready_appeal_quality_contract(),
            },
        },
    )

    requirement = audit.synthetic_900_format_contract_requirement(
        report_path,
        min_pairs=800,
        max_pairs=1000,
    )

    assert requirement["status"] == "ready"
    assert requirement["requirement_id"] == "phase6_synthetic_900_format_contract_audit"
    assert requirement["evidence"]["unique_text_count"] == 1800


def test_synthetic_900_format_contract_requirement_blocks_incomplete_profile_matrix(tmp_path):
    audit = _load_audit()
    report_path = tmp_path / "synthetic_denial_appeal_corpus_format_audit_report.json"
    profile_matrix = _ready_synthetic_profile_matrix()
    profile_matrix["split"]["test"]["typography_profile"]["ready"] = False
    profile_matrix["split"]["test"]["typography_profile"]["variant_count"] = 7
    _write_json(
        report_path,
        {
            "artifact": "synthetic_denial_appeal_corpus_format_audit",
            "ready": True,
            "blockers": [],
            "warnings": [],
            "evidence": {
                "pair_count": 900,
                "letter_count": 1800,
                "unique_text_count": 1800,
                "complete_pair_count": 900,
                "content_contract": {
                    "missing_file_count": 0,
                    "checksum_mismatch_count": 0,
                    "profile_missing_count": 0,
                    "profile_mismatch_count": 0,
                    "missing_marker_count": 0,
                    "invalid_training_gate_count": 0,
                    "split_path_mismatch_count": 0,
                },
                "documentation": {"ready": True},
                "phi_scan": {"finding_count": 0},
                "word_count": {"range": 180},
                "profile_matrix_coverage": profile_matrix,
            },
        },
    )

    requirement = audit.synthetic_900_format_contract_requirement(
        report_path,
        min_pairs=800,
        max_pairs=1000,
    )

    assert requirement["status"] == "blocked"
    assert any(
        "profile_matrix_coverage.split.test.typography_profile" in blocker
        for blocker in requirement["blockers"]
    )


def test_synthetic_900_format_contract_requirement_blocks_failed_appeal_quality(tmp_path):
    audit = _load_audit()
    report_path = tmp_path / "synthetic_denial_appeal_corpus_format_audit_report.json"
    appeal_quality = _ready_appeal_quality_contract()
    appeal_quality["ready"] = False
    appeal_quality["missing_source_grounding_count"] = 1
    _write_json(
        report_path,
        {
            "artifact": "synthetic_denial_appeal_corpus_format_audit",
            "ready": True,
            "blockers": [],
            "warnings": [],
            "evidence": {
                "pair_count": 900,
                "letter_count": 1800,
                "unique_text_count": 1800,
                "complete_pair_count": 900,
                "content_contract": {
                    "missing_file_count": 0,
                    "checksum_mismatch_count": 0,
                    "profile_missing_count": 0,
                    "profile_mismatch_count": 0,
                    "missing_marker_count": 0,
                    "invalid_training_gate_count": 0,
                    "split_path_mismatch_count": 0,
                },
                "documentation": {"ready": True},
                "phi_scan": {"finding_count": 0},
                "word_count": {"range": 180},
                "profile_matrix_coverage": _ready_synthetic_profile_matrix(),
                "appeal_quality_contract": appeal_quality,
            },
        },
    )

    requirement = audit.synthetic_900_format_contract_requirement(
        report_path,
        min_pairs=800,
        max_pairs=1000,
    )

    assert requirement["status"] == "blocked"
    assert "format audit appeal_quality_contract must be ready" in requirement["blockers"]
    assert "format audit appeal_quality_contract.missing_source_grounding_count must be 0" in requirement["blockers"]


def test_synthetic_900_format_contract_requirement_blocks_unready_report(tmp_path):
    audit = _load_audit()
    report_path = tmp_path / "synthetic_denial_appeal_corpus_format_audit_report.json"
    _write_json(
        report_path,
        {
            "artifact": "synthetic_denial_appeal_corpus_format_audit",
            "ready": False,
            "blockers": ["DOC-SYN-LARGE-0001-APPEAL: missing content marker draft_status_marker"],
            "warnings": [],
            "evidence": {
                "pair_count": 900,
                "letter_count": 1800,
                "unique_text_count": 1799,
                "complete_pair_count": 900,
                "content_contract": {
                    "missing_file_count": 0,
                    "checksum_mismatch_count": 0,
                    "profile_missing_count": 0,
                    "profile_mismatch_count": 0,
                    "missing_marker_count": 1,
                    "invalid_training_gate_count": 0,
                    "split_path_mismatch_count": 0,
                },
                "documentation": {"ready": True},
                "phi_scan": {"finding_count": 0},
                "word_count": {"range": 180},
            },
        },
    )

    requirement = audit.synthetic_900_format_contract_requirement(
        report_path,
        min_pairs=800,
        max_pairs=1000,
    )

    assert requirement["status"] == "blocked"
    assert any("draft_status_marker" in blocker for blocker in requirement["blockers"])
    assert any("unique text" in blocker for blocker in requirement["blockers"])


def _ready_synthetic_extraction_evidence() -> dict:
    return {
        "checked_denial_count": 900,
        "minimum_required_denial_count": 800,
        "missing_file_count": 0,
        "read_error_count": 0,
        "phi_finding_count": 0,
        "missing_payer_name_count": 0,
        "missing_denial_reason_count": 0,
        "missing_claim_amount_count": 0,
        "missing_procedure_code_count": 0,
        "unexpected_patient_name_count": 0,
        "unexpected_policy_number_count": 0,
    }


def test_synthetic_document_analysis_extraction_requirement_accepts_ready_report(tmp_path):
    audit = _load_audit()
    report_path = tmp_path / "synthetic_document_analysis_extraction_report.json"
    _write_json(
        report_path,
        {
            "artifact": "synthetic_document_analysis_extraction_audit",
            "ready": True,
            "blockers": [],
            "warnings": [],
            "evidence": _ready_synthetic_extraction_evidence(),
        },
    )

    requirement = audit.synthetic_document_analysis_extraction_requirement(
        report_path,
        min_denials=800,
    )

    assert requirement["status"] == "ready"
    assert requirement["requirement_id"] == "phase6_synthetic_document_analysis_extraction"
    assert requirement["evidence"]["checked_denial_count"] == 900


def test_synthetic_document_analysis_extraction_requirement_blocks_missing_fields(tmp_path):
    audit = _load_audit()
    report_path = tmp_path / "synthetic_document_analysis_extraction_report.json"
    evidence = _ready_synthetic_extraction_evidence()
    evidence["missing_procedure_code_count"] = 1
    _write_json(
        report_path,
        {
            "artifact": "synthetic_document_analysis_extraction_audit",
            "ready": False,
            "blockers": ["missing_procedure_code_count must be 0"],
            "warnings": [],
            "evidence": evidence,
        },
    )

    requirement = audit.synthetic_document_analysis_extraction_requirement(
        report_path,
        min_denials=800,
    )

    assert requirement["status"] == "blocked"
    assert "synthetic document-analysis extraction audit report must be ready" in requirement["blockers"]
    assert "document-analysis extraction audit missing_procedure_code_count must be 0" in requirement["blockers"]


def test_synthetic_900_sft_requirement_relabels_corpus_export(tmp_path):
    audit = _load_audit()
    synthetic_manifest = tmp_path / "generated_synthetic_pairs" / "manifest_synthetic_900.json"
    sft_dir = tmp_path / "mlx_sft_synthetic_900"
    _write_json(synthetic_manifest, {"version": "synthetic-large-test", "records": []})
    for split in ["train", "valid", "test"]:
        _write_split(sft_dir / f"{split}.jsonl", split, f"PAIR-{split.upper()}")
    _write_json(
        sft_dir / "manifest.json",
        {
            "artifact": "claimguard_mlx_sft_corpus",
            "training_allowed": True,
            "blocked_reasons": [],
            "source_manifest": str(synthetic_manifest),
            "pair_count": 3,
            "record_count": 3,
            "split_counts": {"train": 1, "valid": 1, "test": 1},
            "micro_skill_coverage_complete": True,
            "missing_required_micro_skill_ids": [],
            "micro_skill_counts": {f"MS{index:02d}": 3 for index in range(1, 13)},
            "coverage_counts": {
                "payer_type": {"commercial": 3},
                "denial_type": {"medical_necessity": 3},
                "appeal_route": {"internal_appeal": 3},
                "appeal_level": {"first_level": 3},
                "outcome": {"drafted_appeal": 3},
                "source_type": {"synthetic_deidentified_pair": 3},
                "document_role": {"denial_letter": 3, "appeal_letter": 3},
            },
            "data_safety": {
                "data_tier": "approved_deidentified_corpus",
                "phi_status": "no_phi",
                "user_phi_allowed": False,
                "requires_training_eligible_manifest_records": True,
                "requires_privacy_review": True,
                "requires_zero_phi_scan_findings": True,
            },
        },
    )

    requirement = audit.synthetic_900_sft_export_requirement(
        sft_dir / "manifest.json",
        synthetic_manifest,
        min_pairs=3,
    )

    assert requirement["status"] == "ready"
    assert requirement["requirement_id"] == "phase6_synthetic_900_sft_export"
    assert requirement["evidence"]["pair_count"] == 3


def test_synthetic_900_mlx_runtime_gate_warns_without_metal(tmp_path):
    audit = _load_audit()
    report_path = tmp_path / "mlx_finetune_synthetic_900_run_report.json"
    adapter_path = tmp_path / "adapter"
    _write_json(
        report_path,
        {
            "mode": "run",
            "ready": False,
            "training_attempted": False,
            "training_succeeded": None,
            "blocked_reasons": ["mlx_lm.lora cannot access a Metal device in this session"],
            "checks": {
                "data": {"ready": True},
                "manifest": {"training_allowed": True},
                "mlx_lm_lora": {
                    "available": True,
                    "runtime_ready": False,
                    "error": "mlx_lm.lora cannot access a Metal device in this session",
                },
                "adapter_output": {
                    "path": str(adapter_path),
                    "exists_before_run": False,
                    "exists_after_run": None,
                },
            },
        },
    )

    requirement = audit.synthetic_900_mlx_runtime_gate_requirement(report_path)

    assert requirement["status"] == "warning"
    assert requirement["blockers"] == []
    assert "MLX cannot access Metal" in requirement["warnings"][0]
    assert requirement["evidence"]["adapter_exists_currently"] is False


def test_file_ingestion_surface_requirement_blocks_unready_report(tmp_path):
    audit = _load_audit()
    report = tmp_path / "file_ingestion_surface_audit_report.json"
    _write_json(
        report,
        {
            "ready": False,
            "blocked_reasons": ["unregistered file-ingestion endpoint: /demo/upload"],
            "summary": {"discovered_count": 2, "registered_count": 1},
        },
    )

    requirement = audit.file_ingestion_surface_requirement(report)

    assert requirement["status"] == "blocked"
    assert any("unregistered file-ingestion endpoint" in blocker for blocker in requirement["blockers"])


def test_file_ingestion_surface_requirement_accepts_ready_report(tmp_path):
    audit = _load_audit()
    report = tmp_path / "file_ingestion_surface_audit_report.json"
    _write_json(
        report,
        {
            "ready": True,
            "blocked_reasons": [],
            "summary": {"discovered_count": 1, "registered_count": 1},
        },
    )

    requirement = audit.file_ingestion_surface_requirement(report)

    assert requirement["status"] == "ready"
    assert requirement["blockers"] == []
    assert requirement["evidence"]["summary"]["registered_count"] == 1


def test_next_required_actions_do_not_repeat_completed_corpus_steps_when_release_ready():
    audit = _load_audit()

    release_ready_actions = audit.build_next_required_actions([], release_ready=True)
    blocked_actions = audit.build_next_required_actions(
        [
            {
                "requirement_id": "phase6_corpus_manifest_training_gates",
                "phase": "safe_corpus",
                "name": "Safe corpus manifest",
                "blockers": ["corpus manifest has no records"],
            }
        ],
        release_ready=False,
    )

    assert all("Build a safe hybrid corpus" not in action for action in release_ready_actions)
    assert any("CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false" in action for action in release_ready_actions)
    assert any("CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=true" in action for action in release_ready_actions)
    assert any("CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=true" in action for action in release_ready_actions)
    assert any("Build a safe hybrid corpus" in action for action in blocked_actions)
