"""Healthcare code format validation utilities.

These checks are intentionally local and metadata-only. They validate syntax
and check digits where applicable; they do not call external code-set services
or assert payer-specific medical necessity.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from app.utils.carc_rarc_database import (
    CarcRarcLookup,
    resolve_carc_reason_code,
    resolve_rarc_code,
)


NPI_RE = re.compile(r"^\d{10}$")
NDC_DIGIT_RE = re.compile(r"^\d{10,12}$")
NDC_HYPHENATED_SEGMENT_LENGTHS = {
    (4, 4, 2),
    (5, 3, 2),
    (5, 4, 1),
    (5, 4, 2),
    (6, 3, 2),
    (6, 4, 1),
    (6, 4, 2),
}
ICD10_CM_RE = re.compile(r"^[A-TV-Z][0-9][A-Z0-9](?:\.?[A-Z0-9]{1,4})?$")
CPT_RE = re.compile(r"^(?:[0-9]{5}|[0-9]{4}[FT])$")
HCPCS_RE = re.compile(r"^[A-V][0-9]{4}$")
CARC_GROUP_CODES = {"CO", "CR", "OA", "PI", "PR"}
CARC_REASON_RE = re.compile(r"^(?:[0-9]{1,4}|[A-Z][0-9][A-Z0-9]{0,2})$")
RARC_RE = re.compile(r"^[MN][A-Z0-9]{1,4}$")
REVENUE_CODE_RE = re.compile(r"^[0-9]{4}$")
PLACE_OF_SERVICE_CODES = {
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "31",
    "32",
    "33",
    "34",
    "41",
    "42",
    "49",
    "50",
    "51",
    "52",
    "53",
    "54",
    "55",
    "56",
    "57",
    "58",
    "60",
    "61",
    "62",
    "65",
    "66",
    "71",
    "72",
    "81",
    "99",
}
CLAIM_FREQUENCY_CODES = {"1", "6", "7", "8"}


@dataclass(frozen=True)
class HealthcareCodeValidationIssue:
    field: str
    code_type: str
    error_code: str
    index: int | None = None
    segment_index: int | None = None
    segment_id: str | None = None
    parser_stage: str = "healthcare_code_validation"
    severity: str = "error"

    def safe_detail(self) -> dict[str, object]:
        return {
            "field": self.field,
            "code_type": self.code_type,
            "error_code": self.error_code,
            "index": self.index,
            "segment_index": self.segment_index,
            "segment_id": self.segment_id,
            "parser_stage": self.parser_stage,
            "severity": self.severity,
            "safe_context": {
                "raw_code_value_included": False,
                "raw_claim_data_included": False,
                "raw_document_text_included": False,
                "patient_identifier_included": False,
                "provider_identifier_included": False,
            },
        }


def normalize_healthcare_code(value: object) -> str:
    return str(value or "").strip().replace(" ", "").upper()


def normalize_icd10_code(value: object) -> str:
    return normalize_healthcare_code(value)


def normalize_cpt_hcpcs_code(value: object) -> str:
    return normalize_healthcare_code(value)


def normalize_carc_code(value: object) -> str:
    return normalize_healthcare_code(value)


def normalize_rarc_code(value: object) -> str:
    return normalize_healthcare_code(value)


def normalize_place_of_service_code(value: object) -> str:
    return normalize_healthcare_code(value).zfill(2)


def normalize_ndc_code(value: object) -> str:
    code = str(value or "").strip().upper()
    if code.startswith("N4"):
        code = code[2:].strip()
    return code


def normalize_claim_frequency_code(value: object) -> str:
    return normalize_healthcare_code(value)


def normalize_revenue_code(value: object) -> str:
    return normalize_healthcare_code(value).zfill(4)


def is_valid_npi(value: object) -> bool:
    npi = normalize_healthcare_code(value)
    if not NPI_RE.fullmatch(npi):
        return False

    digits = [int(char) for char in f"80840{npi[:-1]}"]
    total = 0
    parity = (len(digits) + 1) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            digit = (digit // 10) + (digit % 10)
        total += digit
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(npi[-1])


def is_valid_icd10_code(value: object) -> bool:
    code = normalize_icd10_code(value)
    return bool(ICD10_CM_RE.fullmatch(code))


def is_valid_cpt_hcpcs_code(value: object) -> bool:
    code = normalize_cpt_hcpcs_code(value)
    return bool(CPT_RE.fullmatch(code) or HCPCS_RE.fullmatch(code))


def is_valid_carc_group_code(value: object) -> bool:
    return normalize_carc_code(value) in CARC_GROUP_CODES


def is_valid_carc_reason_code(value: object) -> bool:
    return lookup_carc_reason_code_status(value).allows_code


def is_valid_rarc_code(value: object) -> bool:
    return lookup_rarc_code_status(value).allows_code


def lookup_carc_reason_code_status(value: object) -> CarcRarcLookup:
    code = normalize_carc_code(value)
    return resolve_carc_reason_code(
        code, format_valid=bool(CARC_REASON_RE.fullmatch(code))
    )


def lookup_rarc_code_status(value: object) -> CarcRarcLookup:
    code = normalize_rarc_code(value)
    return resolve_rarc_code(code, format_valid=bool(RARC_RE.fullmatch(code)))


def is_valid_place_of_service_code(value: object) -> bool:
    return normalize_place_of_service_code(value) in PLACE_OF_SERVICE_CODES


def is_valid_ndc_code(value: object) -> bool:
    code = normalize_ndc_code(value)
    if not code:
        return False
    if "-" in code:
        parts = code.split("-")
        segment_lengths = tuple(len(part) for part in parts)
        return (
            len(parts) == 3
            and segment_lengths in NDC_HYPHENATED_SEGMENT_LENGTHS
            and all(part.isdigit() for part in parts)
        )
    return bool(NDC_DIGIT_RE.fullmatch(code))


def is_valid_claim_frequency_code(value: object) -> bool:
    return normalize_claim_frequency_code(value) in CLAIM_FREQUENCY_CODES


def is_valid_revenue_code(value: object) -> bool:
    return bool(REVENUE_CODE_RE.fullmatch(normalize_revenue_code(value)))


def validate_claim_billing_codes(
    *,
    diagnosis_codes: Iterable[object] | None = None,
    procedure_codes: Iterable[object] | None = None,
) -> list[HealthcareCodeValidationIssue]:
    issues: list[HealthcareCodeValidationIssue] = []

    for index, code in enumerate(diagnosis_codes or []):
        if not is_valid_icd10_code(code):
            issues.append(
                HealthcareCodeValidationIssue(
                    field="diagnosis_codes",
                    code_type="icd10_cm",
                    error_code="invalid_icd10_code",
                    index=index,
                )
            )

    for index, code in enumerate(procedure_codes or []):
        if not is_valid_cpt_hcpcs_code(code):
            issues.append(
                HealthcareCodeValidationIssue(
                    field="procedure_codes",
                    code_type="cpt_hcpcs",
                    error_code="invalid_cpt_hcpcs_code",
                    index=index,
                )
            )

    return issues


def validate_administrative_claim_codes(
    *,
    place_of_service_codes: Iterable[object] | None = None,
    ndc_codes: Iterable[object] | None = None,
    claim_frequency_codes: Iterable[object] | None = None,
    revenue_codes: Iterable[object] | None = None,
) -> list[HealthcareCodeValidationIssue]:
    issues: list[HealthcareCodeValidationIssue] = []

    for index, code in enumerate(place_of_service_codes or []):
        if not is_valid_place_of_service_code(code):
            issues.append(
                HealthcareCodeValidationIssue(
                    field="place_of_service_codes",
                    code_type="place_of_service",
                    error_code="invalid_place_of_service_code",
                    index=index,
                )
            )

    for index, code in enumerate(ndc_codes or []):
        if not is_valid_ndc_code(code):
            issues.append(
                HealthcareCodeValidationIssue(
                    field="ndc_codes",
                    code_type="ndc",
                    error_code="invalid_ndc_code",
                    index=index,
                )
            )

    for index, code in enumerate(claim_frequency_codes or []):
        if not is_valid_claim_frequency_code(code):
            issues.append(
                HealthcareCodeValidationIssue(
                    field="claim_frequency_codes",
                    code_type="claim_frequency",
                    error_code="invalid_claim_frequency_code",
                    index=index,
                )
            )

    for index, code in enumerate(revenue_codes or []):
        if not is_valid_revenue_code(code):
            issues.append(
                HealthcareCodeValidationIssue(
                    field="revenue_codes",
                    code_type="revenue_code",
                    error_code="invalid_revenue_code",
                    index=index,
                )
            )

    return issues
