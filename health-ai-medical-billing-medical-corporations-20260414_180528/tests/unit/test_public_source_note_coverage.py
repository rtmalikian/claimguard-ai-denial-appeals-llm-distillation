import importlib.util
import json
import sys
from hashlib import sha256
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
AUDIT_SCRIPT = SCRIPT_DIR / "audit_public_source_notes.py"


def _load_audit() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "audit_public_source_notes",
        AUDIT_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _note_text(url: str) -> str:
    return f"""Public government corpus source note: Synthetic public source.

Source URL:
{url}

Corpus role:
Appeal-process reference for route and source-grounding checks.

Safety notes:
This checked-in source note contains no user documents, no patient facts, no
claim identifiers, no contact details, and no credentials. It is not a denial
letter or appeal letter pair and is not exported to MLX SFT training splits.

Use constraints:
Use this record as public source coverage and retrieval/governance context only.
Any deadline, route, or plan-specific instruction must be verified before use.
"""


def _checksum(text: str) -> str:
    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()


def _registry(url: str) -> list[dict]:
    return [
        {
            "source_id": "SRC-PUBLIC-1",
            "title": "Synthetic public source",
            "url": url,
            "source_type": "public_rule",
            "tier": 1,
            "phi_status": "no_phi",
            "license_status": "public_government_source",
        }
    ]


def _manifest(note_path: Path, note_text: str, *, training_eligible: bool = False) -> dict:
    return {
        "version": "test",
        "records": [
            {
                "source_id": "SRC-PUBLIC-NOTE-1",
                "document_id": "DOC-PUBLIC-NOTE-1",
                "pair_id": None,
                "source_type": "public_government_source",
                "document_role": "rule_source",
                "source_url_or_path": str(note_path),
                "checksum": _checksum(note_text),
                "phi_status": "no_phi",
                "deidentification_status": "privacy_review_passed",
                "license_status": "public_government_source",
                "review_status": "privacy_review_passed",
                "residual_risk_score": 0.0,
                "training_eligible": training_eligible,
                "split": "none",
                "micro_skill_ids": ["MS01"],
            }
        ],
    }


def test_public_source_note_coverage_passes_for_registry_note(tmp_path):
    audit = _load_audit()
    url = "https://example.gov/public-source"
    note_text = _note_text(url)
    note_path = tmp_path / "public_source.txt"
    registry_path = tmp_path / "source_registry.json"
    manifest_path = tmp_path / "manifest.json"
    note_path.write_text(note_text, encoding="utf-8")
    _write_json(registry_path, _registry(url))
    _write_json(manifest_path, _manifest(note_path, note_text))

    report = audit.audit_public_source_notes(
        registry_path=registry_path,
        manifest_path=manifest_path,
    )

    assert report["ready"] is True
    assert report["evidence"]["expected_public_source_count"] == 1
    assert report["evidence"]["covered_registry_source_count"] == 1
    assert report["evidence"]["training_exclusion_attested"] is True


def test_public_source_note_coverage_blocks_missing_registry_note(tmp_path):
    audit = _load_audit()
    registry_path = tmp_path / "source_registry.json"
    manifest_path = tmp_path / "manifest.json"
    _write_json(registry_path, _registry("https://example.gov/missing-source"))
    _write_json(manifest_path, {"version": "test", "records": []})

    report = audit.audit_public_source_notes(
        registry_path=registry_path,
        manifest_path=manifest_path,
    )

    assert report["ready"] is False
    assert "SRC-PUBLIC-1" in report["evidence"]["missing_registry_source_ids"]
    assert "public source notes missing registry coverage" in report["blockers"]


def test_public_source_note_coverage_blocks_training_eligible_notes(tmp_path):
    audit = _load_audit()
    url = "https://example.gov/public-source"
    note_text = _note_text(url)
    note_path = tmp_path / "public_source.txt"
    registry_path = tmp_path / "source_registry.json"
    manifest_path = tmp_path / "manifest.json"
    note_path.write_text(note_text, encoding="utf-8")
    _write_json(registry_path, _registry(url))
    _write_json(manifest_path, _manifest(note_path, note_text, training_eligible=True))

    report = audit.audit_public_source_notes(
        registry_path=registry_path,
        manifest_path=manifest_path,
    )

    assert report["ready"] is False
    assert report["evidence"]["invalid_training_flag_count"] == 1
    assert "public source note must not be training eligible" in json.dumps(report)


def test_public_source_note_coverage_blocks_phi_without_emitting_value(tmp_path):
    audit = _load_audit()
    url = "https://example.gov/public-source"
    raw_email = "person" + "@" + "example.com"
    note_text = _note_text(url) + f"\nUnsafe contact marker: {raw_email}\n"
    note_path = tmp_path / "public_source.txt"
    registry_path = tmp_path / "source_registry.json"
    manifest_path = tmp_path / "manifest.json"
    note_path.write_text(note_text, encoding="utf-8")
    _write_json(registry_path, _registry(url))
    _write_json(manifest_path, _manifest(note_path, note_text))

    report = audit.audit_public_source_notes(
        registry_path=registry_path,
        manifest_path=manifest_path,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ready"] is False
    assert report["evidence"]["phi_scan"]["finding_count"] == 1
    assert "email_like" in serialized
    assert raw_email not in serialized
