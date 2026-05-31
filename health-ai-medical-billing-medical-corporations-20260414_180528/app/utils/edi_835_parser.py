"""
EDI 835 remittance parser utilities.

This parser extracts safe claim payment and adjustment fields from X12 835 text
without logging raw segment payloads or patient-identifying values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Optional

from app.utils.healthcare_codes import (
    is_valid_carc_group_code,
    lookup_carc_reason_code_status,
    lookup_rarc_code_status,
    normalize_carc_code,
    normalize_rarc_code,
)

logger = logging.getLogger(__name__)


class EDI835ParserError(ValueError):
    """Raised when EDI 835 input is empty or structurally unusable."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "edi_835_parse_error",
        parser_stage: str = "edi_835_parse",
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
                "edi_parser": "edi_835",
                "raw_edi_text_included": False,
                "raw_segment_included": False,
            },
        }


@dataclass
class EDI835ValidationIssue:
    """Safe parser validation issue context."""

    message: str
    field: str
    error_code: str = "edi_835_validation_issue"
    parser_stage: str = "claim_payment_validation"
    severity: str = "error"
    claim_index: Optional[int] = None
    segment_index: Optional[int] = None
    segment_id: Optional[str] = None
    code_list_id: Optional[str] = None
    code_status: Optional[str] = None
    code_category: Optional[str] = None


@dataclass
class EDI835Adjustment:
    """Parsed CAS adjustment data."""

    segment_index: int
    group_code: str
    reason_code: str
    amount: float
    quantity: Optional[float] = None
    reason_code_status: str = "format_valid_unconfirmed"
    reason_code_category: Optional[str] = None
    reason_code_list_id: str = "CARC"


@dataclass
class EDI835RemarkCode:
    """Parsed LQ remark-code data."""

    segment_index: int
    qualifier: str
    remark_code: str
    remark_code_status: str = "format_valid_unconfirmed"
    remark_code_category: Optional[str] = None
    remark_code_list_id: str = "RARC"


@dataclass
class EDI835ClaimPayment:
    """Parsed CLP claim payment data."""

    claim_index: int
    segment_index: int
    patient_control_number: Optional[str]
    claim_status_code: Optional[str]
    total_charge_amount: Optional[float]
    paid_amount: Optional[float]
    patient_responsibility_amount: Optional[float]
    payer_claim_control_number: Optional[str]
    payment_status: str
    adjustments: list[EDI835Adjustment] = field(default_factory=list)
    remark_codes: list[EDI835RemarkCode] = field(default_factory=list)
    validation_issues: list[EDI835ValidationIssue] = field(default_factory=list)


@dataclass
class EDI835ParseResult:
    """Structured result for an EDI 835 parse."""

    claims: list[EDI835ClaimPayment]
    validation_issues: list[EDI835ValidationIssue]
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


@dataclass
class _EDISegment:
    index: int
    segment_id: str
    elements: list[str]


class EDI835Parser:
    """Parse core payment fields from X12 EDI 835 files."""

    DEFAULT_ELEMENT_SEPARATOR = "*"
    DEFAULT_COMPONENT_SEPARATOR = ":"
    DEFAULT_SEGMENT_TERMINATOR = "~"
    DENIED_STATUS_CODES = {"4"}

    def __init__(self, edi_text: str):
        if not isinstance(edi_text, str) or not edi_text.strip():
            raise EDI835ParserError(
                "EDI 835 input is required",
                error_code="edi_835_input_empty",
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

    def parse(self) -> EDI835ParseResult:
        segments = self._split_segments()
        if not segments:
            raise EDI835ParserError(
                "EDI 835 input does not contain parseable segments",
                error_code="edi_835_no_parseable_segments",
                parser_stage="segment_split",
                field="segments",
                segment_count=0,
            )

        claims: list[EDI835ClaimPayment] = []
        validation_issues: list[EDI835ValidationIssue] = []
        current_claim: Optional[EDI835ClaimPayment] = None

        for segment in segments:
            if segment.segment_id == "CLP":
                current_claim = self._parse_claim_payment(segment, len(claims) + 1)
                claims.append(current_claim)
                continue

            if segment.segment_id == "CAS":
                if current_claim is None:
                    validation_issues.append(
                        EDI835ValidationIssue(
                            message="CAS adjustment appeared before any CLP claim payment",
                            field="adjustments",
                            error_code="adjustment_before_claim_payment",
                            parser_stage="adjustment_parse",
                            segment_index=segment.index,
                            segment_id=segment.segment_id,
                        )
                    )
                    continue

                adjustments, issues = self._parse_adjustments(
                    segment, current_claim.claim_index
                )
                current_claim.adjustments.extend(adjustments)
                current_claim.validation_issues.extend(issues)
                validation_issues.extend(issues)
                continue

            if segment.segment_id == "LQ":
                if current_claim is None:
                    validation_issues.append(
                        EDI835ValidationIssue(
                            message="LQ remark code appeared before any CLP claim payment",
                            field="remark_codes",
                            error_code="remark_code_before_claim_payment",
                            parser_stage="remark_code_parse",
                            segment_index=segment.index,
                            segment_id=segment.segment_id,
                        )
                    )
                    continue

                remark_code, issue = self._parse_remark_code(
                    segment, current_claim.claim_index
                )
                if remark_code is not None:
                    current_claim.remark_codes.append(remark_code)
                if issue is not None:
                    current_claim.validation_issues.append(issue)
                    validation_issues.append(issue)

        if not claims:
            validation_issues.append(
                EDI835ValidationIssue(
                    message="No CLP claim payment segments found",
                    field="claim_payment",
                    error_code="missing_claim_payment",
                    parser_stage="claim_payment_validation",
                    segment_id="CLP",
                )
            )

        for claim in claims:
            claim_issues = self._validate_claim_payment(claim)
            claim.validation_issues.extend(claim_issues)
            validation_issues.extend(claim_issues)

        self._log_validation_issues(validation_issues)

        return EDI835ParseResult(
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

    def _parse_claim_payment(
        self, segment: _EDISegment, claim_index: int
    ) -> EDI835ClaimPayment:
        total_charge_amount = self._parse_decimal(self._field(segment, 3))
        paid_amount = self._parse_decimal(self._field(segment, 4))
        claim_status_code = self._field(segment, 2)

        return EDI835ClaimPayment(
            claim_index=claim_index,
            segment_index=segment.index,
            patient_control_number=self._field(segment, 1),
            claim_status_code=claim_status_code,
            total_charge_amount=total_charge_amount,
            paid_amount=paid_amount,
            patient_responsibility_amount=self._parse_decimal(self._field(segment, 5)),
            payer_claim_control_number=self._field(segment, 7),
            payment_status=self._derive_payment_status(
                claim_status_code, total_charge_amount, paid_amount
            ),
        )

    def _parse_adjustments(
        self, segment: _EDISegment, claim_index: int
    ) -> tuple[list[EDI835Adjustment], list[EDI835ValidationIssue]]:
        group_code = normalize_carc_code(self._field(segment, 1))
        adjustments: list[EDI835Adjustment] = []
        issues: list[EDI835ValidationIssue] = []

        if not group_code:
            issues.append(
                self._adjustment_issue(
                    claim_index,
                    segment,
                    "group_code",
                    "CAS segment is missing the adjustment group code",
                )
            )
            return adjustments, issues

        if not is_valid_carc_group_code(group_code):
            issues.append(
                self._adjustment_issue(
                    claim_index,
                    segment,
                    "group_code",
                    "CAS segment has an invalid adjustment group code",
                )
            )
            return adjustments, issues

        adjustment_fields = segment.elements[2:]
        for offset in range(0, len(adjustment_fields), 3):
            triplet = adjustment_fields[offset : offset + 3]
            triplet_position = (offset // 3) + 1

            if len(triplet) < 2:
                issues.append(
                    self._adjustment_issue(
                        claim_index,
                        segment,
                        "adjustment_triplet",
                        f"CAS adjustment triplet {triplet_position} is incomplete",
                    )
                )
                continue

            reason_code = normalize_carc_code(triplet[0])
            amount = self._parse_decimal(triplet[1])
            quantity = self._parse_decimal(triplet[2]) if len(triplet) > 2 else None

            if not reason_code:
                issues.append(
                    self._adjustment_issue(
                        claim_index,
                        segment,
                        "reason_code",
                        f"CAS adjustment triplet {triplet_position} is missing a reason code",
                    )
                )
                continue

            reason_code_lookup = lookup_carc_reason_code_status(reason_code)
            if not reason_code_lookup.allows_code:
                issues.append(
                    self._adjustment_issue(
                        claim_index,
                        segment,
                        "reason_code",
                        f"CAS adjustment triplet {triplet_position} has an invalid CARC reason code",
                        code_list_id=reason_code_lookup.list_id,
                        code_status=reason_code_lookup.status,
                        code_category=reason_code_lookup.category,
                    )
                )
                continue

            if amount is None:
                issues.append(
                    self._adjustment_issue(
                        claim_index,
                        segment,
                        "adjustment_amount",
                        f"CAS adjustment triplet {triplet_position} has an invalid amount",
                    )
                )
                continue

            adjustments.append(
                EDI835Adjustment(
                    segment_index=segment.index,
                    group_code=group_code,
                    reason_code=reason_code,
                    amount=amount,
                    quantity=quantity,
                    reason_code_status=reason_code_lookup.status,
                    reason_code_category=reason_code_lookup.category,
                    reason_code_list_id=reason_code_lookup.list_id,
                )
            )

        return adjustments, issues

    def _parse_remark_code(
        self, segment: _EDISegment, claim_index: int
    ) -> tuple[Optional[EDI835RemarkCode], Optional[EDI835ValidationIssue]]:
        qualifier = self._field(segment, 1)
        remark_code = normalize_rarc_code(self._field(segment, 2))
        if not qualifier:
            return None, self._remark_code_issue(
                claim_index,
                segment,
                "remark_code_qualifier",
                "LQ segment is missing the remark-code qualifier",
            )

        if not remark_code:
            return None, self._remark_code_issue(
                claim_index,
                segment,
                "remark_code",
                "LQ segment is missing the remark code",
            )

        remark_code_lookup = lookup_rarc_code_status(remark_code)
        if not remark_code_lookup.allows_code:
            return None, self._remark_code_issue(
                claim_index,
                segment,
                "remark_code",
                "LQ segment has an invalid RARC remark code",
                code_list_id=remark_code_lookup.list_id,
                code_status=remark_code_lookup.status,
                code_category=remark_code_lookup.category,
            )

        return (
            EDI835RemarkCode(
                segment_index=segment.index,
                qualifier=qualifier,
                remark_code=remark_code,
                remark_code_status=remark_code_lookup.status,
                remark_code_category=remark_code_lookup.category,
                remark_code_list_id=remark_code_lookup.list_id,
            ),
            None,
        )

    def _validate_claim_payment(
        self, claim: EDI835ClaimPayment
    ) -> list[EDI835ValidationIssue]:
        issues: list[EDI835ValidationIssue] = []

        if not claim.patient_control_number:
            issues.append(
                self._claim_issue(
                    claim,
                    "patient_control_number",
                    "CLP segment is missing the patient control number",
                )
            )

        if claim.total_charge_amount is None:
            issues.append(
                self._claim_issue(
                    claim,
                    "total_charge_amount",
                    "CLP segment is missing or has an invalid total charge amount",
                )
            )

        if claim.paid_amount is None:
            issues.append(
                self._claim_issue(
                    claim,
                    "paid_amount",
                    "CLP segment is missing or has an invalid paid amount",
                )
            )

        return issues

    def _claim_issue(
        self,
        claim: EDI835ClaimPayment,
        field_name: str,
        message: str,
    ) -> EDI835ValidationIssue:
        return EDI835ValidationIssue(
            message=message,
            field=field_name,
            error_code=f"missing_{field_name}",
            parser_stage="claim_payment_validation",
            claim_index=claim.claim_index,
            segment_index=claim.segment_index,
            segment_id="CLP",
        )

    def _adjustment_issue(
        self,
        claim_index: int,
        segment: _EDISegment,
        field_name: str,
        message: str,
        *,
        code_list_id: Optional[str] = None,
        code_status: Optional[str] = None,
        code_category: Optional[str] = None,
    ) -> EDI835ValidationIssue:
        return EDI835ValidationIssue(
            message=message,
            field=field_name,
            error_code=f"invalid_{field_name}",
            parser_stage="adjustment_parse",
            claim_index=claim_index,
            segment_index=segment.index,
            segment_id=segment.segment_id,
            code_list_id=code_list_id,
            code_status=code_status,
            code_category=code_category,
        )

    def _remark_code_issue(
        self,
        claim_index: int,
        segment: _EDISegment,
        field_name: str,
        message: str,
        *,
        code_list_id: Optional[str] = None,
        code_status: Optional[str] = None,
        code_category: Optional[str] = None,
    ) -> EDI835ValidationIssue:
        return EDI835ValidationIssue(
            message=message,
            field=field_name,
            error_code=f"invalid_{field_name}",
            parser_stage="remark_code_parse",
            claim_index=claim_index,
            segment_index=segment.index,
            segment_id=segment.segment_id,
            code_list_id=code_list_id,
            code_status=code_status,
            code_category=code_category,
        )

    def _log_validation_issues(self, issues: list[EDI835ValidationIssue]) -> None:
        for issue in issues:
            logger.warning(
                "EDI 835 validation issue",
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
                        "code_list_id": issue.code_list_id,
                        "code_status": issue.code_status,
                        "code_category": issue.code_category,
                        "safe_context": {
                            "edi_parser": "edi_835",
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

    def _derive_payment_status(
        self,
        claim_status_code: Optional[str],
        total_charge_amount: Optional[float],
        paid_amount: Optional[float],
    ) -> str:
        if claim_status_code in self.DENIED_STATUS_CODES:
            return "denied"

        if total_charge_amount is None or paid_amount is None:
            return "unknown"

        if paid_amount <= 0 and total_charge_amount > 0:
            return "denied"

        if paid_amount >= total_charge_amount:
            return "paid"

        if paid_amount > 0:
            return "partially_paid"

        return "unknown"

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


def parse_edi_835(edi_text: str) -> EDI835ParseResult:
    """Parse EDI 835 text into structured claim remittance data."""
    return EDI835Parser(edi_text).parse()
