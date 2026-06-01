import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
GATE_SCRIPT = SCRIPT_DIR / "run_student_acceptance.py"


def _load_gate() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("run_student_acceptance", GATE_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _configure_temp_repo(monkeypatch, gate: ModuleType, tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path / "repo"
    report_dir = repo_root / "llm-distill" / "evals" / "reports"
    adapter_root = repo_root / "llm-distill" / "models" / "adapters"
    adapter_path = adapter_root / "claimguard-qwen3-4b-lora-reviewed"
    adapter_path.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    monkeypatch.setattr(gate, "REPO_ROOT", repo_root)
    monkeypatch.setattr(gate, "REPORT_DIR", report_dir)
    monkeypatch.setattr(gate, "DEFAULT_ADAPTER_ROOT", adapter_root)
    return {
        "repo_root": repo_root,
        "report_dir": report_dir,
        "adapter_root": adapter_root,
        "adapter_path": adapter_path,
    }


def _workflow_report() -> dict:
    return {
        "summary": {
            "score_ratio": 1.0,
            "scenario_count": 10,
            "passed_count": 10,
        },
        "results": [
            {
                "scenario_id": f"synthetic-{index}",
                "passed": True,
                "forbidden_terms_found": [],
            }
            for index in range(10)
        ],
    }


def _benchmark_report() -> dict:
    return {
        "model": "Qwen/Qwen3-4B-MLX-4bit",
        "summary": {
            "endpoint_available": True,
            "dry_run": False,
            "endpoint_error_count": 0,
            "record_count": 10,
            "score_ratio": 0.9667,
        },
        "results": [
            {
                "runtime": {"parse_error": False},
                "score": {
                    "json_valid": True,
                    "required_keys_present": True,
                    "human_review_required": True,
                    "draft_for_human_review": True,
                },
            }
            for _ in range(10)
        ],
    }


def _fine_tune_report(adapter_path: Path) -> dict:
    return {
        "mode": "run",
        "training_attempted": True,
        "training_succeeded": True,
        "blocked_reasons": [],
        "preflight_errors": [],
        "process": {"returncode": 0},
        "checks": {
            "manifest": {"training_allowed": True},
            "data": {"total_phi_findings": 0},
            "adapter_output": {"path": str(adapter_path)},
        },
    }


def _write_ready_reports(paths: dict[str, Path]) -> dict[str, Path]:
    report_dir = paths["report_dir"]
    workflow = report_dir / "workflow_baseline_report.json"
    fine_tune = report_dir / "mlx_finetune_preflight_report.json"
    base = report_dir / "local_mlx_benchmark_report.json"
    student = report_dir / "student_mlx_benchmark_report.json"
    _write_json(workflow, _workflow_report())
    _write_json(fine_tune, _fine_tune_report(paths["adapter_path"]))
    _write_json(base, _benchmark_report())
    _write_json(student, _benchmark_report())
    return {
        "workflow": workflow,
        "fine_tune": fine_tune,
        "base": base,
        "student": student,
    }


def _build_report(gate: ModuleType, reports: dict[str, Path]) -> dict:
    return gate.build_report(
        workflow_report_path=reports["workflow"],
        fine_tune_report_path=reports["fine_tune"],
        base_benchmark_path=reports["base"],
        student_benchmark_path=reports["student"],
    )


def test_student_acceptance_ready_requires_repo_report_paths_and_adapter_root(
    monkeypatch,
    tmp_path,
):
    gate = _load_gate()
    paths = _configure_temp_repo(monkeypatch, gate, tmp_path)
    reports = _write_ready_reports(paths)

    report = _build_report(gate, reports)
    serialized = json.dumps(report, sort_keys=True)

    assert report["release_ready"] is True
    assert report["blocked_reasons"] == []
    assert str(paths["repo_root"]) not in serialized
    assert report["inputs"]["workflow_report"] == (
        "llm-distill/evals/reports/workflow_baseline_report.json"
    )
    for check in report["checks"]["input_paths"].values():
        assert check["inside_report_dir"] is True
        assert check["path"].startswith("llm-distill/evals/reports/")
        assert check["expected_report_dir"] == "llm-distill/evals/reports"
        assert check["raw_report_values_included"] is False
    assert (
        report["checks"]["fine_tune_run"]["adapter_path_inside_expected_root"]
        is True
    )
    assert report["checks"]["fine_tune_run"]["adapter_path_exists"] is True
    assert report["checks"]["fine_tune_run"]["adapter_path"] == (
        "llm-distill/models/adapters/claimguard-qwen3-4b-lora-reviewed"
    )
    assert report["checks"]["fine_tune_run"]["expected_adapter_root"] == (
        "llm-distill/models/adapters"
    )


def test_student_acceptance_blocks_outside_input_report_path(
    monkeypatch,
    tmp_path,
):
    gate = _load_gate()
    paths = _configure_temp_repo(monkeypatch, gate, tmp_path)
    reports = _write_ready_reports(paths)
    outside_workflow = tmp_path / "outside-workflow-report.json"
    _write_json(outside_workflow, _workflow_report())
    reports["workflow"] = outside_workflow

    report = _build_report(gate, reports)
    serialized = json.dumps(report, sort_keys=True)

    assert report["release_ready"] is False
    assert (
        "workflow report path must stay inside llm-distill/evals/reports"
        in report["blocked_reasons"]
    )
    assert report["checks"]["input_paths"]["workflow"]["inside_report_dir"] is False
    assert report["checks"]["input_paths"]["workflow"]["path"] == "external_path_redacted"
    assert "external_path_redacted" in serialized
    assert str(outside_workflow) not in serialized
    assert "outside-workflow-report" not in serialized


def test_student_acceptance_blocks_adapter_outside_adapter_root(
    monkeypatch,
    tmp_path,
):
    gate = _load_gate()
    paths = _configure_temp_repo(monkeypatch, gate, tmp_path)
    reports = _write_ready_reports(paths)
    outside_adapter = tmp_path / "outside-adapter"
    outside_adapter.mkdir()
    _write_json(reports["fine_tune"], _fine_tune_report(outside_adapter))

    report = _build_report(gate, reports)
    fine_tune_check = report["checks"]["fine_tune_run"]

    assert report["release_ready"] is False
    assert (
        "trained adapter output path must stay inside llm-distill/models/adapters"
        in report["blocked_reasons"]
    )
    assert fine_tune_check["adapter_path_exists"] is True
    assert fine_tune_check["adapter_path_inside_expected_root"] is False
    assert fine_tune_check["adapter_path"] == "external_path_redacted"
    assert str(outside_adapter) not in json.dumps(report, sort_keys=True)
