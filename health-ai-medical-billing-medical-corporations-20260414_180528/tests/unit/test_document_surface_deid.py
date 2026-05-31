import json

from app.schemas.corpus import CorpusDocumentSurfaceInspectRequest
from app.services.corpus import CorpusSafetyService


def test_document_surface_inspection_flags_hidden_metadata_barcode_and_filenames_without_values():
    raw_member_value = "SYN-MEMBER-7788"
    raw_claim_value = "SYN-CLAIM-9900"
    raw_email_value = "sample.person@example.test"

    result = CorpusSafetyService().inspect_document_surfaces(
        CorpusDocumentSurfaceInspectRequest(
            source_id="SRC-SURFACE",
            document_id="DOC-SURFACE",
            source_filename=f"denial_member_id_{raw_member_value}.pdf",
            source_mime_type="application/pdf",
            visible_text="Deidentified visible denial text with missing documentation.",
            hidden_text=f"Hidden footer Member ID: {raw_member_value}",
            ocr_text="OCR page text has no identifiers.",
            metadata={"producer": f"Generated for {raw_email_value}", "subject": "Synthetic denial"},
            barcode_qr_text=[f"Claim Number: {raw_claim_value}"],
            attachment_filenames=[f"appeal_packet_claim_number_{raw_claim_value}.pdf"],
        )
    )

    serialized = json.dumps(result.model_dump(mode="json"))
    surface_names = {surface.surface for surface in result.surface_scans}
    finding_types = {
        finding.finding_type
        for surface in result.surface_scans
        for finding in surface.findings
    }

    assert result.deidentification_status == "qa_failed"
    assert result.training_eligible is False
    assert result.human_review_required is True
    assert result.blocking_surface_count >= 4
    assert {"source_filename", "hidden_text", "metadata", "barcode_qr_text", "attachment_filenames"}.issubset(
        surface_names
    )
    assert {"member_id_label", "claim_number_label", "email_like"}.issubset(finding_types)
    assert result.values_redacted is True
    assert raw_member_value not in serialized
    assert raw_claim_value not in serialized
    assert raw_email_value not in serialized


def test_document_surface_inspection_infers_header_footer_surface():
    result = CorpusSafetyService().inspect_document_surfaces(
        CorpusDocumentSurfaceInspectRequest(
            source_id="SRC-HEADER",
            document_id="DOC-HEADER",
            visible_text=(
                "Claim Number: SYN-HEADER-1\n"
                "Page 1 of 1\n"
                "Body text has no identifiers.\n"
                "Footer: Appeal packet\n"
            ),
        )
    )

    inferred = next(
        surface for surface in result.surface_scans if surface.surface == "inferred_header_footer_text"
    )

    assert result.deidentification_status == "qa_failed"
    assert inferred.phi_scan.finding_count >= 1
    assert any(finding.finding_type == "claim_number_label" for finding in inferred.findings)


def test_clean_pdf_surface_inspection_still_requires_human_review_before_training():
    result = CorpusSafetyService().inspect_document_surfaces(
        CorpusDocumentSurfaceInspectRequest(
            source_id="SRC-CLEAN",
            document_id="DOC-CLEAN",
            source_filename="deidentified-denial-example.pdf",
            source_mime_type="application/pdf",
            visible_text="Deidentified denial example with generic missing documentation language.",
            hidden_text="No identifiers in hidden text.",
            ocr_text="Scanned page text remains deidentified.",
            metadata={"title": "Synthetic deidentified example"},
            barcode_qr_text=["deidentified-example"],
            attachment_filenames=["deidentified-appeal-packet.pdf"],
        )
    )

    assert result.deidentification_status == "machine_deidentified"
    assert result.blocking_surface_count == 0
    assert result.training_eligible is False
    assert result.human_review_required is True
    assert any("Raphael/privacy review" in warning for warning in result.warnings)


def test_contextual_surface_risk_requires_expert_determination_without_values():
    rare_context = "92-year-old in a small town with ultra-rare device and $125000 charge"

    result = CorpusSafetyService().inspect_document_surfaces(
        CorpusDocumentSurfaceInspectRequest(
            source_id="SRC-CONTEXT-SURFACE",
            document_id="DOC-CONTEXT-SURFACE",
            visible_text=(
                "Deidentified denial narrative describes a 92-year-old in a small town "
                "with an ultra-rare device and a $125000 charge."
            ),
        )
    )

    serialized = json.dumps(result.model_dump(mode="json"))
    finding_types = {
        finding.finding_type
        for surface in result.surface_scans
        for finding in surface.contextual_risk_findings
    }

    assert result.deidentification_status == "expert_determination_required"
    assert result.blocking_surface_count == 0
    assert result.contextual_risk_finding_count >= 4
    assert result.contextual_risk_surface_count >= 1
    assert result.residual_risk_score > 0.2
    assert result.training_eligible is False
    assert {
        "age_over_89",
        "small_geography_or_unique_provider",
        "rare_condition_or_device",
        "unusual_dollar_amount",
    }.issubset(finding_types)
    assert rare_context not in serialized
    assert "92-year-old" not in serialized
    assert "$125000" not in serialized
