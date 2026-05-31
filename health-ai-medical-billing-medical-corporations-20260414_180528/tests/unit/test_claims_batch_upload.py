from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile


def _isa_segment() -> str:
    elements = [
        "ISA",
        "00",
        "          ",
        "00",
        "          ",
        "ZZ",
        "SENDERID       ",
        "ZZ",
        "RECEIVERID     ",
        "260529",
        "1047",
        "^",
        "00501",
        "000000905",
        "1",
        "T",
        ":",
    ]
    isa = "*".join(elements)
    assert len(isa) == 105
    return isa


def _synthetic_837_batch() -> str:
    return (
        f"{_isa_segment()}~"
        "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "NM1*PR*2*SYNTHETIC PAYER ONE*****PI*PAYER111~"
        "CLM*SYNTH-CLAIM-001*150***11:B:1*Y*A*Y*Y~"
        "HI*ABK:I10~"
        "SV1*HC:99213:25*150*UN*1***1~"
        "NM1*PR*2*SYNTHETIC PAYER TWO*****PI*PAYER222~"
        "CLM*SYNTH-CLAIM-002*275***11:B:1*Y*A*Y*Y~"
        "HI*ABK:M5450~"
        "SV1*HC:97110:GP*275*UN*1***1~"
        "SE*10*0001~"
        "GE*1*1~"
        "IEA*1*000000905~"
    )


def _oversized_claim_batch(max_claims: int) -> str:
    claim_segments = []
    for claim_number in range(max_claims + 1):
        claim_segments.append(f"CLM*SYNTH-CLAIM-{claim_number:03d}*100***11:B:1*Y*A*Y*Y")

    return (
        f"{_isa_segment()}~"
        "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        + "~".join(claim_segments)
        + "~"
        "SE*999*0001~"
        "GE*1*1~"
        "IEA*1*000000905~"
    )


def _upload_file(filename: str, content: bytes, content_type: str = "application/edi-x12"):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.read = AsyncMock(return_value=content)
    return mock_file


class TestBatchUploadClaims:
    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    async def test_batch_upload_returns_multi_claim_parser_results(self, mock_log_audit):
        from app.api.v1.claims import batch_upload_claims

        result = await batch_upload_claims(
            file=_upload_file("synthetic_batch.edi", _synthetic_837_batch().encode("utf-8")),
            db=MagicMock(),
        )

        assert result.accepted is True
        assert result.source_filename_present is True
        assert result.source_file_extension == ".edi"
        assert result.claim_count == 2
        assert result.valid_claim_count == 2
        assert result.invalid_claim_count == 0
        assert result.validation_issue_count == 0
        assert result.segment_count == 14
        assert result.document_surface_inspection.values_redacted is True

        first_claim = result.claims[0]
        second_claim = result.claims[1]
        assert first_claim.status == "ready_for_claim_review"
        assert first_claim.claim_control_number == "SYNTH-CLAIM-001"
        assert first_claim.procedure_codes == ["99213"]
        assert first_claim.service_lines[0].procedure_modifiers == ["25"]
        assert second_claim.claim_control_number == "SYNTH-CLAIM-002"
        assert second_claim.procedure_codes == ["97110"]
        assert second_claim.service_lines[0].procedure_modifiers == ["GP"]

        payload = result.model_dump_json()
        assert "raw_segment" not in payload
        assert "SENDERID" not in payload
        assert "RECEIVERID" not in payload

        mock_log_audit.assert_called_once()
        audit_details = mock_log_audit.call_args.kwargs["details"]
        assert audit_details["claim_count"] == 2
        assert audit_details["valid_claim_count"] == 2
        assert audit_details["source_filename_present"] is True
        assert "source_filename" not in audit_details
        assert "visible_text" not in audit_details

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    async def test_batch_upload_rejects_unsupported_extension(self, mock_log_audit):
        from app.api.v1.claims import batch_upload_claims

        with pytest.raises(HTTPException) as exc_info:
            await batch_upload_claims(
                file=_upload_file("synthetic_batch.pdf", b"not an edi file"),
                db=MagicMock(),
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == "unsupported_file_type"
        assert exc_info.value.detail["parser_stage"] == "file_validation"
        assert exc_info.value.detail["source_file_extension"] == ".pdf"
        assert exc_info.value.detail["field"] is None
        assert exc_info.value.detail["safe_context"]["raw_filename_included"] is False
        assert exc_info.value.detail["safe_context"]["raw_edi_text_included"] is False
        assert exc_info.value.detail["safe_context"]["raw_segment_included"] is False
        assert "synthetic_batch.pdf" not in str(exc_info.value.detail)
        mock_log_audit.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    async def test_batch_upload_rejects_disguised_inner_extension_before_read(
        self, mock_log_audit
    ):
        from app.api.v1.claims import batch_upload_claims

        mock_file = _upload_file(
            "synthetic-claims.php.edi",
            _synthetic_837_batch().encode("utf-8"),
        )

        with patch("app.api.v1.claims.parse_edi_837") as mock_parse_edi:
            with pytest.raises(HTTPException) as exc_info:
                await batch_upload_claims(file=mock_file, db=MagicMock())

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 400
        assert detail["error_code"] == "suspicious_extension_chain"
        assert detail["parser_stage"] == "file_validation"
        assert detail["source_filename_present"] is True
        assert detail["source_file_extension"] == ".edi"
        assert detail["source_mime_type"] == "application/edi-x12"
        assert detail["safe_context"]["inner_extension_chain_checked"] is True
        assert detail["safe_context"]["raw_filename_included"] is False
        assert detail["safe_context"]["raw_edi_text_included"] is False
        assert detail["safe_context"]["raw_segment_included"] is False
        assert "synthetic-claims.php.edi" not in str(detail)
        mock_file.read.assert_not_awaited()
        mock_parse_edi.assert_not_called()
        mock_log_audit.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    async def test_batch_upload_rejects_oversized_file_before_decode(
        self, mock_log_audit
    ):
        from app.api.v1.claims import (
            EDI_BATCH_UPLOAD_MAX_BYTES,
            batch_upload_claims,
        )

        mock_file = _upload_file(
            "synthetic-large-batch.edi",
            b"x" * (EDI_BATCH_UPLOAD_MAX_BYTES + 1),
        )

        with patch("app.api.v1.claims.parse_edi_837") as mock_parse_edi:
            with pytest.raises(HTTPException) as exc_info:
                await batch_upload_claims(file=mock_file, db=MagicMock())

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 400
        assert detail["error_code"] == "file_too_large"
        assert detail["parser_stage"] == "file_validation"
        assert detail["source_file_extension"] == ".edi"
        assert detail["content_length"] == EDI_BATCH_UPLOAD_MAX_BYTES + 1
        assert detail["safe_context"]["raw_edi_text_included"] is False
        assert "synthetic-large-batch.edi" not in str(detail)
        mock_file.read.assert_awaited_once_with(EDI_BATCH_UPLOAD_MAX_BYTES + 1)
        mock_parse_edi.assert_not_called()
        mock_log_audit.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    async def test_batch_upload_marks_claims_with_validation_issues(self, mock_log_audit):
        from app.api.v1.claims import batch_upload_claims

        invalid_claim_batch = (
            f"{_isa_segment()}~"
            "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
            "ST*837*0001*005010X222A1~"
            "CLM*SYNTH-CLAIM-001*150***11:B:1*Y*A*Y*Y~"
            "SE*4*0001~"
            "GE*1*1~"
            "IEA*1*000000905~"
        )

        result = await batch_upload_claims(
            file=_upload_file("synthetic_batch.txt", invalid_claim_batch.encode("utf-8")),
            db=MagicMock(),
        )

        assert result.accepted is True
        assert result.claim_count == 1
        assert result.valid_claim_count == 0
        assert result.invalid_claim_count == 1
        assert result.validation_issue_count == 3
        assert result.claims[0].status == "validation_failed"
        assert {issue.field for issue in result.claims[0].validation_issues} == {
            "diagnosis_codes",
            "payer",
            "service_lines",
        }
        assert {issue.parser_stage for issue in result.claims[0].validation_issues} == {
            "claim_validation"
        }
        assert {issue.error_code for issue in result.claims[0].validation_issues} == {
            "missing_diagnosis_codes",
            "missing_payer",
            "missing_service_lines",
        }
        assert all(not hasattr(issue, "raw_segment") for issue in result.claims[0].validation_issues)
        mock_log_audit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    async def test_batch_upload_parse_error_returns_safe_structured_context(self, mock_log_audit):
        from app.api.v1.claims import batch_upload_claims

        with pytest.raises(HTTPException) as exc_info:
            await batch_upload_claims(
                file=_upload_file("synthetic_batch.edi", b"~~~"),
                db=MagicMock(),
            )

        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        assert detail["error_code"] == "edi_no_parseable_segments"
        assert detail["parser_stage"] == "segment_split"
        assert detail["field"] == "segments"
        assert detail["segment_count"] == 0
        assert detail["segment_index"] is None
        assert detail["segment_id"] is None
        assert detail["source_filename_present"] is True
        assert detail["source_file_extension"] == ".edi"
        assert detail["safe_context"] == {
            "edi_parser": "edi_837",
            "raw_filename_included": False,
            "raw_edi_text_included": False,
            "raw_segment_included": False,
        }
        assert "synthetic_batch.edi" not in str(detail)
        assert "~~~" not in str(detail)
        mock_log_audit.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.parse_edi_837")
    @patch("app.api.v1.claims.log_audit")
    async def test_batch_upload_rejects_too_many_claims_before_parse(
        self, mock_log_audit, mock_parse_edi
    ):
        from app.api.v1.claims import EDI_BATCH_UPLOAD_MAX_CLAIMS, batch_upload_claims

        content = _oversized_claim_batch(EDI_BATCH_UPLOAD_MAX_CLAIMS).encode("utf-8")
        with pytest.raises(HTTPException) as exc_info:
            await batch_upload_claims(
                file=_upload_file("synthetic_large_batch.edi", content),
                db=MagicMock(),
            )

        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        assert detail["error_code"] == "too_many_claims"
        assert detail["parser_stage"] == "pre_parse_batch_validation"
        assert detail["field"] == "claim_count"
        assert detail["safe_context"]["pre_parse_guard"] is True
        assert detail["safe_context"]["claim_count"] == EDI_BATCH_UPLOAD_MAX_CLAIMS + 1
        assert detail["safe_context"]["max_claim_count"] == EDI_BATCH_UPLOAD_MAX_CLAIMS
        assert detail["safe_context"]["raw_edi_text_included"] is False
        assert detail["safe_context"]["raw_segment_included"] is False
        assert "SYNTH-CLAIM" not in str(detail)
        mock_parse_edi.assert_not_called()
        mock_log_audit.assert_not_called()
