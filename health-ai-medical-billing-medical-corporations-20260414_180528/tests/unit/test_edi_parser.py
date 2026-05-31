import pytest


def _isa_segment(element_separator: str = "*", component_separator: str = ":") -> str:
    repetition_separator = "^"
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
        repetition_separator,
        "00501",
        "000000905",
        "1",
        "T",
        component_separator,
    ]
    isa = element_separator.join(elements)
    assert len(isa) == 105
    return isa


def _synthetic_837() -> str:
    return (
        f"{_isa_segment()}~"
        "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "BHT*0019*00*SYNTHBATCH001*20260529*1047*CH~"
        "NM1*PR*2*SYNTHETIC PAYER*****PI*PAYER123~"
        "CLM*SYNTH-CLAIM-001*150***11:B:1*Y*A*Y*Y~"
        "HI*ABK:I10*ABF:E119~"
        "SV1*HC:99213:25*150*UN*1***1~"
        "SE*8*0001~"
        "GE*1*1~"
        "IEA*1*000000905~"
    )


class TestEDI837Parser:
    def test_parse_valid_837_claim(self):
        from app.utils.edi_parser import parse_edi_837

        result = parse_edi_837(_synthetic_837())

        assert result.segment_count == 11
        assert result.interchange_control_number == "000000905"
        assert result.group_control_number == "1"
        assert result.transaction_control_number == "0001"
        assert result.has_errors is False
        assert len(result.claims) == 1

        claim = result.claims[0]
        assert claim.claim_control_number == "SYNTH-CLAIM-001"
        assert claim.total_charge_amount == 150.0
        assert claim.payer_name == "SYNTHETIC PAYER"
        assert claim.payer_identifier == "PAYER123"
        assert claim.diagnosis_codes == ["I10", "E119"]
        assert len(claim.service_lines) == 1

        service_line = claim.service_lines[0]
        assert service_line.segment_id == "SV1"
        assert service_line.procedure_code == "99213"
        assert service_line.procedure_modifiers == ["25"]
        assert service_line.charge_amount == 150.0
        assert service_line.unit_count == 1.0
        assert service_line.product_service_qualifier == "HC"
        assert service_line.diagnosis_pointers == ["1"]

    def test_parse_multiple_claim_loops(self):
        from app.utils.edi_parser import parse_edi_837

        edi_text = (
            f"{_isa_segment()}~"
            "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
            "ST*837*0001*005010X222A1~"
            "NM1*PR*2*SYNTHETIC PAYER ONE*****PI*PAYER111~"
            "CLM*SYNTH-CLAIM-001*150***11:B:1*Y*A*Y*Y~"
            "HI*ABK:I10~"
            "SV1*HC:99213*150*UN*1***1~"
            "NM1*PR*2*SYNTHETIC PAYER TWO*****PI*PAYER222~"
            "CLM*SYNTH-CLAIM-002*275***11:B:1*Y*A*Y*Y~"
            "HI*ABK:M5450~"
            "SV1*HC:97110:GP*275*UN*1***1~"
            "SE*10*0001~"
            "GE*1*1~"
            "IEA*1*000000905~"
        )

        result = parse_edi_837(edi_text)

        assert len(result.claims) == 2
        assert result.claims[0].claim_control_number == "SYNTH-CLAIM-001"
        assert result.claims[0].payer_identifier == "PAYER111"
        assert result.claims[1].claim_control_number == "SYNTH-CLAIM-002"
        assert result.claims[1].payer_identifier == "PAYER222"
        assert result.claims[1].service_lines[0].procedure_modifiers == ["GP"]
        assert result.has_errors is False

    def test_parse_sv2_institutional_service_line(self):
        from app.utils.edi_parser import parse_edi_837

        edi_text = (
            f"{_isa_segment()}~"
            "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X223A3~"
            "ST*837*0001*005010X223A3~"
            "NM1*PR*2*SYNTHETIC FACILITY PAYER*****PI*PAYER999~"
            "CLM*SYNTH-INST-001*350***11:B:1*Y*A*Y*Y~"
            "HI*ABK:R079~"
            "SV2*0450*HC:99284*350*UN*1~"
            "SE*7*0001~"
            "GE*1*1~"
            "IEA*1*000000905~"
        )

        result = parse_edi_837(edi_text)

        service_line = result.claims[0].service_lines[0]
        assert service_line.segment_id == "SV2"
        assert service_line.revenue_code == "0450"
        assert service_line.procedure_code == "99284"
        assert service_line.charge_amount == 350.0
        assert service_line.unit_count == 1.0
        assert result.has_errors is False

    def test_missing_payer_diagnosis_and_service_lines_return_safe_issues(self):
        from app.utils.edi_parser import parse_edi_837

        result = parse_edi_837(
            f"{_isa_segment()}~"
            "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
            "ST*837*0001*005010X222A1~"
            "CLM*SYNTH-CLAIM-001*150***11:B:1*Y*A*Y*Y~"
            "SE*4*0001~"
            "GE*1*1~"
            "IEA*1*000000905~"
        )

        issue_fields = {issue.field for issue in result.validation_issues}
        assert issue_fields == {"diagnosis_codes", "service_lines", "payer"}
        assert result.has_errors is True
        assert all(issue.claim_index == 1 for issue in result.validation_issues)
        assert {issue.parser_stage for issue in result.validation_issues} == {
            "claim_validation"
        }
        assert {issue.error_code for issue in result.validation_issues} == {
            "missing_diagnosis_codes",
            "missing_payer",
            "missing_service_lines",
        }
        assert all(not hasattr(issue, "raw_segment") for issue in result.validation_issues)

    def test_malformed_service_line_returns_validation_issue(self):
        from app.utils.edi_parser import parse_edi_837

        result = parse_edi_837(
            f"{_isa_segment()}~"
            "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
            "ST*837*0001*005010X222A1~"
            "NM1*PR*2*SYNTHETIC PAYER*****PI*PAYER123~"
            "CLM*SYNTH-CLAIM-001*150***11:B:1*Y*A*Y*Y~"
            "HI*ABK:I10~"
            "SV1*HC:*150*UN*1***1~"
            "SE*7*0001~"
            "GE*1*1~"
            "IEA*1*000000905~"
        )

        issue_fields = [issue.field for issue in result.validation_issues]
        assert "procedure_code" in issue_fields
        assert "service_lines" in issue_fields
        assert result.validation_issues[0].segment_id == "SV1"
        assert result.validation_issues[0].segment_index == 7
        assert result.validation_issues[0].parser_stage == "service_line_parse"
        assert result.validation_issues[0].error_code == "missing_procedure_code"

    def test_professional_service_line_requires_diagnosis_pointer(self):
        from app.utils.edi_parser import parse_edi_837

        result = parse_edi_837(
            f"{_isa_segment()}~"
            "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
            "ST*837*0001*005010X222A1~"
            "NM1*PR*2*SYNTHETIC PAYER*****PI*PAYER123~"
            "CLM*SYNTH-CLAIM-001*150***11:B:1*Y*A*Y*Y~"
            "HI*ABK:I10~"
            "SV1*HC:99213*150*UN*1~"
            "SE*7*0001~"
            "GE*1*1~"
            "IEA*1*000000905~"
        )

        issues = [
            issue
            for issue in result.validation_issues
            if issue.error_code == "missing_diagnosis_pointer"
        ]
        assert len(issues) == 1
        assert issues[0].field == "diagnosis_pointers"
        assert issues[0].parser_stage == "diagnosis_procedure_linkage_validation"
        assert issues[0].segment_id == "SV1"
        assert not hasattr(issues[0], "raw_segment")

    def test_service_line_rejects_out_of_range_diagnosis_pointer(self):
        from app.utils.edi_parser import parse_edi_837

        result = parse_edi_837(
            f"{_isa_segment()}~"
            "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
            "ST*837*0001*005010X222A1~"
            "NM1*PR*2*SYNTHETIC PAYER*****PI*PAYER123~"
            "CLM*SYNTH-CLAIM-001*150***11:B:1*Y*A*Y*Y~"
            "HI*ABK:I10~"
            "SV1*HC:99213*150*UN*1***2~"
            "SE*7*0001~"
            "GE*1*1~"
            "IEA*1*000000905~"
        )

        issues = [
            issue
            for issue in result.validation_issues
            if issue.error_code == "diagnosis_pointer_out_of_range"
        ]
        assert len(issues) == 1
        assert issues[0].field == "diagnosis_pointers"
        assert issues[0].parser_stage == "diagnosis_procedure_linkage_validation"
        assert issues[0].segment_id == "SV1"
        assert not hasattr(issues[0], "raw_segment")

    def test_no_claim_loop_returns_validation_issue(self):
        from app.utils.edi_parser import parse_edi_837

        result = parse_edi_837(
            f"{_isa_segment()}~"
            "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
            "ST*837*0001*005010X222A1~"
            "NM1*PR*2*SYNTHETIC PAYER*****PI*PAYER123~"
            "SE*4*0001~"
            "GE*1*1~"
            "IEA*1*000000905~"
        )

        assert result.claims == []
        assert len(result.validation_issues) == 1
        assert result.validation_issues[0].field == "claim_loop"
        assert result.validation_issues[0].segment_id == "CLM"
        assert result.validation_issues[0].parser_stage == "claim_loop_validation"
        assert result.validation_issues[0].error_code == "missing_claim_loop"

    def test_empty_input_raises_parser_error(self):
        from app.utils.edi_parser import EDIParserError, parse_edi_837

        with pytest.raises(EDIParserError) as exc_info:
            parse_edi_837("   ")

        assert exc_info.value.error_code == "edi_input_empty"
        assert exc_info.value.parser_stage == "input_validation"
        assert exc_info.value.field == "edi_text"
        assert exc_info.value.segment_count == 0
        assert exc_info.value.safe_detail()["safe_context"]["raw_segment_included"] is False

    def test_no_parseable_segments_raises_structured_parser_error(self):
        from app.utils.edi_parser import EDIParserError, parse_edi_837

        with pytest.raises(EDIParserError) as exc_info:
            parse_edi_837("~~~")

        assert exc_info.value.error_code == "edi_no_parseable_segments"
        assert exc_info.value.parser_stage == "segment_split"
        assert exc_info.value.field == "segments"
        assert exc_info.value.segment_count == 0
        detail = exc_info.value.safe_detail()
        assert detail["segment_id"] is None
        assert detail["safe_context"] == {
            "edi_parser": "edi_837",
            "raw_edi_text_included": False,
            "raw_segment_included": False,
        }

    def test_custom_isa_delimiters_are_respected(self):
        from app.utils.edi_parser import parse_edi_837

        element = "|"
        component = ">"
        segment = "!"
        edi_text = (
            f"{_isa_segment(element, component)}{segment}"
            "GS|HC|SENDER|RECEIVER|20260529|1047|1|X|005010X222A1!"
            "ST|837|0001|005010X222A1!"
            "NM1|PR|2|SYNTHETIC PAYER|||||PI|PAYER123!"
            "CLM|SYNTH-CLAIM-001|150|||11>B>1|Y|A|Y|Y!"
            "HI|ABK>I10|ABF>E119!"
            "SV1|HC>99213>25|150|UN|1|||1!"
            "SE|7|0001!"
            "GE|1|1!"
            "IEA|1|000000905!"
        )

        result = parse_edi_837(edi_text)

        assert result.element_separator == element
        assert result.component_separator == component
        assert result.segment_terminator == segment
        assert result.claims[0].diagnosis_codes == ["I10", "E119"]
        assert result.claims[0].service_lines[0].procedure_modifiers == ["25"]

    def test_batch_size_estimate_counts_segments_and_claims_without_parsing_claims(self):
        from app.utils.edi_parser import estimate_edi_837_batch_size

        estimate = estimate_edi_837_batch_size(_synthetic_837())

        assert estimate.segment_count == 11
        assert estimate.claim_count == 1
