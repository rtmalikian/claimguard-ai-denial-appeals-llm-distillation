from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.appeal_deadlines import (
    build_appeal_deadline_tracking,
    summarize_appeal_deadline_tracking,
)


def test_appeal_deadline_tracking_calculates_from_structured_metadata():
    records = build_appeal_deadline_tracking(
        {
            "denial_received_date": "2026-01-10",
            "appeal_deadline_days": 30,
        },
        generated_on=date(2026, 1, 15),
    )

    assert len(records) == 1
    record = records[0]
    assert record["calculated_deadline"] == date(2026, 2, 9)
    assert record["days_until_deadline"] == 25
    assert record["source_status"] == "inferred"
    assert record["verification_status"] == "needs_human_verification"
    assert record["human_verification_required"] is True
    assert record["safe_context"]["raw_claim_data_included"] is False


def test_appeal_deadline_tracking_uses_workflow_deadline_table():
    records = build_appeal_deadline_tracking(
        {
            "denial_workflow": {
                "deadline_table": [
                    {
                        "deadline_type": "internal_appeal",
                        "source_stated_deadline": "2026-02-01",
                        "rule_source_id": "SRC-SYNTHETIC-RULE",
                        "verification_status": "verified",
                    }
                ]
            }
        },
        generated_on=date(2026, 1, 20),
    )

    assert records[0]["deadline_type"] == "internal_appeal"
    assert records[0]["source_stated_deadline"] == date(2026, 2, 1)
    assert records[0]["rule_source_id"] == "SRC-SYNTHETIC-RULE"
    assert records[0]["verification_status"] == "verified"
    assert records[0]["human_verification_required"] is False


def test_appeal_deadline_tracking_blocks_when_no_deadline_metadata_exists():
    records = build_appeal_deadline_tracking({}, generated_on=date(2026, 1, 15))
    summary = summarize_appeal_deadline_tracking(records)

    assert records[0]["calculated_deadline"] is None
    assert records[0]["source_status"] == "missing_needs_human_verification"
    assert summary["status"] == "needs_human_verification"
    assert summary["human_verification_required"] is True


def test_appeal_deadline_summary_flags_urgent_and_past_due_deadlines():
    urgent_records = build_appeal_deadline_tracking(
        {"appeal_deadline": "2026-01-20"},
        generated_on=date(2026, 1, 15),
    )
    past_due_records = build_appeal_deadline_tracking(
        {"appeal_deadline": "2026-01-10"},
        generated_on=date(2026, 1, 15),
    )

    assert summarize_appeal_deadline_tracking(urgent_records)["status"] == (
        "urgent_needs_human_review"
    )
    assert summarize_appeal_deadline_tracking(past_due_records)["status"] == (
        "past_due_needs_human_review"
    )


def test_fallback_letter_includes_deadline_tracking_without_filing_ready_claim():
    from app.api.v1.appeals import generate_fallback_letter

    claim = MagicMock()
    claim.id = 321
    claim.denial_reasons = [{"code": "CO16", "reason": "Missing information"}]
    claim.claim_data = {"amount": 500, "service_date": "2026-01-05"}
    deadline_tracking = build_appeal_deadline_tracking(
        {"denial_received_date": "2026-01-10", "appeal_deadline_days": 30},
        generated_on=date(2026, 1, 15),
    )

    letter, _ = generate_fallback_letter(
        claim,
        "Synthetic appeal reason",
        "",
        deadline_tracking,
    )

    assert "DEADLINE TRACKING:" in letter
    assert "2026-02-09" in letter
    assert "verify before submission" in letter
    assert "filing-ready" not in letter.lower().replace("not filing-ready", "")


@pytest.mark.asyncio
async def test_generate_appeal_returns_deadline_tracking_metadata():
    from app.api.v1.appeals import generate_appeal
    from app.schemas.analytics import AppealGenerateRequest

    db = MagicMock()
    claim = MagicMock()
    claim.id = 7
    claim.claim_data = {
        "amount": 750,
        "denial_received_date": "2026-06-10",
        "appeal_deadline_days": 30,
    }
    claim.diagnosis_codes = []
    claim.procedure_codes = []
    claim.denial_reasons = [{"code": "CO16", "reason": "Missing information"}]
    claim.denial_prediction = 0.7
    db.query.return_value.filter.return_value.first.return_value = claim

    request = AppealGenerateRequest(
        claim_id=7,
        appeal_reason="Synthetic missing information appeal",
    )

    with patch("app.api.v1.appeals.llm_service.generate", new_callable=AsyncMock) as generate:
        generate.return_value = (
            '{"appeal_letter": "draft_for_human_review\\nSynthetic draft", '
            '"supporting_evidence": ["denial notice"]}'
        )
        response = await generate_appeal(request=request, db=db)

    assert response.deadline_tracking
    assert response.deadline_tracking[0].calculated_deadline == date(2026, 7, 10)
    assert response.deadline_tracking[0].human_verification_required is True
    assert response.deadline_tracking_summary["status"] == "needs_human_verification"
