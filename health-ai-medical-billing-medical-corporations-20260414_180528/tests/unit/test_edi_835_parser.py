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
        "1058",
        repetition_separator,
        "00501",
        "000000906",
        "1",
        "T",
        component_separator,
    ]
    isa = element_separator.join(elements)
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
        "SE*7*0002~"
        "GE*1*2~"
        "IEA*1*000000906~"
    )


class TestEDI835Parser:
    def test_parse_valid_835_claim_payment(self):
        from app.utils.edi_835_parser import parse_edi_835

        result = parse_edi_835(_synthetic_835())

        assert result.segment_count == 10
        assert result.interchange_control_number == "000000906"
        assert result.group_control_number == "2"
        assert result.transaction_control_number == "0002"
        assert result.has_errors is False
        assert len(result.claims) == 1

        claim = result.claims[0]
        assert claim.patient_control_number == "SYNTH-CLAIM-001"
        assert claim.claim_status_code == "1"
        assert claim.total_charge_amount == 150.0
        assert claim.paid_amount == 125.0
        assert claim.patient_responsibility_amount == 25.0
        assert claim.payer_claim_control_number == "PAYER-CLAIM-001"
        assert claim.payment_status == "partially_paid"
        assert len(claim.adjustments) == 1

        adjustment = claim.adjustments[0]
        assert adjustment.group_code == "CO"
        assert adjustment.reason_code == "45"
        assert adjustment.reason_code_status == "active"
        assert adjustment.reason_code_category == "fee_schedule_contract"
        assert adjustment.amount == 25.0
        assert adjustment.quantity is None

    def test_parse_multiple_claim_payments(self):
        from app.utils.edi_835_parser import parse_edi_835

        edi_text = (
            f"{_isa_segment()}~"
            "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
            "ST*835*0002~"
            "CLP*SYNTH-CLAIM-001*1*150*150*0*12*PAYER-CLAIM-001~"
            "CAS*CO*45*0~"
            "CLP*SYNTH-CLAIM-002*4*200*0*0*12*PAYER-CLAIM-002~"
            "CAS*PR*96*200~"
            "SE*7*0002~"
            "GE*1*2~"
            "IEA*1*000000906~"
        )

        result = parse_edi_835(edi_text)

        assert len(result.claims) == 2
        assert result.claims[0].patient_control_number == "SYNTH-CLAIM-001"
        assert result.claims[0].payment_status == "paid"
        assert result.claims[0].adjustments[0].group_code == "CO"
        assert result.claims[1].patient_control_number == "SYNTH-CLAIM-002"
        assert result.claims[1].payment_status == "denied"
        assert result.claims[1].adjustments[0].reason_code == "96"
        assert result.has_errors is False

    def test_parse_multiple_cas_adjustment_triplets(self):
        from app.utils.edi_835_parser import parse_edi_835

        result = parse_edi_835(
            f"{_isa_segment()}~"
            "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
            "ST*835*0002~"
            "CLP*SYNTH-CLAIM-001*1*200*165*35*12*PAYER-CLAIM-001~"
            "CAS*CO*45*25*1*97*10~"
            "SE*5*0002~"
            "GE*1*2~"
            "IEA*1*000000906~"
        )

        adjustments = result.claims[0].adjustments
        assert len(adjustments) == 2
        assert adjustments[0].reason_code == "45"
        assert adjustments[0].reason_code_status == "active"
        assert adjustments[0].amount == 25.0
        assert adjustments[0].quantity == 1.0
        assert adjustments[1].reason_code == "97"
        assert adjustments[1].reason_code_status == "active"
        assert adjustments[1].reason_code_category == "bundled_service"
        assert adjustments[1].amount == 10.0
        assert adjustments[1].quantity is None

    def test_payment_status_derivation(self):
        from app.utils.edi_835_parser import parse_edi_835

        result = parse_edi_835(
            f"{_isa_segment()}~"
            "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
            "ST*835*0002~"
            "CLP*SYNTH-PAID*1*100*100*0*12*PAYER-PAID~"
            "CLP*SYNTH-PARTIAL*1*100*75*25*12*PAYER-PARTIAL~"
            "CLP*SYNTH-DENIED*4*100*0*0*12*PAYER-DENIED~"
            "SE*6*0002~"
            "GE*1*2~"
            "IEA*1*000000906~"
        )

        assert [claim.payment_status for claim in result.claims] == [
            "paid",
            "partially_paid",
            "denied",
        ]

    def test_cas_before_clp_returns_safe_validation_issue(self):
        from app.utils.edi_835_parser import parse_edi_835

        result = parse_edi_835(
            f"{_isa_segment()}~"
            "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
            "ST*835*0002~"
            "CAS*CO*45*25~"
            "CLP*SYNTH-CLAIM-001*1*150*125*25*12*PAYER-CLAIM-001~"
            "SE*5*0002~"
            "GE*1*2~"
            "IEA*1*000000906~"
        )

        assert len(result.validation_issues) == 1
        assert result.validation_issues[0].field == "adjustments"
        assert result.validation_issues[0].segment_id == "CAS"
        assert result.validation_issues[0].segment_index == 4
        assert result.validation_issues[0].error_code == "adjustment_before_claim_payment"
        assert result.validation_issues[0].parser_stage == "adjustment_parse"
        assert not hasattr(result.validation_issues[0], "raw_segment")

    def test_malformed_cas_triplet_returns_validation_issue(self):
        from app.utils.edi_835_parser import parse_edi_835

        result = parse_edi_835(
            f"{_isa_segment()}~"
            "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
            "ST*835*0002~"
            "CLP*SYNTH-CLAIM-001*1*150*125*25*12*PAYER-CLAIM-001~"
            "CAS*CO*45~"
            "SE*5*0002~"
            "GE*1*2~"
            "IEA*1*000000906~"
        )

        assert result.validation_issues[0].field == "adjustment_triplet"
        assert result.validation_issues[0].claim_index == 1
        assert result.validation_issues[0].segment_id == "CAS"
        assert result.validation_issues[0].segment_index == 5
        assert result.validation_issues[0].error_code == "invalid_adjustment_triplet"
        assert result.validation_issues[0].parser_stage == "adjustment_parse"

    def test_invalid_clp_amounts_return_safe_structured_issues(self):
        from app.utils.edi_835_parser import parse_edi_835

        result = parse_edi_835(
            f"{_isa_segment()}~"
            "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
            "ST*835*0002~"
            "CLP*SYNTH-CLAIM-001*1*not-a-number**25*12*PAYER-CLAIM-001~"
            "SE*4*0002~"
            "GE*1*2~"
            "IEA*1*000000906~"
        )

        assert {issue.field for issue in result.validation_issues} == {
            "paid_amount",
            "total_charge_amount",
        }
        assert {issue.error_code for issue in result.validation_issues} == {
            "missing_paid_amount",
            "missing_total_charge_amount",
        }
        assert {issue.parser_stage for issue in result.validation_issues} == {
            "claim_payment_validation"
        }
        assert all(issue.segment_id == "CLP" for issue in result.validation_issues)
        assert all(not hasattr(issue, "raw_segment") for issue in result.validation_issues)

    def test_missing_clp_returns_validation_issue(self):
        from app.utils.edi_835_parser import parse_edi_835

        result = parse_edi_835(
            f"{_isa_segment()}~"
            "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
            "ST*835*0002~"
            "BPR*I*125*C*ACH*CCP*01*999999999*DA*123456789*9999999999**01*111111111*DA*987654321*20260529~"
            "SE*4*0002~"
            "GE*1*2~"
            "IEA*1*000000906~"
        )

        assert result.claims == []
        assert len(result.validation_issues) == 1
        assert result.validation_issues[0].field == "claim_payment"
        assert result.validation_issues[0].segment_id == "CLP"
        assert result.validation_issues[0].error_code == "missing_claim_payment"
        assert result.validation_issues[0].parser_stage == "claim_payment_validation"

    def test_empty_input_raises_parser_error(self):
        from app.utils.edi_835_parser import EDI835ParserError, parse_edi_835

        with pytest.raises(EDI835ParserError) as exc_info:
            parse_edi_835("   ")

        assert exc_info.value.error_code == "edi_835_input_empty"
        assert exc_info.value.parser_stage == "input_validation"
        assert exc_info.value.field == "edi_text"
        assert exc_info.value.segment_count == 0
        assert exc_info.value.safe_detail()["safe_context"] == {
            "edi_parser": "edi_835",
            "raw_edi_text_included": False,
            "raw_segment_included": False,
        }

    def test_no_parseable_segments_raises_structured_parser_error(self):
        from app.utils.edi_835_parser import EDI835ParserError, parse_edi_835

        with pytest.raises(EDI835ParserError) as exc_info:
            parse_edi_835("~~~")

        assert exc_info.value.error_code == "edi_835_no_parseable_segments"
        assert exc_info.value.parser_stage == "segment_split"
        assert exc_info.value.field == "segments"
        assert exc_info.value.segment_count == 0
        detail = exc_info.value.safe_detail()
        assert detail["segment_id"] is None
        assert detail["safe_context"] == {
            "edi_parser": "edi_835",
            "raw_edi_text_included": False,
            "raw_segment_included": False,
        }

    def test_custom_isa_delimiters_are_respected(self):
        from app.utils.edi_835_parser import parse_edi_835

        element = "|"
        component = ">"
        segment = "!"
        edi_text = (
            f"{_isa_segment(element, component)}{segment}"
            "GS|HP|SENDER|RECEIVER|20260529|1058|2|X|005010X221A1!"
            "ST|835|0002!"
            "CLP|SYNTH-CLAIM-001|1|150|125|25|12|PAYER-CLAIM-001!"
            "CAS|CO|45|25!"
            "SE|5|0002!"
            "GE|1|2!"
            "IEA|1|000000906!"
        )

        result = parse_edi_835(edi_text)

        assert result.element_separator == element
        assert result.component_separator == component
        assert result.segment_terminator == segment
        assert result.claims[0].patient_control_number == "SYNTH-CLAIM-001"
        assert result.claims[0].adjustments[0].reason_code == "45"
