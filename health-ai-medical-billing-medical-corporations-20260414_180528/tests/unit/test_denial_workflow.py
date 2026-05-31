import base64

import pytest

from app.schemas.denial_workflow import (
    DenialWorkflowAnalysisRequest,
    DenialWorkflowExportRequest,
)
from app.services.denial_workflow import DenialWorkflowService
from app.services.export import export_workflow
from app.services.retrieval import KeywordRetrievalIndex, build_default_rule_chunks


@pytest.mark.asyncio
async def test_medical_necessity_workflow_has_source_status_and_review_gate():
    text = (
        "Denial Notice\n"
        "Insurance: Example Health\n"
        "Date of Service: 04/10/2026\n"
        "Denial Date: 04/20/2026\n"
        "Claim Number: SYN-1001\n"
        "Reason for Denial: The MRI is denied because it is not medically necessary.\n"
        "You may appeal within 180 days."
    )

    result = await DenialWorkflowService().analyze(
        DenialWorkflowAnalysisRequest(document_text=text, source_document_id="syn-denial-1")
    )

    assert result.denial_type == "medical_necessity"
    assert result.recommended_route == "formal_internal_appeal"
    assert result.human_review_required is True
    assert result.draft_appeal_letter
    assert "draft_for_human_review" in result.draft_appeal_letter
    assert any(item.source.source_status == "known_from_documents" for item in result.known_from_documents)
    assert any(task.task == "Verify plan type and controlling appeal authority" for task in result.missing_needs_human_verification)
    assert any(deadline.rule_source_id == "SRC-DOL-CLAIMS" for deadline in result.deadline_table)
    assert any(gap.evidence_type == "clinician_lmn" for gap in result.evidence_gaps)
    assert len(result.workflow_phase_checklist) == 15
    assert any(
        phase.phase_id == "P09" and phase.status == "ready_for_human_review"
        for phase in result.workflow_phase_checklist
    )
    assert result.model_metadata["student_schema_contract"] == "strict_claim_guard_json_v1"


@pytest.mark.asyncio
async def test_coding_modifier_denial_routes_to_corrected_claim():
    text = (
        "EOB\n"
        "Payer: Example Health\n"
        "Claim Number: SYN-2001\n"
        "Denial Code: CO-4\n"
        "Reason for Denial: Procedure code is inconsistent with modifier. "
        "Corrected claim accepted within 30 days."
    )

    result = await DenialWorkflowService().analyze(
        DenialWorkflowAnalysisRequest(document_text=text, source_document_id="syn-eob-1")
    )

    assert result.denial_type == "coding_billing"
    assert result.recommended_route == "corrected_claim_or_reopening"
    assert any(
        item.route == "corrected_claim_or_reopening" and item.decision == "selected"
        for item in result.routes_considered
    )
    assert "preserve" in (" ".join(result.warnings) + result.appeal_strategy).lower()
    assert any(gap.evidence_type == "corrected_claim_packet" for gap in result.evidence_gaps)


@pytest.mark.asyncio
async def test_authority_gap_blocks_filing_ready_output():
    text = (
        "Synthetic commercial denial notice. Insurance: Example Health. "
        "Reason for denial: missing documentation. The provider may appeal only "
        "with a signed AOB or authorized representative form. No patient "
        "authorization is on file."
    )

    result = await DenialWorkflowService().analyze(
        DenialWorkflowAnalysisRequest(document_text=text, source_document_id="syn-auth-1")
    )

    assert result.human_review_required is True
    assert any("AOB or authorized representative" in task.task for task in result.missing_needs_human_verification)
    assert any(gap.evidence_type == "representative_authority" for gap in result.evidence_gaps)
    assert "filing-ready" in " ".join(result.warnings).lower()


@pytest.mark.asyncio
async def test_upheld_final_adverse_response_routes_to_next_level_review():
    text = (
        "Synthetic appeal response. Example Health upheld the prior denial as a "
        "final adverse determination. The response says external review rights "
        "may be available and the prior packet remains under review for medical "
        "necessity rationale completeness."
    )

    result = await DenialWorkflowService().analyze(
        DenialWorkflowAnalysisRequest(document_text=text, source_document_id="syn-response-1")
    )

    assert result.recommended_route == "external_review_or_next_level"
    assert any("final adverse determination" in task.task.lower() for task in result.missing_needs_human_verification)
    assert any(gap.evidence_type == "final_adverse_determination" for gap in result.evidence_gaps)
    assert any(check.check == "next_level_rights_review" and check.status == "blocker" for check in result.quality_checks)


def test_retrieval_returns_cited_public_rule_source():
    index = KeywordRetrievalIndex(build_default_rule_chunks())

    results = index.search("Medicare Advantage reconsideration 65 days", top_k=1)

    assert results
    assert results[0]["source_id"] == "SRC-MEDICARE-MA-RECON"
    assert results[0]["phi_status"] == "no_phi"


def test_student_model_status_accepts_after_corpus_readiness_passes_without_default_use():
    status = DenialWorkflowService.student_model_status(
        {"status": "ok", "provider": "mlx_lm", "model": "Qwen/Qwen3-4B-MLX-4bit"}
    )

    assert status.model == "Qwen/Qwen3-4B-MLX-4bit"
    assert status.schema_contract_name == "strict_claim_guard_json_v1"
    assert status.accepted_for_denial_workflow is True
    assert status.adapter_path_exists is True
    assert status.acceptance_release_ready is True
    assert status.readiness_distillation_ready is True
    assert status.readiness_release_ready is True
    assert status.blocked_count == 0
    assert status.benchmark_score_ratio == 0.9667
    assert status.runtime_checked is True
    assert status.runtime_available is True
    assert "--adapter-path" in status.server_command
    assert "claimguard-qwen3-4b-lora-reviewed" in status.server_command_display
    assert status.use_by_default is False
    assert status.effective_use_by_default is False
    assert status.default_cutover_ready is False
    assert status.default_cutover_blockers == []


def test_student_model_status_runtime_defaults_to_not_checked():
    status = DenialWorkflowService.student_model_status()

    assert status.runtime_checked is False
    assert status.runtime_available is False
    assert status.runtime_status == "not_checked"
    assert status.max_tokens == 1800
    assert status.enable_thinking is False


def test_student_model_status_blocks_requested_default_without_cutover_attestations(monkeypatch):
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_USE_BY_DEFAULT",
        True,
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED",
        False,
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE",
        "",
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED",
        False,
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA",
        False,
    )

    status = DenialWorkflowService.student_model_status(
        {"status": "ok", "provider": "mlx_lm", "model": "Qwen/Qwen3-4B-MLX-4bit"}
    )

    assert status.use_by_default is True
    assert status.effective_use_by_default is False
    assert status.default_cutover_ready is False
    assert "Raphael approval for default student cutover is not attested" in status.default_cutover_blockers
    assert "default cutover approval reference is not configured" in status.default_cutover_blockers
    assert "supervised MLX runtime is not configured" in status.default_cutover_blockers


def test_student_model_status_allows_default_only_after_cutover_attestations(monkeypatch):
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_USE_BY_DEFAULT",
        True,
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED",
        True,
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE",
        "SYN-APPROVAL-REF",
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED",
        True,
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA",
        False,
    )

    status = DenialWorkflowService.student_model_status(
        {"status": "ok", "provider": "mlx_lm", "model": "Qwen/Qwen3-4B-MLX-4bit"}
    )

    assert status.default_cutover_ready is True
    assert status.effective_use_by_default is True
    assert status.default_cutover_approved is True
    assert status.default_approval_reference_configured is True
    assert status.runtime_supervised is True
    assert status.default_cutover_blockers == []


def test_student_model_status_rollback_flag_disables_effective_default(monkeypatch):
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_USE_BY_DEFAULT",
        True,
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED",
        True,
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE",
        "SYN-APPROVAL-REF",
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED",
        True,
    )
    monkeypatch.setattr(
        "app.services.denial_workflow.settings.CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA",
        True,
    )

    status = DenialWorkflowService.student_model_status(
        {"status": "ok", "provider": "mlx_lm", "model": "Qwen/Qwen3-4B-MLX-4bit"}
    )

    assert status.rollback_to_nvidia_enabled is True
    assert status.effective_use_by_default is False
    assert "rollback-to-NVIDIA flag is enabled" in status.default_cutover_blockers


@pytest.mark.asyncio
async def test_export_workflow_markdown_docx_and_pdf():
    result = await DenialWorkflowService().analyze(
        DenialWorkflowAnalysisRequest(
            document_text=(
                "Denial Notice. Insurance: Example Health. Denial Date: 2026-04-20. "
                "Claim Number: SYN-3001. Reason for Denial: missing documentation."
            )
        )
    )

    markdown = export_workflow(result, "markdown", "test-workflow")
    docx = export_workflow(result, "docx", "test-workflow")
    pdf = export_workflow(result, "pdf", "test-workflow")

    assert markdown.encoding == "utf-8"
    assert "draft_for_human_review" in markdown.content
    assert base64.b64decode(docx.content).startswith(b"PK")
    assert base64.b64decode(pdf.content).startswith(b"%PDF")


def test_export_request_accepts_workflow_model():
    request = DenialWorkflowExportRequest(
        workflow={
            "document_type": "denial_letter",
            "case_summary": "Synthetic case.",
            "known_from_documents": [],
            "inferred": [],
            "missing_needs_human_verification": [],
            "cited_rules": [],
            "appeal_strategy": "Human review required.",
            "submission_plan": {
                "route": "verify_plan_type",
                "required_channel": "Verify locally.",
                "proof_to_capture": [],
                "blocker_tasks": [],
                "source": {
                    "source_status": "missing_needs_human_verification",
                    "human_verified": False,
                },
            },
        },
        export_format="markdown",
    )

    assert request.workflow.human_review_required is True
