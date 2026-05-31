from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, Optional


CHARGE_AMOUNT_FIELDS = (
    "billed_amount",
    "charge_amount",
    "claim_amount",
    "total_charge_amount",
    "amount",
)
CONTRACT_RATE_FIELDS = (
    "contract_rate",
    "allowed_amount",
    "expected_allowed_amount",
    "payer_allowed_amount",
)
CONTRACT_RATE_MAP_FIELDS = (
    "contract_rates",
    "allowed_amounts",
    "expected_allowed_amounts",
    "payer_allowed_amounts",
)
CHARGE_MASTER_FIELDS = (
    "charge_master_rate",
    "charge_master_amount",
    "standard_charge",
)
CHARGE_MASTER_MAP_FIELDS = (
    "charge_master",
    "charge_master_rates",
    "standard_charges",
)
SERVICE_LINE_FIELDS = ("service_lines", "lines", "items")
PROCEDURE_CODE_FIELDS = ("procedure_code", "cpt_code", "hcpcs_code", "code")


@dataclass(frozen=True)
class ContractRateFinding:
    finding_type: str
    severity: str
    procedure_code: Optional[str]
    ratio: float
    description: str
    recommendation: str
    safe_context: Dict[str, bool]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_contract_rates(
    claim_data: Any,
    procedure_codes: Optional[List[str]] = None,
    contract_tolerance: float = 1.15,
) -> List[ContractRateFinding]:
    """Evaluate explicit structured charge-master and contract-rate metadata."""
    if not isinstance(claim_data, Mapping):
        return []

    findings: List[ContractRateFinding] = []
    normalized_codes = _normalize_codes(procedure_codes or [])
    line_count = 0

    for line in _iter_service_lines(claim_data):
        line_count += 1
        code = _extract_procedure_code(line) or _first_code(normalized_codes)
        charge = _first_amount(line, CHARGE_AMOUNT_FIELDS)
        contract_rate = _explicit_amount(
            line,
            claim_data,
            code,
            CONTRACT_RATE_FIELDS,
            CONTRACT_RATE_MAP_FIELDS,
        )
        charge_master_rate = _explicit_amount(
            line,
            claim_data,
            code,
            CHARGE_MASTER_FIELDS,
            CHARGE_MASTER_MAP_FIELDS,
        )
        findings.extend(
            _build_findings(code, charge, contract_rate, charge_master_rate, contract_tolerance)
        )

    if line_count == 0:
        code = _extract_procedure_code(claim_data) or _first_code(normalized_codes)
        charge = _first_amount(claim_data, CHARGE_AMOUNT_FIELDS)
        contract_rate = _explicit_amount(
            claim_data,
            claim_data,
            code,
            CONTRACT_RATE_FIELDS,
            CONTRACT_RATE_MAP_FIELDS,
            allow_claim_direct=True,
        )
        charge_master_rate = _explicit_amount(
            claim_data,
            claim_data,
            code,
            CHARGE_MASTER_FIELDS,
            CHARGE_MASTER_MAP_FIELDS,
            allow_claim_direct=True,
        )
        findings.extend(
            _build_findings(code, charge, contract_rate, charge_master_rate, contract_tolerance)
        )

    return findings


def _build_findings(
    procedure_code: Optional[str],
    charge: Optional[Decimal],
    contract_rate: Optional[Decimal],
    charge_master_rate: Optional[Decimal],
    contract_tolerance: float,
) -> List[ContractRateFinding]:
    findings: List[ContractRateFinding] = []
    tolerance = Decimal(str(contract_tolerance))
    if charge is None or charge <= 0:
        return findings

    if contract_rate is not None and contract_rate > 0 and charge > contract_rate * tolerance:
        ratio = _safe_ratio(charge, contract_rate)
        findings.append(
            ContractRateFinding(
                finding_type="charge_exceeds_contract_rate",
                severity="high" if ratio >= 1.5 else "medium",
                procedure_code=procedure_code,
                ratio=ratio,
                description=(
                    "Structured contract-rate check: billed charge exceeds configured "
                    "contract-rate tolerance using explicit claim metadata."
                ),
                recommendation=(
                    "Review the structured contract rate or allowed amount before "
                    "submission; do not infer payer-specific rates from free text."
                ),
                safe_context=_safe_context(
                    explicit_contract_metadata_used=True,
                    explicit_charge_master_metadata_used=False,
                ),
            )
        )

    if charge_master_rate is not None and charge_master_rate > 0:
        upper_limit = charge_master_rate * tolerance
        lower_limit = charge_master_rate / tolerance
        if charge > upper_limit or charge < lower_limit:
            ratio = _safe_ratio(charge, charge_master_rate)
            findings.append(
                ContractRateFinding(
                    finding_type="charge_master_mismatch",
                    severity="high" if ratio >= 1.5 else "medium",
                    procedure_code=procedure_code,
                    ratio=ratio,
                    description=(
                        "Structured charge-master check: billed charge differs from "
                        "configured charge-master tolerance using explicit claim metadata."
                    ),
                    recommendation=(
                        "Reconcile the service-line charge against the configured "
                        "charge master before submission."
                    ),
                    safe_context=_safe_context(
                        explicit_contract_metadata_used=False,
                        explicit_charge_master_metadata_used=True,
                    ),
                )
            )

    return findings


def _iter_service_lines(claim_data: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for field in SERVICE_LINE_FIELDS:
        value = claim_data.get(field)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping):
                    yield item
        elif isinstance(value, Mapping):
            for code, item in value.items():
                if isinstance(item, Mapping):
                    if _extract_procedure_code(item):
                        yield item
                    else:
                        line = dict(item)
                        line["code"] = str(code)
                        yield line


def _explicit_amount(
    line_data: Mapping[str, Any],
    claim_data: Mapping[str, Any],
    procedure_code: Optional[str],
    direct_fields: Iterable[str],
    map_fields: Iterable[str],
    allow_claim_direct: bool = False,
) -> Optional[Decimal]:
    direct = _first_amount(line_data, direct_fields)
    if direct is not None:
        return direct

    if procedure_code:
        from_maps = _amount_from_maps(claim_data, procedure_code, map_fields)
        if from_maps is not None:
            return from_maps

    if allow_claim_direct:
        return _first_amount(claim_data, direct_fields)
    return None


def _amount_from_maps(
    claim_data: Mapping[str, Any],
    procedure_code: str,
    map_fields: Iterable[str],
) -> Optional[Decimal]:
    for field in map_fields:
        value = claim_data.get(field)
        if not isinstance(value, Mapping):
            continue
        for key in (procedure_code, procedure_code.upper(), procedure_code.lower()):
            if key in value:
                amount = _to_decimal(value.get(key))
                if amount is not None:
                    return amount
    return None


def _first_amount(data: Mapping[str, Any], fields: Iterable[str]) -> Optional[Decimal]:
    for field in fields:
        amount = _to_decimal(data.get(field))
        if amount is not None:
            return amount
    return None


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace(",", "")
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


def _extract_procedure_code(data: Mapping[str, Any]) -> Optional[str]:
    for field in PROCEDURE_CODE_FIELDS:
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def _normalize_codes(codes: List[str]) -> List[str]:
    normalized = []
    for code in codes:
        if isinstance(code, str) and code.strip():
            normalized.append(code.strip().upper())
    return normalized


def _first_code(codes: List[str]) -> Optional[str]:
    return codes[0] if codes else None


def _safe_ratio(numerator: Decimal, denominator: Decimal) -> float:
    return round(float(numerator / denominator), 2)


def _safe_context(
    explicit_contract_metadata_used: bool,
    explicit_charge_master_metadata_used: bool,
) -> Dict[str, bool]:
    return {
        "raw_amount_values_included": False,
        "raw_claim_data_included": False,
        "explicit_contract_metadata_used": explicit_contract_metadata_used,
        "explicit_charge_master_metadata_used": explicit_charge_master_metadata_used,
        "inferred_payer_contract_used": False,
    }
