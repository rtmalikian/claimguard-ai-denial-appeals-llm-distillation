def _isa_segment(element_separator: str = "*", component_separator: str = ":") -> str:
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
        component_separator,
    ]
    isa = element_separator.join(elements)
    assert len(isa) == 105
    return isa


def test_edi_837_invalid_icd_and_cpt_codes_return_safe_issues():
    from app.utils.edi_parser import parse_edi_837

    result = parse_edi_837(
        f"{_isa_segment()}~"
        "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "NM1*PR*2*SYNTHETIC PAYER*****PI*PAYER123~"
        "CLM*SYNTH-CLAIM-001*150***11:B:1*Y*A*Y*Y~"
        "HI*ABK:12345~"
        "SV1*HC:ABCDE*150*UN*1***1~"
        "SE*7*0001~"
        "GE*1*1~"
        "IEA*1*000000905~"
    )

    assert result.has_errors is True
    assert {issue.error_code for issue in result.validation_issues} == {
        "invalid_icd10_code",
        "invalid_cpt_hcpcs_code",
    }
    assert {issue.parser_stage for issue in result.validation_issues} == {
        "healthcare_code_validation"
    }
    assert all(not hasattr(issue, "raw_segment") for issue in result.validation_issues)
    assert "12345" not in str([issue.__dict__ for issue in result.validation_issues])
    assert "ABCDE" not in str([issue.__dict__ for issue in result.validation_issues])


def test_edi_837_invalid_administrative_codes_return_safe_issues():
    from app.utils.edi_parser import parse_edi_837

    result = parse_edi_837(
        f"{_isa_segment()}~"
        "GS*HC*SENDER*RECEIVER*20260529*1047*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "NM1*PR*2*SYNTHETIC PAYER*****PI*PAYER123~"
        "CLM*SYNTH-CLAIM-001*150***30:B:9*Y*A*Y*Y~"
        "HI*ABK:Z0000~"
        "SV2*45A*HC:99213*150*UN*1~"
        "SE*7*0001~"
        "GE*1*1~"
        "IEA*1*000000905~"
    )

    assert result.has_errors is True
    assert {issue.error_code for issue in result.validation_issues} == {
        "invalid_place_of_service_code",
        "invalid_claim_frequency_code",
        "invalid_revenue_code",
    }
    assert {issue.parser_stage for issue in result.validation_issues} == {
        "healthcare_code_validation"
    }
    assert result.claims[0].place_of_service_code == "30"
    assert result.claims[0].claim_frequency_code == "9"
    assert all(not hasattr(issue, "raw_segment") for issue in result.validation_issues)
    assert "30:B:9" not in str([issue.__dict__ for issue in result.validation_issues])
    assert "45A" not in str([issue.__dict__ for issue in result.validation_issues])


def test_edi_835_valid_carc_and_rarc_codes_are_parsed():
    from app.utils.edi_835_parser import parse_edi_835

    result = parse_edi_835(
        f"{_isa_segment()}~"
        "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
        "ST*835*0002~"
        "CLP*SYNTH-CLAIM-001*1*150*125*25*12*PAYER-CLAIM-001~"
        "CAS*CO*45*25~"
        "LQ*HE*N123~"
        "SE*6*0002~"
        "GE*1*2~"
        "IEA*1*000000905~"
    )

    assert result.has_errors is False
    assert result.claims[0].adjustments[0].group_code == "CO"
    assert result.claims[0].adjustments[0].reason_code == "45"
    assert result.claims[0].adjustments[0].reason_code_status == "active"
    assert result.claims[0].adjustments[0].reason_code_category == "fee_schedule_contract"
    assert result.claims[0].remark_codes[0].qualifier == "HE"
    assert result.claims[0].remark_codes[0].remark_code == "N123"
    assert result.claims[0].remark_codes[0].remark_code_status == "format_valid_unconfirmed"


def test_edi_835_active_alphanumeric_carc_and_known_rarc_include_metadata():
    from app.utils.edi_835_parser import parse_edi_835

    result = parse_edi_835(
        f"{_isa_segment()}~"
        "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
        "ST*835*0002~"
        "CLP*SYNTH-CLAIM-001*1*150*125*25*12*PAYER-CLAIM-001~"
        "CAS*CO*P12*25~"
        "LQ*HE*M20~"
        "SE*6*0002~"
        "GE*1*2~"
        "IEA*1*000000905~"
    )

    assert result.has_errors is False
    adjustment = result.claims[0].adjustments[0]
    remark = result.claims[0].remark_codes[0]
    assert adjustment.reason_code == "P12"
    assert adjustment.reason_code_status == "active"
    assert adjustment.reason_code_category == "workers_comp_fee_schedule"
    assert adjustment.reason_code_list_id == "CARC"
    assert remark.remark_code == "M20"
    assert remark.remark_code_status == "active"
    assert remark.remark_code_category == "procedure_code_metadata"
    assert remark.remark_code_list_id == "RARC"


def test_edi_835_inactive_carc_and_rarc_codes_return_safe_issues():
    from app.utils.edi_835_parser import parse_edi_835

    result = parse_edi_835(
        f"{_isa_segment()}~"
        "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
        "ST*835*0002~"
        "CLP*SYNTH-CLAIM-001*1*150*125*25*12*PAYER-CLAIM-001~"
        "CAS*CO*D4*25~"
        "LQ*HE*MA38~"
        "SE*6*0002~"
        "GE*1*2~"
        "IEA*1*000000905~"
    )

    assert result.has_errors is True
    assert {issue.error_code for issue in result.validation_issues} == {
        "invalid_reason_code",
        "invalid_remark_code",
    }
    assert {issue.code_status for issue in result.validation_issues} == {"inactive"}
    assert {issue.code_list_id for issue in result.validation_issues} == {"CARC", "RARC"}
    serialized = str([issue.__dict__ for issue in result.validation_issues])
    assert "D4" not in serialized
    assert "MA38" not in serialized
    assert "raw_segment" not in serialized


def test_edi_835_invalid_carc_and_rarc_codes_return_safe_issues():
    from app.utils.edi_835_parser import parse_edi_835

    result = parse_edi_835(
        f"{_isa_segment()}~"
        "GS*HP*SENDER*RECEIVER*20260529*1058*2*X*005010X221A1~"
        "ST*835*0002~"
        "CLP*SYNTH-CLAIM-001*1*150*125*25*12*PAYER-CLAIM-001~"
        "CAS*ZZ*AB*25~"
        "LQ*HE*X123~"
        "SE*6*0002~"
        "GE*1*2~"
        "IEA*1*000000905~"
    )

    assert result.has_errors is True
    assert {issue.error_code for issue in result.validation_issues} == {
        "invalid_group_code",
        "invalid_remark_code",
    }
    assert {issue.parser_stage for issue in result.validation_issues} == {
        "adjustment_parse",
        "remark_code_parse",
    }
    assert all(not hasattr(issue, "raw_segment") for issue in result.validation_issues)
    assert "ZZ" not in str([issue.__dict__ for issue in result.validation_issues])
    assert "X123" not in str([issue.__dict__ for issue in result.validation_issues])
