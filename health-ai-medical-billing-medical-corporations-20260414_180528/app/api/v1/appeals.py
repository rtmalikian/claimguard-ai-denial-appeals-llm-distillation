import json
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import WRITE_ROLES, get_client_ip, require_roles
from app.schemas.analytics import AppealGenerateRequest, AppealGenerateResponse
from app.services.prediction import llm_service
from app.services.appeal_deadlines import (
    build_appeal_deadline_tracking,
    summarize_appeal_deadline_tracking,
)
from app.models import Claim
from app.utils.audit import log_audit
from datetime import datetime

router = APIRouter(prefix="/appeals", tags=["appeals"])

SYSTEM_PROMPT = """You are a ClaimGuard denial appeal workflow assistant.
Generate source-grounded provider-staff drafts only. Do not give legal advice,
medical advice, filing-ready language, fabricated deadlines, fabricated plan
terms, fabricated policy citations, or unsupported clinical conclusions. Mark
the letter draft_for_human_review and require human verification of facts,
deadlines, payer channel, citations, PHI scope, and clinician/provider sign-off."""


def _format_deadline_tracking_for_letter(deadline_tracking: list[dict] | None) -> str:
    if not deadline_tracking:
        return "- Deadline tracking unavailable; human reviewer must verify before submission."

    lines = []
    for item in deadline_tracking[:4]:
        deadline_value = item.get("source_stated_deadline") or item.get("calculated_deadline")
        if deadline_value:
            deadline_text = str(deadline_value)
        else:
            deadline_text = "not available"
        lines.append(
            "- "
            f"{item.get('deadline_type', 'appeal_deadline')}: {deadline_text}; "
            f"status={item.get('verification_status', 'needs_human_verification')}; "
            "verify before submission."
        )
    return "\n".join(lines)


def generate_fallback_letter(
    claim: Claim,
    appeal_reason: str,
    additional_context: str,
    deadline_tracking: list[dict] | None = None,
) -> tuple:
    denial_code = claim.denial_reasons[0].get("code", "N/A") if claim.denial_reasons else "N/A"
    denial_reason = (
        claim.denial_reasons[0].get("reason", "Not specified")
        if claim.denial_reasons
        else "Not specified"
    )
    amount = claim.claim_data.get("amount", 0) if claim.claim_data else 0
    service_date = claim.claim_data.get("service_date", "N/A") if claim.claim_data else "N/A"

    workflow = claim.claim_data.get("denial_workflow", {}) if claim.claim_data else {}
    route = workflow.get("recommended_route", "verify_plan_type")
    plan_type = workflow.get("plan_type", "unknown")
    evidence_gaps = workflow.get("evidence_gaps", [])
    evidence_gap_lines = "\n".join(
        f"- {item.get('evidence_type', 'evidence')}: {item.get('description', '')}"
        for item in evidence_gaps[:8]
        if isinstance(item, dict)
    )
    if not evidence_gap_lines:
        evidence_gap_lines = "- Complete denial letter/EOB and plan/policy sources\n- Verified medical records or administrative proof tied to the denial reason"

    letter = f"""draft_for_human_review

[Date]

[Insurance Company Name]
[Address]
[City, State ZIP]

RE: Appeal for Claim Denial
Patient Claim Number: CLM-{claim.id:06d}
Plan Type: {plan_type} (verify locally)
Route: {route} (verify before submission)

Dear Appeals Department,

This is a draft for human review. We request review and reprocessing of claim CLM-{claim.id:06d} submitted on {service_date}, subject to verification of the controlling appeal route, deadline, payer channel, and representative authority.

CLAIM DETAILS:
- Claim Amount: ${amount:,.2f}
- Service Date: {service_date}
- Denial Code: {denial_code}
- Reason for Denial: {denial_reason}

APPEAL REASON:
{appeal_reason}

ADDITIONAL INFORMATION:
{additional_context}

SOURCE-GROUNDED DRAFT POSITION:
The provider staff reviewer should verify the source documents and attach only evidence that supports the requested remedy. The current draft position is:

1. Reconcile the denial rationale, service lines, codes, dates, and amounts against the denial letter, EOB/ERA, and claim record.
2. Map each verified clinical, coding, authorization, network, eligibility, or timely-filing fact to the controlling plan, payer policy, or rule source.
3. Exclude unsupported clinical conclusions until the treating clinician/provider verifies and signs them.

EVIDENCE NEEDED BEFORE SUBMISSION:
{evidence_gap_lines}

DEADLINE TRACKING:
{_format_deadline_tracking_for_letter(deadline_tracking)}

REQUESTED ACTION:
After human verification and attachment review, please overturn the denial or otherwise reprocess the claim according to the verified appeal/correction route.

HUMAN REVIEW REQUIRED:
- Verify all identifiers, codes, dates, amounts, payer instructions, forms, deadline, and channel.
- Verify every policy, plan, rule, deadline, and citation before use.
- Obtain clinician/provider sign-off for medical necessity, urgency, and clinical facts.
- Limit PHI to the minimum necessary for the appeal purpose.

Thank you for your prompt attention to this matter.

Sincerely,

[Provider Name]
[Practice Name]
[Contact Information]
[NPI Number]
[Tax ID]

Enclosures:
- Copy of original claim
- Denial letter and EOB/ERA
- Verified appeal evidence packet
- Source and citation index
"""

    evidence = [
        "Medical records and clinical notes",
        "Physician's treatment plan",
        "Prior authorization documentation",
        "Complete denial letter and EOB/ERA",
        "Plan/SPD/EOC or payer policy controlling the denial reason",
        "Verified service-line, coding, authorization, and submission proof",
        "Clinician/provider-verified records or letter when clinical facts are used",
        "Proof of payer channel, deadline, representative authority, and submission",
    ]

    return letter, evidence


def _current_user_id(current_user: dict) -> int | None:
    return current_user.get("id") if isinstance(current_user, dict) else None


def _request_ip(request: Request | None) -> str | None:
    return get_client_ip(request) if request is not None else None


def _log_appeal_generation(
    *,
    db: Session,
    request: Request | None,
    current_user: dict,
    claim_id: int,
    appeal_request: AppealGenerateRequest,
    generation_path: str,
    supporting_evidence_count: int,
    deadline_tracking_summary: dict,
) -> None:
    log_audit(
        db=db,
        action="appeal_generated",
        user_id=_current_user_id(current_user),
        claim_id=claim_id,
        details={
            "claim_id": claim_id,
            "appeal_reason_present": bool(appeal_request.appeal_reason),
            "additional_context_present": bool(appeal_request.additional_context),
            "generation_path": generation_path,
            "supporting_evidence_count": supporting_evidence_count,
            "draft_for_human_review": True,
            "deadline_tracking_status": deadline_tracking_summary.get("status"),
            "deadline_tracking_item_count": deadline_tracking_summary.get("item_count", 0),
            "deadline_tracking_human_verification_required": deadline_tracking_summary.get(
                "human_verification_required", True
            ),
        },
        ip_address=_request_ip(request),
    )


@router.post("/generate", response_model=AppealGenerateResponse)
async def generate_appeal(
    request: AppealGenerateRequest,
    http_request: Request = None,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    claim = db.query(Claim).filter(Claim.id == request.claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim_info = {
        "claim_id": claim.id,
        "claim_data": claim.claim_data,
        "diagnosis_codes": claim.diagnosis_codes,
        "procedure_codes": claim.procedure_codes,
        "denial_reasons": claim.denial_reasons,
        "denial_prediction": claim.denial_prediction,
    }
    generated_at = datetime.utcnow()
    deadline_tracking = build_appeal_deadline_tracking(
        claim.claim_data,
        generated_on=generated_at.date(),
    )
    deadline_tracking_summary = summarize_appeal_deadline_tracking(deadline_tracking)

    prompt = f"""Generate a provider-staff appeal packet draft for this denied/submitted claim.
The output must be marked draft_for_human_review and must not be filing-ready.
Do not fabricate plan terms, policy citations, deadlines, medical conclusions, payer addresses, or legal conclusions.

Claim Information: {json.dumps(claim_info)}

Appeal Reason: {request.appeal_reason}
Additional Context: {request.additional_context or "None provided"}
Appeal Deadline Tracking Metadata: {json.dumps(deadline_tracking, default=str)}
Deadline Rule: do not state any deadline as verified unless its verification_status is verified. Keep deadline review human-verification gated.

Generate ONLY a JSON response with this exact format:
{{"appeal_letter": "full draft_for_human_review letter text", "supporting_evidence": ["evidence1", "evidence2"]}}
"""

    try:
        response = await llm_service.generate(
            prompt,
            SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=2048,
            timeout=60,
        )

        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
                appeal_letter = data.get("appeal_letter", "")
                if "draft_for_human_review" not in appeal_letter:
                    appeal_letter = f"draft_for_human_review\n\n{appeal_letter}"
                supporting_evidence = data.get("supporting_evidence", [])
                _log_appeal_generation(
                    db=db,
                    request=http_request,
                    current_user=current_user,
                    claim_id=request.claim_id,
                    appeal_request=request,
                    generation_path="llm_json",
                    supporting_evidence_count=len(supporting_evidence),
                    deadline_tracking_summary=deadline_tracking_summary,
                )
                return AppealGenerateResponse(
                    claim_id=request.claim_id,
                    appeal_letter=appeal_letter,
                    supporting_evidence=supporting_evidence,
                    generated_at=generated_at,
                    deadline_tracking=deadline_tracking,
                    deadline_tracking_summary=deadline_tracking_summary,
                )
        except (json.JSONDecodeError, Exception):
            pass

        fallback_letter, fallback_evidence = generate_fallback_letter(
            claim,
            request.appeal_reason,
            request.additional_context or "",
            deadline_tracking,
        )
        _log_appeal_generation(
            db=db,
            request=http_request,
            current_user=current_user,
            claim_id=request.claim_id,
            appeal_request=request,
            generation_path="fallback_invalid_llm_json",
            supporting_evidence_count=len(fallback_evidence),
            deadline_tracking_summary=deadline_tracking_summary,
        )
        return AppealGenerateResponse(
            claim_id=request.claim_id,
            appeal_letter=fallback_letter,
            supporting_evidence=fallback_evidence,
            generated_at=generated_at,
            deadline_tracking=deadline_tracking,
            deadline_tracking_summary=deadline_tracking_summary,
        )

    except Exception as e:
        fallback_letter, fallback_evidence = generate_fallback_letter(
            claim,
            request.appeal_reason,
            request.additional_context or "",
            deadline_tracking,
        )
        _log_appeal_generation(
            db=db,
            request=http_request,
            current_user=current_user,
            claim_id=request.claim_id,
            appeal_request=request,
            generation_path="fallback_llm_error",
            supporting_evidence_count=len(fallback_evidence),
            deadline_tracking_summary=deadline_tracking_summary,
        )
        return AppealGenerateResponse(
            claim_id=request.claim_id,
            appeal_letter=fallback_letter,
            supporting_evidence=fallback_evidence,
            generated_at=generated_at,
            deadline_tracking=deadline_tracking,
            deadline_tracking_summary=deadline_tracking_summary,
        )
