import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPORT_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "export_corpus_sft_data.py"
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"


def _load_exporter() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("export_corpus_sft_data", EXPORT_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_script(script_name: str) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(script_name, SCRIPT_DIR / f"{script_name}.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_text(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record(
    *,
    path: Path,
    text: str,
    document_id: str,
    role: str,
    pair_id: str,
    split: str,
    training_eligible: bool = True,
) -> dict:
    return {
        "source_id": f"SRC-{document_id}",
        "document_id": document_id,
        "pair_id": pair_id,
        "source_type": "synthetic_deidentified_pair",
        "document_role": role,
        "source_url_or_path": str(path),
        "checksum": _write_text(path, text),
        "phi_status": "deidentified" if training_eligible else "contains_phi",
        "deidentification_status": "training_eligible" if training_eligible else "raw_quarantined",
        "license_status": "synthetic_allowed" if training_eligible else "review_required",
        "review_status": "training_approved" if training_eligible else "not_reviewed",
        "residual_risk_score": 0.0 if training_eligible else 1.0,
        "training_eligible": training_eligible,
        "split": split if training_eligible else "none",
        "micro_skill_ids": [f"MS{index:02d}" for index in range(1, 13)] if training_eligible else [],
        "reviewer_id": "privacy-reviewer-synthetic" if training_eligible else None,
        "review_method": "synthetic_fixture" if training_eligible else None,
        "payer_type": "commercial",
        "denial_type": "medical_necessity",
        "appeal_route": "internal_appeal",
        "appeal_level": "first_level",
        "outcome": "drafted_appeal" if role == "appeal_letter" else "denied",
    }


def _write_manifest(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps({"version": "1.0", "records": records}, indent=2), encoding="utf-8")


def test_corpus_sft_export_requires_training_eligible_pairs(tmp_path):
    exporter = _load_exporter()
    raw_text = "Denied because the packet contains an unsafe Member ID: SYN-MEMBER-123."
    appeal_text = "Appeal draft references [MEMBER_ID_1] and remains draft_for_human_review."
    denial_path = tmp_path / "unsafe-denial.txt"
    appeal_path = tmp_path / "safe-appeal.txt"
    manifest_path = tmp_path / "manifest.json"
    output_dir = tmp_path / "mlx_sft_corpus"
    _write_manifest(
        manifest_path,
        [
            _record(
                path=denial_path,
                text=raw_text,
                document_id="DOC-RAW-DENIAL",
                role="denial_letter",
                pair_id="PAIR-RAW",
                split="train",
                training_eligible=False,
            ),
            _record(
                path=appeal_path,
                text=appeal_text,
                document_id="DOC-RAW-APPEAL",
                role="appeal_letter",
                pair_id="PAIR-RAW",
                split="train",
                training_eligible=False,
            ),
        ],
    )

    manifest = exporter.export_corpus_sft(
        manifest_path=manifest_path,
        output_dir=output_dir,
        model="test-model",
        adapter_path=tmp_path / "adapter",
    )

    assert manifest["training_allowed"] is False
    assert manifest["ignored_records"]["not_training_eligible"] == 2
    assert manifest["pair_count"] == 0
    assert (output_dir / "train.jsonl").read_text(encoding="utf-8") == ""
    assert "SYN-MEMBER-123" not in json.dumps(manifest)


def test_corpus_sft_export_preserves_pairs_splits_and_coverage(tmp_path):
    exporter = _load_exporter()
    records = []
    for split in ["train", "valid", "test"]:
        pair_id = f"PAIR-{split.upper()}"
        denial_path = tmp_path / f"{pair_id}-denial.txt"
        appeal_path = tmp_path / f"{pair_id}-appeal.txt"
        records.append(
            _record(
                path=denial_path,
                text=f"Deidentified denial example {pair_id} with missing documentation.",
                document_id=f"DOC-{pair_id}-DENIAL",
                role="denial_letter",
                pair_id=pair_id,
                split=split,
            )
        )
        records.append(
            _record(
                path=appeal_path,
                text=f"Draft appeal for {pair_id}. Cite attached records and request review.",
                document_id=f"DOC-{pair_id}-APPEAL",
                role="appeal_letter",
                pair_id=pair_id,
                split=split,
            )
        )
    manifest_path = tmp_path / "manifest.json"
    output_dir = tmp_path / "mlx_sft_corpus"
    _write_manifest(manifest_path, records)

    manifest = exporter.export_corpus_sft(
        manifest_path=manifest_path,
        output_dir=output_dir,
        model="test-model",
        adapter_path=tmp_path / "adapter",
    )

    assert manifest["training_allowed"] is True
    assert manifest["split_counts"] == {"train": 1, "valid": 1, "test": 1}
    assert manifest["pair_count"] == 3
    assert manifest["micro_skill_coverage_complete"] is True
    assert manifest["coverage_counts"]["payer_type"] == {"commercial": 3}
    train_row = json.loads((output_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert train_row["metadata"]["pair_id"] == "PAIR-TRAIN"
    assert train_row["metadata"]["document_ids"]["denial_letter"] == "DOC-PAIR-TRAIN-DENIAL"
    assistant_payload = json.loads(train_row["messages"][-1]["content"])
    assert assistant_payload["human_review_required"] is True
    assert assistant_payload["draft_sections"][0]["draft_status"] == "draft_for_human_review"


def test_corpus_sft_export_sanitizes_source_controlled_manifest_paths(tmp_path, monkeypatch):
    exporter = _load_exporter()
    fake_repo = tmp_path / "repo"
    source_dir = fake_repo / "llm-distill" / "data" / "corpus" / "sources"
    source_dir.mkdir(parents=True)
    records = []
    for split in ["train", "valid", "test"]:
        pair_id = f"PAIR-{split.upper()}"
        denial_path = source_dir / f"{pair_id}-denial.txt"
        appeal_path = source_dir / f"{pair_id}-appeal.txt"
        records.append(
            _record(
                path=denial_path,
                text=f"Deidentified denial example {pair_id} with missing documentation.",
                document_id=f"DOC-{pair_id}-DENIAL",
                role="denial_letter",
                pair_id=pair_id,
                split=split,
            )
        )
        records.append(
            _record(
                path=appeal_path,
                text=f"Draft appeal for {pair_id}. Cite attached records and request review.",
                document_id=f"DOC-{pair_id}-APPEAL",
                role="appeal_letter",
                pair_id=pair_id,
                split=split,
            )
        )
    manifest_path = fake_repo / "llm-distill" / "data" / "corpus" / "manifest.json"
    output_dir = fake_repo / "llm-distill" / "data" / "distillation" / "mlx_sft_corpus"
    adapter_path = fake_repo / "llm-distill" / "models" / "adapters" / "corpus"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_manifest(manifest_path, records)
    monkeypatch.setattr(exporter, "REPO_ROOT", fake_repo)
    monkeypatch.setitem(exporter.write_command_file.__globals__, "REPO_ROOT", fake_repo)

    exporter.export_corpus_sft(
        manifest_path=manifest_path,
        output_dir=output_dir,
        model="test-model",
        adapter_path=adapter_path,
    )

    manifest_text = (output_dir / "manifest.json").read_text(encoding="utf-8")
    command_text = (output_dir / "train_lora_command.txt").read_text(encoding="utf-8")
    assert str(fake_repo) not in manifest_text
    assert str(fake_repo) not in command_text
    assert "llm-distill/data/corpus/manifest.json" in manifest_text
    assert "llm-distill/models/adapters/corpus" in manifest_text
    assert "llm-distill/models/adapters/corpus" in command_text
    assert "Run from the repository root:" in command_text


def test_corpus_sft_export_blocks_phi_scan_findings_without_values(tmp_path):
    exporter = _load_exporter()
    denial_path = tmp_path / "denial.txt"
    appeal_path = tmp_path / "appeal.txt"
    manifest_path = tmp_path / "manifest.json"
    output_dir = tmp_path / "mlx_sft_corpus"
    raw_member_value = "SYN-MEMBER-987"
    _write_manifest(
        manifest_path,
        [
            _record(
                path=denial_path,
                text=f"Denial has Member ID: {raw_member_value}. Missing authorization.",
                document_id="DOC-BLOCK-DENIAL",
                role="denial_letter",
                pair_id="PAIR-BLOCK",
                split="train",
            ),
            _record(
                path=appeal_path,
                text="Draft appeal requests review and keeps the record deidentified.",
                document_id="DOC-BLOCK-APPEAL",
                role="appeal_letter",
                pair_id="PAIR-BLOCK",
                split="train",
            ),
        ],
    )

    manifest = exporter.export_corpus_sft(
        manifest_path=manifest_path,
        output_dir=output_dir,
        model="test-model",
        adapter_path=tmp_path / "adapter",
    )

    serialized_manifest = json.dumps(manifest)
    assert manifest["training_allowed"] is False
    assert "member_id_label" in serialized_manifest
    assert raw_member_value not in serialized_manifest
    assert (output_dir / "train.jsonl").read_text(encoding="utf-8") == ""


def test_mlx_finetune_preflight_accepts_deidentified_corpus_manifest_tier(tmp_path):
    run_mlx_finetune = _load_script("run_mlx_finetune")
    manifest = {
        "adapter_path": str(tmp_path / "adapter"),
        "data_safety": {
            "data_tier": "approved_deidentified_corpus",
            "phi_status": "deidentified",
            "user_phi_allowed": False,
        },
        "format": "mlx_lm_chat_jsonl",
        "model": "test-model",
        "split_counts": {"train": 1, "valid": 1, "test": 1},
        "train_command": [
            "mlx_lm.lora",
            "--model",
            "test-model",
            "--train",
            "--data",
            str(tmp_path / "sft"),
            "--adapter-path",
            str(tmp_path / "adapter"),
        ],
        "training_allowed": True,
    }

    _, errors, _, blocked_reasons, _, _ = run_mlx_finetune.validate_manifest(
        manifest,
        tmp_path / "manifest.json",
    )

    assert errors == []
    assert blocked_reasons == []


def test_mlx_finetune_run_gate_blocks_corpus_training_without_ready_evidence(tmp_path):
    run_mlx_finetune = _load_script("run_mlx_finetune")
    manifest = {
        "data_safety": {
            "data_tier": "approved_deidentified_corpus",
            "phi_status": "deidentified",
            "user_phi_allowed": False,
        }
    }
    blocked_report = {
        "safe_to_review": True,
        "production_corpus_ready": False,
        "requirements": [
            {
                "requirement_id": "production_corpus_manifest_pair_evidence",
                "status": "blocked",
            }
        ],
    }

    report, blockers = run_mlx_finetune.production_corpus_run_gate(
        manifest,
        report_path=tmp_path / "production-corpus-report.json",
        report_payload=blocked_report,
        enforce=True,
    )

    assert "production_corpus_evidence_report_not_ready_for_training_run" in blockers
    assert "production_corpus_evidence_report_has_blocked_requirements" in blockers
    assert report["required_for_run"] is True
    assert report["report_ready"] is False
    assert report["blocked_requirement_ids"] == [
        "production_corpus_manifest_pair_evidence"
    ]
    assert report["safe_context"]["raw_document_content_included"] is False


def test_mlx_finetune_run_gate_allows_ready_corpus_evidence(tmp_path):
    run_mlx_finetune = _load_script("run_mlx_finetune")
    manifest = {
        "data_safety": {
            "data_tier": "approved_deidentified_corpus",
            "phi_status": "deidentified",
            "user_phi_allowed": False,
        }
    }
    ready_report = {
        "safe_to_review": True,
        "production_corpus_ready": True,
        "requirements": [
            {
                "requirement_id": "production_corpus_manifest_pair_evidence",
                "status": "ready",
            }
        ],
    }

    report, blockers = run_mlx_finetune.production_corpus_run_gate(
        manifest,
        report_path=tmp_path / "production-corpus-report.json",
        report_payload=ready_report,
        enforce=True,
    )

    assert blockers == []
    assert report["required_for_run"] is True
    assert report["report_ready"] is True
    assert report["report_safe_to_review"] is True


def test_mlx_finetune_run_gate_does_not_require_corpus_evidence_for_synthetic(tmp_path):
    run_mlx_finetune = _load_script("run_mlx_finetune")
    manifest = {
        "data_safety": {
            "data_tier": "synthetic",
            "phi_status": "no_phi",
            "user_phi_allowed": False,
        }
    }

    report, blockers = run_mlx_finetune.production_corpus_run_gate(
        manifest,
        report_path=tmp_path / "missing-report.json",
        enforce=True,
    )

    assert blockers == []
    assert report["required_for_run"] is False
    assert report["report_loaded"] is False


def test_mlx_finetune_runtime_check_blocks_without_metal(monkeypatch):
    run_mlx_finetune = _load_script("run_mlx_finetune")

    class Result:
        returncode = 1
        stdout = ""
        stderr = "RuntimeError: [metal::load_device] No Metal device available."

    monkeypatch.setattr(run_mlx_finetune.shutil, "which", lambda _: "/tmp/mlx_lm.lora")
    monkeypatch.setattr(run_mlx_finetune.subprocess, "run", lambda *_, **__: Result())

    report, errors = run_mlx_finetune.check_mlx_lora()

    assert report["available"] is True
    assert report["runtime_ready"] is False
    assert report["help_returncode"] == 1
    assert "Metal device" in report["error"]
    assert errors == ["mlx_lm.lora cannot access a Metal device in this session"]


def test_mlx_finetune_runtime_check_accepts_help(monkeypatch):
    run_mlx_finetune = _load_script("run_mlx_finetune")

    class Result:
        returncode = 0
        stdout = "usage: mlx_lm.lora"
        stderr = ""

    monkeypatch.setattr(run_mlx_finetune.shutil, "which", lambda _: "/tmp/mlx_lm.lora")
    monkeypatch.setattr(run_mlx_finetune.subprocess, "run", lambda *_, **__: Result())

    report, errors = run_mlx_finetune.check_mlx_lora()

    assert report["available"] is True
    assert report["runtime_ready"] is True
    assert report["help_returncode"] == 0
    assert report["error"] is None
    assert errors == []
