"""
EDI 837 claim parser utilities.

This parser extracts safe claim-level billing fields from X12 837 text without
logging raw segment payloads or patient-identifying values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Optional

from app.utils.healthcare_codes import (
    is_valid_claim_frequency_code,
    is_valid_cpt_hcpcs_code,
    is_valid_icd10_code,
    is_valid_place_of_service_code,
    is_valid_revenue_code,
)

logger = logging.getLogger(__name__)


class EDIParserError(ValueError):
    """Raised when EDI input is empty or structurally unusable."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "edi_837_parse_error",
        parser_stage: str = "edi_837_parse",
        field: Optional[str] = None,
        claim_index: Optional[int] = None,
        segment_index: Optional[int] = None,
        segment_id: Optional[str] = None,
        segment_count: Optional[int] = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.parser_stage = parser_stage
        self.field = field
        self.claim_index = claim_index
        self.segment_index = segment_index
        self.segment_id = segment_id
        self.segment_count = segment_count

    def safe_detail(self) -> dict:
        """Return structured parser context without raw EDI payload values."""
        return {
            "error_code": self.error_code,
            "parser_stage": self.parser_stage,
            "field": self.field,
            "claim_index": self.claim_index,
            "segment_index": self.segment_index,
            "segment_id": self.segment_id,
            "segment_count": self.segment_count,
            "safe_context": {
                "edi_parser": "edi_837",
                "raw_edi_text_included": False,
                "raw_segment_included": False,
            },
        }


@dataclass
class EDIValidationIssue:
    """Safe parser validation issue context."""

    message: str
    field: str
    error_code: str = "edi_837_validation_issue"
    parser_stage: str = "claim_validation"
    severity: str = "error"
    claim_index: Optional[int] = None
    segment_index: Optional[int] = None
    segment_id: Optional[str] = None


@dataclass
class EDI837ServiceLine:
    """Parsed 2400 service-line data."""

    segment_index: int
    segment_id: str
    procedure_code: Optional[str]
    procedure_modifiers: list[str] = field(default_factory=list)
    charge_amount: Optional[float] = None
    unit_count: Optional[float] = None
    revenue_code: Optional[str] = None
    product_service_qualifier: Optional[str] = None
    diagnosis_pointers: list[str] = field(default_factory=list)


@dataclass
class EDI837Claim:
    """Parsed 2300 claim loop data."""

    claim_index: int
    segment_index: int
    claim_control_number: Optional[str]
    total_charge_amount: Optional[float]
    place_of_service_code: Optional[str] = None
    facility_code_qualifier: Optional[str] = None
    claim_frequency_code: Optional[str] = None
    payer_name: Optional[str] = None
    payer_identifier: Optional[str] = None
    diagnosis_codes: list[str] = field(default_factory=list)
    service_lines: list[EDI837ServiceLine] = field(default_factory=list)
    validation_issues: list[EDIValidationIssue] = field(default_factory=list)


@dataclass
class EDI837ParseResult:
    """Structured result for an EDI 837 parse."""

    claims: list[EDI837Claim]
    validation_issues: list[EDIValidationIssue]
    segment_count: int
    element_separator: str
    component_separator: str
    segment_terminator: str
    interchange_control_number: Optional[str] = None
    group_control_number: Optional[str] = None
    transaction_control_number: Optional[str] = None

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.validation_issues)


@dataclass(frozen=True)
class EDI837BatchSizeEstimate:
    """Safe aggregate EDI 837 size metadata for pre-parse upload guards."""

    segment_count: int
    claim_count: int


@dataclass
class _EDISegment:
    index: int
    segment_id: str
    elements: list[str]


@dataclass
class _PayerContext:
    name: Optional[str] = None
    identifier: Optional[str] = None


class EDI837Parser:
    """Parse core claim fields from X12 EDI 837 files."""

    DEFAULT_ELEMENT_SEPARATOR = "*"
    DEFAULT_COMPONENT_SEPARATOR = ":"
    DEFAULT_SEGMENT_TERMINATOR = "~"
    DIAGNOSIS_QUALIFIERS = {"ABK", "ABF", "BK", "BF", "ABJ", "APR"}

    def __init__(self, edi_text: str):
        if not isinstance(edi_text, str) or not edi_text.strip():
            raise EDIParserError(
                "EDI input is required",
                error_code="edi_input_empty",
                parser_stage="input_validation",
                field="edi_text",
                segment_count=0,
            )

        self.edi_text = edi_text.strip()
        (
            self.element_separator,
            self.component_separator,
            self.segment_terminator,
        ) = self._detect_delimiters(self.edi_text)

    def parse(self) -> EDI837ParseResult:
        segments = self._split_segments()
        if not segments:
            raise EDIParserError(
                "EDI input does not contain parseable segments",
                error_code="edi_no_parseable_segments",
                parser_stage="segment_split",
                field="segments",
                segment_count=0,
            )

        claims: list[EDI837Claim] = []
        validation_issues: list[EDIValidationIssue] = []
        current_claim: Optional[EDI837Claim] = None
        current_payer = _PayerContext()

        for segment in segments:
            if segment.segment_id == "NM1" and self._field(segment, 1) == "PR":
                current_payer = self._parse_payer(segment)
                if (
                    current_claim is not None
                    and not current_claim.payer_name
                    and not current_claim.payer_identifier
                ):
                    current_claim.payer_name = current_payer.name
                    current_claim.payer_identifier = current_payer.identifier
                continue

            if segment.segment_id == "CLM":
                current_claim = self._parse_claim(segment, len(claims) + 1, current_payer)
                claims.append(current_claim)
                continue

            if segment.segment_id == "HI" and current_claim is not None:
                current_claim.diagnosis_codes.extend(self._parse_diagnosis_codes(segment))
                current_claim.diagnosis_codes = self._dedupe(current_claim.diagnosis_codes)
                continue

            if segment.segment_id in {"SV1", "SV2"}:
                if current_claim is None:
                    validation_issues.append(
                        EDIValidationIssue(
                            message="Service line appeared before any claim loop",
                            field="service_line",
                            error_code="service_line_before_claim_loop",
                            parser_stage="service_line_parse",
                            segment_index=segment.index,
                            segment_id=segment.segment_id,
                        )
                    )
                    continue

                service_line, issue = self._parse_service_line(segment, current_claim.claim_index)
                if issue is not None:
                    current_claim.validation_issues.append(issue)
                    validation_issues.append(issue)
                if service_line is not None:
                    current_claim.service_lines.append(service_line)

        if not claims:
            validation_issues.append(
                EDIValidationIssue(
                    message="No CLM claim loops found",
                    field="claim_loop",
                    error_code="missing_claim_loop",
                    parser_stage="claim_loop_validation",
                    segment_id="CLM",
                )
            )

        for claim in claims:
            claim_issues = self._validate_claim(claim)
            claim.validation_issues.extend(claim_issues)
            validation_issues.extend(claim_issues)

        self._log_validation_issues(validation_issues)

        return EDI837ParseResult(
            claims=claims,
            validation_issues=validation_issues,
            segment_count=len(segments),
            element_separator=self.element_separator,
            component_separator=self.component_separator,
            segment_terminator=self.segment_terminator,
            interchange_control_number=self._envelope_value(segments, "ISA", 13),
            group_control_number=self._envelope_value(segments, "GS", 6),
            transaction_control_number=self._envelope_value(segments, "ST", 2),
        )

    @classmethod
    def _detect_delimiters(cls, edi_text: str) -> tuple[str, str, str]:
        element_separator = cls.DEFAULT_ELEMENT_SEPARATOR
        component_separator = cls.DEFAULT_COMPONENT_SEPARATOR
        segment_terminator = cls.DEFAULT_SEGMENT_TERMINATOR

        if edi_text.startswith("ISA") and len(edi_text) >= 106:
            element_separator = edi_text[3]
            component_separator = edi_text[104]
            segment_terminator = edi_text[105]
        elif cls.DEFAULT_SEGMENT_TERMINATOR not in edi_text and "\n" in edi_text:
            segment_terminator = "\n"

        return element_separator, component_separator, segment_terminator

    def _split_segments(self) -> list[_EDISegment]:
        raw_segments = self.edi_text.split(self.segment_terminator)
        segments: list[_EDISegment] = []

        for raw_index, raw_segment in enumerate(raw_segments, start=1):
            cleaned = raw_segment.strip().replace("\r", "").replace("\n", "")
            if not cleaned:
                continue

            elements = cleaned.split(self.element_separator)
            segment_id = elements[0].strip().upper()
            if not segment_id:
                continue

            segments.append(
                _EDISegment(
                    index=raw_index,
                    segment_id=segment_id,
                    elements=elements,
                )
            )

        return segments

    def _parse_payer(self, segment: _EDISegment) -> _PayerContext:
        name_parts = [
            self._field(segment, 3),
            self._field(segment, 4),
            self._field(segment, 5),
        ]
        name = " ".join(part for part in name_parts if part).strip() or None
        identifier = self._field(segment, 9)
        return _PayerContext(name=name, identifier=identifier)

    def _parse_claim(
        self,
        segment: _EDISegment,
        claim_index: int,
        current_payer: _PayerContext,
    ) -> EDI837Claim:
        location_components = self._split_component_values(self._field(segment, 5))
        return EDI837Claim(
            claim_index=claim_index,
            segment_index=segment.index,
            claim_control_number=self._field(segment, 1),
            total_charge_amount=self._parse_decimal(self._field(segment, 2)),
            place_of_service_code=self._component_value(location_components, 0),
            facility_code_qualifier=self._component_value(location_components, 1),
            claim_frequency_code=self._component_value(location_components, 2),
            payer_name=current_payer.name,
            payer_identifier=current_payer.identifier,
        )

    def _parse_diagnosis_codes(self, segment: _EDISegment) -> list[str]:
        codes: list[str] = []
        for composite in segment.elements[1:]:
            components = composite.split(self.component_separator)
            if len(components) < 2:
                continue

            qualifier = components[0].strip().upper()
            code = self._normalize_code(components[1])
            if qualifier in self.DIAGNOSIS_QUALIFIERS and code:
                codes.append(code)

        return codes

    def _parse_service_line(
        self, segment: _EDISegment, claim_index: int
    ) -> tuple[Optional[EDI837ServiceLine], Optional[EDIValidationIssue]]:
        if segment.segment_id == "SV1":
            return self._parse_sv1(segment, claim_index)
        return self._parse_sv2(segment, claim_index)

    def _parse_sv1(
        self, segment: _EDISegment, claim_index: int
    ) -> tuple[Optional[EDI837ServiceLine], Optional[EDIValidationIssue]]:
        composite = self._field(segment, 1)
        components = composite.split(self.component_separator) if composite else []
        if len(components) < 2 or not components[1].strip():
            return None, self._service_line_issue(
                claim_index,
                segment,
                "procedure_code",
                "SV1 service line is missing a procedure code",
            )

        return (
            EDI837ServiceLine(
                segment_index=segment.index,
                segment_id=segment.segment_id,
                procedure_code=self._normalize_code(components[1]),
                procedure_modifiers=[
                    self._normalize_code(component) for component in components[2:] if component
                ],
                charge_amount=self._parse_decimal(self._field(segment, 2)),
                unit_count=self._parse_decimal(self._field(segment, 4)),
                product_service_qualifier=components[0].strip() or None,
                diagnosis_pointers=self._split_component_values(self._field(segment, 7)),
            ),
            None,
        )

    def _parse_sv2(
        self, segment: _EDISegment, claim_index: int
    ) -> tuple[Optional[EDI837ServiceLine], Optional[EDIValidationIssue]]:
        composite = self._field(segment, 2)
        components = composite.split(self.component_separator) if composite else []
        if len(components) < 2 or not components[1].strip():
            return None, self._service_line_issue(
                claim_index,
                segment,
                "procedure_code",
                "SV2 service line is missing a procedure code",
            )

        return (
            EDI837ServiceLine(
                segment_index=segment.index,
                segment_id=segment.segment_id,
                procedure_code=self._normalize_code(components[1]),
                procedure_modifiers=[
                    self._normalize_code(component) for component in components[2:] if component
                ],
                charge_amount=self._parse_decimal(self._field(segment, 3)),
                unit_count=self._parse_decimal(self._field(segment, 5)),
                revenue_code=self._field(segment, 1),
                product_service_qualifier=components[0].strip() or None,
            ),
            None,
        )

    def _validate_claim(self, claim: EDI837Claim) -> list[EDIValidationIssue]:
        issues: list[EDIValidationIssue] = []

        if not claim.claim_control_number:
            issues.append(
                self._claim_issue(
                    claim,
                    "claim_control_number",
                    "CLM segment is missing the claim control number",
                )
            )

        if not claim.diagnosis_codes:
            issues.append(
                self._claim_issue(
                    claim,
                    "diagnosis_codes",
                    "Claim is missing HI diagnosis codes",
                    segment_id="HI",
                )
            )
        else:
            for diagnosis_code in claim.diagnosis_codes:
                if not is_valid_icd10_code(diagnosis_code):
                    issues.append(
                        EDIValidationIssue(
                            message="Claim contains an invalid diagnosis code format",
                            field="diagnosis_codes",
                            error_code="invalid_icd10_code",
                            parser_stage="healthcare_code_validation",
                            claim_index=claim.claim_index,
                            segment_index=claim.segment_index,
                            segment_id="HI",
                        )
                    )

        if claim.place_of_service_code and not is_valid_place_of_service_code(
            claim.place_of_service_code
        ):
            issues.append(
                EDIValidationIssue(
                    message="Claim contains an invalid place of service code",
                    field="place_of_service_code",
                    error_code="invalid_place_of_service_code",
                    parser_stage="healthcare_code_validation",
                    claim_index=claim.claim_index,
                    segment_index=claim.segment_index,
                    segment_id="CLM",
                )
            )

        if claim.claim_frequency_code and not is_valid_claim_frequency_code(
            claim.claim_frequency_code
        ):
            issues.append(
                EDIValidationIssue(
                    message="Claim contains an invalid claim frequency code",
                    field="claim_frequency_code",
                    error_code="invalid_claim_frequency_code",
                    parser_stage="healthcare_code_validation",
                    claim_index=claim.claim_index,
                    segment_index=claim.segment_index,
                    segment_id="CLM",
                )
            )

        if not claim.service_lines:
            issues.append(
                self._claim_issue(
                    claim,
                    "service_lines",
                    "Claim is missing SV1 or SV2 service lines",
                    segment_id="SV1/SV2",
                )
            )
        else:
            for service_line in claim.service_lines:
                if not is_valid_cpt_hcpcs_code(service_line.procedure_code):
                    issues.append(
                        EDIValidationIssue(
                            message="Service line contains an invalid procedure code format",
                            field="procedure_code",
                            error_code="invalid_cpt_hcpcs_code",
                            parser_stage="healthcare_code_validation",
                            claim_index=claim.claim_index,
                            segment_index=service_line.segment_index,
                            segment_id=service_line.segment_id,
                        )
                    )
                if (
                    service_line.segment_id == "SV1"
                    and service_line.procedure_code
                    and not service_line.diagnosis_pointers
                ):
                    issues.append(
                        EDIValidationIssue(
                            message=(
                                "Professional service line is missing diagnosis "
                                "pointer metadata"
                            ),
                            field="diagnosis_pointers",
                            error_code="missing_diagnosis_pointer",
                            parser_stage="diagnosis_procedure_linkage_validation",
                            claim_index=claim.claim_index,
                            segment_index=service_line.segment_index,
                            segment_id=service_line.segment_id,
                        )
                    )
                for pointer in service_line.diagnosis_pointers:
                    normalized_pointer = str(pointer or "").strip()
                    if not normalized_pointer.isdigit():
                        issues.append(
                            EDIValidationIssue(
                                message="Service line contains an invalid diagnosis pointer format",
                                field="diagnosis_pointers",
                                error_code="invalid_diagnosis_pointer_format",
                                parser_stage="diagnosis_procedure_linkage_validation",
                                claim_index=claim.claim_index,
                                segment_index=service_line.segment_index,
                                segment_id=service_line.segment_id,
                            )
                        )
                        continue
                    pointer_index = int(normalized_pointer)
                    if pointer_index < 1 or pointer_index > len(claim.diagnosis_codes):
                        issues.append(
                            EDIValidationIssue(
                                message="Service line diagnosis pointer is outside the claim diagnosis list",
                                field="diagnosis_pointers",
                                error_code="diagnosis_pointer_out_of_range",
                                parser_stage="diagnosis_procedure_linkage_validation",
                                claim_index=claim.claim_index,
                                segment_index=service_line.segment_index,
                                segment_id=service_line.segment_id,
                            )
                        )
                if service_line.revenue_code and not is_valid_revenue_code(
                    service_line.revenue_code
                ):
                    issues.append(
                        EDIValidationIssue(
                            message="Service line contains an invalid revenue code format",
                            field="revenue_code",
                            error_code="invalid_revenue_code",
                            parser_stage="healthcare_code_validation",
                            claim_index=claim.claim_index,
                            segment_index=service_line.segment_index,
                            segment_id=service_line.segment_id,
                        )
                    )

        if not claim.payer_name and not claim.payer_identifier:
            issues.append(
                self._claim_issue(
                    claim,
                    "payer",
                    "Claim is missing NM1*PR payer information",
                    segment_id="NM1",
                )
            )

        return issues

    def _claim_issue(
        self,
        claim: EDI837Claim,
        field_name: str,
        message: str,
        segment_id: str = "CLM",
    ) -> EDIValidationIssue:
        return EDIValidationIssue(
            message=message,
            field=field_name,
            error_code=f"missing_{field_name}",
            parser_stage="claim_validation",
            claim_index=claim.claim_index,
            segment_index=claim.segment_index,
            segment_id=segment_id,
        )

    def _service_line_issue(
        self,
        claim_index: int,
        segment: _EDISegment,
        field_name: str,
        message: str,
    ) -> EDIValidationIssue:
        return EDIValidationIssue(
            message=message,
            field=field_name,
            error_code=f"missing_{field_name}",
            parser_stage="service_line_parse",
            claim_index=claim_index,
            segment_index=segment.index,
            segment_id=segment.segment_id,
        )

    def _log_validation_issues(self, issues: list[EDIValidationIssue]) -> None:
        for issue in issues:
            logger.warning(
                "EDI 837 validation issue",
                extra={
                    "edi_issue": {
                        "error_code": issue.error_code,
                        "parser_stage": issue.parser_stage,
                        "message": issue.message,
                        "field": issue.field,
                        "severity": issue.severity,
                        "claim_index": issue.claim_index,
                        "segment_index": issue.segment_index,
                        "segment_id": issue.segment_id,
                        "safe_context": {
                            "edi_parser": "edi_837",
                            "raw_edi_text_included": False,
                            "raw_segment_included": False,
                        },
                    }
                },
            )

    def _envelope_value(
        self, segments: list[_EDISegment], segment_id: str, field_index: int
    ) -> Optional[str]:
        for segment in segments:
            if segment.segment_id == segment_id:
                return self._field(segment, field_index)
        return None

    def _field(self, segment: _EDISegment, field_index: int) -> Optional[str]:
        if len(segment.elements) <= field_index:
            return None
        value = segment.elements[field_index].strip()
        return value or None

    def _split_component_values(self, value: Optional[str]) -> list[str]:
        if not value:
            return []
        return [
            self._normalize_code(component)
            for component in value.split(self.component_separator)
            if component.strip()
        ]

    @staticmethod
    def _parse_decimal(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        normalized = value.replace(",", "").replace("$", "").strip()
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None

    @staticmethod
    def _normalize_code(value: str) -> str:
        return value.strip().replace(" ", "").upper()

    @staticmethod
    def _component_value(components: list[str], index: int) -> Optional[str]:
        if index >= len(components):
            return None
        value = components[index].strip()
        return value or None

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen = set()
        deduped = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped


def parse_edi_837(edi_text: str) -> EDI837ParseResult:
    """Parse EDI 837 text into structured claim-level data."""
    return EDI837Parser(edi_text).parse()


def estimate_edi_837_batch_size(edi_text: str) -> EDI837BatchSizeEstimate:
    """Estimate aggregate batch size without constructing claim objects."""
    if not isinstance(edi_text, str) or not edi_text.strip():
        return EDI837BatchSizeEstimate(segment_count=0, claim_count=0)

    text = edi_text.strip()
    element_separator, _, segment_terminator = EDI837Parser._detect_delimiters(text)
    segment_count = 0
    claim_count = 0

    for raw_segment in text.split(segment_terminator):
        cleaned = raw_segment.strip().replace("\r", "").replace("\n", "")
        if not cleaned:
            continue

        segment_id = cleaned.split(element_separator, 1)[0].strip().upper()
        if not segment_id:
            continue

        segment_count += 1
        if segment_id == "CLM":
            claim_count += 1

    return EDI837BatchSizeEstimate(
        segment_count=segment_count,
        claim_count=claim_count,
    )
