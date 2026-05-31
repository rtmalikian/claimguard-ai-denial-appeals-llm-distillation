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
        "1058",
        "^",
        "00501",
        "000000906",
        "1",
        "T",
        ":",
    ]
    isa = "*".join(elements)
    assert len(isa) == 105
    return isa


def _synthetic_835() -> str:
    return (
        f"{_isa_segment()}~"
        "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
        "ST*835*0002~"
        "BPR*I*125*C*ACH*CCP*01*999999999*DA*123456789*9999999999**01*111111111*DA*987654321*20260529~"
        "TRN*1*SYNTHETIC-TRACE-001*1512345678~"
        "CLP*SYNTH-CLAIM-001*1*150*125*25*12*PAYER-CLAIM-001~"
        "CAS*CO*45*25~"
        "LQ*HE*N130~"
        "SE*8*0002~"
        "GE*1*2~"
        "IEA*1*000000906~"
    )


def _upload_file(filename: str, content: bytes, content_type: str = "application/edi-x12"):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.read = AsyncMock(return_value=content)
    return mock_file


class TestUploadRemittance:
    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    async def test_remittance_upload_returns_safe_payment_results(self, mock_log_audit):
        from app.api.v1.claims import upload_remittance

        result = await upload_remittance(
            file=_upload_file("synthetic_remit.835", _synthetic_835().encode("utf-8")),
            db=MagicMock(),
        )

        assert result.accepted is True
        assert result.source_filename_present is True
        assert result.source_file_extension == ".835"
        assert result.claim_payment_count == 1
        assert result.valid_claim_payment_count == 1
        assert result.invalid_claim_payment_count == 0
        assert result.adjustment_count == 1
        assert result.remark_code_count == 1
        assert result.validation_issue_count == 0
        assert result.segment_count == 11
        assert result.document_surface_inspection.values_redacted is True

        claim_payment = result.claim_payments[0]
        assert claim_payment.status == "ready_for_remittance_review"
        assert claim_payment.payment_status == "partially_paid"
        assert claim_payment.patient_control_number_present is True
        assert claim_payment.payer_claim_control_number_present is True
        assert claim_payment.claim_status_code == "1"
        assert claim_payment.adjustments[0].group_code == "CO"
        assert claim_payment.adjustments[0].reason_code == "45"
        assert claim_payment.remark_codes[0].remark_code == "N130"

        payload = result.model_dump_json()
        assert "raw_segment" not in payload
        assert "SYNTH-CLAIM-001" not in payload
        assert "PAYER-CLAIM-001" not in payload
        assert "SENDERID" not in payload
        assert "RECEIVERID" not in payload

        mock_log_audit.assert_called_once()
        audit_details = mock_log_audit.call_args.kwargs["details"]
        assert audit_details["remittance_claim_count"] == 1
        assert audit_details["remittance_valid_claim_count"] == 1
        assert audit_details["remittance_invalid_claim_count"] == 0
        assert audit_details["remittance_adjustment_count"] == 1
        assert audit_details["remittance_remark_code_count"] == 1
        assert audit_details["payment_status_counts"] == {"partially_paid": 1}
        assert audit_details["source_filename_present"] is True
        assert "source_filename" not in audit_details
        assert "visible_text" not in audit_details
        assert "patient_control_number" not in audit_details
        assert "payer_claim_control_number" not in audit_details

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    async def test_remittance_upload_rejects_unsupported_extension(self, mock_log_audit):
        from app.api.v1.claims import upload_remittance

        with pytest.raises(HTTPException) as exc_info:
            await upload_remittance(
                file=_upload_file("synthetic_remit.pdf", b"not an edi file"),
                db=MagicMock(),
            )

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 400
        assert detail["error_code"] == "unsupported_file_type"
        assert detail["parser_stage"] == "file_validation"
        assert detail["source_file_extension"] == ".pdf"
        assert detail["safe_context"]["raw_filename_included"] is False
        assert detail["safe_context"]["raw_edi_text_included"] is False
        assert detail["safe_context"]["raw_segment_included"] is False
        assert detail["safe_context"]["patient_identifier_included"] is False
        assert detail["safe_context"]["payer_control_number_included"] is False
        assert "synthetic_remit.pdf" not in str(detail)
        mock_log_audit.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    async def test_remittance_upload_rejects_parse_error_with_safe_context(
        self, mock_log_audit
    ):
        from app.api.v1.claims import upload_remittance

        with pytest.raises(HTTPException) as exc_info:
            await upload_remittance(
                file=_upload_file("synthetic_remit.835", b"~~~"),
                db=MagicMock(),
            )

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 400
        assert detail["error_code"] == "edi_835_no_parseable_segments"
        assert detail["parser_stage"] == "segment_split"
        assert detail["field"] == "segments"
        assert detail["segment_count"] == 0
        assert detail["segment_index"] is None
        assert detail["segment_id"] is None
        assert detail["safe_context"] == {
            "edi_parser": "edi_835",
            "raw_filename_included": False,
            "raw_edi_text_included": False,
            "raw_segment_included": False,
            "patient_identifier_included": False,
            "payer_control_number_included": False,
        }
        assert "synthetic_remit.835" not in str(detail)
        assert "~~~" not in str(detail)
        mock_log_audit.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    async def test_remittance_upload_blocks_disguised_inner_extension_before_read(
        self, mock_log_audit
    ):
        from app.api.v1.claims import upload_remittance

        mock_file = _upload_file(
            "synthetic-remit.php.835",
            _synthetic_835().encode("utf-8"),
        )

        with patch("app.api.v1.claims.parse_edi_835") as mock_parse_edi:
            with pytest.raises(HTTPException) as exc_info:
                await upload_remittance(file=mock_file, db=MagicMock())

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 400
        assert detail["error_code"] == "suspicious_extension_chain"
        assert detail["parser_stage"] == "file_validation"
        assert detail["source_filename_present"] is True
        assert detail["source_file_extension"] == ".835"
        assert detail["safe_context"]["inner_extension_chain_checked"] is True
        assert detail["safe_context"]["raw_filename_included"] is False
        assert detail["safe_context"]["raw_edi_text_included"] is False
        assert detail["safe_context"]["raw_segment_included"] is False
        assert detail["safe_context"]["patient_identifier_included"] is False
        assert detail["safe_context"]["payer_control_number_included"] is False
        assert "synthetic-remit.php.835" not in str(detail)
        mock_file.read.assert_not_awaited()
        mock_parse_edi.assert_not_called()
        mock_log_audit.assert_not_called()
