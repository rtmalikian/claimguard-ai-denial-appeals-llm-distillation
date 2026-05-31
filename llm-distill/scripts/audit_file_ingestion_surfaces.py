#!/usr/bin/env python3
"""Audit file-ingestion endpoints for PHI surface and governance coverage."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "health-ai-medical-billing-medical-corporations-20260414_180528"
DEFAULT_API_ROOT = APP_ROOT / "app" / "api" / "v1"
DEFAULT_OUTPUT = (
    REPO_ROOT / "llm-distill" / "evals" / "reports" / "file_ingestion_surface_audit_report.json"
)

DEFAULT_EXPECTED_SURFACES: list[dict[str, Any]] = [
    {
        "route": "/claims/upload-document",
        "function_name": "upload_document",
        "module_path": "app/api/v1/claims.py",
        "required_markers": [
            "_inspect_document_surfaces",
            "document_surface_inspection",
            "document_access_scope",
            "CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM",
            "document_uploaded",
            "surface_count",
            "surface_blocking_count",
            "surface_residual_risk_score",
            "surface_deidentification_status",
            "source_filename_present",
            "source_file_extension",
            "_raise_upload_document_error",
            "CLAIM_DOCUMENT_UPLOAD_MAX_BYTES",
            "error_code",
            "processing_stage",
            "content_length",
            "max_upload_size_bytes",
        ],
        "coverage_notes": [
            "Runs metadata-only document surface inspection over filename, MIME type, extracted text/OCR text, and processing metadata.",
            "Rejects unsupported, empty, and oversized uploads with structured safe error details before file processing or OCR.",
            "Persists redacted inspection summary with the analyzed claim.",
            "Stores claim document access-scope metadata and safe audit counters without raw filenames or matched PHI/PII values.",
        ],
    },
    {
        "route": "/claims/batch-upload",
        "function_name": "batch_upload_claims",
        "module_path": "app/api/v1/claims.py",
        "required_markers": [
            "_inspect_document_surfaces",
            "document_surface_inspection",
            "CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM",
            "claims_batch_uploaded",
            "source_filename_present",
            "source_file_extension",
            "source_mime_type",
            "edi_parser",
            "segment_count",
            "claim_count",
            "validation_issue_count",
            "surface_count",
            "surface_blocking_count",
            "surface_residual_risk_score",
            "surface_deidentification_status",
            "_raise_batch_claim_upload_error",
            "EDIParserError",
            "error_code",
            "parser_stage",
            "field",
            "segment_index",
            "segment_id",
            "safe_context",
        ],
        "coverage_notes": [
            "Accepts only text EDI 837 batch files with .edi or .txt extensions and a 10 MB limit.",
            "Runs metadata-only document surface inspection over filename, MIME type, EDI text, and parser metadata.",
            "Returns structured per-claim parser results without raw segment payloads and logs only safe counters/booleans.",
            "Rejected uploads return structured parser-stage, field, and segment context without raw filenames, EDI text, or raw segment payloads.",
        ],
    },
    {
        "route": "/claims/remittance-upload",
        "function_name": "upload_remittance",
        "module_path": "app/api/v1/claims.py",
        "required_markers": [
            "_inspect_document_surfaces",
            "document_surface_inspection",
            "CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM",
            "remittance_uploaded",
            "source_filename_present",
            "source_file_extension",
            "source_mime_type",
            "edi_parser",
            "segment_count",
            "claim_payment_count",
            "validation_issue_count",
            "surface_count",
            "surface_blocking_count",
            "surface_residual_risk_score",
            "surface_deidentification_status",
            "_raise_remittance_upload_error",
            "EDI835ParserError",
            "error_code",
            "parser_stage",
            "field",
            "segment_index",
            "segment_id",
            "safe_context",
        ],
        "coverage_notes": [
            "Accepts only text EDI 835 remittance files with .835, .edi, or .txt extensions and a 10 MB limit.",
            "Runs metadata-only document surface inspection over filename, MIME type, EDI text, and parser metadata.",
            "Returns safe per-claim payment, adjustment, and remark-code summaries without raw patient or payer control numbers.",
            "Rejected uploads return structured parser-stage, field, and segment context without raw filenames, EDI text, raw segment payloads, patient identifiers, or payer control numbers.",
        ],
    }
]


@dataclass
class RouteSurface:
    module_path: str
    route: str
    methods: list[str]
    function_name: str
    file_parameter_names: list[str]
    source_text: str


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _call_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _annotation_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _annotation_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    if isinstance(node, ast.Subscript):
        return _annotation_name(node.value)
    return ""


def _router_prefix(tree: ast.Module) -> str:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "router" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        if _call_name(node.value.func) != "APIRouter":
            continue
        for keyword in node.value.keywords:
            if keyword.arg == "prefix":
                return _literal_string(keyword.value) or ""
    return ""


def _route_decorators(node: ast.AsyncFunctionDef | ast.FunctionDef) -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        call_name = _call_name(decorator.func)
        if call_name not in {"router.post", "router.put", "router.patch", "router.delete"}:
            continue
        route_path = _literal_string(decorator.args[0]) if decorator.args else None
        if route_path is None:
            continue
        routes.append((call_name.rsplit(".", 1)[-1].upper(), route_path))
    return routes


def _is_file_default(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Call) and _call_name(node.func) == "File"


def _file_parameter_names(node: ast.AsyncFunctionDef | ast.FunctionDef) -> list[str]:
    args = list(node.args.args)
    defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)
    file_args: list[str] = []
    for arg, default in zip(args, defaults, strict=True):
        annotation = _annotation_name(arg.annotation)
        if annotation.endswith("UploadFile") or _is_file_default(default):
            if annotation.endswith("UploadFile") or _is_file_default(default):
                file_args.append(arg.arg)
    return file_args


def discover_file_ingestion_surfaces(api_root: Path) -> list[RouteSurface]:
    surfaces: list[RouteSurface] = []
    for path in sorted(api_root.rglob("*.py")):
        try:
            source_text = path.read_text(encoding="utf-8")
            tree = ast.parse(source_text, filename=str(path))
        except (OSError, SyntaxError):
            continue
        prefix = _router_prefix(tree)
        for node in tree.body:
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            file_parameter_names = _file_parameter_names(node)
            if not file_parameter_names:
                continue
            route_entries = _route_decorators(node)
            if not route_entries:
                continue
            function_source = ast.get_source_segment(source_text, node) or ""
            for method, route_path in route_entries:
                surfaces.append(
                    RouteSurface(
                        module_path=str(path.relative_to(api_root.parent.parent.parent)),
                        route=f"{prefix}{route_path}",
                        methods=[method],
                        function_name=node.name,
                        file_parameter_names=file_parameter_names,
                        source_text=function_source,
                    )
                )
    return surfaces


def _expected_by_key(expected_surfaces: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(surface["route"]), str(surface["function_name"])): surface
        for surface in expected_surfaces
    }


def audit_file_ingestion_surfaces(
    *,
    api_root: Path = DEFAULT_API_ROOT,
    expected_surfaces: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected = expected_surfaces or DEFAULT_EXPECTED_SURFACES
    expected_by_key = _expected_by_key(expected)
    discovered = discover_file_ingestion_surfaces(api_root)
    discovered_by_key = {(surface.route, surface.function_name): surface for surface in discovered}
    blockers: list[str] = []
    warnings: list[str] = []
    surface_reports: list[dict[str, Any]] = []

    for key, surface in sorted(discovered_by_key.items()):
        expected_surface = expected_by_key.get(key)
        if expected_surface is None:
            blockers.append(
                f"unregistered file-ingestion endpoint: {surface.route} ({surface.function_name})"
            )
            surface_reports.append(
                {
                    "route": surface.route,
                    "function_name": surface.function_name,
                    "module_path": surface.module_path,
                    "methods": surface.methods,
                    "file_parameter_names": surface.file_parameter_names,
                    "registered": False,
                    "missing_markers": [],
                    "status": "blocked",
                }
            )
            continue

        missing_markers = [
            marker
            for marker in expected_surface.get("required_markers", [])
            if marker not in surface.source_text
        ]
        if missing_markers:
            blockers.append(
                f"{surface.route} ({surface.function_name}) missing required coverage markers: "
                + ", ".join(missing_markers)
            )
        surface_reports.append(
            {
                "route": surface.route,
                "function_name": surface.function_name,
                "module_path": surface.module_path,
                "methods": surface.methods,
                "file_parameter_names": surface.file_parameter_names,
                "registered": True,
                "expected_module_path": expected_surface.get("module_path"),
                "required_markers": expected_surface.get("required_markers", []),
                "missing_markers": missing_markers,
                "coverage_notes": expected_surface.get("coverage_notes", []),
                "status": "blocked" if missing_markers else "ready",
            }
        )

    for key, expected_surface in sorted(expected_by_key.items()):
        if key not in discovered_by_key:
            blockers.append(
                f"expected file-ingestion endpoint not found: {expected_surface['route']} "
                f"({expected_surface['function_name']})"
            )

    if not discovered:
        warnings.append("No UploadFile/File endpoints were discovered under the API root.")

    unique_blockers = sorted(set(blockers))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": not unique_blockers,
        "api_root": str(api_root),
        "blocked_reasons": unique_blockers,
        "warnings": warnings,
        "summary": {
            "discovered_count": len(discovered),
            "registered_count": sum(1 for report in surface_reports if report["registered"]),
            "unregistered_count": sum(1 for report in surface_reports if not report["registered"]),
            "expected_count": len(expected),
        },
        "surfaces": surface_reports,
        "notes": [
            "This audit uses AST/source metadata and does not inspect uploaded file contents.",
            "Any future UploadFile/File endpoint must be registered here and show metadata-only surface inspection plus governance/audit markers before production use.",
            "Matched PHI/PII values, raw filenames, and uploaded document content are not included in this report.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-root", type=Path, default=DEFAULT_API_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = audit_file_ingestion_surfaces(api_root=args.api_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote file-ingestion surface audit report to {args.output}")
    if args.fail_on_blocked and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
