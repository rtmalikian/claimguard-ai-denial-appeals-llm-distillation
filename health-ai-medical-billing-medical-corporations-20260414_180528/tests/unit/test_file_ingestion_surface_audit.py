import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
AUDIT_SCRIPT = SCRIPT_DIR / "audit_file_ingestion_surfaces.py"


def _load_audit() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("audit_file_ingestion_surfaces", AUDIT_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_file_ingestion_surfaces_are_registered_and_ready():
    audit = _load_audit()

    report = audit.audit_file_ingestion_surfaces()

    assert report["ready"] is True
    assert report["blocked_reasons"] == []
    assert report["summary"]["discovered_count"] == 3
    assert report["summary"]["registered_count"] == 3
    statuses_by_route = {
        surface["route"]: surface["status"]
        for surface in report["surfaces"]
    }
    assert statuses_by_route == {
        "/claims/batch-upload": "ready",
        "/claims/remittance-upload": "ready",
        "/claims/upload-document": "ready",
    }
    batch_surface = next(
        surface for surface in report["surfaces"]
        if surface["route"] == "/claims/batch-upload"
    )
    assert batch_surface["missing_markers"] == []
    for marker in [
        "_raise_batch_claim_upload_error",
        "EDIParserError",
        "parser_stage",
        "segment_index",
        "segment_id",
        "safe_context",
    ]:
        assert marker in batch_surface["required_markers"]
    remittance_surface = next(
        surface for surface in report["surfaces"]
        if surface["route"] == "/claims/remittance-upload"
    )
    assert remittance_surface["missing_markers"] == []
    for marker in [
        "_raise_remittance_upload_error",
        "EDI835ParserError",
        "claim_payment_count",
        "validation_issue_count",
        "parser_stage",
        "segment_index",
        "segment_id",
        "safe_context",
    ]:
        assert marker in remittance_surface["required_markers"]
    upload_surface = next(
        surface for surface in report["surfaces"]
        if surface["route"] == "/claims/upload-document"
    )
    assert upload_surface["missing_markers"] == []
    for marker in [
        "_raise_upload_document_error",
        "CLAIM_DOCUMENT_UPLOAD_MAX_BYTES",
        "processing_stage",
        "content_length",
        "max_upload_size_bytes",
    ]:
        assert marker in upload_surface["required_markers"]


def test_unregistered_uploadfile_endpoint_is_blocked(tmp_path):
    audit = _load_audit()
    api_root = tmp_path / "app" / "api" / "v1"
    api_root.mkdir(parents=True)
    (api_root / "new_upload.py").write_text(
        "\n".join(
            [
                "from fastapi import APIRouter, File, UploadFile",
                "router = APIRouter(prefix='/new')",
                "@router.post('/upload')",
                "async def upload_new_file(file: UploadFile = File(...)):",
                "    return {'ok': True}",
            ]
        ),
        encoding="utf-8",
    )

    report = audit.audit_file_ingestion_surfaces(
        api_root=api_root,
        expected_surfaces=[],
    )

    assert report["ready"] is False
    assert report["summary"]["unregistered_count"] == 1
    assert any("unregistered file-ingestion endpoint" in item for item in report["blocked_reasons"])


def test_registered_endpoint_missing_surface_markers_is_blocked(tmp_path):
    audit = _load_audit()
    api_root = tmp_path / "app" / "api" / "v1"
    api_root.mkdir(parents=True)
    (api_root / "claims.py").write_text(
        "\n".join(
            [
                "from fastapi import APIRouter, File, UploadFile",
                "router = APIRouter(prefix='/claims')",
                "@router.post('/upload-document')",
                "async def upload_document(file: UploadFile = File(...)):",
                "    return {'ok': True}",
            ]
        ),
        encoding="utf-8",
    )

    report = audit.audit_file_ingestion_surfaces(
        api_root=api_root,
        expected_surfaces=[
            {
                "route": "/claims/upload-document",
                "function_name": "upload_document",
                "required_markers": ["document_surface_inspection"],
            }
        ],
    )

    assert report["ready"] is False
    assert report["surfaces"][0]["registered"] is True
    assert report["surfaces"][0]["missing_markers"] == ["document_surface_inspection"]
