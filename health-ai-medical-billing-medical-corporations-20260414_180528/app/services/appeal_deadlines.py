"""Metadata-only appeal deadline tracking helpers.

The helpers use dates or appeal-window metadata already present on the claim.
They do not infer payer-specific rules from free text and never treat a draft
appeal as filing-ready.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


SAFE_CONTEXT = {
    "raw_claim_data_included": False,
    "raw_denial_text_included": False,
    "raw_document_text_included": False,
    "patient_identifier_included": False,
    "provider_identifier_included": False,
}


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _parse_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _safe_assumptions(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values[:6] if value]


def _days_until(deadline: date | None, generated_on: date) -> int | None:
    if deadline is None:
        return None
    return (deadline - generated_on).days


def _deadline_status(days_until_deadline: int | None, verified: bool) -> str:
    if days_until_deadline is None:
        return "needs_human_verification"
    if days_until_deadline < 0:
        return "past_due_needs_human_review"
    if days_until_deadline <= 7:
        return "urgent_needs_human_review"
    return "verified" if verified else "needs_human_verification"


def _deadline_record(
    *,
    deadline_type: str,
    generated_on: date,
    source_stated_deadline: date | None = None,
    calculated_deadline: date | None = None,
    basis_date: date | None = None,
    days_from_basis: int | None = None,
    rule_source_id: str | None = None,
    assumptions: list[str] | None = None,
    source_status: str = "missing_needs_human_verification",
    verified: bool = False,
) -> dict[str, Any]:
    effective_deadline = source_stated_deadline or calculated_deadline
    days_until_deadline = _days_until(effective_deadline, generated_on)
    verification_status = _deadline_status(days_until_deadline, verified)
    human_verification_required = verification_status != "verified"

    return {
        "deadline_type": deadline_type,
        "source_stated_deadline": source_stated_deadline,
        "calculated_deadline": calculated_deadline,
        "basis_date": basis_date,
        "days_from_basis": days_from_basis,
        "days_until_deadline": days_until_deadline,
        "rule_source_id": rule_source_id,
        "source_status": source_status,
        "verification_status": verification_status,
        "human_verification_required": human_verification_required,
        "assumptions": assumptions or [],
        "safe_context": dict(SAFE_CONTEXT),
    }


def build_appeal_deadline_tracking(
    claim_data: dict[str, Any] | None,
    *,
    generated_on: date | None = None,
) -> list[dict[str, Any]]:
    """Build conservative appeal deadline tracking rows from safe metadata."""

    generated_date = generated_on or date.today()
    data = claim_data if isinstance(claim_data, dict) else {}
    workflow = data.get("denial_workflow") if isinstance(data.get("denial_workflow"), dict) else {}

    deadline_table = workflow.get("deadline_table") or data.get("deadline_table") or []
    records: list[dict[str, Any]] = []
    if isinstance(deadline_table, list):
        for item in deadline_table:
            if not isinstance(item, dict):
                continue
            source_stated_deadline = _parse_date(item.get("source_stated_deadline"))
            calculated_deadline = _parse_date(item.get("calculated_deadline"))
            if not (source_stated_deadline or calculated_deadline):
                continue

            records.append(
                _deadline_record(
                    deadline_type=str(item.get("deadline_type") or "appeal_deadline"),
                    generated_on=generated_date,
                    source_stated_deadline=source_stated_deadline,
                    calculated_deadline=calculated_deadline,
                    rule_source_id=item.get("rule_source_id"),
                    assumptions=_safe_assumptions(item.get("assumptions"))
                    + ["Verify payer instructions, route, and deadline before submission."],
                    source_status=(
                        "known_from_documents"
                        if source_stated_deadline
                        else "cited_rule"
                    ),
                    verified=item.get("verification_status") == "verified",
                )
            )

    if records:
        return records

    source_stated_deadline = (
        _parse_date(data.get("appeal_deadline"))
        or _parse_date(data.get("appeal_due_date"))
        or _parse_date(data.get("filing_deadline"))
    )
    if source_stated_deadline:
        return [
            _deadline_record(
                deadline_type="appeal_deadline",
                generated_on=generated_date,
                source_stated_deadline=source_stated_deadline,
                assumptions=[
                    "Deadline came from structured claim metadata.",
                    "Verify the denial letter, plan terms, payer channel, and receipt date before submission.",
                ],
                source_status="known_from_documents",
            )
        ]

    basis_date = (
        _parse_date(data.get("denial_received_date"))
        or _parse_date(data.get("denial_date"))
        or _parse_date(data.get("notice_date"))
    )
    days_from_basis = (
        _parse_positive_int(data.get("appeal_deadline_days"))
        or _parse_positive_int(data.get("appeal_window_days"))
        or _parse_positive_int(data.get("days_to_appeal"))
    )
    if basis_date and days_from_basis:
        return [
            _deadline_record(
                deadline_type="appeal_deadline",
                generated_on=generated_date,
                calculated_deadline=basis_date + timedelta(days=days_from_basis),
                basis_date=basis_date,
                days_from_basis=days_from_basis,
                assumptions=[
                    "Calculated from structured claim metadata, not from a payer-specific legal rule.",
                    "Verify the controlling plan, denial notice, receipt date, route, and payer instructions before submission.",
                ],
                source_status="inferred",
            )
        ]

    return [
        _deadline_record(
            deadline_type="appeal_deadline",
            generated_on=generated_date,
            assumptions=[
                "No structured appeal deadline, denial received date, or appeal-window metadata was available.",
                "Human reviewer must verify the deadline from the denial notice, plan terms, payer portal, or rule source before submission.",
            ],
            source_status="missing_needs_human_verification",
        )
    ]


def summarize_appeal_deadline_tracking(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "status": "needs_human_verification",
            "item_count": 0,
            "urgent_count": 0,
            "past_due_count": 0,
            "verified_count": 0,
            "human_verification_required": True,
        }

    statuses = [record.get("verification_status") for record in records]
    return {
        "status": (
            "past_due_needs_human_review"
            if "past_due_needs_human_review" in statuses
            else "urgent_needs_human_review"
            if "urgent_needs_human_review" in statuses
            else "verified"
            if statuses and all(status == "verified" for status in statuses)
            else "needs_human_verification"
        ),
        "item_count": len(records),
        "urgent_count": statuses.count("urgent_needs_human_review"),
        "past_due_count": statuses.count("past_due_needs_human_review"),
        "verified_count": statuses.count("verified"),
        "human_verification_required": any(
            record.get("human_verification_required", True) for record in records
        ),
    }
