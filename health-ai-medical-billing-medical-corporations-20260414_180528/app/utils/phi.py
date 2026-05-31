"""PHI/PII safety helpers that never return matched values."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class PhiFinding:
    finding_type: str
    line: int
    column: int
    category: str = "identifier_like"


PHI_PATTERNS: dict[str, re.Pattern[str]] = {
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_like": re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    "email_like": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "dob_label": re.compile(r"\b(?:DOB|date of birth)\b", re.IGNORECASE),
    "member_id_label": re.compile(
        r"\b(?:member id|subscriber id|policy number|policy #|member #)\b",
        re.IGNORECASE,
    ),
    "claim_number_label": re.compile(r"\b(?:claim number|claim #|ICN|DCN)\b", re.IGNORECASE),
    "mrn_label": re.compile(r"\b(?:MRN|medical record number)\b", re.IGNORECASE),
    "patient_name_label": re.compile(r"\b(?:patient|member)\s*(?:name)?\s*:", re.IGNORECASE),
    "street_address_like": re.compile(
        r"\b\d{2,6}\s+[A-Z0-9][A-Z0-9.'-]*(?:\s+[A-Z0-9][A-Z0-9.'-]*){0,4}\s+"
        r"(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd)\b",
        re.IGNORECASE,
    ),
}


def scan_text_for_phi(text: str) -> list[PhiFinding]:
    """Return location metadata for PHI/PII-like patterns without matched values."""
    findings: list[PhiFinding] = []
    if not text:
        return findings

    for line_number, line in enumerate(text.splitlines(), start=1):
        for finding_type, pattern in PHI_PATTERNS.items():
            for match in pattern.finditer(line):
                findings.append(
                    PhiFinding(
                        finding_type=finding_type,
                        line=line_number,
                        column=match.start() + 1,
                    )
                )
    return findings


def serialize_phi_findings(findings: Iterable[PhiFinding]) -> list[dict]:
    return [asdict(finding) for finding in findings]


def phi_scan_summary(findings: Iterable[PhiFinding]) -> dict:
    finding_list = list(findings)
    finding_types = sorted({finding.finding_type for finding in finding_list})
    return {
        "status": "findings_detected" if finding_list else "no_findings",
        "finding_count": len(finding_list),
        "finding_types": finding_types,
        "contains_phi_or_pii_like_content": bool(finding_list),
        "values_redacted": True,
        "review_required": bool(finding_list),
        "note": (
            "Scanner reports metadata only; matched PHI/PII-like values are not returned."
        ),
    }


def validate_declared_phi_status(
    *,
    declared_phi_status: str,
    findings: Iterable[PhiFinding],
    privacy_review_completed: bool = False,
    user_data_opt_in_for_model_improvement: bool = False,
) -> None:
    """Raise ValueError when an ingestion declaration conflicts with scan evidence."""
    finding_list = list(findings)
    if declared_phi_status == "no_phi" and finding_list:
        raise ValueError(
            "PHI/PII-like content detected; source cannot be declared no_phi."
        )
    if declared_phi_status == "deidentified" and finding_list and not privacy_review_completed:
        raise ValueError(
            "PHI/PII-like content detected; deidentified sources require privacy review."
        )
    if user_data_opt_in_for_model_improvement:
        if declared_phi_status not in {"no_phi", "deidentified"}:
            raise ValueError(
                "Model-improvement opt-in requires no_phi or deidentified source status."
            )
        if finding_list and not privacy_review_completed:
            raise ValueError(
                "Model-improvement opt-in requires completed privacy review when findings exist."
            )
