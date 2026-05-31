import base64
import html
import io
import textwrap
import zipfile
from datetime import datetime

from app.schemas.denial_workflow import (
    DenialWorkflowAnalysisResponse,
    DenialWorkflowExportResponse,
)


def _lines_for_items(label: str, items: list[str]) -> list[str]:
    lines = [f"## {label}", ""]
    if not items:
        lines.extend(["- None identified.", ""])
        return lines
    lines.extend([f"- {item}" for item in items])
    lines.append("")
    return lines


def render_workflow_markdown(workflow: DenialWorkflowAnalysisResponse) -> str:
    lines = [
        "# ClaimGuard Denial Workflow Packet",
        "",
        "Status: draft_for_human_review",
        "Human review required: yes",
        "",
        f"Generated: {workflow.analyzed_at.isoformat()}Z",
        "",
        "## Case Summary",
        "",
        workflow.case_summary,
        "",
        "## Routing",
        "",
        f"- Plan type: {workflow.plan_type}",
        f"- Denial type: {workflow.denial_type}",
        f"- Recommended route: {workflow.recommended_route}",
        f"- Route confidence: {workflow.route_confidence}",
        "",
    ]

    known = [f"{item.field}: {item.value}" for item in workflow.known_from_documents]
    inferred = [f"{item.field}: {item.value}" for item in workflow.inferred]
    missing = [task.task for task in workflow.missing_needs_human_verification]
    deadlines = [
        (
            f"{item.deadline_type}: source={item.source_stated_deadline}, "
            f"calculated={item.calculated_deadline}, source_id={item.rule_source_id}, "
            f"status={item.verification_status}"
        )
        for item in workflow.deadline_table
    ]
    evidence = [
        f"{item.evidence_type}: {item.description} ({item.priority})"
        for item in workflow.evidence_gaps
    ]
    attachments = [
        f"{item.label}: {item.description}"
        for item in workflow.attachment_index
    ]
    follow_up = [
        f"{item.action}; trigger={item.trigger}; due={item.due_date}"
        for item in workflow.follow_up_plan
    ]
    phases = [
        (
            f"{item.phase_id} {item.phase_name}: {item.status}; owner={item.owner}; "
            f"artifact={item.output_artifact}"
        )
        for item in workflow.workflow_phase_checklist
    ]
    quality = [
        f"{item.status}: {item.check} - {item.details}"
        for item in workflow.quality_checks
    ]
    phi_scan = [
        f"status: {workflow.phi_scan.status}",
        f"finding_count: {workflow.phi_scan.finding_count}",
        f"finding_types: {', '.join(workflow.phi_scan.finding_types) or 'none'}",
        f"values_redacted: {workflow.phi_scan.values_redacted}",
        f"review_required: {workflow.phi_scan.review_required}",
    ]
    model = [
        f"provider: {workflow.model_metadata.get('provider')}",
        f"model: {workflow.model_metadata.get('model')}",
        f"student_schema_contract: {workflow.model_metadata.get('student_schema_contract')}",
        f"accepted_for_denial_workflow: {workflow.model_metadata.get('accepted_for_denial_workflow')}",
        f"llm_used: {workflow.model_metadata.get('llm_used')}",
    ]

    lines.extend(_lines_for_items("Known From Documents", known))
    lines.extend(_lines_for_items("Inferred", inferred))
    lines.extend(_lines_for_items("Missing Or Needs Human Verification", missing))
    lines.extend(_lines_for_items("Deadlines", deadlines))
    lines.extend(_lines_for_items("Evidence Gaps", evidence))
    lines.extend(["## Appeal Strategy", "", workflow.appeal_strategy, ""])
    if workflow.draft_appeal_letter:
        lines.extend(["## Draft Appeal Letter", "", workflow.draft_appeal_letter, ""])
    lines.extend(_lines_for_items("Attachment Index", attachments))
    lines.extend(_lines_for_items("Follow-Up Plan", follow_up))
    lines.extend(_lines_for_items("Denial Skill Phase Checklist", phases))
    lines.extend(_lines_for_items("Quality Checks", quality))
    lines.extend(_lines_for_items("PHI Scan Summary", phi_scan))
    lines.extend(_lines_for_items("Model And Student Contract", model))
    lines.extend(["## Warnings", ""])
    if workflow.warnings:
        lines.extend([f"- {warning}" for warning in workflow.warnings])
    else:
        lines.append("- Human reviewer must still verify facts, deadlines, channels, and PHI scope.")
    lines.append("")
    return "\n".join(lines)


def _minimal_docx(markdown: str) -> bytes:
    escaped_lines = [
        f"<w:p><w:r><w:t>{html.escape(line)}</w:t></w:r></w:p>"
        for line in markdown.splitlines()
    ]
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(escaped_lines)}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _minimal_pdf(text: str) -> bytes:
    wrapped_lines: list[str] = []
    for line in text.splitlines():
        wrapped_lines.extend(textwrap.wrap(line, width=88) or [""])
    content_lines = []
    y = 760
    for line in wrapped_lines[:55]:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines.append(f"BT /F1 10 Tf 50 {y} Td ({safe}) Tj ET")
        y -= 13
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length "
        + str(len(stream)).encode("ascii")
        + b" >> stream\n"
        + stream
        + b"\nendstream endobj\n",
    ]
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(output.tell())
        output.write(obj)
    xref_start = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    return output.getvalue()


def export_workflow(
    workflow: DenialWorkflowAnalysisResponse,
    export_format: str,
    filename_prefix: str,
) -> DenialWorkflowExportResponse:
    markdown = render_workflow_markdown(workflow)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_prefix = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-"
        for char in filename_prefix
    ).strip("-") or "claimguard-denial-workflow"

    if export_format == "markdown":
        return DenialWorkflowExportResponse(
            filename=f"{safe_prefix}-{timestamp}.md",
            content_type="text/markdown; charset=utf-8",
            encoding="utf-8",
            content=markdown,
        )
    if export_format == "docx":
        return DenialWorkflowExportResponse(
            filename=f"{safe_prefix}-{timestamp}.docx",
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            encoding="base64",
            content=base64.b64encode(_minimal_docx(markdown)).decode("ascii"),
        )
    if export_format == "pdf":
        return DenialWorkflowExportResponse(
            filename=f"{safe_prefix}-{timestamp}.pdf",
            content_type="application/pdf",
            encoding="base64",
            content=base64.b64encode(_minimal_pdf(markdown)).decode("ascii"),
        )
    raise ValueError(f"Unsupported export format: {export_format}")
