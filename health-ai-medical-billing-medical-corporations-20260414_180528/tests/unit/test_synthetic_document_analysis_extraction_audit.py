import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
AUDIT_SCRIPT = SCRIPT_DIR / "audit_synthetic_document_analysis_extraction.py"


def _load_audit() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "audit_synthetic_document_analysis_extraction",
        AUDIT_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_denial(path: Path, *, procedure: str = "99214") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""Training synthetic corpus pair PAIR-SYN-TEST.

Aster Health Plan
Synthetic adverse benefit determination
Case reference SYN-CASE-TEST
Coverage reference SYN-COVERAGE-TEST

Administrative context: Synthetic member placeholder [PATIENT_TEST]; provider
group Northgate Surgical Center; service reviewed office visit follow-up;
procedure code {procedure}; billed amount $612.00.

Determination rationale: required documentation was missing or incomplete.
This synthetic notice is for model training only and is not connected to any
real person.
""",
        encoding="utf-8",
    )


def _manifest_record(document_id: str, path: Path, role: str = "denial_letter") -> dict:
    return {
        "document_id": document_id,
        "document_role": role,
        "source_url_or_path": str(path),
    }


def test_synthetic_document_analysis_extraction_audit_accepts_generated_style(tmp_path):
    audit = _load_audit()
    denial_one = tmp_path / "letters" / "train" / "pair-001_denial.txt"
    denial_two = tmp_path / "letters" / "valid" / "pair-002_denial.txt"
    _write_denial(denial_one, procedure="G0299")
    _write_denial(denial_two, procedure="72148")
    manifest = tmp_path / "manifest_synthetic_900.json"
    _write_json(
        manifest,
        {
            "records": [
                _manifest_record("DOC-SYN-001-DENIAL", denial_one),
                _manifest_record("DOC-SYN-002-DENIAL", denial_two),
                _manifest_record("DOC-SYN-001-APPEAL", tmp_path / "appeal.txt", "appeal_letter"),
            ],
        },
    )

    report = audit.build_report(manifest, tmp_path, min_denials=2)

    assert report["ready"] is True
    assert report["evidence"]["checked_denial_count"] == 2
    assert report["evidence"]["missing_procedure_code_count"] == 0
    assert report["evidence"]["unexpected_policy_number_count"] == 0


def test_synthetic_document_analysis_extraction_audit_blocks_missing_procedure(tmp_path):
    audit = _load_audit()
    denial = tmp_path / "letters" / "train" / "pair-001_denial.txt"
    _write_denial(denial, procedure="review pending")
    manifest = tmp_path / "manifest_synthetic_900.json"
    _write_json(
        manifest,
        {
            "records": [
                _manifest_record("DOC-SYN-001-DENIAL", denial),
            ],
        },
    )

    report = audit.build_report(manifest, tmp_path, min_denials=1)

    assert report["ready"] is False
    assert report["evidence"]["missing_procedure_code_count"] == 1
    assert "missing_procedure_code_count must be 0" in report["blockers"]
